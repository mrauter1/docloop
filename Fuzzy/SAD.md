# Fuzzy Framework Software Architecture Document

## 1. Purpose and Scope
Fuzzy is a framework for turning LLM output into validated application decisions and structured data that downstream code can consume without free-form parsing.

The framework standardizes four LLM-backed primitives and one local preprocessing helper:
- `drop`: deterministic context pruning/sanitization with no model call,
- `eval_bool`: validated boolean evaluation,
- `classify`: single-label classification from a closed set,
- `extract`: schema-constrained structured extraction,
- `dispatch`: constrained selection of either a label or a command from a closed menu.

This document defines the externally relevant architecture and contracts required for a conforming implementation. It does not mandate one internal code structure, prompt template, or retry algorithm beyond the observable behavior stated here.

## 2. Design Goals and Non-Goals

### 2.1 Goals
- Return typed results suitable for direct use in application logic.
- Constrain model output through finite choices or explicit schemas.
- Hide provider-specific request/response details behind a stable adapter contract.
- Recover from malformed or schema-invalid model output through bounded repair/retry.
- Treat caller context as data, not instructions.
- Support both async-first usage and sync wrappers with identical semantics.

### 2.2 Non-Goals
- Long-form or stylistic text generation.
- Open-ended planning or autonomous tool use outside an explicit closed menu.
- Provider-specific prompt engineering as part of the public API.
- Mandatory persistence, queues, databases, or background workers.

## 3. System Context
A conforming deployment contains these logical components:

- Caller application: supplies adapter, model, context, and operation-specific constraints.
- `LLMOps`: convenience facade that stores defaults and exposes the public methods.
- Core primitives: implement normalization, validation, repair/retry, and typed return conversion.
- `LLMAdapter`: provider abstraction used by primitives.
- Provider backend: an external LLM service such as OpenAI Responses API or OpenRouter.
- Optional command executor functions: caller-supplied side-effecting or pure functions used by `dispatch` in command mode.

Fuzzy is logically stateless across calls. The framework may keep in-memory configuration objects, but no persisted state is required by the architecture.

## 4. Common Architectural Rules

### 4.1 Context Handling
- Context supplied to an LLM-backed primitive is application data, not executable instruction text.
- The implementation MUST serialize context into a deterministic data envelope before sending it to the model.
- The exact internal envelope keys are not part of the public contract, but the envelope MUST preserve the caller-supplied data structure and MUST separate framework instructions from embedded context data.
- Context values that cannot be represented in the target structured format are invalid unless the caller preprocesses them with `drop` or an equivalent caller-side transformation.

### 4.2 Output Validation
- Every LLM-backed primitive MUST declare an explicit target shape before the provider call.
- A model response is successful only if it can be parsed as JSON and validated against the primitive's declared constraints.
- Native provider-side structured output enforcement may be used when available, but provider support does not remove the requirement for local parsing and validation.

### 4.3 Failure Boundary
- Caller configuration errors MUST fail before any provider call.
- Provider transport, authentication, rate-limit, and provider-contract failures MUST surface as framework errors with the public categories defined in Section 5.5 and MUST NOT be rewritten as validation errors.
- Malformed JSON and schema-invalid model output are recoverable failures and are eligible for bounded repair/retry.
- Command executor failures in `dispatch(..., auto_execute=True)` are execution failures, not model-validation failures.

### 4.4 Retry Boundary
- Repair/retry applies only to failures where another model attempt could plausibly yield a valid response, primarily malformed JSON or schema/choice violations.
- Retry behavior MUST be bounded by a maximum attempt count.
- Once the maximum attempt count is reached, the framework MUST raise a terminal framework error for that operation.
- The implementation MAY apply backoff between attempts. The exact timing strategy is not part of the public contract.

### 4.5 Configuration Surface
Every LLM-backed primitive call has these externally relevant configuration values:
- `model`: provider-specific model identifier string.
- `max_attempts`: positive integer controlling the total number of model attempts, including the first attempt.
- optional supplemental system prompt text.

