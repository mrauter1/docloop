from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SAD = REPO_ROOT / "refined_reflow_v1.2" / "SAD.md"
POINTER_SAD = REPO_ROOT / "reflow_SAD_v1.2.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def markdown_headings(path: Path) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    in_fence = False

    for raw_line in read_text(path).splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()

        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped.startswith("#"):
            continue

        level = len(stripped) - len(stripped.lstrip("#"))
        title = stripped[level:].strip()
        headings.append((level, title))

    return headings


def section_body(path: Path, heading: str) -> str:
    lines = read_text(path).splitlines()
    start_idx: int | None = None
    start_level: int | None = None

    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue

        level = len(stripped) - len(stripped.lstrip("#"))
        title = stripped[level:].strip()
        if title == heading:
            start_idx = idx + 1
            start_level = level
            break

    if start_idx is None or start_level is None:
        raise AssertionError(f"Missing heading: {heading}")

    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        stripped = lines[idx].lstrip()
        if not stripped.startswith("#"):
            continue

        level = len(stripped) - len(stripped.lstrip("#"))
        if level <= start_level:
            end_idx = idx
            break

    return "\n".join(lines[start_idx:end_idx]).strip()


def test_refined_sad_has_expected_top_level_section_order():
    level_2_titles = [title for level, title in markdown_headings(CANONICAL_SAD) if level == 2]

    assert level_2_titles == [
        "1. Purpose and normative status",
        "2. Design principles",
        "3. Scope",
        "4. Provider model",
        "5. Canonical repository layout",
        "6. One active controller per workspace",
        "7. Workflow contract",
        "8. Transitions contract",
        "9. Policy contract",
        "10. Provider configuration contract",
        "11. Minimal run state",
        "12. History and per-iteration records",
        "13. Agent request assembly",
        "14. Input-request lifecycle",
        "15. Runtime algorithm",
        "16. Failure model",
        "17. Resume, reply, stop",
        "18. Provider wrappers",
        "19. Shell steps and runtime environment",
        "20. Validation rules",
        "21. Exit codes",
        "22. Testing requirements",
        "23. Informative example: Doc-Loop style workflow",
        "24. Implementation sequence",
    ]


def test_refined_sad_has_finalized_section_14_structure():
    section_14_titles = [title for level, title in markdown_headings(CANONICAL_SAD) if level == 3 and title.startswith("14.")]

    assert section_14_titles == [
        "14.1 Request detection",
        "14.2 Inline interactive mode",
        "14.3 Explicit waiting state",
        "14.4 Full-auto answer contract",
        "14.5 Full-auto mode",
    ]
    assert section_14_titles.count("14.4 Full-auto answer contract") == 1


def test_canonical_v12_source_and_pointer_contract_are_unambiguous():
    purpose_text = section_body(CANONICAL_SAD, "1. Purpose and normative status")
    pointer_text = read_text(POINTER_SAD)

    assert "This document is the normative architecture for Reflow v1.2." in purpose_text
    assert "Within this repository, `refined_reflow_v1.2/SAD.md` is the canonical v1.2 source." in purpose_text
    assert "Any duplicate file MUST either point to this document explicitly or be an exact mirror of it." in purpose_text

    assert pointer_text.startswith("# Reflow v1.2 Pointer")
    assert "The canonical Reflow v1.2 architecture document is `refined_reflow_v1.2/SAD.md`." in pointer_text
    assert "This file is non-normative" in pointer_text
    assert "## 1. Purpose and normative status" not in pointer_text


def test_pending_input_contract_preserves_question_order_and_auto_round_rules():
    pending_input_text = section_body(CANONICAL_SAD, "11.3 `pending_input` contract")
    request_detection_text = section_body(CANONICAL_SAD, "14.1 Request detection")

    assert "* `auto_round`" in pending_input_text
    assert "* A newly created `pending_input` record MUST initialize `auto_round` to `0`." in pending_input_text
    assert "* `pending_input` is control-plane state only. Resolved answers belong in `operator_inputs.md`, not in `run.json`." in pending_input_text
    assert "it MUST preserve the emitted questions in order and initialize `auto_round` to `0`." in request_detection_text


def test_full_auto_mode_documents_budget_edge_success_and_failure_paths():
    full_auto_text = section_body(CANONICAL_SAD, "14.5 Full-auto mode")

    numbered_rules = {
        int(match.group(1)): match.group(2).strip()
        for match in re.finditer(r"^(\d+)\.\s+(.*)$", full_auto_text, re.MULTILINE)
    }

    assert numbered_rules[2] == "If `pending_input.auto_round >= max_auto_rounds`, Reflow MUST enter `awaiting_input` instead of launching another auto-answer pass."
    assert numbered_rules[3] == "Otherwise, Reflow MUST increment `pending_input.auto_round`, persist it, and invoke a fresh provider pass using the workflow `full_auto_instructions` file, or the built-in default if none is configured."
    assert numbered_rules[7] == "A full-auto answer pass is not a workflow step iteration. It MUST NOT increment `step_loops`, MUST NOT increment `cycle_count`, and MUST NOT create a step iteration directory."
    assert numbered_rules[8] == "If the answer pass cannot be started, exits nonzero, times out, emits an invalid `<answers>` block, or returns the wrong number of answers, Reflow MUST append `input_auto_failed`, leave `pending_input` intact, set the run to `awaiting_input`, and follow the waiting-state rules from Section 14.3."
    assert numbered_rules[9] == "On success, Reflow MUST append the resulting answers to `operator_inputs.md` with `mode: auto`, clear `pending_input`, append `input_resolved`, and start a fresh iteration of the same step."


def test_history_and_reply_contracts_capture_auto_failures_and_reply_ordering():
    history_text = section_body(CANONICAL_SAD, "12.1 Required event types")
    reply_text = section_body(CANONICAL_SAD, "17.3 Reply semantics")

    assert "* `reply_started`" in history_text
    assert "* `input_auto_failed`" in history_text
    assert "* `reply_started`: `current_step`" in history_text
    assert "* `input_auto_failed`: `step`, `loop`, `auto_round`, `reason`" in history_text
    assert "* `reply` MUST fail if `pending_input` is absent." in reply_text
    assert "* `reply` MUST reacquire the workspace lock before resolving input." in reply_text
    assert "* `reply` MUST append `reply_started` after taking controller ownership and before collecting or auto-generating answers." in reply_text
    assert "* In `--full-auto`, `reply` MUST use the full-auto answer path." in reply_text


def test_request_assembly_keeps_context_and_operator_inputs_as_repository_resident_memory():
    repo_memory_text = section_body(CANONICAL_SAD, "2.4 Repo-first memory")
    instruction_loading_text = section_body(CANONICAL_SAD, "13.1 Instruction loading")
    footer_text = section_body(CANONICAL_SAD, "13.2 Required footer content")

    assert "Memory lives in repository files, provider-native project files, optional `.reflow/context.md`, the per-run `operator_inputs.md` log, and per-run history artifacts." in repo_memory_text
    assert "Reflow does not mirror full working memory into `run.json`." in repo_memory_text
    assert "Reflow MUST NOT inline the contents of `.reflow/context.md` or `operator_inputs.md`; the request may reference their paths, but those files remain repository-resident memory." in instruction_loading_text
    assert "* the path to `operator_inputs.md`" in footer_text


def test_legacy_v12_sad_path_is_only_a_pointer():
    text = read_text(POINTER_SAD)

    assert text.startswith("# Reflow v1.2 Pointer")
    assert "`refined_reflow_v1.2/SAD.md`" in text
    assert "non-normative" in text
    assert "## 1. Purpose and normative status" not in text
