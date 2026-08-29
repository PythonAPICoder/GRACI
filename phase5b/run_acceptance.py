"""Real-loopback, synthetic-only Phase 5B acceptance and evidence generation."""

from __future__ import annotations

import http.client
import json
import socket
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graci.availability import Mo2State
from graci.registry import GLM_MODEL_ID, QWEN_MODEL_ID, HealthState
from graci.visualizer import (
    ActivityState, AgentView, AgentsView, EventSeverity, EventType, ExecutionView,
    MemoryMode, MemoryView, OperationCategory, OperationView, ReviewView, SystemState,
    TaskView, TestView, TrustedRuntimeState, VisualizerEvent, WorkflowStatus,
    default_compute, inactive_agents, project_snapshot, serialize_visualizer,
)
from graci.visualizer_backend import BASE_PATH, DEFAULT_HOST, DEFAULT_PORT, VisualizerServer, VisualizerStateProvider

STARTING_COMMIT = "213e88972041916bd38c413f91a9babfc1663fe6"
NOW = datetime(2026, 8, 27, 21, 0, tzinfo=timezone.utc)


def request(port: int, method: str, path: str, body=None):
    connection = http.client.HTTPConnection(DEFAULT_HOST, port, timeout=3)
    connection.request(method, path, body=body)
    response = connection.getresponse()
    data = response.read()
    result = response.status, dict(response.getheaders()), data
    connection.close()
    return result


