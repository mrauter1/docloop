# Superloop/Docloop Skill Rollout Roadmap

## Goal
Enable Codex to consistently choose, run, and recover Superloop/Docloop workflows with minimal operator intervention.

## Phase 1: Baseline usability (week 1)
- Ship SKILL.md + command templates + loop-control reference.
- Validate trigger coverage using sample requests:
  - "Run docloop update mode"
  - "Resume my superloop task"
  - "Why is verifier stuck on INCOMPLETE?"

## Phase 2: Reliability hardening (weeks 2-3)
- Add troubleshooting playbooks for:
  - malformed loop-control,
  - repeated BLOCKED outcomes,
  - dirty workspace conflicts.
- Add deterministic scripts for common diagnostics.

## Phase 3: Automation leverage (weeks 4-6)
- Add reusable prompt snippets for plan/implement/test intents.
- Add templates for acceptance criteria quality.
- Add a compact run-summary generator script for post-run handoffs.

## Success metrics
- Reduced manual intervention per run.
- Higher first-pass COMPLETE rate.
- Faster root-cause diagnosis for stalled loops.
