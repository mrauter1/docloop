# Superloop/Docloop Command Reference

## Docloop

### New SAD refinement
```bash
python docloop.py --type SAD --input-file ./notes.md --output ./SAD.md --model gpt-5.4
```

### Update existing SAD with explicit change request
```bash
python docloop.py --update --update-text "Add migration strategy and rollback constraints." --output ./SAD.md --model gpt-5.4
```

### PRD generation without git checkpoints
```bash
python docloop.py --type PRD --input-text "# Draft PRD" --output ./PRD.md --no-git
```

## Superloop

### List known task workspaces
```bash
python superloop.py --list-tasks --workspace .
```

### Start a new task (plan+implement+test)
```bash
python superloop.py \
  --workspace . \
  --intent "Implement X with clear acceptance tests" \
  --pairs plan,implement,test \
  --model gpt-5.4
```

### Resume an existing task
```bash
python superloop.py \
  --workspace . \
  --task-id <task-id> \
  --resume \
  --pairs plan,implement,test \
  --model gpt-5.4
```

### Run only implementation/test for an existing task
```bash
python superloop.py \
  --workspace . \
  --task-id <task-id> \
  --resume \
  --pairs implement,test \
  --model gpt-5.4
```

## Observability and debugging

### Check latest run artifacts
```bash
find .superloop/tasks -maxdepth 4 -type f | sed -n '1,120p'
```

### Inspect current repo deltas
```bash
git status --short
git diff --stat
```

### Validate tool option surface
```bash
python superloop.py --help
python docloop.py --help
```
