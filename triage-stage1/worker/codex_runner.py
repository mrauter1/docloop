from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import uuid

from shared.bootstrap import ensure_workspace_files
from shared.config import Settings
from shared.workspace_contract import EXACT_AGENTS_MD, EXACT_SKILL_MD

EXACT_SCHEMA_JSON = """{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "ticket_class": {
      "type": "string",
      "enum": ["support", "access_config", "data_ops", "bug", "feature", "unknown"]
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "impact_level": {
      "type": "string",
      "enum": ["low", "medium", "high", "unknown"]
    },
    "requester_language": {
      "type": "string",
      "minLength": 2
    },
    "summary_short": {
      "type": "string",
      "minLength": 1,
      "maxLength": 120
    },
    "summary_internal": {
      "type": "string",
      "minLength": 1
    },
    "development_needed": {
      "type": "boolean"
    },
    "needs_clarification": {
      "type": "boolean"
    },
    "clarifying_questions": {
      "type": "array",
      "maxItems": 3,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "incorrect_or_conflicting_details": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "evidence_found": {
      "type": "boolean"
    },
    "relevant_paths": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "path": { "type": "string" },
          "reason": { "type": "string" }
        },
        "required": ["path", "reason"]
      }
    },
    "recommended_next_action": {
      "type": "string",
      "enum": [
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
        "draft_public_reply",
        "route_dev_ti"
      ]
    },
    "auto_public_reply_allowed": {
      "type": "boolean"
    },
    "public_reply_markdown": {
      "type": "string"
    },
    "internal_note_markdown": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "ticket_class",
    "confidence",
    "impact_level",
    "requester_language",
    "summary_short",
    "summary_internal",
    "development_needed",
    "needs_clarification",
    "clarifying_questions",
    "incorrect_or_conflicting_details",
    "evidence_found",
    "relevant_paths",
    "recommended_next_action",
    "auto_public_reply_allowed",
    "public_reply_markdown",
    "internal_note_markdown"
  ]
}
"""


class CodexExecutionError(RuntimeError):
    """Raised when the Codex CLI execution fails or returns invalid artifacts."""


@dataclass(frozen=True)
class CodexPreparedRun:
    run_dir: Path
    prompt_path: Path
    schema_path: Path
    final_output_path: Path
    stdout_jsonl_path: Path
    stderr_path: Path
    command: tuple[str, ...]


@dataclass(frozen=True)
class CodexRunResult:
    payload: dict[str, object]
    stdout: str
    stderr: str
def _format_messages(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "(none)"
    blocks: list[str] = []
    for index, message in enumerate(messages, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[{index}] author_type: {message['author_type']}",
                    f"source: {message['source']}",
                    "body:",
                    message["body_markdown"] or message["body_text"] or "(empty)",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_prompt(
    *,
    reference: str,
    title: str,
    status: str,
    urgent: bool,
    public_messages: list[dict[str, str]],
    internal_messages: list[dict[str, str]],
) -> str:
    return f"""$stage1-triage

Task:
Analyze this internal ticket for Stage 1 triage only.

Constraints:
- Use only the ticket title, ticket messages, attached images, files under manuals/, and files under app/.
- Search manuals/ first when support, access, or operations guidance may exist.
- Inspect app/ when repository understanding is needed.
- Do not use databases, logs, DDL, schema dumps, or external web search.
- Return only valid JSON matching the provided schema.
- Ask at most 3 clarifying questions.
- Never promise a fix, implementation, or timeline.
- Internal messages may inform internal analysis and routing but MUST NOT be disclosed in automatic public replies unless the same information is already public on the ticket.

Ticket reference:
{reference}

Ticket title:
{title}

Current status:
{status}

Urgent:
{str(urgent)}

Public messages:
{_format_messages(public_messages)}

Internal messages:
{_format_messages(internal_messages)}

Decision policy:
- Classify into exactly one of: support, access_config, data_ops, bug, feature, unknown.
- impact_level means business/user impact only.
- development_needed is only a triage estimate.
- Search manuals/ before answering support or access/config questions.
- Inspect app/ when repository understanding is needed.
- If the available evidence strongly supports an answer and confidence is high, you may draft a concise public reply.
- If the request is understood but should go to Dev/TI, you may draft a safe public confirmation and route it.
- If information is ambiguous, missing, conflicting, or likely incorrect, ask concise clarifying questions instead of guessing.
- If no safe public reply should be prepared, leave public_reply_markdown empty and set auto_public_reply_allowed to false.

Output:
Return only the JSON object.
"""


def prepare_codex_run(
    settings: Settings,
    *,
    ticket_id: uuid.UUID,
    run_id: uuid.UUID,
    prompt: str,
    image_paths: list[Path],
) -> CodexPreparedRun:
    ensure_workspace_files(settings)

    run_dir = settings.triage_workspace_dir / "runs" / str(ticket_id) / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = run_dir / "prompt.txt"
    schema_path = run_dir / "schema.json"
    final_output_path = run_dir / "final.json"
    stdout_jsonl_path = run_dir / "stdout.jsonl"
    stderr_path = run_dir / "stderr.txt"

    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(EXACT_SCHEMA_JSON, encoding="utf-8")
    if not stdout_jsonl_path.exists():
        stdout_jsonl_path.write_text("", encoding="utf-8")
    if not stderr_path.exists():
        stderr_path.write_text("", encoding="utf-8")

    command: list[str] = [
        settings.codex_bin,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "--json",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(final_output_path),
        "-c",
        'web_search="disabled"',
    ]
    if settings.codex_model:
        command.extend(["--model", settings.codex_model])
    for image_path in image_paths:
        command.extend(["--image", str(image_path)])
    command.append(prompt)

    return CodexPreparedRun(
        run_dir=run_dir,
        prompt_path=prompt_path,
        schema_path=schema_path,
        final_output_path=final_output_path,
        stdout_jsonl_path=stdout_jsonl_path,
        stderr_path=stderr_path,
        command=tuple(command),
    )


def run_codex(prepared: CodexPreparedRun, *, settings: Settings) -> CodexRunResult:
    env = os.environ.copy()
    env["CODEX_API_KEY"] = settings.codex_api_key
    try:
        completed = subprocess.run(
            prepared.command,
            cwd=settings.triage_workspace_dir,
            env=env,
            text=True,
            capture_output=True,
            timeout=settings.codex_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        prepared.stdout_jsonl_path.write_text(stdout, encoding="utf-8")
        prepared.stderr_path.write_text(stderr, encoding="utf-8")
        raise CodexExecutionError(
            f"Codex execution timed out after {settings.codex_timeout_seconds} seconds"
        ) from exc

    prepared.stdout_jsonl_path.write_text(completed.stdout or "", encoding="utf-8")
    prepared.stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    if completed.returncode != 0:
        raise CodexExecutionError(f"Codex exited with status {completed.returncode}")
    if not prepared.final_output_path.exists():
        raise CodexExecutionError("Codex did not produce the canonical final output artifact")

    try:
        payload = json.loads(prepared.final_output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodexExecutionError("Codex final output was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise CodexExecutionError("Codex final output must be a JSON object")

    return CodexRunResult(
        payload=payload,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
