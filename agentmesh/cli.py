from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .runtime import (
    LocalControlPlane,
    describe_runtime_object,
    load_resource_file,
    summarize_workflow_run,
)
from .schema import scaffold_resource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meshctl",
        description="AgentMesh local control plane CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the AgentMesh CLI version")

    init_parser = subparsers.add_parser("init", help="Create a starter resource spec")
    init_parser.add_argument(
        "kind",
        choices=["agentpod", "agentset", "workflow", "toolmount", "memoryvolume"],
    )
    init_parser.add_argument("name")
    init_parser.add_argument(
        "-o",
        "--output",
        help="Write the scaffold to a file instead of stdout",
    )

    apply_parser = subparsers.add_parser("apply", help="Apply a JSON resource file")
    apply_parser.add_argument("file")

    get_parser = subparsers.add_parser("get", help="List applied resources")
    get_parser.add_argument("kind", nargs="?", choices=["runs"])
    get_parser.add_argument("name", nargs="?")

    run_parser = subparsers.add_parser("run", help="Execute an applied resource")
    run_subparsers = run_parser.add_subparsers(dest="run_kind", required=True)
    run_workflow_parser = run_subparsers.add_parser("workflow", help="Run an applied workflow")
    run_workflow_parser.add_argument("name")

    rerun_parser = subparsers.add_parser("rerun", help="Execute a new run from an existing workflow run")
    rerun_subparsers = rerun_parser.add_subparsers(dest="rerun_kind", required=True)
    rerun_workflow_parser = rerun_subparsers.add_parser(
        "workflow-run",
        help="Rerun a workflow from a prior workflow run id",
    )
    rerun_workflow_parser.add_argument("run_id")
    rerun_workflow_parser.add_argument("--from-step", dest="from_step")

    scale_parser = subparsers.add_parser("scale", help="Scale a local resource")
    scale_subparsers = scale_parser.add_subparsers(dest="scale_kind", required=True)
    scale_agentset_parser = scale_subparsers.add_parser("agentset", help="Scale an applied AgentSet")
    scale_agentset_parser.add_argument("name")
    scale_agentset_parser.add_argument("--replicas", type=int, required=True)

    describe_parser = subparsers.add_parser("describe", help="Describe a resource or workflow run")
    describe_parser.add_argument("kind_or_name")
    describe_parser.add_argument("name", nargs="?")

    logs_parser = subparsers.add_parser("logs", help="Show recent events for a resource or workflow run")
    logs_parser.add_argument("kind_or_name")
    logs_parser.add_argument("name", nargs="?")

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
        try:
            runtime_object = control_plane.apply(load_resource_file(Path(args.file)))
        except ValueError as exc:
            print(f"apply failed: {exc}", file=sys.stderr)
            return 1
        resource = runtime_object.resource
        print(
            f"applied {resource['kind']}/{resource['metadata']['name']} "
            f"generation={runtime_object.observed_generation} phase={runtime_object.phase}"
        )
        return 0

    if args.command == "get":
        if args.kind == "runs":
            output = control_plane.format_workflow_runs_table(args.name)
            print(output)
            return 0
        resources = control_plane.list_resources()
        if not resources:
            print("no resources applied")
            return 0
        print(control_plane.format_table())
        return 0

    if args.command == "run":
        if args.run_kind == "workflow":
            try:
                run = control_plane.run_workflow(args.name)
            except ValueError as exc:
                print(f"workflow run failed: {exc}", file=sys.stderr)
                return 1
            print(summarize_workflow_run(run))
            return 0

    if args.command == "rerun":
        if args.rerun_kind == "workflow-run":
            try:
                run = control_plane.rerun_workflow(args.run_id, start_step=args.from_step)
            except ValueError as exc:
                print(f"workflow rerun failed: {exc}", file=sys.stderr)
                return 1
            print(summarize_workflow_run(run))
            return 0

    if args.command == "scale":
        if args.scale_kind == "agentset":
            try:
                runtime_object = control_plane.scale_agentset(args.name, args.replicas)
            except ValueError as exc:
                print(f"scale failed: {exc}", file=sys.stderr)
                return 1
            print(describe_runtime_object(runtime_object))
            return 0

    if args.command == "describe":
        if args.kind_or_name == "run":
            if not args.name:
                print("run id is required", file=sys.stderr)
                return 1
            run = control_plane.get_workflow_run(args.name)
            if not run:
                print(f"workflow run not found: {args.name}", file=sys.stderr)
                return 1
            print(summarize_workflow_run(run))
            return 0

        runtime_object = control_plane.get_resource(args.kind_or_name)
        if not runtime_object:
            print(f"resource not found: {args.kind_or_name}", file=sys.stderr)
            return 1
        description = describe_runtime_object(runtime_object)
        if runtime_object.resource["kind"] == "Workflow":
            latest_run = control_plane.latest_workflow_run(args.kind_or_name)
            if latest_run:
                description += "\nlatest_run:\n" + summarize_workflow_run(latest_run)
        print(description)
        return 0

    if args.command == "logs":
        if args.kind_or_name == "run":
            if not args.name:
                print("run id is required", file=sys.stderr)
                return 1
            run = control_plane.get_workflow_run(args.name)
            if not run:
                print(f"workflow run not found: {args.name}", file=sys.stderr)
                return 1
            if not run.events:
                print("no events")
                return 0
            for event in run.events[-20:]:
                print(f"{event.timestamp} [{event.level}] {event.message}")
            return 0

        runtime_object = control_plane.get_resource(args.kind_or_name)
        if not runtime_object:
            print(f"resource not found: {args.kind_or_name}", file=sys.stderr)
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
