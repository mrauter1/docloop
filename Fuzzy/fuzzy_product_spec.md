# Fuzzy Product Spec: 10x Utility Without Ethos Drift

## 1. Product Thesis

Fuzzy should become the default decision-and-structure layer for application teams that want LLM capability without adopting an agent platform.

That means:

- keep the core surface small,
- keep outputs typed and validated,
- keep orchestration explicit and code-first,
- expand utility through recipes, evals, adapters, and observability,
- avoid drifting into visual workflow builders, autonomous agents, or platform-heavy runtime concerns.

The target outcome is not "more AI features." The target outcome is that teams can safely embed LLM-backed decisions into production code with much less custom glue.

## 2. Product Principles

### Preserve

- Constrained primitives over open-ended prompting.
- Typed return values over prose.
- Local validation over provider trust.
- Bounded retries over opaque agent loops.
- Stateless library ergonomics over platform lock-in.
- Provider abstraction over provider-specific app architecture.

### Add

- Faster onboarding.
- More common tasks solved out of the box.
- Better production visibility.
- Better testing and regression control.
- Better integration ergonomics.

### Avoid

- Drag-and-drop workflow UI.
- Long-running orchestration runtime.
- Mandatory persistence or databases.
- Open-ended tool-using agents.
- High-level abstractions that hide the actual decision boundary.

## 3. Problem Statement

Today Fuzzy is strong where the problem is:

- "Given context, return a boolean."
- "Choose exactly one label."
- "Extract structured data that matches this schema."
- "Choose one command from a closed menu and validate its arguments."

That is useful, but many teams will still not adopt it because they must build too much around it:

- authoring schemas,
- defining command contracts,
- evaluating prompt/model changes,
- collecting traces and failure diagnostics,
- normalizing messy inputs,
- packaging domain-specific patterns for repeated use.

The 10x opportunity is to eliminate that surrounding friction without changing the core philosophy.

## 4. Who Fuzzy Is For

### Persona 1: Backend Product Engineer

Profile:
- Owns business logic in an existing Python service.
- Wants to add AI-assisted decisions to product flows.
- Does not want to introduce a new platform.

Goals:
- Route requests.
- Extract structured values.
- Gate actions behind policy decisions.

Current pain:
- Free-form prompting leads to brittle parsing.
- Workflow tools feel too heavy for small, high-leverage decisions.

Why Fuzzy fits:
- It behaves like an application library, not an external control plane.

### Persona 2: Applied AI Engineer

Profile:
- Builds extraction, classification, and decision systems.
- Cares about evals, failure rates, schema validity, and model portability.

Goals:
- Improve quality over time.
- Benchmark models and prompts safely.
- Keep outputs production-safe.

Current pain:
- Many LLM libraries optimize for generation, not validated decisions.

Why Fuzzy fits:
- The public contract is already framed around validation and bounded recovery.

### Persona 3: Platform Engineer

Profile:
- Supports multiple internal teams adding AI features.
- Wants standard patterns and predictable operational behavior.

Goals:
- Reduce repeated prompt/parsing mistakes.
- Create one sanctioned way to do typed LLM calls.
- Offer reusable patterns for common business cases.

Current pain:
- Each team builds custom wrappers and error handling.

Why Fuzzy fits:
- The primitives are small enough to standardize across teams.

### Persona 4: Compliance / Operations Engineer

Profile:
- Owns workflows where actions must be approved, rejected, escalated, or deferred.
- Needs explainable outcomes and constrained execution.

Goals:
- Minimize unsafe automation.
- Encode simple policy boundaries.
- Support human-in-the-loop workflows.

Current pain:
- Agentic systems are too open-ended for audit-sensitive flows.

Why Fuzzy fits:
- Closed labels and closed command menus match operational policy boundaries.

### Persona 5: Founder / Solo Builder

Profile:
- Ships product quickly with a small codebase.
- Needs AI capabilities that remain maintainable later.

Goals:
- Add a few high-value AI features quickly.
- Avoid technical debt from hand-rolled prompt glue.

