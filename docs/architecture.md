# Architecture Overview

AgentMesh is organized around a control plane and one or more execution runtimes.

## Control plane responsibilities

- accept declarative specs for agent workloads
- schedule agents onto available runtimes
- enforce policy, quotas, and token budgets
- manage rollout state and desired replica counts
- emit unified telemetry for prompts, tool calls, and handoffs

## Runtime responsibilities

- instantiate agent processes from `AgentPod` specs
- attach configured `ToolMount` and `MemoryVolume` resources
- execute model calls and tool invocations
- report health, utilization, and execution traces back to the control plane

## Data plane components

- model providers: OpenAI, Anthropic, Google, local inference endpoints
- tool providers: HTTP APIs, MCP servers, databases, queues, filesystems
- memory providers: vector stores, SQL stores, KV stores, object storage
- observability sinks: OTEL collectors, log drains, metrics backends

## Resource model

The initial API surface revolves around these resource kinds:

- `AgentPod`
- `AgentSet`
- `Workflow`
- `ToolMount`
- `MemoryVolume`
- `Policy`

## Scheduler goals

The scheduler should optimize for:

- latency-sensitive agent tasks
- bounded token budgets
- retry-safe execution
- fair resource sharing across tenants and workflows
- graceful degradation when tools or models fail

## Deployment model

The project should support three progressive targets:

1. Local single-node runtime for development.
2. Self-hosted cluster mode for production teams.
3. Managed cloud control plane for hosted operations.

## API philosophy

The API should feel familiar to operators:

- declarative specs
- explicit status fields
- event streams for lifecycle changes
- clear separation between desired state and observed state

The implementation language is intentionally left open for now, but the control plane should be built around stable schemas and transport boundaries so the CLI, SDKs, and hosted product can evolve independently.
