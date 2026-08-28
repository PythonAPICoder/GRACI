"""Phase 5B localhost visualizer transport, concurrency, and security tests."""

import http.client
import json
import socket
import threading
import time
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

from graci.visualizer import (
    EVENT_SCHEMA_VERSION, SNAPSHOT_SCHEMA_VERSION, EventSeverity, EventType,
    SystemState, TaskView, TrustedRuntimeState, VisualizerEvent, WorkflowStatus,
    default_compute, inactive_agents, MemoryView, ExecutionView, ReviewView,
    project_snapshot, serialize_visualizer,
)
from graci.visualizer_backend import (
    API_VERSION, BASE_PATH, DEFAULT_HOST, DEFAULT_PORT, MAX_LIVE_CLIENTS,
    MAX_REQUEST_TARGET, VisualizerServer, VisualizerStateProvider,
)

NOW = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)


def make_event(index: int) -> VisualizerEvent:
    return VisualizerEvent(f"event-{index:03}", NOW + timedelta(seconds=index),
                           EventType.TASK_STARTED if index == 0 else EventType.TOOL_COMPLETED,
                           EventSeverity.ACTIVITY, "synthetic-controller", f"Event {index}.")


def make_snapshot():
    state = TrustedRuntimeState(SystemState.IDLE, TaskView(), default_compute(),
                                inactive_agents(), MemoryView(), ExecutionView(), ReviewView())
    return project_snapshot(state, snapshot_id="phase5b-snapshot",
                            generated_at=NOW + timedelta(minutes=10))


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.provider = VisualizerStateProvider()
        self.server = VisualizerServer(self.provider, port=0, heartbeat_seconds=.05)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def request(self, method, path, *, body=None, headers=None):
        connection = http.client.HTTPConnection(DEFAULT_HOST, self.server.bound_port, timeout=2)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        result = (response.status, dict(response.getheaders()), payload)
        connection.close()
        return result


class LifecycleNetworkTests(ServerCase):
    def test_defaults_are_fixed_loopback_and_documented_port(self):
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")
        self.assertEqual(DEFAULT_PORT, 8766)
        self.assertEqual(self.server._httpd.server_address[0], "127.0.0.1")
        with self.assertRaises(ValueError):
            VisualizerServer(self.provider, host="0.0.0.0")

    def test_start_second_start_shutdown_and_port_release(self):
        with self.assertRaises(RuntimeError):
            self.server.start()
        port = self.server.bound_port
        self.server.stop()
        replacement = VisualizerServer(VisualizerStateProvider(), port=port)
        replacement.start()
        replacement.stop()

    def test_port_conflict_fails_explicitly(self):
        duplicate = VisualizerServer(VisualizerStateProvider(), port=self.server.bound_port)
        with self.assertRaises(OSError):
            duplicate.start()


class HealthSnapshotTests(ServerCase):
    def test_health_before_snapshot_has_versions_headers_and_truth(self):
        status, headers, body = self.request("GET", f"{BASE_PATH}/health")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual((data["api_version"], data["snapshot_schema_version"],
                          data["event_schema_version"]),
                         (API_VERSION, SNAPSHOT_SCHEMA_VERSION, EVENT_SCHEMA_VERSION))
        self.assertFalse(data["snapshot_available"])
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_unavailable_then_exact_snapshot_and_head(self):
        self.assertEqual(self.request("GET", f"{BASE_PATH}/snapshot")[0], 503)
        snapshot = make_snapshot()
        self.provider.publish_snapshot(snapshot)
        status, _, body = self.request("GET", f"{BASE_PATH}/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(body.decode(), serialize_visualizer(snapshot))
        status, headers, body = self.request("HEAD", f"{BASE_PATH}/snapshot")
        self.assertEqual((status, body), (200, b""))
        self.assertEqual(int(headers["Content-Length"]), len(serialize_visualizer(snapshot).encode()))
        with self.assertRaises(FrozenInstanceError):
            snapshot.snapshot_id = "changed"

    def test_concurrent_snapshot_publication_never_partially_serializes(self):
        failures = []
        def publish():
            for _ in range(200):
                self.provider.publish_snapshot(make_snapshot())
        thread = threading.Thread(target=publish)
        thread.start()
        for _ in range(50):
            value = self.provider.snapshot()
            if value is not None:
                try:
                    json.loads(serialize_visualizer(value))
                except Exception as exc:  # pragma: no cover - assertion collection
                    failures.append(exc)
        thread.join()
        self.assertEqual(failures, [])


class EventsTests(ServerCase):
    def test_events_order_ids_and_hard_100_bound(self):
        for index in range(105):
            self.provider.publish_event(make_event(index), observed_at=NOW + timedelta(minutes=5))
        status, _, body = self.request("GET", f"{BASE_PATH}/events")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(data), 100)
        self.assertEqual([item["event_id"] for item in data],
                         [f"event-{index:03}" for index in range(5, 105)])
        rendered = body.decode()
        for sensitive in ("prompt", "memory_content", "stdout", "stderr", "chain_of_thought"):
            self.assertNotIn(sensitive, rendered)

    def test_duplicate_event_rejected_without_state_change(self):
        event = make_event(0)
        self.provider.publish_event(event, observed_at=NOW + timedelta(minutes=5))
        with self.assertRaises(ValueError):
            self.provider.publish_event(event, observed_at=NOW + timedelta(minutes=5))
        self.assertEqual(self.provider.events(), (event,))

    def test_concurrent_event_publication_and_read(self):
        def publish(start):
            for index in range(start, start + 20):
                self.provider.publish_event(make_event(index), observed_at=NOW + timedelta(minutes=5))
        # Ordered timestamps are part of Phase 5A, so serialize publishers while readers race.
        thread = threading.Thread(target=publish, args=(0,))
        thread.start()
        observed = []
        while thread.is_alive():
            observed.append(tuple(item.event_id for item in self.provider.events()))
        thread.join()
        self.assertTrue(all(len(items) <= 100 for items in observed))