Current pain:
- Framework sprawl and unclear abstractions slow simple product work.

Why Fuzzy fits:
- It can solve narrow, valuable problems with a very small mental model.

## 5. Core Jobs To Be Done

Fuzzy should win when the user's actual job is one of these:

1. Turn messy human input into a small typed decision.
2. Turn messy human input into structured records for downstream systems.
3. Choose one allowed next action from a controlled set.
4. Insert an LLM-based judgment step before a risky or expensive automation.
5. Standardize how multiple teams use LLMs in backend systems.

## 6. Best-Fit Use Cases

### A. Support Intake Triage

Inputs:
- support email,
- previous account state,
- billing metadata.

Desired outputs:
- issue type,
- urgency,
- refund eligibility,
- selected backend workflow.

Why Fuzzy:
- The result should be labels, booleans, extracted fields, and validated commands.

### B. CRM Lead Qualification

Inputs:
- lead form,
- company description,
- inbound message.

Desired outputs:
- segment label,
- budget range,
- urgency,
- sales routing decision.

Why Fuzzy:
- This is constrained business logic, not agentic research.

### C. Procurement / Vendor Intake

Inputs:
- free-text request,
- vendor metadata,
- expected spend,
- uploaded docs.

Desired outputs:
- risk tier,
- required review tracks,
- extracted fields,
- dispatch to approval path.

Why Fuzzy:
- The available actions are finite and policy-shaped.

### D. KYC / Onboarding Completeness

Inputs:
- submitted forms,
- uploaded identity/company documents,
- jurisdiction info.

Desired outputs:
- completeness decision,
- missing fields list,
- risk flags,
- route to manual review or request-more-info.

Why Fuzzy:
- Strong fit for extraction + policy evaluation + controlled routing.

### E. Legal / Contract Review

Inputs:
- contract text,
- clause requirements,
- customer segment.

Desired outputs:
- clause presence booleans,
- extracted key terms,
- risk label,
- dispatch to legal review if thresholds are met.

Why Fuzzy:
- This is contract-focused decisioning, not general-purpose summarization.

### F. Internal Access Approval

Inputs:
- access request,
- requested systems,
- employee role,
- justification text.

Desired outputs:
- policy match boolean,
- extracted scope,
- risk category,
- next-step command.

Why Fuzzy:
- Safety comes from explicit constraints and closed actions.

## 7. Simulated Practical Situations

### Scenario 1: Refund Triage In SaaS Support

Context:
- Customer writes: "I was charged twice on March 10. Please refund the duplicate."
- Account shows two charges within 30 minutes.
- Existing refund policy allows duplicate-charge review.

Fuzzy flow:
- `classify(context, labels=["billing", "bug", "feature_request", "abuse"])`
- `eval_bool(context, expression="customer is claiming a duplicate charge")`
- `extract(context, schema=RefundClaimSchema)`
- `dispatch(context, commands=[open_refund_review_case, request_invoice_id], auto_execute=False)`

Why Fuzzy is right:
- The system needs one category, one truth judgment, a few extracted fields, and one allowed next action.
- A general agent would add surface area without adding value.

### Scenario 2: Vendor Security Intake

Context:
- Employee requests approval for a new analytics vendor.
- Text mentions customer data ingestion and EU customers.
- Spend is under a review threshold, but data sensitivity is high.

Fuzzy flow:
- `extract` vendor name, data classes, regions, spend, deployment model.
- `classify` risk as `low`, `medium`, or `high`.
- `dispatch` to `security_review`, `privacy_review`, or `auto_approve`.

Why Fuzzy is right:
- The workflow is policy-bounded and downstream systems already exist.
- The need is reliable structured judgment, not agent autonomy.

### Scenario 3: Lead Qualification At Inbound Volume

Context:
- Hundreds of inbound leads arrive daily.
- Sales wants immediate routing for enterprise-grade leads only.

Fuzzy flow:
- `extract` employee count, use case, budget, geography.
- `classify` segment as `enterprise`, `mid_market`, `self_serve`, or `junk`.
- `eval_bool` "lead should page sales immediately."
- `dispatch` to `create_sdr_task`, `send_self_serve_sequence`, or `drop_lead`.

