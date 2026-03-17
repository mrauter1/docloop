# Agent Instructions

You are the only agent in this workflow. Complete the task described in the Reflow Runtime footer by updating the target file directly.

## Rules

- Edit the target file in place.
- Use `.reflow/context.md` as the authoritative source of requirements and constraints.
- If the task is not complete after one pass, explain what remains.

## When finished

End your response with one of:
- `<route>done</route>` - the task is complete
- `<route>retry</route>` - another pass is needed
- `<route>blocked</route>` - cannot continue without human input
