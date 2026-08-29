"""Bounded resident-host ownership, lifecycle, and non-authority tests."""

import json
import tempfile
import threading
import time
import unittest
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path
from unittest.mock import patch

from graci.__main__ import main as cli_main
from graci.operator_cli import OperatorComposition
from graci.resident_host import (OWNER, ResidentAlreadyRunning, ResidentHost,
                                 ResidentOwnership, read_valid_record,
                                 resident_is_active)
from graci.visualizer import SystemState
from graci.visualizer_backend import VisualizerServer, VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver


class Coordinator:
    def __init__(self):
        self.typed_calls = 0
        self.speech_calls = 0

    def run_typed(self, *_args, **_kwargs):
        self.typed_calls += 1
        raise AssertionError("resident startup must not submit a governed run")

    def run_speech(self, *_args, **_kwargs):
        self.speech_calls += 1
        raise AssertionError("resident startup must not activate microphone input")


class FailingServer:
    def start(self): raise OSError("port unavailable")
    def stop(self): raise AssertionError("unstarted server must not be stopped")


class ResidentHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name) / "resident"

    def tearDown(self):
        self.temp.cleanup()

    def test_first_acquisition_and_second_instance_rejection(self):
        first = ResidentOwnership(self.runtime, "a" * 32)
        second = ResidentOwnership(self.runtime, "b" * 32)
        first.acquire()
        try:
            with self.assertRaises(ResidentAlreadyRunning):
                second.acquire()
            self.assertTrue(resident_is_active(self.runtime))
        finally:
            first.release()
        self.assertFalse(resident_is_active(self.runtime))

    def test_stale_state_is_recovered_only_after_lock_acquisition(self):
        self.runtime.mkdir(parents=True)
        stale = {
            "schema_version": 1, "owner": OWNER, "instance_id": "s" * 32,
            "pid": 999999, "executable": "stale-python", "module": "graci.resident_host",
            "repository_root": str(self.runtime.parent), "started_at": "stale",
            "visualizer": {"host": "127.0.0.1", "port": 8766},
        }
        (self.runtime / "state.json").write_text(json.dumps(stale), encoding="utf-8")
        owner = ResidentOwnership(self.runtime, "n" * 32)
        owner.acquire(); owner.publish(port=1234)
        try:
            current = read_valid_record(owner.state_path)
            self.assertEqual((current["instance_id"], current["visualizer"]["port"]),
                             ("n" * 32, 1234))
        finally:
            owner.release()
        self.assertFalse(owner.state_path.exists())

    def test_clean_shutdown_owns_observer_server_and_stays_idle(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        server = VisualizerServer(provider, port=0, heartbeat_seconds=0.05)
        coordinator = Coordinator()
        composition = OperatorComposition(coordinator, provider, observer, None, server)
        owner = ResidentOwnership(self.runtime, "c" * 32)
        host = ResidentHost(owner, lambda **kwargs: composition, poll_seconds=0.01)
        outcome = []
        thread = threading.Thread(target=lambda: outcome.append(host.run()))
        thread.start()
        deadline = time.time() + 3
        while not owner.state_path.exists() and time.time() < deadline:
            time.sleep(0.01)
        state = read_valid_record(owner.state_path)
        snapshot = provider.snapshot()
        self.assertEqual(snapshot.system_state, SystemState.IDLE)
        self.assertEqual((coordinator.typed_calls, coordinator.speech_calls), (0, 0))
        owner.stop_path.write_text(json.dumps({
            "schema_version": 1, "owner": OWNER, "instance_id": state["instance_id"]
        }), encoding="utf-8")
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [0])
        self.assertFalse(owner.state_path.exists())
        self.assertFalse(resident_is_active(self.runtime))

    def test_start_failure_is_isolated_and_releases_ownership(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        composition = OperatorComposition(Coordinator(), provider, observer, None, FailingServer())
        owner = ResidentOwnership(self.runtime, "d" * 32)
        with self.assertRaisesRegex(OSError, "port unavailable"):
            ResidentHost(owner, lambda **kwargs: composition).run()
        self.assertFalse(resident_is_active(self.runtime))
        self.assertFalse(owner.state_path.exists())

    def test_explicit_local_restart_recovers_failed_projection_and_is_bounded(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        observer.state, observer.terminal = SystemState.FAILED, "FAIL"
        resets = []

        def restart():
            resets.append("restart")
            observer.reset_transient()

        server = VisualizerServer(provider, port=0, restart_runtime=restart)
        observer.publish_current("failed")
        server.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.bound_port}/graci/visualizer/v1/restart",
                data=b"{}", method="POST",
                headers={"Content-Type": "application/json", "Origin":
                         f"http://127.0.0.1:{server.bound_port}"})
            with urlopen(request, timeout=2) as response:
                self.assertEqual(json.load(response)["status"], "ready")
            self.assertEqual(resets, ["restart"])
            self.assertIs(provider.snapshot().system_state, SystemState.IDLE)
        finally:
            server.stop()

    def test_restart_failure_remains_failed_and_is_visible(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        observer.state, observer.terminal = SystemState.FAILED, "FAIL"
        observer.publish_current("failed")
        server = VisualizerServer(
            provider, port=0,
            restart_runtime=lambda: (_ for _ in ()).throw(RuntimeError("cleanup failed")))
        server.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.bound_port}/graci/visualizer/v1/restart",
                data=b"{}", method="POST",
                headers={"Content-Type": "application/json", "Origin":
                         f"http://127.0.0.1:{server.bound_port}"})
            with self.assertRaises(HTTPError) as raised:
                urlopen(request, timeout=2)
            self.assertEqual(raised.exception.code, 500)
            raised.exception.close()
            self.assertIs(provider.snapshot().system_state, SystemState.FAILED)
        finally:
            server.stop()

    def test_one_shot_cli_fails_closed_while_resident_is_active(self):
        with patch("graci.__main__.resident_is_active", return_value=True), \
             patch("graci.__main__.build_operator_coordinator") as factory:
            with self.assertRaises(SystemExit) as raised:
                cli_main(["task"])
        self.assertEqual(raised.exception.code, 2)
        factory.assert_not_called()

    def test_records_reject_wrong_owner_and_process_identity(self):
        self.runtime.mkdir(parents=True)
        path = self.runtime / "state.json"
        for value in (
            {"schema_version": 1, "owner": "OTHER", "instance_id": "x" * 32},
            {"schema_version": 1, "owner": OWNER, "instance_id": "x" * 32,
             "pid": 1, "module": "other", "visualizer": {"host": "127.0.0.1", "port": 1}},
        ):
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError): read_valid_record(path)

    def test_stop_request_accepts_bom_free_and_bom_prefixed_utf8(self):
        owner = ResidentOwnership(self.runtime, "e" * 32)
        owner.runtime_directory.mkdir(parents=True)
        request = json.dumps({
            "schema_version": 1, "owner": OWNER, "instance_id": owner.instance_id
        })
        for encoding in ("utf-8", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                owner.stop_path.write_text(request, encoding=encoding)
                self.assertTrue(owner.stop_requested())

    def test_stop_request_mismatched_instance_remains_rejected_with_bom(self):
        owner = ResidentOwnership(self.runtime, "f" * 32)
        owner.runtime_directory.mkdir(parents=True)
        owner.stop_path.write_text(json.dumps({
            "schema_version": 1, "owner": OWNER, "instance_id": "x" * 32
        }), encoding="utf-8-sig")
        self.assertFalse(owner.stop_requested())

    @unittest.skipUnless(sys.platform == "win32", "PowerShell resolution is Windows-only")
    def test_powershell_python_resolution_override_invalid_and_ambiguous(self):
        root = Path(__file__).resolve().parents[1]
        common = root / "ops" / "resident-host-common.ps1"
        escaped_common = str(common).replace("'", "''")
        escaped_python = str(Path(sys.executable).resolve()).replace("'", "''")
        cases = (
            (f". '{escaped_common}'; Resolve-GraciPythonPath -Python '{escaped_python}'",
             0, str(Path(sys.executable).resolve())),
            (f". '{escaped_common}'; Resolve-GraciPythonPath -Python '{escaped_python}.missing'",
             1, "does not exist"),
            (f". '{escaped_common}'; Resolve-GraciPythonPath -Python @('{escaped_python}','{escaped_python}')",
             1, "one concrete absolute executable path"),
        )
        for command, expected_code, marker in cases:
            with self.subTest(marker=marker):
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive",
                     "-ExecutionPolicy", "Bypass", "-Command", command],
                    text=True, capture_output=True, timeout=10, check=False)
                self.assertEqual(result.returncode, expected_code, result.stderr)
                self.assertIn(marker, result.stdout + result.stderr)

    def test_windows_scripts_are_explicit_bounded_and_never_force_stop(self):
        root = Path(__file__).resolve().parents[1]
        start = (root / "ops" / "start-graci-resident.ps1").read_text(encoding="utf-8")
        stop = (root / "ops" / "stop-graci-resident.ps1").read_text(encoding="utf-8")
        install = (root / "ops" / "install-graci-resident-task.ps1").read_text(encoding="utf-8")
        remove = (root / "ops" / "remove-graci-resident-task.ps1").read_text(encoding="utf-8")
        self.assertIn("-m', $script:ResidentModule, '--instance-id'", start)
        self.assertNotIn("Stop-Process", start + stop)
        self.assertNotIn("Get-Command $Python", start)
        self.assertIn("$PSBoundParameters.ContainsKey('Python')", start)
        self.assertIn("$PSBoundParameters.ContainsKey('Python')", install)
        self.assertIn("UTF8Encoding($false)", stop)
        self.assertIn("stop-request.json", (root / "ops" / "resident-host-common.ps1").read_text(encoding="utf-8"))
        self.assertIn("-ExecutionPolicy Bypass", install)
        self.assertIn("-MultipleInstances IgnoreNew", install)
        self.assertIn("Register-ScheduledTask", install)
        self.assertIn("Unregister-ScheduledTask", remove)


if __name__ == "__main__":
    unittest.main()
