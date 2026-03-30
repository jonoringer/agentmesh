from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set

from .schema import Resource, resource_from_dict, summarize_resource


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Event:
    timestamp: str
    level: str
    message: str


@dataclass
class RuntimeObject:
    resource: Dict[str, Any]
    phase: str
    applied_at: str
    observed_generation: int = 1
    status: Dict[str, Any] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)


@dataclass
class WorkflowStepRun:
    name: str
    agent_ref: str
    phase: str
    started_at: str
    finished_at: Optional[str] = None
    retries: int = 0
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class WorkflowRun:
    run_id: str
    workflow: str
    phase: str
    started_at: str
    finished_at: Optional[str] = None
    current_step: Optional[str] = None
    steps: List[WorkflowStepRun] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    error: Optional[str] = None
    source_run_id: Optional[str] = None
    start_step: Optional[str] = None


class LocalControlPlane:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_dir = self.root / ".agentmesh"
        self.state_file = self.state_dir / "state.json"
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {"resources": {}, "workflow_runs": []}

        with self.state_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("resources", {})
        data.setdefault("workflow_runs", [])
        return data

    def _save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)
            handle.write("\n")

    def apply(self, resource: Resource) -> RuntimeObject:
        self.data = self._load()
        validation_errors = self.validate_resource(resource)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        key = self._resource_key(resource.kind, resource.metadata.name)
        existing = self.data["resources"].get(key)
        status = self._initial_status_for_resource(resource)

        if existing:
            generation = int(existing.get("observed_generation", 1)) + 1
            events = [Event(**event) for event in existing.get("events", [])]
            events.append(Event(timestamp=now_iso(), level="info", message="resource updated"))
            runtime_object = RuntimeObject(
                resource=resource.to_dict(),
                phase="Running",
                applied_at=now_iso(),
                observed_generation=generation,
                status=status,
                events=events[-25:],
            )
        else:
            runtime_object = RuntimeObject(
                resource=resource.to_dict(),
                phase="Running",
                applied_at=now_iso(),
                observed_generation=1,
                status=status,
                events=[
                    Event(timestamp=now_iso(), level="info", message="resource scheduled"),
                    Event(timestamp=now_iso(), level="info", message="local runtime attached"),
                ],
            )

        self.data["resources"][key] = {
            "resource": runtime_object.resource,
            "phase": runtime_object.phase,
            "applied_at": runtime_object.applied_at,
            "observed_generation": runtime_object.observed_generation,
            "status": runtime_object.status,
            "events": [asdict(event) for event in runtime_object.events],
        }
        self._save()
        return runtime_object

    def list_resources(self) -> List[RuntimeObject]:
        self.data = self._load()
        items: List[RuntimeObject] = []
        for payload in self.data["resources"].values():
            items.append(
                RuntimeObject(
                    resource=payload["resource"],
                    phase=payload["phase"],
                    applied_at=payload["applied_at"],
                    observed_generation=payload.get("observed_generation", 1),
                    status=payload.get("status", {}),
                    events=[Event(**event) for event in payload.get("events", [])],
                )
            )
        items.sort(key=lambda item: (item.resource["kind"], item.resource["metadata"]["name"]))
        return items

    def get_resource(self, name: str) -> Optional[RuntimeObject]:
        self.data = self._load()
        for payload in self.data["resources"].values():
            if payload["resource"]["metadata"]["name"] == name:
                return RuntimeObject(
                    resource=payload["resource"],
                    phase=payload["phase"],
                    applied_at=payload["applied_at"],
                    observed_generation=payload.get("observed_generation", 1),
                    status=payload.get("status", {}),
                    events=[Event(**event) for event in payload.get("events", [])],
                )
        return None

    def format_table(self) -> str:
        rows = [["KIND", "NAME", "PHASE", "APPLIED"]]
        for item in self.list_resources():
            rows.append(
                [
                    item.resource["kind"],
                    item.resource["metadata"]["name"],
                    item.phase,
                    item.applied_at,
                ]
            )

        widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
        return "\n".join(
            "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
            for row in rows
        )

    def format_workflow_runs_table(self, workflow_name: Optional[str] = None) -> str:
        runs = self.list_workflow_runs(workflow_name)
        rows = [["RUN ID", "WORKFLOW", "PHASE", "CURRENT STEP", "STARTED"]]
        for run in runs:
            rows.append(
                [
                    run.run_id,
                    run.workflow,
                    run.phase,
                    run.current_step or "-",
                    run.started_at,
                ]
            )

        widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
        return "\n".join(
            "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
            for row in rows
        )

    @staticmethod
    def _resource_key(kind: str, name: str) -> str:
        return f"{kind}/{name}"

    def validate_resource(self, resource: Resource) -> List[str]:
        if resource.kind == "AgentPod":
            return self._validate_agentpod(resource)
        if resource.kind == "AgentSet":
            return self._validate_agentset(resource)
        if resource.kind == "Workflow":
            return self._validate_workflow_resource(resource)
        return []

    def validate_workflow(self, workflow_name: str) -> List[str]:
        workflow_object = self.get_resource(workflow_name)
        if not workflow_object:
            return [f"workflow not found: {workflow_name}"]
        if workflow_object.resource["kind"] != "Workflow":
            return [f"resource is not a Workflow: {workflow_name}"]
        return self._validate_workflow_resource(resource_from_dict(workflow_object.resource))

    def run_workflow(
        self,
        workflow_name: str,
        source_run_id: Optional[str] = None,
        start_step: Optional[str] = None,
    ) -> WorkflowRun:
        self.data = self._load()
        workflow_object = self.get_resource(workflow_name)
        if not workflow_object:
            raise ValueError(f"workflow not found: {workflow_name}")
        if workflow_object.resource["kind"] != "Workflow":
            raise ValueError(f"resource is not a Workflow: {workflow_name}")

        workflow = resource_from_dict(workflow_object.resource)
        steps = workflow.spec.get("steps") or []
        steps_by_name = {step["name"]: step for step in steps}
        entrypoint = start_step or workflow.spec.get("entrypoint") or steps[0]["name"]

        errors = self.validate_workflow(workflow_name)
        if start_step and start_step not in steps_by_name:
            errors = errors + [f"workflow step not found: {start_step}"]

        if errors:
            run = WorkflowRun(
                run_id=self._next_workflow_run_id(workflow_name),
                workflow=workflow_name,
                phase="Failed",
                started_at=now_iso(),
                finished_at=now_iso(),
                events=[Event(timestamp=now_iso(), level="error", message=message) for message in errors],
                error="; ".join(errors),
                source_run_id=source_run_id,
                start_step=start_step,
            )
            self._persist_workflow_run(run)
            self._update_workflow_status(
                workflow_name=workflow_name,
                phase="Failed",
                run_id=run.run_id,
                current_step=start_step,
                error=run.error,
            )
            raise ValueError(run.error)

        run = WorkflowRun(
            run_id=self._next_workflow_run_id(workflow_name),
            workflow=workflow_name,
            phase="Running",
            started_at=now_iso(),
            current_step=entrypoint,
            events=[
                Event(
                    timestamp=now_iso(),
                    level="info",
                    message=self._start_message(workflow_name, source_run_id, start_step),
                )
            ],
            source_run_id=source_run_id,
            start_step=start_step,
        )
        self._update_workflow_status(
            workflow_name=workflow_name,
            phase="Running",
            run_id=run.run_id,
            current_step=entrypoint,
            error=None,
        )

        queue: Deque[str] = deque([entrypoint])
        enqueued: Set[str] = {entrypoint}
        completed: Set[str] = set()

        while queue:
            step_name = queue.popleft()
            step = steps_by_name[step_name]
            step_run = self._execute_workflow_step(step)
            run.current_step = step_run.name
            run.steps.append(step_run)
            run.events.append(
                Event(
                    timestamp=step_run.started_at,
                    level="info",
                    message=f"step {step_run.name} started using AgentPod/{step_run.agent_ref}",
                )
            )

            if step_run.phase == "Succeeded":
                run.events.append(
                    Event(
                        timestamp=step_run.finished_at or now_iso(),
                        level="info",
                        message=f"step {step_run.name} completed",
                    )
                )
            else:
                run.phase = "Failed"
                run.finished_at = step_run.finished_at
                run.error = step_run.error
                run.events.append(
                    Event(
                        timestamp=step_run.finished_at or now_iso(),
                        level="error",
                        message=f"step {step_run.name} failed: {step_run.error}",
                    )
                )
                break

            completed.add(step_name)
            for next_step in self._step_successors(step, steps):
                if next_step in completed or next_step in enqueued:
                    continue
                queue.append(next_step)
                enqueued.add(next_step)

        if run.phase != "Failed":
            run.phase = "Succeeded"
            run.finished_at = now_iso()
            run.current_step = run.steps[-1].name if run.steps else entrypoint
            run.events.append(
                Event(
                    timestamp=run.finished_at,
                    level="info",
                    message=f"workflow run completed for {workflow_name}",
                )
            )

        self._persist_workflow_run(run)
        self._update_workflow_status(
            workflow_name=workflow_name,
            phase=run.phase,
            run_id=run.run_id,
            current_step=run.current_step,
            error=run.error,
        )
        self._record_resource_event(
            kind="Workflow",
            name=workflow_name,
            level="info" if run.phase == "Succeeded" else "error",
            message=f"run {run.run_id} {run.phase.lower()}",
        )
        return run

    def rerun_workflow(self, run_id: str, start_step: Optional[str] = None) -> WorkflowRun:
        run = self.get_workflow_run(run_id)
        if not run:
            raise ValueError(f"workflow run not found: {run_id}")
        return self.run_workflow(run.workflow, source_run_id=run_id, start_step=start_step)

    def scale_agentset(self, name: str, replicas: int) -> RuntimeObject:
        self.data = self._load()
        key = self._resource_key("AgentSet", name)
        payload = self.data["resources"].get(key)
        if not payload:
            raise ValueError(f"agentset not found: {name}")

        resource = resource_from_dict(payload["resource"])
        replicas_spec = resource.spec.setdefault("replicas", {})
        min_replicas = int(replicas_spec.get("min", replicas))
        max_replicas = int(replicas_spec.get("max", replicas))
        if replicas < min_replicas or replicas > max_replicas:
            raise ValueError(
                f"desired replicas {replicas} out of range [{min_replicas}, {max_replicas}]"
            )

        replicas_spec["desired"] = replicas
        payload["resource"] = resource.to_dict()
        payload["phase"] = "Running"
        status = payload.get("status", {})
        status["desiredReplicas"] = replicas
        status["currentReplicas"] = replicas
        status["readyReplicas"] = replicas
        status["lastScaledAt"] = now_iso()
        payload["status"] = status

        events = [Event(**event) for event in payload.get("events", [])]
        events.append(
            Event(
                timestamp=now_iso(),
                level="info",
                message=f"scaled AgentSet/{name} to {replicas} replicas",
            )
        )
        payload["events"] = [asdict(event) for event in events[-25:]]
        self._save()

        return RuntimeObject(
            resource=payload["resource"],
            phase=payload["phase"],
            applied_at=payload["applied_at"],
            observed_generation=payload.get("observed_generation", 1),
            status=payload.get("status", {}),
            events=[Event(**event) for event in payload.get("events", [])],
        )

    def list_workflow_runs(self, workflow_name: Optional[str] = None) -> List[WorkflowRun]:
        self.data = self._load()
        runs: List[WorkflowRun] = []
        for payload in self.data["workflow_runs"]:
            if workflow_name and payload["workflow"] != workflow_name:
                continue
            runs.append(
                WorkflowRun(
                    run_id=payload["run_id"],
                    workflow=payload["workflow"],
                    phase=payload["phase"],
                    started_at=payload["started_at"],
                    finished_at=payload.get("finished_at"),
                    current_step=payload.get("current_step"),
                    steps=[WorkflowStepRun(**step) for step in payload.get("steps", [])],
                    events=[Event(**event) for event in payload.get("events", [])],
                    error=payload.get("error"),
                    source_run_id=payload.get("source_run_id"),
                    start_step=payload.get("start_step"),
                )
            )
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return runs

    def latest_workflow_run(self, workflow_name: str) -> Optional[WorkflowRun]:
        runs = self.list_workflow_runs(workflow_name)
        return runs[0] if runs else None

    def get_workflow_run(self, run_id: str) -> Optional[WorkflowRun]:
        for run in self.list_workflow_runs():
            if run.run_id == run_id:
                return run
        return None

    def _execute_workflow_step(self, step: Dict[str, Any]) -> WorkflowStepRun:
        started_at = now_iso()
        name = step["name"]
        agent_ref = step["agentRef"]
        agent = self.get_resource(agent_ref)
        if not agent:
            return WorkflowStepRun(
                name=name,
                agent_ref=agent_ref,
                phase="Failed",
                started_at=started_at,
                finished_at=now_iso(),
                error=f"AgentPod not found: {agent_ref}",
            )

        summary = summarize_resource(resource_from_dict(agent.resource))
        return WorkflowStepRun(
            name=name,
            agent_ref=agent_ref,
            phase="Succeeded",
            started_at=started_at,
            finished_at=now_iso(),
            output=f"Executed {name} with {summary}",
        )

    @staticmethod
    def _step_successors(step: Dict[str, Any], steps: List[Dict[str, Any]]) -> List[str]:
        declared = step.get("onSuccess")
        if declared is not None:
            return list(declared)

        names = [candidate["name"] for candidate in steps]
        index = names.index(step["name"])
        if index + 1 < len(names):
            return [names[index + 1]]
        return []

    def _reachable_steps(
        self,
        entrypoint: str,
        steps: List[Dict[str, Any]],
        steps_by_name: Dict[str, Dict[str, Any]],
    ) -> Set[str]:
        visited: Set[str] = set()
        queue: Deque[str] = deque([entrypoint])

        while queue:
            step_name = queue.popleft()
            if step_name in visited or step_name not in steps_by_name:
                continue
            visited.add(step_name)
            for next_step in self._step_successors(steps_by_name[step_name], steps):
                if next_step not in visited:
                    queue.append(next_step)

        return visited

    def _detect_cycle(
        self,
        entrypoint: str,
        steps: List[Dict[str, Any]],
        steps_by_name: Dict[str, Dict[str, Any]],
    ) -> Optional[str]:
        visited: Set[str] = set()
        active: Set[str] = set()

        def visit(step_name: str) -> Optional[str]:
            if step_name not in steps_by_name:
                return None
            if step_name in active:
                return f"workflow graph contains a cycle at step: {step_name}"
            if step_name in visited:
                return None

            active.add(step_name)
            for next_step in self._step_successors(steps_by_name[step_name], steps):
                error = visit(next_step)
                if error:
                    return error
            active.remove(step_name)
            visited.add(step_name)
            return None

        return visit(entrypoint)

    def _next_workflow_run_id(self, workflow_name: str) -> str:
        matching = [run for run in self.data["workflow_runs"] if run["workflow"] == workflow_name]
        return f"{workflow_name}-{len(matching) + 1:04d}"

    def _persist_workflow_run(self, run: WorkflowRun) -> None:
        self.data["workflow_runs"].append(
            {
                "run_id": run.run_id,
                "workflow": run.workflow,
                "phase": run.phase,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "current_step": run.current_step,
                "steps": [asdict(step) for step in run.steps],
                "events": [asdict(event) for event in run.events],
                "error": run.error,
                "source_run_id": run.source_run_id,
                "start_step": run.start_step,
            }
        )
        self._save()

    def _record_resource_event(self, kind: str, name: str, level: str, message: str) -> None:
        key = self._resource_key(kind, name)
        payload = self.data["resources"].get(key)
        if not payload:
            return

        events = [Event(**event) for event in payload.get("events", [])]
        events.append(Event(timestamp=now_iso(), level=level, message=message))
        payload["events"] = [asdict(event) for event in events[-25:]]
        if kind == "Workflow":
            payload["phase"] = "Succeeded" if level == "info" else "Failed"
        self._save()

    def _update_workflow_status(
        self,
        workflow_name: str,
        phase: str,
        run_id: str,
        current_step: Optional[str],
        error: Optional[str],
    ) -> None:
        key = self._resource_key("Workflow", workflow_name)
        payload = self.data["resources"].get(key)
        if not payload:
            return

        status = payload.get("status", {})
        status["currentRunId"] = run_id if phase == "Running" else None
        status["currentStep"] = current_step
        status["lastRunId"] = run_id
        status["lastRunPhase"] = phase
        status["lastError"] = error
        status["lastUpdatedAt"] = now_iso()
        payload["status"] = status
        payload["phase"] = phase
        self._save()

    def _validate_agentpod(self, resource: Resource) -> List[str]:
        errors: List[str] = []

        for index, tool in enumerate(resource.spec.get("tools") or [], start=1):
            tool_ref = tool.get("ref")
            if not tool_ref:
                errors.append(f"tool entry {index} is missing ref")
                continue
            existing = self.get_resource(tool_ref)
            if not existing or existing.resource["kind"] != "ToolMount":
                errors.append(f"tool ref not found: {tool_ref}")

        for index, memory in enumerate(resource.spec.get("memory") or [], start=1):
            memory_ref = memory.get("ref")
            if not memory_ref:
                errors.append(f"memory entry {index} is missing ref")
                continue
            existing = self.get_resource(memory_ref)
            if not existing or existing.resource["kind"] != "MemoryVolume":
                errors.append(f"memory ref not found: {memory_ref}")

        return errors

    def _validate_agentset(self, resource: Resource) -> List[str]:
        errors: List[str] = []
        template = resource.spec.get("template") or {}
        template_ref = template.get("ref")
        if not template_ref:
            errors.append("agentset spec.template.ref is required")
        else:
            existing = self.get_resource(template_ref)
            if not existing or existing.resource["kind"] != "AgentPod":
                errors.append(f"agentset template ref not found: {template_ref}")

        replicas = resource.spec.get("replicas") or {}
        min_replicas = replicas.get("min")
        max_replicas = replicas.get("max")
        desired = replicas.get("desired", min_replicas)
        if min_replicas is None or max_replicas is None:
            errors.append("agentset replicas.min and replicas.max are required")
            return errors
        if min_replicas > max_replicas:
            errors.append("agentset replicas.min cannot exceed replicas.max")
        if desired is None:
            errors.append("agentset replicas.desired is required")
        elif desired < min_replicas or desired > max_replicas:
            errors.append(
                f"agentset desired replicas {desired} out of range [{min_replicas}, {max_replicas}]"
            )
        return errors

    def _validate_workflow_resource(self, resource: Resource) -> List[str]:
        errors: List[str] = []
        steps = resource.spec.get("steps") or []
        entrypoint = resource.spec.get("entrypoint")
        step_names: List[str] = []
        steps_by_name: Dict[str, Dict[str, Any]] = {}

        if not steps:
            return ["workflow spec.steps must contain at least one step"]

        for index, step in enumerate(steps, start=1):
            name = step.get("name")
            agent_ref = step.get("agentRef")
            if not name:
                errors.append(f"step {index} is missing name")
                continue
            if name in step_names:
                errors.append(f"duplicate step name: {name}")
            step_names.append(name)
            steps_by_name[name] = step
            if not agent_ref:
                errors.append(f"step {name} is missing agentRef")
                continue
            agent = self.get_resource(agent_ref)
            if not agent or agent.resource["kind"] != "AgentPod":
                errors.append(f"step {name} references missing AgentPod: {agent_ref}")

        if entrypoint and entrypoint not in step_names:
            errors.append(f"workflow entrypoint references unknown step: {entrypoint}")
        if errors:
            return errors

        for step_name, step in steps_by_name.items():
            if "onSuccess" in step and not isinstance(step.get("onSuccess"), list):
                errors.append(f"step {step_name} field onSuccess must be a list")
                continue
            for next_step in self._step_successors(step, steps):
                if next_step not in steps_by_name:
                    errors.append(f"step {step_name} references unknown successor: {next_step}")

        reachable = self._reachable_steps(
            entrypoint=entrypoint or steps[0]["name"],
            steps=steps,
            steps_by_name=steps_by_name,
        )
        for step_name in sorted(set(step_names) - reachable):
            errors.append(f"step {step_name} is unreachable from workflow entrypoint")

        cycle_error = self._detect_cycle(
            entrypoint=entrypoint or steps[0]["name"],
            steps=steps,
            steps_by_name=steps_by_name,
        )
        if cycle_error:
            errors.append(cycle_error)

        return errors

    def _initial_status_for_resource(self, resource: Resource) -> Dict[str, Any]:
        if resource.kind == "AgentPod":
            return {
                "toolRefs": [tool.get("ref") for tool in resource.spec.get("tools") or []],
                "memoryRefs": [memory.get("ref") for memory in resource.spec.get("memory") or []],
                "validatedAt": now_iso(),
            }
        if resource.kind == "Workflow":
            step_names = [step.get("name") for step in resource.spec.get("steps") or [] if step.get("name")]
            return {
                "entrypoint": resource.spec.get("entrypoint") or (step_names[0] if step_names else None),
                "stepCount": len(step_names),
                "lastRunId": None,
                "lastRunPhase": None,
                "lastError": None,
                "currentRunId": None,
                "currentStep": None,
                "validatedAt": now_iso(),
            }
        if resource.kind == "AgentSet":
            replicas = resource.spec.get("replicas") or {}
            desired = replicas.get("desired", replicas.get("min"))
            template = resource.spec.get("template") or {}
            return {
                "templateRef": template.get("ref"),
                "desiredReplicas": desired,
                "currentReplicas": desired,
                "readyReplicas": desired,
                "validatedAt": now_iso(),
                "lastScaledAt": None,
            }
        if resource.kind == "ToolMount":
            return {
                "type": resource.spec.get("type"),
                "endpoint": resource.spec.get("endpoint"),
                "validatedAt": now_iso(),
            }
        if resource.kind == "MemoryVolume":
            backend = resource.spec.get("backend") or {}
            return {
                "class": resource.spec.get("class"),
                "backendType": backend.get("type"),
                "validatedAt": now_iso(),
            }
        return {"validatedAt": now_iso()}

    @staticmethod
    def _start_message(
        workflow_name: str,
        source_run_id: Optional[str],
        start_step: Optional[str],
    ) -> str:
        if source_run_id and start_step:
            return (
                f"workflow checkpoint rerun started for {workflow_name} "
                f"from {source_run_id} at step {start_step}"
            )
        if source_run_id:
            return f"workflow rerun started for {workflow_name} from {source_run_id}"
        return f"workflow run started for {workflow_name}"