Why Fuzzy is right:
- The company needs a robust decision kernel that plugs into CRM automation.

### Scenario 4: Contract Risk Scan Before Human Review

Context:
- A legal ops team wants each contract pre-scanned before counsel looks at it.

Fuzzy flow:
- `eval_bool` for clause presence checks.
- `extract` term length, renewal rules, liability caps, governing law.
- `classify` overall risk tier.
- `dispatch` to `queue_standard_review` or `queue_escalated_review`.

Why Fuzzy is right:
- The tool is augmenting an existing review operation with narrow, typed outputs.

### Scenario 5: Identity Verification Completeness Check

Context:
- A fintech onboarding system receives messy OCR text and user-entered fields.

Fuzzy flow:
- deterministic preprocessing redacts secrets and trims noise,
- `extract` identity fields into a validated schema,
- `eval_bool` "submitted package is complete enough for manual review,"
- `dispatch` to `request_missing_documents` or `advance_to_analyst_queue`.

Why Fuzzy is right:
- This is a reliability problem, not a conversation problem.

## 8. Product Strategy

Fuzzy should grow in four layers:

1. Core primitives
Keep the current model stable.

2. Reliability tooling
Add tracing, evals, and better preprocessing.

3. Integration ergonomics
Add helpers for commands, schemas, and adapters.

4. Domain recipes
Package common production patterns on top of the core.

This preserves ethos because the center remains small and explicit, while optional layers do the utility expansion.

## 9. Prioritized Roadmap

### Phase 1: Immediate Utility Multipliers

#### 1. `fuzzy.recipes`

Goal:
- Ship reusable production patterns built on current primitives.

Initial recipes:
- support triage,
- lead qualification,
- document completeness,
- policy gate,
- constrained approval router.

Why first:
- Highest utility per unit of implementation.
- Demonstrates value using the existing API.

#### 2. `fuzzy.trace`

Goal:
- Provide optional structured trace output per call.

Trace contents:
- request metadata,
- attempt count,
- final raw text,
- validation errors per attempt,
- provider response IDs,
- normalized schema metadata.

Why first:
- Needed for debugging, tuning, and trust.

#### 3. `fuzzy.evals`

Goal:
- Make prompt/model iteration measurable.

Capabilities:
- fixture-driven tests,
- prompt variants,
- model comparisons,
- label accuracy,
- extraction validity rate,
- retry rate and exhaustion rate.

Why first:
- Moves Fuzzy from "library" to "operationally credible library."

#### 4. `fuzzy.preprocess`

Goal:
- Expand deterministic local helpers.

Examples:
- `drop_large_fields`,
- `redact_patterns`,
- `truncate_text`,
- `normalize_whitespace`,
- `pick_fields`.

Why first:
- Improves cost, consistency, and safety without touching the LLM contract.

### Phase 2: Broaden Adoption Without Bloat

#### 5. More first-party adapters

Targets:
- Anthropic,
- Azure OpenAI,
- Google,
- local OpenAI-compatible endpoints.

Why:
- Increases addressable adoption while preserving the current abstraction.

#### 6. Command ergonomics

Goal:
- Make `dispatch` dramatically easier to use.

Features:
- command decorator,
- command registry,
- schema inference where safe,
- command validation helpers,
- registry docs generation.

Why:
- `dispatch` is one of the most powerful primitives but also one of the most setup-heavy.

#### 7. Better model contract support

Goal:
- Expand beyond raw JSON Schema authoring.

Features:
- first-class Pydantic integration,
- dataclass-to-schema helper,
- TypedDict helper,
- schema builder utilities.

Why:
- Schema friction is a top adoption barrier.

### Phase 3: Strategic Extensions

#### 8. Domain packs

Examples:
- `fuzzy-support`
- `fuzzy-crm`
- `fuzzy-compliance`
- `fuzzy-intake`

Each pack includes:
- recipe wrappers,
- prompts,
- schemas,
- command definitions,
- eval fixtures.

