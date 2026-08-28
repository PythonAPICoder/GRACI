"""Run a disposable Phase 5D controller path against local 3090 Qwen."""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config
from graci.registry import QWEN_MODEL_ID
from graci.visualizer_backend import VisualizerStateProvider
from graci.visualizer_backend import VisualizerServer
from graci.visualizer_runtime import VisualizerRuntimeObserver


class Recorder(VisualizerStateProvider):
    def __init__(self):
        super().__init__(); self.states = []
    def publish_snapshot(self, snapshot):
        self.states.append(snapshot.system_state.value)
        super().publish_snapshot(snapshot)


def main():
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary); workspace = root / "fixture"; runs = root / "runs"
        (workspace / "tests").mkdir(parents=True)
        (workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (workspace / "tests" / "test_app.py").write_text(
            "import unittest\nfrom app import VALUE\nclass T(unittest.TestCase):\n"
            " def test_value(self): self.assertEqual(VALUE, 1)\n", encoding="utf-8")
        provider = Recorder(); observer = VisualizerRuntimeObserver(provider)
        server = VisualizerServer(provider, port=0) if "--serve" in sys.argv else None
        if server is not None:
            server.start()
            print(json.dumps({"visualizer_url": f"http://127.0.0.1:{server.bound_port}/"}), flush=True)
        controller = AutonomousRepairController(
            workspace, readable_files=("app.py", "tests/test_app.py"),
            editable_files=("app.py",), config=Config(run_directory=runs),
            limits=LoopLimits(max_iterations=5, max_model_calls=5), observer=observer)
        record = controller.run(
            "Inspect the allowlisted fixture if needed, then run the deterministic tests. "
            "Do not modify files because the fixture is already correct.")
        snapshot = provider.snapshot()
        result = {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": record["status"], "terminal_reason": record["terminal_reason"],
            "model": snapshot.agents.qwen.model_id, "node": snapshot.agents.qwen.assigned_node,
            "states": provider.states, "event_count": len(provider.events()),
            "test_status": snapshot.execution.tests.status.value,
            "memory_status": snapshot.memory.selection_status,
        }
        print(json.dumps(result, indent=2))
        required = {"planning", "retrieving_memory", "reasoning", "testing", "completed"}
        if (record["status"] != "PASS" or snapshot.agents.qwen.model_id != QWEN_MODEL_ID
                or not required.issubset(provider.states)):
            raise SystemExit(1)
        if server is not None:
            try:
                input("Press Enter to stop the visualizer.\n")
            finally:
                server.stop()


if __name__ == "__main__": main()