class SSETests(ServerCase):
    def open_stream(self, last_id=None):
        sock = socket.create_connection((DEFAULT_HOST, self.server.bound_port), timeout=2)
        sock.settimeout(2)
        headers = (f"GET {BASE_PATH}/events/stream HTTP/1.1\r\n"
                   f"Host: 127.0.0.1:{self.server.bound_port}\r\n")
        if last_id is not None:
            headers += f"Last-Event-ID: {last_id}\r\n"
        sock.sendall((headers + "Connection: close\r\n\r\n").encode())
        return sock, sock.makefile("rb")

    def test_sse_receives_event_id_type_and_json(self):
        sock, stream = self.open_stream()
        try:
            headers = b""
            while b"\r\n\r\n" not in headers:
                headers += stream.readline()
            self.assertIn(b"text/event-stream; charset=utf-8", headers)
            event = make_event(0)
            self.provider.publish_event(event, observed_at=NOW + timedelta(minutes=5))
            lines = []
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not any(line.startswith(b"data:") for line in lines):
                lines.append(stream.readline().strip())
            self.assertIn(b"id: event-000", lines)
            self.assertIn(b"event: task_started", lines)
            data = next(line[6:] for line in lines if line.startswith(b"data: "))
            self.assertEqual(json.loads(data)["event_id"], "event-000")
        finally:
            stream.close(); sock.close()

    def test_reconnect_known_id_replays_only_later_and_unknown_replays_retained(self):
        for index in range(3):
            self.provider.publish_event(make_event(index), observed_at=NOW + timedelta(minutes=5))
        sock, stream = self.open_stream("event-001")
        try:
            content = b""
            while b"id: event-002" not in content:
                content += stream.readline()
            self.assertNotIn(b"id: event-000", content)
        finally:
            stream.close(); sock.close()
        sock, stream = self.open_stream("evicted-id")
        try:
            content = b""
            while b"id: event-002" not in content:
                content += stream.readline()
            self.assertIn(b"id: event-000", content)
        finally:
            stream.close(); sock.close()

    def test_heartbeat_is_comment_and_does_not_create_event(self):
        sock, stream = self.open_stream()
        try:
            content = b""
            while b": heartbeat" not in content:
                content += stream.readline()
            self.assertEqual(self.provider.events(), ())
        finally:
            stream.close(); sock.close()

    def test_client_limit_and_disconnect_cleanup(self):
        self.server.stop()
        self.server = VisualizerServer(self.provider, port=0, max_live_clients=1,
                                       heartbeat_seconds=.05)
        self.server.start()
        sockets = []
        try:
            sock, stream = self.open_stream()
            sockets.append((sock, stream))
            deadline = time.monotonic() + 2
            while self.server._httpd.live_clients < 1 and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(self.request("GET", f"{BASE_PATH}/events/stream")[0], 503)
        finally:
            for sock, stream in sockets:
                stream.close(); sock.close()


class MethodWebSecurityTests(ServerCase):
    def test_all_write_and_tunnel_methods_rejected_without_publication(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            status, _, body = self.request(method, f"{BASE_PATH}/snapshot", body=b"command")
            self.assertEqual(status, 405, method)
            self.assertLess(len(body), 300)
        self.assertIsNone(self.provider.snapshot())
        self.assertEqual(self.provider.events(), ())

    def test_body_host_query_malformed_and_oversized_targets_rejected(self):
        self.assertEqual(self.request("GET", f"{BASE_PATH}/health", body=b"x")[0], 400)
        self.assertEqual(self.request("GET", f"{BASE_PATH}/health", headers={"Host": "evil.test"})[0], 400)
        self.assertEqual(self.request("GET", f"{BASE_PATH}/health?url=http://example.test")[0], 400)
        self.assertEqual(self.request("GET", f"{BASE_PATH}/../config")[0], 400)
        self.assertEqual(self.request("GET", "/" + "x" * MAX_REQUEST_TARGET)[0], 414)

    def test_unknown_routes_and_control_concepts_are_bounded_not_found(self):
        for suffix in ("submit-task", "tool", "memory", "route", "mo2", "review",
                       "inference", "shutdown", "fetch", "files"):
            status, _, body = self.request("GET", f"{BASE_PATH}/{suffix}")
            self.assertEqual(status, 404)
            self.assertNotIn(b"Traceback", body)

    def test_backend_source_has_no_authority_or_cloud_dependencies(self):
        source = (Path(__file__).parents[1] / "graci" / "visualizer_backend.py").read_text("utf-8")
        for forbidden in ("subprocess", "requests", "urllib.request", "memory_pipeline",
                          "from .tools", "from .provider", "192.168.0.101", "openai"):
            self.assertNotIn(forbidden, source)


class EvidenceTests(unittest.TestCase):
    def test_phase5b_acceptance_evidence(self):
        path = Path(__file__).parents[1] / "phase5b" / "evidence" / "phase5b-acceptance.json"
        evidence = json.loads(path.read_text("utf-8"))
        self.assertEqual(evidence["starting_commit"], "213e88972041916bd38c413f91a9babfc1663fe6")
        self.assertEqual(evidence["status"], "PASS")
        self.assertTrue(all(evidence["checks"].values()))
        self.assertEqual(evidence["security"]["control_endpoints"], "none")


if __name__ == "__main__":
    unittest.main()
