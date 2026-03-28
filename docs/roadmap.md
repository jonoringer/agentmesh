# Roadmap

## Phase 0: Repo foundation

- publish vision, architecture, and primitive specs
- define the public vocabulary and product boundaries
- decide on initial implementation stack

## Phase 1: Local alpha

- local runtime for `AgentPod`
- `AgentSet` replica management
- workflow execution engine with persisted run history
- workflow rerun support from prior run ids
- CLI for deploy, status, logs, describe, and run inspection
- OpenTelemetry-based tracing

## Current local alpha status

- shipped: apply, get, describe, and logs for local resources
- shipped: workflow execution with per-step run records
- shipped: run history inspection through `get runs`, `describe run`, and `logs run`
- shipped: workflow reruns through `rerun workflow-run <run-id>`
- next: explicit DAG edges, checkpoint reruns, richer status conditions, and tracing export

## Phase 2: Public alpha

- Python SDK for spec authoring and deployment
- first framework adapters
- reference examples and tutorial content
- contributor onboarding and public roadmap

## Phase 3: Hosted control plane

- managed dashboard
- multi-tenant auth and orgs
- usage metering by agent-hours and orchestrated tokens
- hosted traces, logs, and alerts

## Phase 4: Enterprise

- RBAC and policy packs
- audit logs
- regional federation
- compliance controls
- enterprise support workflows