Why:
- Captures real product value without bloating the core package.

#### 9. Batch execution and runtime policies

Features:
- bulk classify/extract,
- concurrency controls,
- fallback model policies,
- retry metrics,
- cost accounting hooks.

Why:
- Important for high-volume production workloads.

## 10. API Direction

The API should remain explicit. Helpers should reduce repetition, not hide the decision boundary.

### A. Trace-aware calls

```python
result = await fuzzy.classify(
    adapter=adapter,
    model="gpt-5.4-mini",
    context=context,
    labels=["low", "medium", "high"],
    trace=True,
)

assert result.value == "high"
assert result.trace.attempt_count == 1
```

Alternative shape:

```python
value, trace = await fuzzy.classify(..., return_trace=True)
```

Recommendation:
- Prefer `return_trace=True` for minimal disruption to the current contract.

### B. Recipe modules

```python
from fuzzy.recipes.support import triage_ticket

decision = await triage_ticket(
    adapter=adapter,
    model="gpt-5.4-mini",
    ticket=ticket,
    customer=customer,
)
```

Returned shape:

```python
{
    "category": "billing",
    "urgency": "high",
    "refund_candidate": True,
    "next_action": {
        "kind": "command",
        "command": {
            "name": "open_refund_review_case",
            "args": {"priority": "high"},
        },
    },
}
```

### C. Command decorator

```python
from fuzzy.commands import command

@command(
    description="Open a refund review case for billing operations",
    input_schema=RefundReviewInput,
    output_schema=RefundReviewResult,
)
def open_refund_review_case(payload: RefundReviewInput) -> RefundReviewResult:
    ...
```

Use in dispatch:

```python
decision = await fuzzy.dispatch(
    adapter=adapter,
    model=model,
    context=context,
    commands=[open_refund_review_case, request_invoice_id],
    auto_execute=False,
)
```

### D. Evals API

```python
from fuzzy.evals import ClassificationCase, run_classification_eval

report = await run_classification_eval(
    adapter=adapter,
    model="gpt-5.4-mini",
    labels=["billing", "bug", "feature_request", "abuse"],
    cases=[
        ClassificationCase(
            name="duplicate charge",
            context={"message": "I was billed twice"},
            expected="billing",
        ),
    ],
)
```

Report shape:

```python
{
    "accuracy": 0.94,
    "validation_exhaustion_rate": 0.01,
    "retry_rate": 0.08,
    "cases": [...],
}
```

### E. Preprocess pipeline

```python
from fuzzy.preprocess import compose, drop_large_fields, redact_patterns, truncate_text

clean_context = compose(
    drop_large_fields(max_chars=4000),
    redact_patterns([r"\\b\\d{16}\\b"]),
    truncate_text(max_chars=6000),
)(raw_context)
```

### F. Domain pack structure

```python
from fuzzy_support import triage_ticket, SupportTicketSchema
```

This keeps the core package focused while allowing domain-specific convenience to flourish separately.

## 11. Example Recipe Modules

### Recipe: Support Triage

Inputs:
- customer message,
- account state,
- recent transactions.

Outputs:
- category,
- urgency,
- refund candidate flag,
- next action decision.

Primitive composition:
- `classify` for category,
- `classify` for urgency,
- `eval_bool` for policy checks,
- `dispatch` for next action.

### Recipe: Lead Qualification

Inputs:
- lead form,
- company description,
- inbound note.

Outputs:
- segment,
- extracted company profile,
- outbound routing decision.

Primitive composition:
- `extract` for fields,
- `classify` for segment,
- `dispatch` for SDR vs nurture vs self-serve routing.

### Recipe: Document Completeness

Inputs:
- uploaded docs,
- expected checklist,
- OCR text.

Outputs:
- completeness boolean,
- missing items,
- next-step command.

Primitive composition:
- deterministic preprocess,
- `extract` for observed fields,
- `eval_bool` for completeness policy,
- `dispatch` for follow-up action.

### Recipe: Approval Router

Inputs:
- request text,
- requester role,
- policy metadata.

Outputs:
- risk label,
- extracted scope,
- route command.