Rules:
- `max_attempts=1` means exactly one provider attempt and no repair retry.
- `max_attempts<1` is invalid caller configuration and MUST fail before any provider call.
- Direct primitive entrypoints and `LLMOps` methods MAY both expose `max_attempts`; when both an instance default and a per-call value exist, the per-call value MUST replace the instance default for that call.
- If the caller does not supply `max_attempts`, the effective default is `2` for all LLM-backed primitives.
- Supplemental system prompt text is optional caller guidance layered on top of framework-owned instructions. It MUST NOT disable output validation, relax declared schemas, or change retry boundaries.

## 5. Canonical Data Contracts

### 5.1 Supported Result Categories
The public primitives return one of these categories:
- `bool` for `eval_bool`,
- one allowed label string for `classify`,
- a validated structured value for `extract`,
- a dispatch decision or dispatch execution record for `dispatch`.

### 5.2 Structured Extraction Value
`extract` returns one of:
- a JSON-compatible Python value that conforms to the caller-provided JSON Schema, or
- an instance of the caller-provided model type when model-type validation is supported in the runtime.

Supported schema/model forms:
- JSON Schema input MUST be a Python mapping representing one complete JSON Schema document. The architecture requires support for schema keywords needed to validate JSON object, array, string, number, integer, boolean, and null values, including `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`, `oneOf`, `anyOf`, `allOf`, `minimum`, `maximum`, `minLength`, `maxLength`, `minItems`, `maxItems`, and `pattern`. Other keywords MAY be supported, but are not required for conformance.
- A supported model type is a Python class whose runtime exposes both `model_json_schema()` and `model_validate(...)` methods with deterministic validation semantics for JSON-compatible input. The framework MUST derive the provider-facing output contract from `model_json_schema()` and MUST construct the returned instance through `model_validate(...)`.

If model-type support is unavailable in the runtime, the implementation MUST reject model-type input during argument validation rather than silently degrading behavior.

### 5.3 Dispatch Types
The canonical dispatch shapes are:

```python
DispatchCommand = {
    "name": str,
    "args": dict,
}

DispatchDecision = {
    "kind": "label" | "command",
    # if kind == "label"
    "label": str,
    # if kind == "command"
    "command": DispatchCommand,
}

DispatchExecution = {
    "decision": DispatchDecision,  # always kind == "command"
    "result": Any,
}
```

Rules:
- `DispatchDecision.kind="label"` MUST include `label` and MUST NOT include `command`.
- `DispatchDecision.kind="command"` MUST include `command` and MUST NOT include `label`.
- `DispatchCommand.name` MUST match exactly one configured command name.
- `DispatchCommand.args` MUST be an object and MUST validate against the selected command's input schema before execution.

### 5.4 Command Definition
A command definition MUST include:
- `name`: unique identifier within one dispatch call,
- `input_schema`: either a JSON Schema mapping or a supported model type used to validate model-selected arguments,
- `executor`: callable invoked only when `auto_execute=True`.

A command definition MAY include:
- `description`: natural-language routing hint for the model,
- `output_schema`: either a JSON Schema mapping or a supported model type for validating executor output.

If `output_schema` is supplied, executor output MUST validate against it before the framework returns a `DispatchExecution`.

Rules:
- Mapping-based `input_schema` and `output_schema` use the same JSON Schema contract defined in Section 5.2.
- Model-type `input_schema` and `output_schema` use the same supported model-type contract defined in Section 5.2.
- Model-selected command arguments MUST remain JSON objects in the public dispatch decision shape.
- When `input_schema` is a supported model type, the executor MUST receive the validated model instance rather than the raw args mapping.
- When `output_schema` is a supported model type, the framework MUST validate the executor result against that model contract and return the materialized model instance in `DispatchExecution.result`.

