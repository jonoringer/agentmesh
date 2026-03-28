# AgentMesh

Open orchestration infrastructure for AI agents.

AgentMesh is a framework-agnostic control plane for deploying, scaling, coordinating, and observing autonomous agents in production. The goal is simple: make agent systems operable the way Kubernetes made containers operable, without forcing teams into one model provider, one framework, or one cloud.

## Why this exists

Teams can get a single agent running quickly. The pain starts when that turns into ten, then fifty:

- packaging prompts, tools, memory, and runtime config consistently
- scaling workers without rewriting queueing and retry logic
- tracing handoffs, tool calls, and token usage across a fleet
- sharing memory and state safely between cooperating agents
- avoiding lock-in to a specific framework or cloud runtime

AgentMesh is the infrastructure layer beneath agent frameworks, not a replacement for them.

## Core primitives

- `AgentPod`: declarative deploy unit for one agent runtime
- `AgentSet`: replica management and autoscaling for homogeneous agents
- `Workflow`: DAG orchestration for multi-agent systems
- `ToolMount`: runtime attachment model for tools and external capabilities
- `MemoryVolume`: persistent and shareable memory abstraction
- `ControlPlane`: scheduling, policy, health, and resource coordination

## Product principles

- Declarative by default
- Framework-agnostic
- Model-agnostic
- Observable from day one
- Portable across local, cloud, and self-hosted environments

## Repository map

- [docs/vision.md](/Users/jon/Documents/Playground/docs/vision.md): product thesis and positioning
- [docs/architecture.md](/Users/jon/Documents/Playground/docs/architecture.md): system architecture overview
- [docs/roadmap.md](/Users/jon/Documents/Playground/docs/roadmap.md): phased delivery plan
- [docs/spec/agentpod.md](/Users/jon/Documents/Playground/docs/spec/agentpod.md): core deploy spec
- [docs/spec/agentset.md](/Users/jon/Documents/Playground/docs/spec/agentset.md): scaling spec
- [docs/spec/workflow.md](/Users/jon/Documents/Playground/docs/spec/workflow.md): orchestration spec
- [docs/spec/toolmount.md](/Users/jon/Documents/Playground/docs/spec/toolmount.md): tool interface spec
- [docs/spec/memoryvolume.md](/Users/jon/Documents/Playground/docs/spec/memoryvolume.md): memory abstraction spec
- [docs/spec/controlplane.md](/Users/jon/Documents/Playground/docs/spec/controlplane.md): runtime and policy spec
- [examples/customer-support-stack/README.md](/Users/jon/Documents/Playground/examples/customer-support-stack/README.md): end-to-end example

## What the first release should do

Phase 1 is intentionally narrow:

1. Run `AgentPod` workloads locally and on a single cluster target.
2. Scale `AgentSet` replicas from queue depth and latency signals.
3. Execute `Workflow` DAGs with retries, checkpoints, and handoffs.
4. Attach tools and memory backends through stable interfaces.
5. Emit traces for prompts, tool calls, handoffs, and token consumption.

## Positioning

AgentMesh should feel like:

- Kubernetes for agent workloads
- Docker Compose to production for multi-agent systems
- an open control plane rather than an app framework

It should not feel like:

- a prompt IDE
- a framework that rewrites agent logic
- a managed black box tied to one vendor

## Business model

The repo is designed for an open-core path:

- Open source core orchestration engine and CLI
- Managed AgentMesh Cloud control plane
- Enterprise self-hosted features for governance and compliance

## Name

`AgentMesh` is the working name for this repo. It keeps the infrastructure feel of the original concept without using `kube`, and it naturally extends to terms like "meshctl", "mesh runtime", and "agent mesh network".

## Next steps

- Define the v0 API surface and CRD-like schemas
- Pick implementation language for control plane and CLI
- Build the local runtime first
- Publish a sharp landing page and docs site
- Add a reference implementation with one real workflow

## License

Apache-2.0
