#!/usr/bin/env python3
"""
Doc-Loop: A minimal, zero-state CLI orchestrator for iterative document refinement.
Architecture: Native I/O Edition (Ralph-style outer loop).

Delegates all cognitive work and file-editing to the official OpenAI Codex CLI.
Requires: 'git' and 'codex' CLI installed and available in your PATH.
"""

import sys
import time
import re
import subprocess
import argparse
import shutil
from pathlib import Path
from typing import List

# --- Configuration & State Paths ---
DOCLOOP_DIR = Path(".docloop")
PROMPT_FILE = DOCLOOP_DIR / "prompt.md"
CRITERIA_FILE = DOCLOOP_DIR / "criteria.md"
PROGRESS_FILE = DOCLOOP_DIR / "progress.txt"
CONTEXT_FILE = DOCLOOP_DIR / "context.md"

# --- Default Templates ---
DEFAULT_PROMPT = """# Doc-Loop Agent Instructions

You are an autonomous expert technical architect. 
Your goal is to iteratively review and refine the target document until it is provably perfect.

## Workflow Rules:
1. READ the target document to analyze its current state.
2. READ `.docloop/context.md` to understand the core requirements.
3. READ `.docloop/progress.txt` to review past iterations and system warnings.
4. READ `.docloop/criteria.md` to understand the strict quality gates.
5. EDIT the target document natively on disk to implement missing requirements.
6. APPEND your reasoning and discoveries to `.docloop/progress.txt`. Do NOT overwrite it.
7. EDIT `.docloop/criteria.md` to physically check off (`- [x]`) the verification boxes ONLY when you can mathematically prove the rule is satisfied.

## Loop Control Signals (CRITICAL):
You must output ONE of the following XML tags in your final standard output to control the loop.

- If you encounter an ambiguity and cannot proceed safely:
  DO NOT EDIT ANY FILES. Output:
  <question>Ask your clarifying question here</question>

- If you have successfully edited the document, checked EVERY box in criteria.md, and no further edits are needed:
  <promise>COMPLETE</promise>

- If you made progress but the document is not yet perfect:
  Exit normally without tags. The system will loop you again.
"""

DEFAULT_CRITERIA = """# Document Verification Criteria
Codex: Check these boxes (`- [x]`) only when mathematically satisfied.

- [ ] **KISS Verification**: No extraneous architectural layers or complex orchestration are defined.
- [ ] **DRY Verification**: No requirement or data model is defined in more than one section.
- [ ] **YAGNI Verification**: Zero speculative or "future-proof" features exist.
- [ ] **Ambiguity Verification**: Every qualitative adjective has been replaced with a quantitative metric.
- [ ] **Internal Consistency**: No section contradicts a prior section.
"""