### 5.5 Public Error Contract
Primitive calls and `LLMOps` factory entrypoints MUST raise framework-specific error objects rather than bare generic exceptions for the failure categories covered by this document.

Each raised framework error MUST expose at least these caller-observable fields or equivalent readable attributes:

```python
FrameworkError = {
    "operation": "eval_bool" | "classify" | "extract" | "dispatch" | "factory",
    "category": (
        "invalid_configuration"
        | "unsupported_runtime"
        | "provider_transport"
        | "provider_authentication"
        | "provider_rate_limit"
        | "provider_contract"
        | "validation_exhausted"
        | "command_execution"
        | "executor_output_validation"
    ),
    "message": str,
    "attempt_count": int,
    "final_validation_category": (
        None
        | "malformed_json"
        | "schema_invalid"
        | "choice_invalid"
        | "decision_invalid"
        | "command_args_invalid"
    ),
}
```

Rules:
- `operation` identifies the primitive or factory entrypoint that failed. `operation="factory"` applies only to `LLMOps` construction/factory failures before an instance is returned.
- `attempt_count` is the number of provider attempts actually made before the error became terminal. It MUST be `0` for preflight failures that occur before any provider call.
- `final_validation_category` MUST be populated only when `category="validation_exhausted"` and MUST describe the final failed validation boundary from the last attempt. For all other categories it MUST be `None`.
- `invalid_configuration` covers caller-supplied argument/configuration errors, including unknown provider names in `from_provider(...)`.
- `unsupported_runtime` covers missing runtime capabilities required by an otherwise valid call, such as model-type extraction support not being available.
- `provider_transport`, `provider_authentication`, `provider_rate_limit`, and `provider_contract` are the caller-visible forms of the adapter/provider categories defined in Section 7.
- `command_execution` covers exceptions raised by a selected executor after model selection has succeeded.
- `executor_output_validation` covers executor results that fail a configured `output_schema`.
- Implementations MAY expose richer exception subclasses or chain the underlying cause, but the machine-readable fields above are the minimum stable contract callers can depend on.

## 6. Public Interface Contracts

Canonical public parameter names for LLM-backed operations are part of the contract:
- Direct primitive functions MUST accept `adapter`, `context`, and `model`, plus optional `max_attempts` and optional `system_prompt`.
- Matching `LLMOps` instance methods MUST accept `context`, plus optional `model`, optional `max_attempts`, and optional `system_prompt`; they MUST NOT require an `adapter` argument because the adapter is instance state.
- Operation-specific public parameter names are `expression` for `eval_bool`, `labels` for `classify`, `schema` for `extract`, and `labels` or `commands` plus optional `auto_execute` for `dispatch`.
- Implementations MAY also support positional calling conventions, but the keyword names above are the canonical stable API surface.

### 6.1 `drop(...) -> Any`
`drop` is a local deterministic helper for pruning or sanitizing nested input data before context serialization.

Contract:
- It MUST NOT call an LLM or provider.
- Given the same input, it MUST return the same output.
- It MUST NOT invent new semantic content.
- It SHOULD return a value that is safer and easier to serialize than the original input.

The exact pruning policy is intentionally not fixed by this architecture document. What is fixed is the boundary: `drop` is preprocessing only and does not change any LLM-backed primitive's semantic contract.

### 6.2 `eval_bool(...) -> bool`
Purpose: decide whether a caller-supplied expression is true or false given context.

Required inputs:
- adapter,
- model,
- context,
- `expression`: a string describing the proposition to evaluate.

Validation contract:
- The primitive MUST constrain the model to a JSON object with exactly one boolean result field in the framework's internal schema.
- The primitive MUST return a plain `bool` to the caller, not the internal object.

Failure contract:
- Invalid caller input fails before provider call.
- Malformed or non-boolean model output enters the repair/retry flow.

### 6.3 `classify(...) -> str`
Purpose: choose exactly one label from a closed set.