def load_resource_file(path: Path) -> Resource:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return resource_from_dict(payload)


def describe_runtime_object(runtime_object: RuntimeObject) -> str:
    resource = resource_from_dict(runtime_object.resource)
    lines = [
        summarize_resource(resource),
        f"phase={runtime_object.phase}",
        f"applied_at={runtime_object.applied_at}",
        f"observed_generation={runtime_object.observed_generation}",
    ]

    if runtime_object.status:
        lines.append("status:")
        for key in sorted(runtime_object.status):
            lines.append(f"- {key}={runtime_object.status[key]}")

    if runtime_object.events:
        lines.append("events:")
        for event in runtime_object.events[-10:]:
            lines.append(f"- {event.timestamp} [{event.level}] {event.message}")

    return "\n".join(lines)


def summarize_workflow_run(run: WorkflowRun) -> str:
    lines = [
        f"WorkflowRun/{run.run_id}",
        f"workflow={run.workflow}",
        f"phase={run.phase}",
        f"started_at={run.started_at}",
    ]
    if run.finished_at:
        lines.append(f"finished_at={run.finished_at}")
    if run.current_step:
        lines.append(f"current_step={run.current_step}")
    if run.error:
        lines.append(f"error={run.error}")
    if run.source_run_id:
        lines.append(f"source_run_id={run.source_run_id}")
    if run.start_step:
        lines.append(f"start_step={run.start_step}")
    if run.steps:
        lines.append("steps:")
        for step in run.steps:
            detail = (
                f"- {step.name} agentRef={step.agent_ref} phase={step.phase}"
                f" started_at={step.started_at}"
            )
            if step.finished_at:
                detail += f" finished_at={step.finished_at}"
            if step.error:
                detail += f" error={step.error}"
            lines.append(detail)
    return "\n".join(lines)