def check_dependencies():
    """Fails fast if required CLI tools are missing."""
    missing = []
    if not shutil.which("git"):
        missing.append("git")
    if not shutil.which("codex"):
        missing.append("codex (install via 'npm i -g @openai/codex')")
    
    if missing:
        print(f"[!] FATAL: Missing required dependencies: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

def run_git(args: List[str], allow_fail: bool = False) -> str:
    """Executes a git command and returns the stripped stdout."""
    res = subprocess.run(["git"] + args, capture_output=True, text=True, encoding='utf-8')
    if res.returncode != 0 and not allow_fail:
        print(f"[!] FATAL GIT ERROR: {' '.join(args)}\n{res.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return res.stdout.strip()

def init_workspace(doc_type: str) -> Path:
    """Initializes the minimal filesystem-as-memory architecture."""
    target_doc = Path(f"{doc_type}.md")
    
    if not DOCLOOP_DIR.exists():
        print(f"[*] Initializing Doc-Loop workspace for target: {target_doc}")
        DOCLOOP_DIR.mkdir()
    
    if not target_doc.exists():
        target_doc.write_text(f"# {doc_type}\n\nDraft starting point...\n", encoding='utf-8')
    if not PROMPT_FILE.exists():
        PROMPT_FILE.write_text(DEFAULT_PROMPT, encoding='utf-8')
    if not CRITERIA_FILE.exists():
        CRITERIA_FILE.write_text(DEFAULT_CRITERIA, encoding='utf-8')
    if not PROGRESS_FILE.exists():
        PROGRESS_FILE.write_text("## Doc-Loop Progress Log\n\n", encoding='utf-8')
    if not CONTEXT_FILE.exists():
        CONTEXT_FILE.write_text("# Context and Requirements\n\nReplace this text with your initial requirements.\n", encoding='utf-8')

    if not Path(".git").exists():
        print("[*] Initializing local Git repository...")
        run_git(["init"])
        # Ensure a local git identity exists so commits don't fail silently
        run_git(["config", "user.name", "Doc-Loop Agent"])
        run_git(["config", "user.email", "docloop@localhost"])
    
    # Only track Doc-Loop specific files to avoid polluting existing repos
    run_git(["add", str(target_doc), str(DOCLOOP_DIR)])
    run_git(["commit", "-m", "docloop: baseline"], allow_fail=True)
    
    return target_doc

def ask_human(question_text: str) -> str:
    """Prompts human for input, ensuring we don't return an empty string."""
    print(f"\n[AGENT QUESTION]:\n{question_text}\n")
    while True:
        try:
            answer = input("Your answer (type 'skip' to provide no answer): ").strip()
            if answer.lower() == 'skip':
                return "[User skipped providing an answer]"
            if answer:
                return answer
            print("Please provide an answer, or type 'skip'.")
        except EOFError:
            print("\n[!] EOF detected. Exiting.")
            sys.exit(130)

def main():
    check_dependencies()

    parser = argparse.ArgumentParser(description="Doc-Loop: Adversarial Document Refinement")
    parser.add_argument("--type", choices=["SAD", "PRD"], default="SAD", help="Target document type")
    parser.add_argument("--max-iterations", type=int, default=15, help="Maximum number of agent loops")
    parser.add_argument("--model", type=str, default="gpt-5.4", help="Codex model to use")
    args = parser.parse_args()

    target_doc = init_workspace(args.type)
    stall_counter = 0

    print("\n[+] Starting Doc-Loop Orchestrator (Codex Native I/O)")
    print(f"[*] Target: {target_doc} | Model: {args.model}")
    print("[*] Press Ctrl+C at any time to gracefully stop the loop.")
    
    try:
        for iteration in range(1, args.max_iterations + 1):
            print(f"\n================ Iteration {iteration}/{args.max_iterations} ================")
            
            # Baseline filesystem state
            run_git(["add", str(target_doc), str(DOCLOOP_DIR)])
            run_git(["commit", "-m", f"docloop: pre-iteration {iteration} snapshot"], allow_fail=True)

            base_instructions = PROMPT_FILE.read_text(encoding='utf-8')
            prompt_payload = f"TARGET DOCUMENT: {target_doc.name}\n\n{base_instructions}"
            
            print("[*] Spawning Codex agent... (Streaming progress below)")
            
            # stdout=PIPE captures final message for regex parsing
            # stderr=sys.stderr streams real-time progress to the terminal
            process = subprocess.run(
                [
                    "codex", "exec",
                    "--ephemeral",
                    "--sandbox", "workspace-write",
                    "--ask-for-approval", "never",
                    "--model", args.model,
                    "-"
                ],
                input=prompt_payload,
                text=True,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                encoding='utf-8'
            )
            
            stdout = process.stdout
            
            if process.returncode != 0:
                print(f"\n[!] Agent returned non-zero exit code ({process.returncode}).")

            # Parse final response for control tags
            question_match = re.search(r"<question>(.*?)</question>", stdout, re.DOTALL | re.IGNORECASE)
            complete_match = re.search(r"<promise>COMPLETE</promise>", stdout, re.IGNORECASE)

            # Prioritize questions over completion claims
            if question_match:
                question_text = question_match.group(1).strip()
                human_answer = ask_human(question_text)
                
                with CONTEXT_FILE.open("a", encoding='utf-8') as f:
                    f.write(f"\n\n### Human Clarification (Iteration {iteration})\n")
                    f.write(f"**Q:** {question_text}\n")
                    f.write(f"**A:** {human_answer}\n")
                
                print("[+] Saving human clarification to git history...")
                run_git(["add", str(target_doc), str(DOCLOOP_DIR)])
                run_git(["commit", "-m", f"docloop: human answered question in iteration {iteration}"], allow_fail=True)
                
                stall_counter = 0
                continue
                
            if complete_match:
                print(f"\n[SUCCESS] Agent emitted <promise>COMPLETE</promise>. Verification successful.")
                run_git(["add", str(target_doc), str(DOCLOOP_DIR)])
                run_git(["commit", "-m", f"docloop: SUCCESSFUL COMPLETION ({args.type})"], allow_fail=True)
                sys.exit(0)

            # Stall Detection (Did the agent change files?)
            git_status = run_git(["status", "--porcelain", str(target_doc), str(DOCLOOP_DIR)])
            
            if not git_status:
                stall_counter += 1
                print(f"[-] No file changes detected. Stall counter: {stall_counter}/2")
                
                if stall_counter >= 2:
                    print("[!] Stall detected. Injecting unblock warning into progress.txt...")
                    with PROGRESS_FILE.open("a", encoding='utf-8') as f:
                        f.write(f"\n\n### System Warning (Iteration {iteration})\n")
                        f.write("You made NO file changes and did NOT emit `<promise>COMPLETE</promise>`. Are you stuck? You must edit files, ask a <question>, or signal completion.\n")
                    stall_counter = 0
            else:
                stall_counter = 0
                print("[+] Agent successfully mutated files. Committing diffs...")
                run_git(["add", str(target_doc), str(DOCLOOP_DIR)])
                run_git(["commit", "-m", f"docloop: post-iteration {iteration} agent edits"], allow_fail=True)

            time.sleep(2) # API Rate-limit cooldown

        print(f"\n[FAILED] Reached max iterations ({args.max_iterations}) without a COMPLETE signal.", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user. Shutting down gracefully...")
        sys.exit(130)

if __name__ == "__main__":
    main()