Required inputs:
- adapter,
- model,
- context,
- `labels`: non-empty finite set of allowed label strings.

Validation contract:
- Labels MUST be unique within one call.
- The model output MUST validate to exactly one label from the allowed set.
- The primitive MUST return the selected label string.

Failure contract:
- Empty or duplicate label configuration MUST fail before provider call.
- Any model output outside the allowed set enters the repair/retry flow.

### 6.4 `extract(...) -> Any`
Purpose: return structured data that conforms to a caller-supplied schema.

Required inputs:
- adapter,
- model,
- context,
- `schema`: target JSON Schema mapping or supported model type.

Validation contract:
- The provided schema/model defines the complete expected output contract for that call.
- The implementation MUST validate the full extracted value against that contract.
- No partially valid result may be returned.

Failure contract:
- Unsupported schema/model inputs fail before provider call.
- Malformed JSON or schema-invalid output enters the repair/retry flow.
- If a model type is supplied, the runtime MUST support the model-type contract from Section 5.2 or reject the call before provider invocation.

### 6.5 `dispatch(...) -> DispatchDecision | DispatchExecution`
Purpose: choose one action from a closed menu and optionally execute the chosen command.

Dispatch has two mutually exclusive modes:
- label mode: choose one label from a finite set,
- command mode: choose one command and validated arguments from a finite set.

Required inputs:
- adapter,
- model,
- context,
- exactly one menu parameter: `labels` or `commands`.

Optional input:
- `auto_execute` in command mode only.

Validation contract:
- A call MUST NOT provide both labels and commands.
- A call MUST NOT provide neither labels nor commands.
- Label mode returns `DispatchDecision` with `kind="label"`.
- Command mode returns `DispatchDecision` with `kind="command"` unless `auto_execute=True`.
- When `auto_execute=True`, the framework MUST validate selected args, execute the chosen command exactly once, validate executor output when `output_schema` is present, and return `DispatchExecution`.
- When `input_schema` is a supported model type, the returned decision MUST still preserve JSON-shaped `command.args`; model materialization applies only at the executor boundary.

Failure contract:
- Duplicate labels or duplicate command names MUST fail before provider call.
- `auto_execute=True` with label mode MUST fail before provider call.
- Unknown command names, invalid args, or wrong decision shape from the model enter the repair/retry flow before any executor is invoked.
- Executor failures and executor-output-schema failures terminate the operation after selection; they are not retried automatically because retry could duplicate side effects.

## 7. Adapter Contract
`LLMAdapter` is the common provider abstraction used by all LLM-backed primitives.

The adapter contract is canonical at the boundary between the core primitives and provider-specific code.

Normalized request:

```python
AdapterRequest = {
    "operation": "eval_bool" | "classify" | "extract" | "dispatch",
    "model": str,
    "instructions": str,   # framework-owned instructions plus any allowed caller supplement
    "context_json": str,   # serialized context envelope
    "output_schema": dict, # JSON Schema contract for this attempt
    "attempt": int,        # 1-based attempt number
}
```

Request rules:
- `instructions` MUST already be fully assembled by the framework core for that attempt. Adapters MUST treat it as opaque text and MUST NOT rewrite its meaning beyond provider-specific transport formatting.
- `context_json` MUST be the exact serialized envelope that the core wants the model to treat as data. Adapters MUST NOT parse and reserialize it in a way that changes content.
- `output_schema` MUST be the complete JSON Schema contract for the provider call, including any schema derived from a supported model type.
- `attempt` is observable only to the adapter implementation and exists so retries can be distinguished without changing the primitive contract.

Normalized success response:

```python
AdapterResponse = {
    "raw_text": str,                  # candidate model output to parse as JSON
    "provider_response_id": str | None,
}
```

Response rules:
- `raw_text` is the only content field the core uses to parse and validate the candidate result.
- Adapters MUST return text, not already-parsed JSON objects. Local JSON parsing and validation remain core responsibilities.
- `provider_response_id` is optional metadata for telemetry/correlation and MUST NOT affect primitive semantics.

