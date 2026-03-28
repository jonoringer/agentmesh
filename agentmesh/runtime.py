from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        # Reload on each mutation so separate CLI processes do not clobber
        # one another's local state when commands run close together.
        self.data = self._load()
        key = self._resource_key(resource.kind, resource.metadata.name)
        existing = self.data["resources"].get(key)

        if existing:
            generation = int(existing.get("observed_generation", 1)) + 1
            events = [
                Event(**event) for event in existing.get("events", [])
            ]
            events.append(Event(timestamp=now_iso(), level="info", message="resource updated"))
            runtime_object = RuntimeObject(
                resource=resource.to_dict(),
                phase="Running",
                applied_at=now_iso(),
                observed_generation=generation,
                events=events[-25:],
            )
        else:
            runtime_object = RuntimeObject(
                resource=resource.to_dict(),
                phase="Running",
                applied_at=now_iso(),
                observed_generation=1,
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
                    events=[Event(**event) for event in payload.get("events", [])],
                )
            )
        items.sort(key=lambda item: (item.resource["kind"], item.resource["metadata"]["name"]))
        return items

    def get_resource(self, name: str) -> Optional[RuntimeObject]:
        self.data = self._load()
        for payload in self.data["resources"].values():
            resource_name = payload["resource"]["metadata"]["name"]
            if resource_name == name:
                return RuntimeObject(
                    resource=payload["resource"],
                    phase=payload["phase"],
                    applied_at=payload["applied_at"],
                    observed_generation=payload.get("observed_generation", 1),
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

    def validate_workflow(self, workflow_name: str) -> List[str]:
        workflow_object = self.get_resource(workflow_name)
        if not workflow_object:
            return [f"workflow not found: {workflow_name}"]
        if workflow_object.resource["kind"] != "Workflow":
            return [f"resource is not a Workflow: {workflow_name}"]

        steps = workflow_object.resource.get("spec", {}).get("steps") or []
        entrypoint = workflow_object.resource.get("spec", {}).get("entrypoint")
        errors: List[str] = []
        step_names: List[str] = []

        if not steps:
            errors.append("workflow spec.steps must contain at least one step")
            return errors

        for index, step in enumerate(steps, start=1):
            name = step.get("name")
            agent_ref = step.get("agentRef")
            if not name:
                errors.append(f"step {index} is missing name")
                continue
            if name in step_names:
                errors.append(f"duplicate step name: {name}")
            step_names.append(name)
            if not agent_ref:
                errors.append(f"step {name} is missing agentRef")
                continue
            agent = self.get_resource(agent_ref)
            if not agent or agent.resource["kind"] != "AgentPod":
                errors.append(f"step {name} references missing AgentPod: {agent_ref}")

        if entrypoint and entrypoint not in step_names:
            errors.append(f"workflow entrypoint references unknown step: {entrypoint}")

        return errors

    def run_workflow(self, workflow_name: str, source_run_id: Optional[str] = None) -> WorkflowRun:
        self.data = self._load()
        workflow_object = self.get_resource(workflow_name)
        if not workflow_object:
            raise ValueError(f"workflow not found: {workflow_name}")
        if workflow_object.resource["kind"] != "Workflow":
            raise ValueError(f"resource is not a Workflow: {workflow_name}")

        errors = self.validate_workflow(workflow_name)
        if errors:
            run = WorkflowRun(
                run_id=self._next_workflow_run_id(workflow_name),
                workflow=workflow_name,
                phase="Failed",
                started_at=now_iso(),
                finished_at=now_iso(),
                events=[
                    Event(timestamp=now_iso(), level="error", message=message)
                    for message in errors
                ],
                error="; ".join(errors),
                source_run_id=source_run_id,
            )
            self._persist_workflow_run(run)
            raise ValueError(run.error)

        workflow = resource_from_dict(workflow_object.resource)
        steps = workflow.spec.get("steps") or []
        run = WorkflowRun(
            run_id=self._next_workflow_run_id(workflow_name),
            workflow=workflow_name,
            phase="Running",
            started_at=now_iso(),
            current_step=workflow.spec.get("entrypoint") or steps[0]["name"],
            events=[
                Event(
                    timestamp=now_iso(),
                    level="info",
                    message=(
                        f"workflow run started for {workflow_name}"
                        if not source_run_id
                        else f"workflow rerun started for {workflow_name} from {source_run_id}"
                    ),
                )
            ],
            source_run_id=source_run_id,
        )

        for step in steps:
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

        if run.phase != "Failed":
            run.phase = "Succeeded"
            run.finished_at = now_iso()
            run.current_step = run.steps[-1].name if run.steps else None
            run.events.append(
                Event(
                    timestamp=run.finished_at,
                    level="info",
                    message=f"workflow run completed for {workflow_name}",
                )
            )

        self._persist_workflow_run(run)
        self._record_resource_event(
            kind="Workflow",
            name=workflow_name,
            level="info" if run.phase == "Succeeded" else "error",
            message=f"run {run.run_id} {run.phase.lower()}",
        )
        return run

    def rerun_workflow(self, run_id: str) -> WorkflowRun:
        run = self.get_workflow_run(run_id)
        if not run:
            raise ValueError(f"workflow run not found: {run_id}")
        return self.run_workflow(run.workflow, source_run_id=run_id)

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
                )
            )
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return runs

    def latest_workflow_run(self, workflow_name: str) -> Optional[WorkflowRun]:
        runs = self.list_workflow_runs(workflow_name)
        return runs[0] if runs else None

    def get_workflow_run(self, run_id: str) -> Optional[WorkflowRun]:
        runs = self.list_workflow_runs()
        for run in runs:
            if run.run_id == run_id:
                return run
        return None

    def _execute_workflow_step(self, step: Dict[str, Any]) -> WorkflowStepRun:
        started_at = now_iso()
        name = step["name"]
        agent_ref = step["agentRef"]
        agent = self.get_resource(agent_ref)
        if not agent:
            finished_at = now_iso()
            return WorkflowStepRun(
                name=name,
                agent_ref=agent_ref,
                phase="Failed",
                started_at=started_at,
                finished_at=finished_at,
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
