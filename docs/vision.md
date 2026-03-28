# Vision

AgentMesh is an orchestration layer for autonomous software systems.

The thesis is straightforward: agents will become a first-class runtime primitive, and every major runtime primitive eventually needs a control plane. Teams should be able to describe an agent system declaratively, deploy it consistently, scale it safely, observe it end to end, and move it across providers without rewriting their stack.

## The problem

Production agent systems currently break down along the same fault lines:

- deployment artifacts are ad hoc and framework-specific
- scaling logic is embedded in application code
- memory and tool attachments are inconsistent
- orchestration state is spread across queues, code, and prompt logic
- observability is fragmented across logs, traces, and vendor dashboards

This creates a tax on every team building serious agent workflows.

## The wedge

AgentMesh is not an agent framework. It is the neutral orchestration layer below frameworks and above infrastructure.

That means:

- teams keep their existing agent code
- frameworks integrate through adapters instead of rewrites
- model vendors are swappable
- infra teams get the operational surface they expect

## The standard we want to create

AgentMesh should become the common language for:

- packaging an agent workload
- attaching tools and memory
- describing multi-agent workflows
- applying policy and resource limits
- querying runtime behavior

If the ecosystem converges on these primitives, cloud vendors and frameworks compete around the control plane rather than trapping users inside proprietary abstractions.