Normalized provider error categories:
- `transport`: network failure, timeout, connection interruption, or unavailable upstream service.
- `authentication`: invalid credentials, missing credentials, or authorization denial.
- `rate_limit`: provider throttling or quota exhaustion that prevents the attempt from completing normally.
- `provider_contract`: provider-side request rejection caused by unsupported model name, malformed provider payload, or other adapter/provider contract mismatch discovered before any usable candidate output is returned.

Error rules:
- Provider-level failures MUST surface to the core with one of the categories above and MUST remain distinct from content-validation failures.
- If a provider returns both an error object and no usable candidate text, the adapter MUST raise a provider error rather than synthesizing `raw_text`.
- If a provider returns usable candidate text, any later JSON parsing or schema validation failure is a core validation failure, not an adapter/provider failure.
- The adapter MUST NOT change the semantic contract of the primitive based on provider-specific capabilities.

Concrete adapters:
- `OpenAIAdapter`: OpenAI Responses API-backed implementation of `LLMAdapter`.
- `OpenRouterAdapter`: OpenRouter-backed implementation of `LLMAdapter`.

Provider-specific prompt format, request fields, and SDK details are adapter internals and are not part of the public contract, provided the observable primitive behavior remains unchanged.

## 8. `LLMOps` Wrapper Contract
`LLMOps` is the convenience facade over the core primitives.

It bundles:
- adapter,
- default model,
- default `max_attempts`,
- optional default system prompt,
- async methods,
- sync wrappers,
- provider-specific factory constructors plus a unified factory.

Canonical constructor:

```python
LLMOps(
    adapter: LLMAdapter,
    model: str,
    max_attempts: int = 2,
    system_prompt: str | None = None,
)
```

Constructor rules:
- `adapter` and `model` are required instance defaults.
- `max_attempts` and `system_prompt` initialize the wrapper defaults described in Section 4.5.
- Constructing `LLMOps` with invalid defaults MUST fail with a framework error in the Section 5.5 shape and `operation="factory"`.

Required behavior:
- Async methods and sync wrappers MUST implement the same validation, retry, and return semantics.
- Instance defaults MAY be overridden per call.
- If a wrapper instance has a default system prompt and a call also supplies `system_prompt`, the per-call `system_prompt` MUST replace the wrapper default for that call rather than append to it.
- Framework-required instructions remain mandatory even when either prompt value is present.
- The wrapper MUST NOT expose provider-specific behavior that changes primitive contracts.

Factory entrypoints:
- `from_openai(...)`
- `from_openrouter(...)`
- `from_provider(...)`

Factory contracts:
- `from_openai(...)` and `from_openrouter(...)` MUST be public constructors that create the corresponding adapter internally and then return an `LLMOps` instance configured as if the caller had invoked `LLMOps(adapter=<constructed adapter>, model=model, max_attempts=max_attempts, system_prompt=system_prompt)`.
- Each provider-specific factory MUST accept keyword-callable `model`, optional `max_attempts`, and optional `system_prompt`, plus any provider-specific credential/configuration arguments needed to construct that adapter.
- Provider-specific factories MUST NOT require the caller to pass a prebuilt adapter instance. Callers that already have an adapter instance use the canonical `LLMOps(...)` constructor instead.
- `from_provider(provider, ...)` MUST dispatch on a provider discriminator string, not on adapter type inference. In this revision the only required discriminator values are `"openai"` and `"openrouter"`.
- `from_provider(provider, ...)` MUST accept the same wrapper-default arguments as the provider-specific factories and MUST forward the remaining provider-construction arguments to the selected provider-specific factory unchanged.
- An unknown `provider` value or missing required factory construction inputs MUST fail before any provider call with a Section 5.5 framework error where `operation="factory"` and `category="invalid_configuration"`.

