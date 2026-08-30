"""Acceptance tests for the bounded optional-node telemetry boundary."""

import json
import socket
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from graci.remote_telemetry import (REMOTE_TELEMETRY_TIMEOUT_SECONDS,
                                    REMOTE_TELEMETRY_URL,
                                    Remote4090TelemetryClient)
from graci.visualizer import TelemetryState
from telemetry_agent.agent import (ALLOWED_CLIENTS, BIND_ADDRESS, EXPECTED_GPU_FRAGMENT,
                                    MAX_RESPONSE_BYTES, NODE_ID, PORT, SCHEMA_VERSION,
                                    SAMPLE_INTERVAL_SECONDS, HardwareSampler,
                                    TelemetryCache, TelemetryHttpServer)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)


def payload(*, observed_at=NOW, node_id="4090", gpu_name="NVIDIA GeForce RTX 4090",
            schema_version=1):
    return {
        "schema_version": schema_version, "node_id": node_id, "hostname": "gaming-pc",
        "observed_at_utc": observed_at.isoformat().replace("+00:00", "Z"),
        "agent": {"version": "1.0.0", "sample_interval_seconds": 3.0,
                  "process_priority": "below_normal"},
        "gpu": {"status": "observed", "reason": None, "name": gpu_name,
                "utilization_percent": 5, "vram_used_bytes": 1_395_864_371,
                "vram_total_bytes": 25_769_803_776, "temperature_c": 39},
        "cpu": {"status": "observed", "reason": None,
                "utilization_percent": 4.2, "temperature_c": None},
        "ram": {"status": "observed", "reason": None,
                "used_bytes": 19_220_234_240, "total_bytes": 68_719_476_736},
    }


class FakeGpu:
    def __init__(self): self.closed = False
    def sample(self): return payload()["gpu"]
    def close(self): self.closed = True


class FakeSystem:
    def sample(self): return payload()["cpu"], payload()["ram"]


class AgentSamplingTests(unittest.TestCase):
    def test_sampler_uses_fixed_schema_and_explicit_cpu_temperature_absence(self):
        gpu = FakeGpu()
        value = HardwareSampler(gpu=gpu, system=FakeSystem(), clock=lambda: NOW).sample("below_normal")
        self.assertEqual(set(value), {"schema_version", "node_id", "hostname",
                                     "observed_at_utc", "agent", "gpu", "cpu", "ram"})
        self.assertEqual((value["schema_version"], value["node_id"]), (1, "4090"))
        self.assertIsNone(value["cpu"]["temperature_c"])
        self.assertEqual(value["agent"]["sample_interval_seconds"], SAMPLE_INTERVAL_SECONDS)

    def test_reviewable_defaults_manifest_matches_compiled_fixed_values(self):
        manifest = json.loads((ROOT / "telemetry_agent" / "config.defaults.json").read_text("utf-8"))
        self.assertEqual(manifest, {
            "allowed_clients": sorted(ALLOWED_CLIENTS), "bind_address": BIND_ADDRESS,
            "expected_gpu_fragment": EXPECTED_GPU_FRAGMENT, "node_id": NODE_ID,
            "port": PORT, "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
            "schema_version": SCHEMA_VERSION})

    def test_agent_source_has_no_subprocess_or_generic_control_surface(self):
        source = (ROOT / "telemetry_agent" / "agent.py").read_text("utf-8").lower()
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("nvidia-smi.exe", source)
        self.assertNotIn("shell=true", source)
        self.assertEqual(source.count('self.path == "/health"'), 1)
        self.assertEqual(source.count('self.path == "/telemetry"'), 1)
        for marker in ("nvmlDeviceGetUtilizationRates", "GetSystemTimes",
                       "GlobalMemoryStatusEx", "SetPriorityClass", "event.wait"):
            self.assertIn(marker.lower(), source)


class AgentHttpTests(unittest.TestCase):
    def setUp(self):
        self.cache = TelemetryCache()
        self.cache.publish(payload())
        self.server = TelemetryHttpServer(("127.0.0.1", 0), self.cache,
                                          frozenset({"127.0.0.1"}))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def test_only_fixed_get_routes_return_cached_bounded_json(self):
        for route in ("/health", "/telemetry"):
            with urlopen(self.base + route, timeout=2) as response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "application/json")
                self.assertLessEqual(len(body), MAX_RESPONSE_BYTES)
                self.assertIsInstance(json.loads(body), dict)
        for request, code in ((Request(self.base + "/telemetry?x=1"), 400),
                              (Request(self.base + "/other"), 404),
                              (Request(self.base + "/telemetry", data=b"x", method="GET"), 400),
                              (Request(self.base + "/telemetry", data=b"{}", method="POST"), 405)):
            with self.subTest(url=request.full_url), self.assertRaises(HTTPError) as raised:
                urlopen(request, timeout=2)
            self.assertEqual(raised.exception.code, code)
            raised.exception.close()
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.base + "/telemetry", method="OPTIONS"), timeout=2)
        self.assertEqual(raised.exception.code, 405); raised.exception.close()

    def test_application_allowlist_is_fixed_and_rejects_untrusted_peer(self):
        self.assertEqual(ALLOWED_CLIENTS,
                         frozenset({"192.168.0.100", "192.168.0.101", "127.0.0.1", "::1"}))
        denied = TelemetryHttpServer(("127.0.0.1", 0), self.cache,
                                     frozenset({"192.168.0.100"}))
        thread = threading.Thread(target=denied.serve_forever, daemon=True); thread.start()
        try:
            with self.assertRaises(HTTPError) as raised:
                urlopen(f"http://127.0.0.1:{denied.server_address[1]}/health", timeout=2)
            self.assertEqual(raised.exception.code, 403); raised.exception.close()
        finally:
            denied.shutdown(); denied.server_close(); thread.join(2)


