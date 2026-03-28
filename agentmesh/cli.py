from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .runtime import LocalControlPlane, describe_runtime_object, load_resource_file
from .schema import scaffold_resource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meshctl",
        description="AgentMesh local control plane CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the AgentMesh CLI version")

    init_parser = subparsers.add_parser("init", help="Create a starter resource spec")
    init_parser.add_argument("kind", choices=["agentpod", "workflow"])
    init_parser.add_argument("name")
    init_parser.add_argument(
        "-o",
        "--output",
        help="Write the scaffold to a file instead of stdout",
    )

    apply_parser = subparsers.add_parser("apply", help="Apply a JSON resource file")
    apply_parser.add_argument("file")

    subparsers.add_parser("get", help="List applied resources")

    describe_parser = subparsers.add_parser("describe", help="Describe one applied resource")
    describe_parser.add_argument("name")

    logs_parser = subparsers.add_parser("logs", help="Show recent events for one resource")
    logs_parser.add_argument("name")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    control_plane = LocalControlPlane(Path.cwd())

    if args.command == "version":
        print(f"meshctl {__version__}")
        return 0

    if args.command == "init":
        resource = scaffold_resource(args.kind, args.name)
        content = json.dumps(resource.to_dict(), indent=2)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content + "\n", encoding="utf-8")
            print(f"wrote {output_path}")
        else:
            print(content)
        return 0

    if args.command == "apply":
        runtime_object = control_plane.apply(load_resource_file(Path(args.file)))
        resource = runtime_object.resource
        print(
            f"applied {resource['kind']}/{resource['metadata']['name']} "
            f"generation={runtime_object.observed_generation} phase={runtime_object.phase}"
        )
        return 0

    if args.command == "get":
        resources = control_plane.list_resources()
        if not resources:
            print("no resources applied")
            return 0
        print(control_plane.format_table())
        return 0

    if args.command == "describe":
        runtime_object = control_plane.get_resource(args.name)
        if not runtime_object:
            print(f"resource not found: {args.name}", file=sys.stderr)
            return 1
        print(describe_runtime_object(runtime_object))
        return 0

    if args.command == "logs":
        runtime_object = control_plane.get_resource(args.name)
        if not runtime_object:
            print(f"resource not found: {args.name}", file=sys.stderr)
            return 1
        if not runtime_object.events:
            print("no events")
            return 0
        for event in runtime_object.events[-20:]:
            print(f"{event.timestamp} [{event.level}] {event.message}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