Primitive composition:
- `extract` for scope,
- `classify` for risk,
- `dispatch` for approval path.

## 12. Product Packaging

### Core package: `fuzzy`

Contains:
- primitives,
- adapters,
- schemas/contracts,
- errors,
- trace hooks,
- preprocess helpers,
- eval framework.

### Optional packages

- `fuzzy-support`
- `fuzzy-crm`
- `fuzzy-compliance`
- `fuzzy-intake`

This preserves a small core while allowing focused expansion.

## 13. Success Metrics

### Adoption metrics

- Time to first successful production use case.
- Number of teams or services using Fuzzy.
- Number of recipe modules adopted.

### Reliability metrics

- Validation exhaustion rate.
- Retry rate.
- Schema-valid output rate.
- Command argument validity rate.

### Product value metrics

- Reduction in hand-written prompt parsing code.
- Reduction in workflow bugs caused by malformed model outputs.
- Faster iteration on prompts/models via evals.

## 14. Risks And Failure Modes

### Risk: Ethos drift

Failure pattern:
- adding too many high-level abstractions,
- hiding the underlying decision contract,
- turning Fuzzy into a mini-platform.

Mitigation:
- keep core primitives central,
- make new features optional layers,
- reject features that require their own runtime story.

### Risk: Recipe sprawl

Failure pattern:
- too many overlapping domain helpers with unclear ownership.

Mitigation:
- maintain a small set of flagship recipes,
- move domain-heavy patterns into separate packages,
- ship eval fixtures with every recipe.

### Risk: Trace API complexity

Failure pattern:
- breaking the current simple return contract.

Mitigation:
- prefer opt-in trace returns instead of changing base return types.

### Risk: Adapter fragmentation

Failure pattern:
- too many provider-specific quirks leaking upward.

Mitigation:
- keep the adapter interface narrow,
- enforce local validation uniformly.

## 15. Why Fuzzy Instead Of Langflow

### Positioning statement

Langflow is a workflow and agent platform.
Fuzzy should be the decision-and-structure kernel for codebases that do not want to adopt a workflow platform.

### When Fuzzy wins

- The team already has an application and backend services.
- The AI task is narrow and operational.
- Outputs must be typed and validated.
- Actions must come from a closed set.
- Teams want code review, tests, and explicit control in the existing repo.

### When Langflow wins

- The team wants a visual builder.
- Non-engineers need to assemble flows.
- The workflow spans many components and iterative prompt experimentation in a UI.
- The system is closer to an agent platform than a typed application helper.

### Practical positioning memo

Do not pitch Fuzzy as "a better Langflow."

Pitch Fuzzy as:
- "the safe backend primitive layer for LLM decisions,"
- "the missing typed contract between models and application logic,"
- "the minimal library for teams that need judgment, not an agent platform."

The comparison should be:
- Langflow helps teams build and operate AI workflows.
- Fuzzy helps teams make a single application decision or extraction step production-safe.

That distinction is strategic. Fuzzy becomes more valuable by deepening its niche, not broadening into theirs.

## 16. Recommended First Release Plan

### Release 1

Ship:
- `fuzzy.trace`
- `fuzzy.preprocess`
- `fuzzy.evals`
- 3 flagship recipes

Flagship recipes:
- support triage,
- lead qualification,
- document completeness.

Reason:
- This produces the largest jump in real-world utility while keeping the architecture coherent.

### Release 2

Ship:
- command decorators and registry,
- 2-3 new adapters,
- schema helpers.

Reason:
- This reduces the biggest API friction points for deeper adoption.

### Release 3

Ship:
- one or two optional domain packs,
- batch/runtime policy features.

Reason:
- This expands scale and repeatability after the core workflow is proven.

## 17. Summary

Fuzzy can 10x its utility by becoming easier to adopt, easier to debug, easier to evaluate, and easier to apply to common production decision problems.

The winning move is not to add more autonomy.

The winning move is to make constrained LLM decisioning so reliable and ergonomic that teams default to Fuzzy whenever a model output must safely drive code.
