from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Metadata:
    name: str
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Resource:
    api_version: str
    kind: str
    metadata: Metadata
    spec: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["apiVersion"] = payload.pop("api_version")
        return payload


def resource_from_dict(payload: Dict[str, Any]) -> Resource:
    metadata = payload.get("metadata") or {}
    name = metadata.get("name")
    if not name:
        raise ValueError("resource metadata.name is required")

    api_version = payload.get("apiVersion")
    kind = payload.get("kind")
    if not api_version or not kind:
        raise ValueError("resource apiVersion and kind are required")

    return Resource(
        api_version=api_version,
        kind=kind,
        metadata=Metadata(name=name, labels=metadata.get("labels") or {}),
        spec=payload.get("spec") or {},
    )


def scaffold_resource(kind: str, name: str) -> Resource:
    normalized_kind = kind.lower()
    if normalized_kind == "agentpod":
        spec: Dict[str, Any] = {
            "runtime": {
                "framework": "python",
                "entrypoint": "./agents/example.py",
            },
            "model": {
                "provider": "openai",
                "name": "gpt-5.4",
                "temperature": 0.2,
            },
            "prompt": {
                "inline": "You are a reliable operations agent."
            },
            "tools": [{"ref": "ticket-api"}],
            "memory": [{"ref": "team-context"}],
            "resources": {
                "maxConcurrency": 4,
                "tokenBudgetPerMinute": 60000,
            },
        }
    elif normalized_kind == "workflow":
        spec = {
            "entrypoint": "triage",
            "steps": [
                {"name": "triage", "agentRef": "router"},
                {"name": "resolve", "agentRef": "responder"},
            ],
        }
    else:
        raise ValueError(f"unsupported scaffold kind: {kind}")

    return Resource(
        api_version="agentmesh.dev/v1alpha1",
        kind=normalized_kind.capitalize() if normalized_kind != "agentpod" else "AgentPod",
        metadata=Metadata(name=name),
        spec=spec,
    )


def summarize_resource(resource: Resource) -> str:
    parts: List[str] = [f"{resource.kind}/{resource.metadata.name}"]

    if resource.kind == "AgentPod":
        runtime = resource.spec.get("runtime", {})
        model = resource.spec.get("model", {})
        tools = resource.spec.get("tools") or []
        parts.append(
            "runtime="
            + f"{runtime.get('framework', 'unknown')}:{runtime.get('entrypoint', 'n/a')}"
        )
        parts.append(
            "model="
            + f"{model.get('provider', 'unknown')}/{model.get('name', 'unknown')}"
        )
        parts.append(f"tools={len(tools)}")
    elif resource.kind == "Workflow":
        steps = resource.spec.get("steps") or []
        parts.append(f"steps={len(steps)}")

    return "  ".join(parts)
