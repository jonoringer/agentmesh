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


class LocalControlPlane:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_dir = self.root / ".agentmesh"
        self.state_file = self.state_dir / "state.json"
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {"resources": {}}

        with self.state_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

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

    @staticmethod
    def _resource_key(kind: str, name: str) -> str:
        return f"{kind}/{name}"


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
