# Loop-Control Contract (Docloop/Superloop)

## Canonical format (preferred)

Use a tagged JSON block:

```text
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"promise","promise":"INCOMPLETE"}
</loop-control>
```

Valid `kind` values:
- `question` (agent requests human clarification)
- `promise` (agent reports completion state)

Valid `promise` values:
- `COMPLETE`
- `INCOMPLETE`
- `BLOCKED`

## Canonical question example

```text
<loop-control>
{"schema":"docloop.loop_control/v1","kind":"question","question":"Should we keep backward compatibility for v1 clients?"}
</loop-control>
```

## Compatibility behavior

Legacy tags can still appear:
- `<question>...</question>`
- final-line `<promise>...</promise>`

But canonical loop-control JSON is the stable contract and should be preferred in prompts and debugging.

## Common failure modes

1. Multiple canonical `<loop-control>` blocks in one response.
2. Malformed JSON payload in canonical block.
3. Canonical blocks mixed with legacy semantic control tags.
4. Verifier omits a promise entirely (framework may default to INCOMPLETE and append warning).

## Recovery checklist

- Keep exactly one canonical block as the last non-empty logical block.
- Ensure JSON has required keys: `schema`, `kind`, and `promise` or `question`.
- Preserve exact schema string: `docloop.loop_control/v1`.
- Re-run after tightening prompt instructions for output contract compliance.
