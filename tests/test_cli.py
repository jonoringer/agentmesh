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
            spec_path = cwd / "agentpod.json"

            init_result = self.run_cli(cwd, "init", "agentpod", "demo-router", "-o", str(spec_path))
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertTrue(spec_path.exists())

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

    def test_logs_missing_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            result = self.run_cli(cwd, "logs", "missing")
            self.assertEqual(result.returncode, 1)
            self.assertIn("resource not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
