# ControlPlane Responsibilities

The control plane is the coordination layer that reconciles desired state with live agent runtime state.

## Responsibilities

- scheduling
- health checks and reconciliation
- policy enforcement
- admission validation
- eventing and telemetry
- rollout coordination
- quota and budget enforcement

## Policy areas

- model allowlists and denylists
- token ceilings
- tool access restrictions
- memory sharing boundaries
- tenancy isolation
- cost guardrails

## Non-goals for v0

- training or fine-tuning models
- replacing application business logic
- becoming a full prompt authoring environment

## Success criteria

An operator should be able to answer these questions from the control plane:

- What agents are running right now?
- Why did this workflow fail?
- Which tool call caused the incident?
- How much token budget has this team consumed?
- What changed between the last successful run and this one?