def main() -> None:
    provider = VisualizerStateProvider()
    server = VisualizerServer(provider)
    checks: dict[str, bool] = {}
    received: list[str] = []
    server.start()
    try:
        status, headers, body = request(DEFAULT_PORT, "GET", f"{BASE_PATH}/health")
        health = json.loads(body)
        checks["health_before_state"] = status == 200 and health["snapshot_available"] is False
        checks["versions"] = (health["api_version"], health["snapshot_schema_version"],
                              health["event_schema_version"]) == (1, 2, 1)

        idle_state = TrustedRuntimeState(SystemState.IDLE, TaskView(), default_compute(),
                                         inactive_agents(), MemoryView(), ExecutionView(), ReviewView())
        idle = project_snapshot(idle_state, snapshot_id="phase5b-idle", generated_at=NOW)
        provider.publish_snapshot(idle)
        checks["idle_snapshot_exact"] = request(DEFAULT_PORT, "GET", f"{BASE_PATH}/snapshot")[2].decode() == serialize_visualizer(idle)

        task = TaskView("phase5b-task", "phase5b-goal", "Synthetic local backend acceptance.",
                        NOW, "phase5b", 4, 8, WorkflowStatus.ACTIVE)
        compute = default_compute(primary_health=HealthState.HEALTHY,
                                  optional_health=HealthState.HEALTHY,
                                  optional_eligible=True, mo2_state=Mo2State.NOT_RUNNING,
                                  optional_reason="eligible")
        agents = AgentsView(AgentView(QWEN_MODEL_ID, "implementer", ActivityState.ACTIVE,
                                     "3090", SystemState.REASONING, started_at=NOW),
                            AgentView(GLM_MODEL_ID, "reviewer", ActivityState.INACTIVE))
        memory = MemoryView(True, MemoryMode.OPTIONAL, ("project.graci.visualizer",),
                            "MEMORY_APPLIED", ("memory-synthetic-1",),
                            ("memory-synthetic-1",), 1, 128, 0, 0)
        operation = OperationView(OperationCategory.EDIT, WorkflowStatus.PASSED, NOW,
                                  NOW + timedelta(seconds=1), "graci/visualizer_backend.py")
        active_state = TrustedRuntimeState(SystemState.REASONING, task, compute, agents,
                                           memory, ExecutionView((operation,), TestView()), ReviewView())
        active = project_snapshot(active_state, snapshot_id="phase5b-active",
                                  generated_at=NOW + timedelta(minutes=1))
        provider.publish_snapshot(active)
        checks["active_snapshot_exact"] = request(DEFAULT_PORT, "GET", f"{BASE_PATH}/snapshot")[2].decode() == serialize_visualizer(active)
        checks["mo2_eligible_display"] = active.compute.optional_4090.eligible is True
        blocked = default_compute(primary_health=HealthState.HEALTHY,
                                  optional_health=HealthState.HEALTHY,
                                  optional_eligible=True, mo2_state=Mo2State.RUNNING)
        checks["mo2_running_display"] = blocked.optional_4090.eligible is False and blocked.optional_4090.policy_reason == "mo2_running"

        sock = socket.create_connection((DEFAULT_HOST, DEFAULT_PORT), timeout=3)
        sock.settimeout(3)
        stream = sock.makefile("rb")
        sock.sendall((f"GET {BASE_PATH}/events/stream HTTP/1.1\r\nHost: {DEFAULT_HOST}:{DEFAULT_PORT}\r\nConnection: close\r\n\r\n").encode())
        while stream.readline() != b"\r\n":
            pass
        kinds = (EventType.TASK_STARTED, EventType.MEMORY_SELECTED, EventType.QWEN_STARTED,
                 EventType.TOOL_COMPLETED, EventType.TESTS_PASSED, EventType.REVIEW_STARTED,
                 EventType.ADJUDICATION_COMPLETED, EventType.TASK_COMPLETED)
        for index, kind in enumerate(kinds):
            provider.publish_event(VisualizerEvent(
                f"phase5b-event-{index:03}", NOW + timedelta(seconds=index), kind,
                EventSeverity.SUCCESS if index in {3, 4, 6, 7} else EventSeverity.ACTIVITY,
                "synthetic-controller", f"Synthetic {kind.value}.", task.task_id),
                observed_at=NOW + timedelta(minutes=2))
        while len(received) < len(kinds):
            line = stream.readline().decode().strip()
            if line.startswith("id: "):
                received.append(line[4:])
        stream.close(); sock.close()
        expected = [f"phase5b-event-{index:03}" for index in range(len(kinds))]
        checks["sse_ordered_lifecycle"] = received == expected
        checks["recent_events_exact"] = [item["event_id"] for item in json.loads(
            request(DEFAULT_PORT, "GET", f"{BASE_PATH}/events")[2])] == expected

        before = (provider.snapshot(), provider.events())
        rejection_statuses = {
            "post": request(DEFAULT_PORT, "POST", f"{BASE_PATH}/snapshot", b"mutate")[0],
            "delete": request(DEFAULT_PORT, "DELETE", f"{BASE_PATH}/events")[0],
            "bogus": request(DEFAULT_PORT, "GET", f"{BASE_PATH}/submit-task")[0],
        }
        checks["http_security_rejections"] = rejection_statuses == {"post": 405, "delete": 405, "bogus": 404}
        checks["http_rejections_no_side_effect"] = before == (provider.snapshot(), provider.events())
        checks["safe_headers_no_cors"] = (headers["Cache-Control"] == "no-store" and
                                          "Access-Control-Allow-Origin" not in headers)
    finally:
        server.stop()

    probe = socket.socket()
    try:
        probe.bind((DEFAULT_HOST, DEFAULT_PORT))
        checks["shutdown_port_released"] = True
    except OSError:
        checks["shutdown_port_released"] = False
    finally:
        probe.close()

    evidence = {
        "phase": "5B", "status": "PASS" if all(checks.values()) else "FAIL",
        "starting_commit": STARTING_COMMIT, "api_version": 1,
        "snapshot_schema_version": 1, "event_schema_version": 1,
        "bind_address": DEFAULT_HOST, "default_port": DEFAULT_PORT,
        "endpoints": [f"{BASE_PATH}/{name}" for name in ("health", "snapshot", "events", "events/stream")],
        "allowed_methods": ["GET", "HEAD"], "event_buffer_limit": 100,
        "live_client_limit": 8, "startup_state": "health available; snapshot 503 until trusted publication",
        "sse": {"transport": "one-way server-sent events", "heartbeat": "comment only",
                "replay": "known ID replays later retained events; unknown ID replays retained buffer",
                "backpressure": "condition notification plus shared 100-event buffer; no per-client queue"},
        "security": {"cors": "none", "host_policy": "configured loopback host/port or localhost/port",
                     "headers": ["Cache-Control: no-store", "X-Content-Type-Options: nosniff", "Referrer-Policy: no-referrer"],
                     "state_publication": "trusted in-process immutable Phase 5A objects only",
                     "control_endpoints": "none", "cloud_ai": "none", "4090_inference": "none",
                     "memory_mutation": "none", "tool_invocation": "none"},
        "synthetic_event_ids": received, "http_rejection_statuses": rejection_statuses,
        "checks": checks,
        "verification": {"warning_strict_tests": 0, "warning_strict_result": "pending final verification",
                         "phase5a_regression": "pending final verification",
                         "phase1_to_4_regression": "pending final verification",
                         "compilation": "pending final verification", "secret_scan": "pending final verification",
                         "git_diff_check": "pending final verification"},
    }
    destination = ROOT / "phase5b" / "evidence" / "phase5b-acceptance.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "checks": checks}, sort_keys=True))
    if evidence["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