class ClientTests(unittest.TestCase):
    @staticmethod
    def encoded(**changes):
        value = payload(**changes)
        return json.dumps(value).encode()

    def test_client_uses_exact_get_url_timeout_and_maps_real_values(self):
        calls = []
        def transport(request, timeout):
            calls.append((request, timeout)); return self.encoded()
        value = Remote4090TelemetryClient(transport=transport, clock=lambda: NOW).sample()
        self.assertEqual(value.state, TelemetryState.OBSERVED)
        self.assertEqual((value.gpu_utilization_percent, value.gpu_temperature_c,
                          value.cpu_utilization_percent), (5.0, 39.0, 4.2))
        self.assertIsNone(value.cpu_temperature_c)
        request, timeout = calls[0]
        self.assertEqual((request.full_url, request.method, timeout),
                         (REMOTE_TELEMETRY_URL, "GET", REMOTE_TELEMETRY_TIMEOUT_SECONDS))

    def test_stale_is_preserved_as_timestamped_observation(self):
        old = NOW - timedelta(seconds=11)
        value = Remote4090TelemetryClient(
            transport=lambda *_: self.encoded(observed_at=old), clock=lambda: NOW).sample()
        self.assertEqual(value.state, TelemetryState.OBSERVED)
        self.assertEqual(value.reason, "remote_telemetry_stale")
        self.assertEqual(value.observed_at, old)

    def test_timeout_unreachable_malformed_schema_and_identity_are_distinct(self):
        cases = (
            (lambda *_: (_ for _ in ()).throw(TimeoutError()), TelemetryState.UNAVAILABLE,
             "remote_telemetry_timeout"),
            (lambda *_: (_ for _ in ()).throw(URLError(OSError("refused"))),
             TelemetryState.UNAVAILABLE, "remote_telemetry_unreachable"),
            (lambda *_: b"not-json", TelemetryState.UNKNOWN, "remote_telemetry_malformed"),
            (lambda *_: self.encoded(schema_version=2), TelemetryState.UNKNOWN,
             "remote_telemetry_schema_mismatch"),
            (lambda *_: self.encoded(node_id="other"), TelemetryState.UNKNOWN,
             "remote_telemetry_node_identity_mismatch"),
            (lambda *_: self.encoded(gpu_name="NVIDIA GeForce RTX 3090"),
             TelemetryState.UNKNOWN, "remote_telemetry_node_identity_mismatch"),
        )
        for transport, state, reason in cases:
            with self.subTest(reason=reason):
                value = Remote4090TelemetryClient(transport=transport, clock=lambda: NOW).sample()
                self.assertEqual((value.state, value.reason), (state, reason))
                self.assertIsNone(value.gpu_utilization_percent)

    def test_unobserved_blocks_cannot_smuggle_measurements(self):
        value = payload(); value["gpu"]["status"] = "unavailable"
        result = Remote4090TelemetryClient(
            transport=lambda *_: json.dumps(value).encode(), clock=lambda: NOW).sample()
        self.assertEqual((result.state, result.reason),
                         (TelemetryState.UNKNOWN, "remote_telemetry_schema_mismatch"))


class DeploymentArtifactTests(unittest.TestCase):
    def test_scripts_are_fixed_bounded_and_do_not_deploy_or_kill_processes(self):
        directory = ROOT / "telemetry_agent" / "windows"
        scripts = "\n".join(path.read_text("utf-8") for path in directory.glob("*.ps1"))
        install = (directory / "Install-GRACI4090Telemetry.ps1").read_text("utf-8")
        self.assertNotIn("Stop-Process", scripts)
        self.assertNotIn("Invoke-Command", scripts)
        self.assertNotIn("Enter-PSSession", scripts)
        for marker in ("192.168.0.101", "192.168.0.100", "8767", "Private", "-Program $python",
                       "-RunLevel Limited", "-MultipleInstances IgnoreNew",
                       "C:\\ProgramData\\GRACI\\telemetry_agent"):
            self.assertIn(marker, install)


if __name__ == "__main__":
    unittest.main()
