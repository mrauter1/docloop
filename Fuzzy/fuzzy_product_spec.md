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
- Explicit instruction/evidence boundaries over hidden normalization.
- Local validation over provider trust.
- Bounded retries over opaque agent loops.
- Stateless library ergonomics over platform lock-in.
- Provider abstraction over provider-specific app architecture.
- `system_prompt` as the simple, standard top-level instruction surface.

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
- structuring evidence cleanly across text, records, and conversation history,
- evaluating prompt/model changes,
- collecting traces and failure diagnostics,
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
- caller-side cleanup redacts secrets and trims noise if needed,
- `extract` identity fields into a validated schema,
- `eval_bool` "submitted package is complete enough for manual review,"
- `dispatch` to `request_missing_documents` or `advance_to_analyst_queue`.

Why Fuzzy is right:
- This is a reliability problem, not a conversation problem.

## 8. Product Strategy

Fuzzy should grow in four layers:

1. Core primitives and input contract
Keep the four primitives stable and make `system_prompt`, `context`, and `messages` boundaries explicit.

2. Reliability tooling
Add tracing, evals, and better debugging.

3. Integration ergonomics
Add helpers for schemas, commands, messages, and adapters.

4. Domain recipes
Package common production patterns on top of the core.

This preserves ethos because the center remains small and explicit, while optional layers do the utility expansion.

## 9. Prioritized Roadmap

### Phase 1: Adoptability First

Goal:
- Make Fuzzy the easiest way to add one safe LLM decision to an existing Python service.

Ship:
- stable public primitive signatures,
- explicit input contract around `system_prompt`, `context`, and `messages`,
- docs overhaul and quickstarts,
- command ergonomics,
- schema ergonomics,
- test doubles and fixture-driven local testing.

Why first:
- Adoption is blocked more by input ambiguity, schema friction, and command setup than by missing breadth.

### Phase 2: Trust Layer

Goal:
- Make Fuzzy production-credible by default.

Ship:
- `fuzzy.trace`,
- `fuzzy.evals`,
- regression tooling for CI,
- local debugging workflows.

Why second:
- Users trust narrow systems that are inspectable and measurable.

### Phase 3: Flagship Utility

Goal:
- Solve common operational workflows out of the box without hiding the core.

Ship:
- `fuzzy.recipes`,
- 3-4 flagship recipes,
- reference service integrations.

Why third:
- Product utility compounds once teams can see their own workflow mirrored in first-party examples.

### Phase 4: Portability And Scale

Goal:
- Expand addressable adoption without changing the abstraction.

Ship:
- more first-party adapters,
- batch execution,
- fallback model policies,
- approval and audit hooks,
- runtime cost controls.

Why fourth:
- Adapter sprawl and scale features matter after the product is easy to adopt and easy to trust.

### Phase 5: Ecosystem Expansion

Goal:
- Capture repeat use cases without bloating the core package.

Ship:
- optional domain packs,
- pack templates,
- eval-backed contribution standards.

## 10. API Direction

The API should remain explicit. Helpers should reduce repetition, not hide the decision boundary.

### A. Trace-aware calls

```python
result = await fuzzy.classify(
    adapter=adapter,
    model="gpt-5.4-mini",
    messages=[
        {"role": "user", "parts": [{"type": "text", "text": inbound_message}]},
        {"role": "user", "parts": [{"type": "json", "data": account_metadata}]},
    ],
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

### B. Input model

```python
result = await fuzzy.extract(
    adapter=adapter,
    model="gpt-5.4-mini",
    system_prompt="Extract a validated refund claim.",
    messages=[
        {"role": "user", "parts": [{"type": "text", "text": ticket.body}]},
        {"role": "user", "parts": [{"type": "json", "data": account_state}]},
    ],
    schema=RefundClaimSchema,
)
```

Simple shorthand:

```python
result = await fuzzy.extract(
    adapter=adapter,
    model="gpt-5.4-mini",
    system_prompt="Extract a validated refund claim.",
    context={"ticket": ticket.body, "account": account_state},
    schema=RefundClaimSchema,
)
```

Recommendation:
- `messages` is the primary advanced input surface.
- `context` remains a shorthand for simple cases.
- `context` and `messages` are mutually exclusive.
- `system_prompt` remains the standard top-level instruction surface.

### C. Recipe modules

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

### D. Command decorator

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
    messages=messages,
    commands=[open_refund_review_case, request_invoice_id],
    auto_execute=False,
)
```

### E. Evals API

```python
from fuzzy.evals import ClassificationCase, run_classification_eval

report = await run_classification_eval(
    adapter=adapter,
    model="gpt-5.4-mini",
    labels=["billing", "bug", "feature_request", "abuse"],
    cases=[
        ClassificationCase(
            name="duplicate charge",
            messages=[
                {"role": "user", "parts": [{"type": "text", "text": "I was billed twice"}]},
            ],
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

### F. Future multimodal direction

```python
decision = await fuzzy.extract(
    adapter=adapter,
    model="gpt-5.4-mini",
    system_prompt="Extract receipt fields for review.",
    messages=[
        {
            "role": "user",
            "parts": [
                {"type": "text", "text": "Review this receipt image."},
                {"type": "image", "source": receipt_image},
            ],
        },
    ],
    schema=ReceiptSchema,
)
```

This is illustrative of the intended direction: the public input surface should be able to grow to image and video inputs without forcing everything through a JSON-only context model.

### G. Domain pack structure

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
- caller-side cleanup only if needed,
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
- message/input contracts,
- schemas/contracts,
- errors,
- trace hooks,
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
- typed input contract around `system_prompt`, `context`, and `messages`
- docs overhaul and quickstarts
- schema helpers
- command decorators and registry
- local testing helpers

Reason:
- This removes the biggest first-use friction and makes the API boundary obvious.

### Release 2

Ship:
- `fuzzy.trace`
- `fuzzy.evals`
- regression and CI helpers
- local trace viewing

Reason:
- This makes Fuzzy production-credible and inspectable.

### Release 3

Ship:
- 3 flagship recipes
- reference service integrations

Flagship recipes:
- support triage,
- lead qualification,
- document completeness.

Reason:
- This turns the core into a repeatable adoption path for real workflows.

## 17. Summary

Fuzzy can 10x its utility by becoming easier to adopt, easier to debug, easier to evaluate, and easier to apply to common production decision problems.

The winning move is not to add more autonomy or more hidden normalization.

The winning move is to make constrained LLM decisioning so reliable, explicit, and ergonomic that teams default to Fuzzy whenever a model output must safely drive code.
