# Fuzzy Framework: Principles, Complete Flow, and Current Interfaces

## Intent
Fuzzy is a focused framework for turning LLM reasoning into **reliable application actions**.

Its core intent is to replace brittle free-form prompting with a small set of constrained primitives that produce predictable return types suitable for downstream automation.

---

## Guiding Principles

1. **Typed outcomes first**  
   Outputs are intended to be directly consumable in code (`bool`, one label, schema-valid JSON/model, dispatch decision/execution), rather than prose.

2. **Constrained decision boundaries**  
   Each operation limits model freedom through explicit schemas or finite option sets.

3. **Provider abstraction with stable UX**  
   Callers use one conceptual API while adapters handle provider specifics.

4. **Validation + recovery loop**  
   The framework assumes responses may be imperfect and includes structured retry/repair to recover to valid outputs.

5. **Data-safe context framing**  
   Context is treated as data, explicitly wrapped to reduce accidental instruction execution from embedded content.

6. **Composable orchestration**  
   The primitives support simple checks, classification, extraction, and controlled tool/command routing in one unified shape.

---

## Complete End-to-End Flow

### 1) Input normalization
You pass:
- an adapter (provider binding),
- a model,
- context data,
- operation-specific constraints (expression, labels, schema, choices).

For structured tasks, context is serialized into a deterministic data envelope.

### 2) Constraint declaration
Fuzzy builds explicit output constraints:
- `eval_bool`: object with a boolean result field,
- `classify`: label constrained to allowed values,
- `extract`: caller-provided schema/model,
- `dispatch`: decision envelope constrained to either label mode or command mode.

### 3) Model call through adapter
The framework requests structured output when the provider supports it.  
If native structure enforcement is unavailable/incomplete, it still proceeds with strict JSON parsing and validation behavior.

### 4) Parse and validate
Model output is parsed as JSON and validated against the declared constraints.

### 5) Repair/retry (if needed)
If output is malformed or invalid:
- deterministic repair instructions are added,
- the call is retried with backoff,
- process stops at max attempts with a framework error.

### 6) Typed return
On success, Fuzzy returns a typed result:
- bool,
- label string,
- dict/list or model instance,
- dispatch decision or dispatch execution result.

---

## Current Public Interfaces

## Adapters
- **`OpenAIAdapter`**: OpenAI Responses API-backed adapter.
- **`OpenRouterAdapter`**: OpenRouter SDK-backed adapter.
- **`LLMAdapter`**: common adapter contract used by primitives.

## Core Primitives

### `drop(...) -> Any`
Deterministic, non-LLM pruning/sanitization of nested data.

### `eval_bool(...) -> bool`
Evaluates whether an expression is true/false given context.

### `classify(...) -> str`
Selects exactly one label from an allowed finite set.

### `extract(...) -> Any`
Extracts structured output that conforms to:
- JSON Schema dict, or
- Pydantic model type (when available).

### `dispatch(...) -> DispatchDecision | DispatchExecution`
Chooses one action from a closed menu:
- **label path**: returns a `DispatchDecision(kind="label")`,
- **command path**: returns a `DispatchDecision(kind="command")`,
- with `auto_execute=True`, executes the selected command and returns `DispatchExecution`.

For command mode, `input_schema` and `output_schema` may be either JSON Schema mappings or supported model types. The public dispatch decision remains JSON-shaped; model materialization happens at the executor/output boundary.

## Dispatch Interface Types
- **`Command`**: named command with input schema, executor, optional description, optional output schema.
- **`DispatchCommand`**: chosen command name + args.
- **`DispatchDecision`**: discriminator for label vs command outcome.
- **`DispatchExecution`**: command invocation + executor result.

## Wrapper Interface (`LLMOps`)
`LLMOps` is a convenience layer that bundles:
- adapter,
- default model,
- default system prompt,
- async methods for all primitives,
- sync wrappers for non-async callers,
- provider-specific constructors plus a unified constructor.

Factory entrypoints:
- `from_openai(...)`
- `from_openrouter(...)`
- `from_provider(...)`

Instance methods:
- `eval_bool(...)`
- `classify(...)`
- `extract(...)`
- `dispatch(...)`
- `eval_bool_sync(...)`
- `classify_sync(...)`
- `extract_sync(...)`
- `dispatch_sync(...)`

---

## Functional Boundaries (What Fuzzy Is / Is Not)

### Fuzzy is for
- Reliable LLM-powered decisioning and extraction.
- Converting uncertain model output into validated program contracts.
- Building lightweight agentic routing with constrained commands.

### Fuzzy is not for
- Long-form text generation workflows.
- Open-ended autonomous planning without explicit constraints.
- Provider-specific prompt engineering lock-in.

---

## Operational Outcome
In practice, Fuzzy gives teams a compact, predictable “decision-and-structure layer” so LLM calls can safely drive product logic, workflows, and tool execution.
