import json
import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MeshctlTests(unittest.TestCase):
    def run_cli(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "agentmesh.cli", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_init_apply_and_describe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            tool_path = cwd / "toolmount.json"
            memory_path = cwd / "memoryvolume.json"
            spec_path = cwd / "agentpod.json"

            init_tool_result = self.run_cli(cwd, "init", "toolmount", "ticket-api", "-o", str(tool_path))
            self.assertEqual(init_tool_result.returncode, 0, init_tool_result.stderr)

            init_memory_result = self.run_cli(cwd, "init", "memoryvolume", "team-context", "-o", str(memory_path))
            self.assertEqual(init_memory_result.returncode, 0, init_memory_result.stderr)

            init_result = self.run_cli(cwd, "init", "agentpod", "demo-router", "-o", str(spec_path))
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertTrue(spec_path.exists())

            self.assertEqual(self.run_cli(cwd, "apply", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(memory_path)).returncode, 0)
            apply_result = self.run_cli(cwd, "apply", str(spec_path))
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertIn("applied AgentPod/demo-router", apply_result.stdout)

            get_result = self.run_cli(cwd, "get")
            self.assertEqual(get_result.returncode, 0, get_result.stderr)
            self.assertIn("demo-router", get_result.stdout)

            describe_result = self.run_cli(cwd, "describe", "demo-router")
            self.assertEqual(describe_result.returncode, 0, describe_result.stderr)
            self.assertIn("AgentPod/demo-router", describe_result.stdout)
            self.assertIn("phase=Running", describe_result.stdout)
            self.assertIn("status:", describe_result.stdout)
            self.assertIn("toolRefs=['ticket-api']", describe_result.stdout)

    def test_run_workflow_and_describe_latest_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            tool_path = cwd / "toolmount.json"
            memory_path = cwd / "memoryvolume.json"
            agent_path = cwd / "agentpod.json"
            workflow_path = cwd / "workflow.json"

            init_tool = self.run_cli(cwd, "init", "toolmount", "ticket-api", "-o", str(tool_path))
            self.assertEqual(init_tool.returncode, 0, init_tool.stderr)

            init_memory = self.run_cli(cwd, "init", "memoryvolume", "team-context", "-o", str(memory_path))
            self.assertEqual(init_memory.returncode, 0, init_memory.stderr)

            init_agent = self.run_cli(cwd, "init", "agentpod", "router", "-o", str(agent_path))
            self.assertEqual(init_agent.returncode, 0, init_agent.stderr)

            workflow_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "Workflow",
                "metadata": {"name": "ticket-flow"},
                "spec": {
                    "entrypoint": "triage",
                    "steps": [
                        {"name": "triage", "agentRef": "router"},
                        {"name": "resolve", "agentRef": "router"},
                    ],
                },
            }
            workflow_path.write_text(json.dumps(workflow_spec), encoding="utf-8")

            self.assertEqual(self.run_cli(cwd, "apply", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(agent_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(workflow_path)).returncode, 0)

            run_result = self.run_cli(cwd, "run", "workflow", "ticket-flow")
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertIn("WorkflowRun/ticket-flow-0001", run_result.stdout)
            self.assertIn("phase=Succeeded", run_result.stdout)
            self.assertIn("triage agentRef=router phase=Succeeded", run_result.stdout)

            describe_result = self.run_cli(cwd, "describe", "ticket-flow")
            self.assertEqual(describe_result.returncode, 0, describe_result.stderr)
            self.assertIn("latest_run:", describe_result.stdout)
            self.assertIn("WorkflowRun/ticket-flow-0001", describe_result.stdout)

            get_runs_result = self.run_cli(cwd, "get", "runs")
            self.assertEqual(get_runs_result.returncode, 0, get_runs_result.stderr)
            self.assertIn("ticket-flow-0001", get_runs_result.stdout)
            self.assertIn("ticket-flow", get_runs_result.stdout)

            describe_run_result = self.run_cli(cwd, "describe", "run", "ticket-flow-0001")
            self.assertEqual(describe_run_result.returncode, 0, describe_run_result.stderr)
            self.assertIn("phase=Succeeded", describe_run_result.stdout)

            logs_run_result = self.run_cli(cwd, "logs", "run", "ticket-flow-0001")
            self.assertEqual(logs_run_result.returncode, 0, logs_run_result.stderr)
            self.assertIn("workflow run started", logs_run_result.stdout)
            self.assertIn("step triage completed", logs_run_result.stdout)

            rerun_result = self.run_cli(cwd, "rerun", "workflow-run", "ticket-flow-0001")
            self.assertEqual(rerun_result.returncode, 0, rerun_result.stderr)
            self.assertIn("WorkflowRun/ticket-flow-0002", rerun_result.stdout)
            self.assertIn("source_run_id=ticket-flow-0001", rerun_result.stdout)

            checkpoint_rerun_result = self.run_cli(
                cwd,
                "rerun",
                "workflow-run",
                "ticket-flow-0001",
                "--from-step",
                "resolve",
            )
            self.assertEqual(checkpoint_rerun_result.returncode, 0, checkpoint_rerun_result.stderr)
            self.assertIn("WorkflowRun/ticket-flow-0003", checkpoint_rerun_result.stdout)
            self.assertIn("start_step=resolve", checkpoint_rerun_result.stdout)
            self.assertNotIn("- triage ", checkpoint_rerun_result.stdout)

            get_runs_after_rerun = self.run_cli(cwd, "get", "runs", "ticket-flow")
            self.assertEqual(get_runs_after_rerun.returncode, 0, get_runs_after_rerun.stderr)
            self.assertIn("ticket-flow-0001", get_runs_after_rerun.stdout)
            self.assertIn("ticket-flow-0002", get_runs_after_rerun.stdout)
            self.assertIn("ticket-flow-0003", get_runs_after_rerun.stdout)

            describe_workflow_result = self.run_cli(cwd, "describe", "ticket-flow")
            self.assertEqual(describe_workflow_result.returncode, 0, describe_workflow_result.stderr)
            self.assertIn("lastRunId=ticket-flow-0003", describe_workflow_result.stdout)
            self.assertIn("lastRunPhase=Succeeded", describe_workflow_result.stdout)

    def test_run_workflow_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            workflow_path = cwd / "workflow.json"

            workflow_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "Workflow",
                "metadata": {"name": "broken-flow"},
                "spec": {
                    "entrypoint": "triage",
                    "steps": [
                        {"name": "triage", "agentRef": "missing-router"},
                    ],
                },
            }
            workflow_path.write_text(json.dumps(workflow_spec), encoding="utf-8")

            apply_result = self.run_cli(cwd, "apply", str(workflow_path))
            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("references missing AgentPod", apply_result.stderr)

    def test_apply_agentpod_requires_toolmount_and_memoryvolume(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            agent_path = cwd / "agentpod.json"

            init_agent = self.run_cli(cwd, "init", "agentpod", "router", "-o", str(agent_path))
            self.assertEqual(init_agent.returncode, 0, init_agent.stderr)

            apply_result = self.run_cli(cwd, "apply", str(agent_path))
            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("tool ref not found: ticket-api", apply_result.stderr)
            self.assertIn("memory ref not found: team-context", apply_result.stderr)

    def test_apply_and_scale_agentset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            tool_path = cwd / "toolmount.json"
            memory_path = cwd / "memoryvolume.json"
            agent_path = cwd / "agentpod.json"
            agentset_path = cwd / "agentset.json"

            self.assertEqual(self.run_cli(cwd, "init", "toolmount", "ticket-api", "-o", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "init", "memoryvolume", "team-context", "-o", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "init", "agentpod", "router", "-o", str(agent_path)).returncode, 0)

            agentset_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "AgentSet",
                "metadata": {"name": "router-set"},
                "spec": {
                    "selector": {"matchLabels": {"app": "router"}},
                    "template": {"ref": "router"},
                    "replicas": {"min": 1, "max": 4, "desired": 2},
                    "rollout": {"strategy": "rolling", "maxUnavailable": 1},
                },
            }
            agentset_path.write_text(json.dumps(agentset_spec), encoding="utf-8")

            self.assertEqual(self.run_cli(cwd, "apply", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(agent_path)).returncode, 0)

            apply_result = self.run_cli(cwd, "apply", str(agentset_path))
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertIn("applied AgentSet/router-set", apply_result.stdout)

            describe_result = self.run_cli(cwd, "describe", "router-set")
            self.assertEqual(describe_result.returncode, 0, describe_result.stderr)
            self.assertIn("AgentSet/router-set", describe_result.stdout)
            self.assertIn("desiredReplicas=2", describe_result.stdout)
            self.assertIn("templateRef=router", describe_result.stdout)

            scale_result = self.run_cli(cwd, "scale", "agentset", "router-set", "--replicas", "3")
            self.assertEqual(scale_result.returncode, 0, scale_result.stderr)
            self.assertIn("desiredReplicas=3", scale_result.stdout)
            self.assertIn("readyReplicas=3", scale_result.stdout)

    def test_apply_agentset_requires_template_agentpod(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            agentset_path = cwd / "agentset.json"
            agentset_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "AgentSet",
                "metadata": {"name": "router-set"},
                "spec": {
                    "selector": {"matchLabels": {"app": "router"}},
                    "template": {"ref": "missing-router"},
                    "replicas": {"min": 1, "max": 4, "desired": 2},
                },
            }
            agentset_path.write_text(json.dumps(agentset_spec), encoding="utf-8")

            result = self.run_cli(cwd, "apply", str(agentset_path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("agentset template ref not found: missing-router", result.stderr)

    def test_run_workflow_with_branching_successors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            tool_path = cwd / "toolmount.json"
            memory_path = cwd / "memoryvolume.json"
            agent_path = cwd / "agentpod.json"
            workflow_path = cwd / "workflow.json"

            init_tool = self.run_cli(cwd, "init", "toolmount", "ticket-api", "-o", str(tool_path))
            self.assertEqual(init_tool.returncode, 0, init_tool.stderr)

            init_memory = self.run_cli(cwd, "init", "memoryvolume", "team-context", "-o", str(memory_path))
            self.assertEqual(init_memory.returncode, 0, init_memory.stderr)

            init_agent = self.run_cli(cwd, "init", "agentpod", "router", "-o", str(agent_path))
            self.assertEqual(init_agent.returncode, 0, init_agent.stderr)

            workflow_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "Workflow",
                "metadata": {"name": "branched-flow"},
                "spec": {
                    "entrypoint": "triage",
                    "steps": [
                        {"name": "triage", "agentRef": "router", "onSuccess": ["draft", "notify"]},
                        {"name": "draft", "agentRef": "router", "onSuccess": ["approve"]},
                        {"name": "notify", "agentRef": "router"},
                        {"name": "approve", "agentRef": "router"},
                    ],
                },
            }
            workflow_path.write_text(json.dumps(workflow_spec), encoding="utf-8")

            self.assertEqual(self.run_cli(cwd, "apply", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(agent_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(workflow_path)).returncode, 0)

            run_result = self.run_cli(cwd, "run", "workflow", "branched-flow")
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertIn("WorkflowRun/branched-flow-0001", run_result.stdout)
            self.assertIn("triage agentRef=router phase=Succeeded", run_result.stdout)
            self.assertIn("draft agentRef=router phase=Succeeded", run_result.stdout)
            self.assertIn("notify agentRef=router phase=Succeeded", run_result.stdout)
            self.assertIn("approve agentRef=router phase=Succeeded", run_result.stdout)

    def test_run_workflow_cycle_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            tool_path = cwd / "toolmount.json"
            memory_path = cwd / "memoryvolume.json"
            agent_path = cwd / "agentpod.json"
            workflow_path = cwd / "workflow.json"

            init_tool = self.run_cli(cwd, "init", "toolmount", "ticket-api", "-o", str(tool_path))
            self.assertEqual(init_tool.returncode, 0, init_tool.stderr)

            init_memory = self.run_cli(cwd, "init", "memoryvolume", "team-context", "-o", str(memory_path))
            self.assertEqual(init_memory.returncode, 0, init_memory.stderr)

            init_agent = self.run_cli(cwd, "init", "agentpod", "router", "-o", str(agent_path))
            self.assertEqual(init_agent.returncode, 0, init_agent.stderr)

            workflow_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "Workflow",
                "metadata": {"name": "cycle-flow"},
                "spec": {
                    "entrypoint": "triage",
                    "steps": [
                        {"name": "triage", "agentRef": "router", "onSuccess": ["resolve"]},
                        {"name": "resolve", "agentRef": "router", "onSuccess": ["triage"]},
                    ],
                },
            }
            workflow_path.write_text(json.dumps(workflow_spec), encoding="utf-8")

            self.assertEqual(self.run_cli(cwd, "apply", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(agent_path)).returncode, 0)
            apply_result = self.run_cli(cwd, "apply", str(workflow_path))
            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("contains a cycle", apply_result.stderr)

    def test_logs_missing_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            result = self.run_cli(cwd, "logs", "missing")
            self.assertEqual(result.returncode, 1)
            self.assertIn("resource not found", result.stderr)

    def test_describe_missing_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            result = self.run_cli(cwd, "describe", "run", "missing-run")
            self.assertEqual(result.returncode, 1)
            self.assertIn("workflow run not found", result.stderr)

    def test_rerun_missing_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            result = self.run_cli(cwd, "rerun", "workflow-run", "missing-run")
            self.assertEqual(result.returncode, 1)
            self.assertIn("workflow run not found", result.stderr)

    def test_checkpoint_rerun_missing_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            tool_path = cwd / "toolmount.json"
            memory_path = cwd / "memoryvolume.json"
            agent_path = cwd / "agentpod.json"
            workflow_path = cwd / "workflow.json"

            self.assertEqual(self.run_cli(cwd, "init", "toolmount", "ticket-api", "-o", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "init", "memoryvolume", "team-context", "-o", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "init", "agentpod", "router", "-o", str(agent_path)).returncode, 0)

            workflow_spec = {
                "apiVersion": "agentmesh.dev/v1alpha1",
                "kind": "Workflow",
                "metadata": {"name": "ticket-flow"},
                "spec": {
                    "entrypoint": "triage",
                    "steps": [
                        {"name": "triage", "agentRef": "router"},
                        {"name": "resolve", "agentRef": "router"},
                    ],
                },
            }
            workflow_path.write_text(json.dumps(workflow_spec), encoding="utf-8")

            self.assertEqual(self.run_cli(cwd, "apply", str(tool_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(memory_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(agent_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "apply", str(workflow_path)).returncode, 0)
            self.assertEqual(self.run_cli(cwd, "run", "workflow", "ticket-flow").returncode, 0)

            result = self.run_cli(cwd, "rerun", "workflow-run", "ticket-flow-0001", "--from-step", "missing")
            self.assertEqual(result.returncode, 1)
            self.assertIn("workflow step not found: missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