Instance methods:
- `eval_bool(...)`
- `classify(...)`
- `extract(...)`
- `dispatch(...)`
- `eval_bool_sync(...)`
- `classify_sync(...)`
- `extract_sync(...)`
- `dispatch_sync(...)`

Method rules:
- Async instance methods MUST preserve the same operation-specific argument names defined in Section 6, except that `adapter` is omitted because it is bound to the instance.
- Sync wrappers MUST preserve the same public argument names and return types as their async counterparts.
- If an instance method call omits `model`, the wrapper's default model is used. If it supplies `model`, that value replaces the instance default for that call only.

## 9. End-to-End Processing Flow

### 9.1 Normal Success Path
1. Validate caller arguments and construct the operation-specific output constraints.
2. Normalize and serialize context into the framework's data envelope.
3. Submit the normalized request through the selected adapter and model.
4. Parse provider output as JSON.
5. Validate output against the operation's declared constraints.
6. Convert the validated result into the primitive's public return type.
7. For `dispatch(..., auto_execute=True)`, validate command args, execute the command once, validate command output if required, and return `DispatchExecution`.

### 9.2 Repair Path
1. If provider output is malformed JSON or fails validation, construct a deterministic repair instruction describing the mismatch.
2. Retry the provider call within the effective `max_attempts` limit from Section 4.5.
3. If a later attempt validates successfully, return the typed result.
4. If all attempts fail, raise a terminal framework error conforming to Section 5.5 with `category="validation_exhausted"` and the final validation category from the last attempt.

### 9.3 No-Retry Cases
The framework MUST fail immediately without repair attempts for:
- invalid caller configuration,
- unsupported runtime features,
- adapter/provider `transport`, `authentication`, `rate_limit`, and `provider_contract` failures,
- command executor failures after command selection,
- output-schema validation failures on executor results.

These failures MUST surface with the corresponding Section 5.5 framework error categories rather than as generic runtime exceptions.

## 10. Operational Constraints

### 10.1 Security and Safety
- Context must be treated as data. Embedded user content MUST NOT be merged into framework instructions in a way that makes it authoritative prompt text.
- `dispatch` MUST operate only on an explicit caller-supplied allowlist of labels or commands.
- Command execution MUST be opt-in through `auto_execute=True`.
- The framework MUST validate command arguments before invoking an executor.
- The architecture does not grant implicit shell, filesystem, or network access. Any such capability exists only if the caller exposes it through a command executor.

### 10.2 Observability
A conforming implementation SHOULD emit operation-level telemetry sufficient to diagnose failures, including:
- primitive name,
- provider/adapter,
- model,
- attempt count,
- failure category,
- provider response identifier when available.

Telemetry SHOULD avoid logging raw context or model output by default when those may contain sensitive data, or it SHOULD support caller-controlled redaction.

### 10.3 Performance and Runtime Assumptions
- `drop` MUST execute locally and deterministically without network access.
- LLM-backed primitive latency is dominated by provider round trips and increases with retry count.
- The implementation MUST support asynchronous invocation as a first-class mode.
- Sync wrappers are compatibility APIs for non-async callers and do not define different business behavior.
- The framework MUST keep per-call state isolated so concurrent calls cannot leak context, prompts, or validation results across requests.
- Repair attempts MUST occur within the lifetime of the original call; this architecture does not define deferred retries, background jobs, or queue-backed recovery.

### 10.4 Compatibility Boundary
- The public semantic contracts defined in this document are provider-independent.
- Adding a new provider adapter is compatible if it preserves the same primitive inputs, validation rules, retry boundaries, and return types.

## 11. Out-of-Scope Boundaries
The following are intentionally outside this architecture unless a future revision adds them explicitly:
- persistence of prompts, responses, or operation history,
- distributed orchestration across multiple model calls,
- long-running workflow state machines,
- automatic side-effect retries for command execution,
- unconstrained natural-language response APIs.
