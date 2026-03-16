from __future__ import annotations

import re
from pathlib import Path

from .loaders import load_instruction_body
from .models import AgentOutcome, AgentTransitions, StepFailedError, Workflow

QUESTIONS_BLOCK_RE = re.compile(r"(?s)\A(.*?)(<questions>(.*?)</questions>)\s*\Z", re.IGNORECASE)
QUESTION_RE = re.compile(r"<question>(.*?)</question>", re.IGNORECASE | re.DOTALL)
QUESTION_TAG_RE = re.compile(r"</?questions?>", re.IGNORECASE)

ANSWERS_BLOCK_RE = re.compile(r"(?s)\A(.*?)(<answers>(.*?)</answers>)\s*\Z", re.IGNORECASE)
ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.IGNORECASE | re.DOTALL)
ANSWER_TAG_RE = re.compile(r"</?answers?>", re.IGNORECASE)


def render_agent_request(
    workflow: Workflow,
    run,
    step,
    loop: int,
    warning: str | None,
    workspace: Path,
    context_present: dict[str, bool] | None = None,
) -> str:
    body = load_instruction_body(workflow, step.instructions)

    policy_lines: list[str] = []
    if step.policy:
        if step.policy.allow_write:
            policy_lines.append(f"- allowed writes: {', '.join(step.policy.allow_write)}")
        if step.policy.forbid_write:
            policy_lines.append(f"- forbidden writes: {', '.join(step.policy.forbid_write)}")
        if step.policy.required_files:
            policy_lines.append(f"- required files: {', '.join(step.policy.required_files)}")

    transition_lines = _render_transition_footer(step.transitions)
    context_lines = _render_declared_context_lines(workflow, step, workspace, context_present or {})
    produces_lines = [f"- expected output: {entry.path} as {entry.as_description}" for entry in step.produces]

    footer_parts = [
        "## Reflow Runtime",
    ]
    if run.task is not None:
        footer_parts.append(f"- task: {run.task}")
    footer_parts.extend(
        [
            f"- workflow: {workflow.name}",
            f"- step: {step.name}",
            f"- loop: {loop}",
        ]
    )
    footer_parts.extend(context_lines)
    footer_parts.extend(produces_lines)
    footer_parts.extend(
        [
            f"- operator_inputs: .reflow/runs/{run.run_id}/operator_inputs.md",
            "- If you need operator input, emit a final <questions> block with one or more <question> entries.",
            transition_lines,
        ]
    )
    footer_parts.extend(policy_lines)
    if warning:
        footer_parts.append(f"- warning: {warning}")
    return f"{body}\n\n" + "\n".join(footer_parts) + "\n"


def parse_agent_outcome(final_text: str, transitions: AgentTransitions) -> AgentOutcome:
    questions = _parse_questions_block(final_text)
    if questions:
        if transitions.tag and _find_last_matching_tag_line(final_text, transitions.tag) is not None:
            raise StepFailedError("final.txt mixed a valid questions block with a decision tag.")
        return AgentOutcome(transition_target=None, decision_value=None, questions=questions)

    if transitions.tag is None:
        return AgentOutcome(
            transition_target=transitions.default_target,
            decision_value=None,
            questions=[],
        )

    decision_value = _find_last_matching_tag_line(final_text, transitions.tag)
    if decision_value is None:
        decision_value = transitions.default_decision
    if decision_value not in transitions.mapping:
        raise StepFailedError(
            f"final.txt emitted invalid decision value {decision_value!r} for tag {transitions.tag!r}."
        )
    return AgentOutcome(
        transition_target=transitions.mapping[decision_value],
        decision_value=decision_value,
        questions=[],
    )


def parse_questions_block(final_text: str) -> list[str]:
    return _parse_questions_block(final_text)


def parse_full_auto_answers(stdout_text: str, expected_count: int) -> list[str]:
    match = ANSWERS_BLOCK_RE.match(stdout_text)
    if not match:
        if ANSWER_RE.search(stdout_text) or ANSWER_TAG_RE.search(stdout_text):
            raise StepFailedError("Full-auto output contains malformed <answers> control.")
        raise StepFailedError("Full-auto output is missing a valid final <answers> block.")

    prefix, _block, inner = match.groups()
    if ANSWER_RE.search(prefix) or ANSWER_TAG_RE.search(prefix):
        raise StepFailedError("Full-auto output contains <answer> tags outside the final <answers> block.")

    answers = [item.rstrip() for item in ANSWER_RE.findall(inner)]
    if len(answers) != expected_count:
        raise StepFailedError("Full-auto output returned the wrong number of answers.")
    if any(not answer.strip() for answer in answers):
        raise StepFailedError("Full-auto output returned an empty answer.")

    remainder = ANSWER_RE.sub("", inner)
    if remainder.strip():
        raise StepFailedError("Full-auto output contains malformed content inside <answers>.")
    return answers


def malformed_control_warning() -> str:
    return "Previous iteration emitted malformed control output. Emit either a valid final <questions> block or a valid transition outcome."


def _render_declared_context_lines(workflow: Workflow, step, workspace: Path, context_present: dict[str, bool]) -> list[str]:
    lines: list[str] = []
    for entry in step.context:
        present = context_present.get(entry.path)
        if present is None:
            present = (workflow.root / entry.path).exists() or (workspace / entry.path).exists()
        suffix = entry.path if present else f"{entry.path} (not present)"
        lines.append(f"- context: {suffix} as {entry.as_description}")
    return lines


def _render_transition_footer(transitions: AgentTransitions) -> str:
    if transitions.tag is None:
        return f"- transition: if no questions are requested, continue to {transitions.default_target}"
    valid_values = ", ".join(sorted(transitions.mapping))
    mapping = ", ".join(f"{key}->{value}" for key, value in sorted(transitions.mapping.items()))
    return (
        f"- transition tag: <{transitions.tag}>VALUE</{transitions.tag}>; "
        f"valid values: {valid_values}; default decision: {transitions.default_decision}; map: {mapping}"
    )


def _parse_questions_block(final_text: str) -> list[str]:
    match = QUESTIONS_BLOCK_RE.match(final_text)
    if not match:
        if QUESTION_RE.search(final_text) or QUESTION_TAG_RE.search(final_text):
            raise StepFailedError("final.txt contains malformed <questions> control.")
        return []

    prefix, _block, inner = match.groups()
    if QUESTION_RE.search(prefix) or QUESTION_TAG_RE.search(prefix):
        raise StepFailedError("final.txt contains <question> tags outside the final <questions> block.")

    questions = [item.strip() for item in QUESTION_RE.findall(inner)]
    if not questions:
        raise StepFailedError("final.txt contains an empty <questions> block.")
    if any(not question for question in questions):
        raise StepFailedError("final.txt contains an empty question.")

    remainder = QUESTION_RE.sub("", inner)
    if remainder.strip():
        raise StepFailedError("final.txt contains malformed content inside <questions>.")
    return questions


def _find_last_matching_tag_line(text: str, tag: str) -> str | None:
    tag_re = re.compile(rf"^\s*<{re.escape(tag)}>([^<]+)</{re.escape(tag)}>\s*$")
    last_value: str | None = None
    for line in text.splitlines():
        match = tag_re.match(line)
        if match:
            last_value = match.group(1).strip()
    return last_value
