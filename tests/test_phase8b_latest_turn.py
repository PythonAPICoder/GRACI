"""Focused Phase 8B resident latest-turn continuity and authority tests."""

import http.client
import json
import unittest
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from graci.browser_ptt import BrowserPTTOperator
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import PresentationStatus, SpeechPresentationResult
from graci.turn_coordinator import (InputOutcome, InputSource, TurnDisposition,
                                    TurnResult)
from graci.tts import AuthoritativeFinalResponse
from graci.visualizer import (LATEST_RESPONSE_LIMIT, LatestTurnView,
                              PresentationOutcome, SystemState, WorkflowStatus,
                              serialize_visualizer)
from graci.visualizer_backend import BASE_PATH, VisualizerServer, VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver
from graci.observation import ObservationKind, RuntimeObservation
from graci.voice_lifecycle import VoiceLifecycle


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def record(status="PASS", *, run_id="run-phase8b", errors=None, raw="REJECTED RAW SECRET"):
    return {
        "run_id": run_id,
        "started_at": "2026-08-29T12:00:00Z",
        "ended_at": "2026-08-29T12:00:02Z",
        "status": status,
        "errors": list(errors or []),
        "submitted_task": "must not be projected",
        "model_generation_attempts": [{"content": raw}],
    }


def turn(status="PASS", *, response="Validated response", presentation=None,
         errors=None, run_id="run-phase8b"):
    authoritative = AuthoritativeFinalResponse(response) if response is not None else None
    return TurnResult(
        InputSource.TYPED, InputOutcome.ACCEPTED, None, True,
        record(status, run_id=run_id, errors=errors), authoritative, True,
        presentation, (TurnDisposition.GOVERNED_PASS if status == "PASS"
                       else TurnDisposition.GOVERNED_FAIL))


class LatestTurnContractTests(unittest.TestCase):
    def test_contract_is_frozen_bounded_terminal_and_deterministic(self):
        value = LatestTurnView(
            "run", "browser_ptt", NOW, NOW + timedelta(seconds=1),
            WorkflowStatus.PASSED, True, "x" * (LATEST_RESPONSE_LIMIT + 100),
            PresentationOutcome.SPOKEN)
        self.assertEqual(len(value.response_text), LATEST_RESPONSE_LIMIT)
        self.assertTrue(value.response_text.endswith("…"))
        with self.assertRaises(FrozenInstanceError):
            value.response_text = "changed"  # type: ignore[misc]
        with self.assertRaises(ValueError):
            LatestTurnView("run", "browser_ptt", NOW, NOW, WorkflowStatus.FAILED,
                           True, "fabricated")
        with self.assertRaises(ValueError):
            LatestTurnView("run", "browser_ptt", NOW + timedelta(seconds=1), NOW,
                           WorkflowStatus.PASSED, False)
        names = {item.name for item in fields(LatestTurnView)}
        prohibited = {"prompt", "transcript", "raw_output", "model_attempts",
                      "memory_content", "stdout", "stderr", "credentials"}
        self.assertTrue(names.isdisjoint(prohibited))

    def test_success_failure_and_rejected_raw_content_projection(self):
        provider = VisualizerStateProvider(); observer = VisualizerRuntimeObserver(provider)
        observer.publish_completed_turn(turn())
        success = provider.snapshot().latest_turn
        self.assertEqual(success.governed_status, WorkflowStatus.PASSED)
        self.assertEqual(success.response_text, "Validated response")
        serialized = serialize_visualizer(provider.snapshot())
        self.assertEqual(serialized, serialize_visualizer(provider.snapshot()))
        self.assertNotIn("submitted_task", serialized)
        self.assertNotIn("REJECTED RAW SECRET", serialized)
        self.assertEqual(provider.events()[-1].event_type.value, "latest_turn_updated")

        observer.publish_completed_turn(turn("FAIL", response="must be ignored",
                                             errors=["validation_error: exhausted"]))
        failed = provider.snapshot().latest_turn
        self.assertEqual(failed.governed_status, WorkflowStatus.FAILED)
        self.assertFalse(failed.response_available)
        self.assertIsNone(failed.response_text)
        self.assertIn("validation_error", failed.failure_reason)

    def test_zero_run_paths_and_malformed_records_publish_nothing(self):
        provider = VisualizerStateProvider(); observer = VisualizerRuntimeObserver(provider)
        rejected = TurnResult(InputSource.SPEECH, InputOutcome.REJECTED, None, False,
                              None, None, False, None,
                              TurnDisposition.INPUT_REJECTED, "blank_transcript", "blank")
        observer.publish_completed_turn(rejected)
        observer.publish_completed_turn(TurnResult(
            InputSource.SPEECH, InputOutcome.FAILED, None, False, None, None, False,
            None, TurnDisposition.INPUT_FAILED, "speech_start_failed", "failed"))
        observer.publish_completed_turn(TurnResult(
            InputSource.TYPED, InputOutcome.ACCEPTED, None, True,
            {"run_id": "missing-times", "status": "FAIL"}, None, False, None,
            TurnDisposition.GOVERNED_FAIL))
        self.assertIsNone(observer.latest_turn)

    def test_barge_in_cancellation_is_separate_from_governed_success(self):
        provider = VisualizerStateProvider(); observer = VisualizerRuntimeObserver(provider)
        response = AuthoritativeFinalResponse("Prior authoritative response")
        presentation = SpeechPresentationResult(PresentationStatus.CANCELLED, response)
        observer.publish_completed_turn(turn(response=response.text, presentation=presentation))
        latest = provider.snapshot().latest_turn
        self.assertEqual(latest.governed_status, WorkflowStatus.PASSED)
        self.assertEqual(latest.response_text, response.text)
        self.assertEqual(latest.presentation_outcome, PresentationOutcome.CANCELLED)


class ResidentContinuityTests(unittest.TestCase):
    def setUp(self):
        self.provider = VisualizerStateProvider()
        self.observer = VisualizerRuntimeObserver(self.provider)
        self.observer.publish_completed_turn(turn())
        self.server = VisualizerServer(self.provider, port=0)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def snapshot(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.bound_port, timeout=2)
        connection.request("GET", f"{BASE_PATH}/snapshot")
        response = connection.getresponse(); body = response.read(); connection.close()
        self.assertEqual(response.status, 200)
        return json.loads(body)

    def test_refresh_and_second_client_receive_same_resident_turn(self):
        first, second = self.snapshot(), self.snapshot()
        self.assertEqual(first["latest_turn"], second["latest_turn"])
        self.assertEqual(first["latest_turn"]["response_text"], "Validated response")

    def test_active_task_is_distinct_and_restart_retains_latest(self):
        before = self.provider.snapshot().latest_turn
        self.observer.observe(RuntimeObservation(
            ObservationKind.TASK_STARTED, datetime.now(timezone.utc), "new-active-run",
            (("summary", "Explicit local operator turn"),)))
        active = self.provider.snapshot()
        self.assertEqual(active.task.task_id, "new-active-run")
        self.assertEqual(active.latest_turn, before)
        self.observer.reset_transient()
        restarted = self.provider.snapshot()
        self.assertEqual(restarted.system_state, SystemState.IDLE)
        self.assertIsNone(restarted.task.task_id)
        self.assertEqual(restarted.latest_turn, before)

    def test_fresh_resident_does_not_reconstruct_history(self):
        fresh_provider = VisualizerStateProvider(); fresh = VisualizerRuntimeObserver(fresh_provider)
        fresh.publish_current("fresh-resident")
        self.assertIsNone(fresh_provider.snapshot().latest_turn)


class BrowserBoundaryTests(unittest.TestCase):
    class STT:
        identity = "local-test"
        def transcribe(self, audio):
            return TranscriptionResult(TranscriptionStatus.SUCCESS, self.identity,
                                       audio.duration_seconds, text="hello")

    class Coordinator:
        def __init__(self, result): self.result, self.calls = result, 0
        def run_typed(self, text, *, present_speech=False):
            self.calls += 1
            return self.result

    @staticmethod
    def wav():
        import io, struct, wave
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16_000)
            wav.writeframes(struct.pack("<h", 1) * 3_200)
        return output.getvalue()

    def test_release_submits_once_observer_failure_is_isolated_and_cancel_is_zero(self):
        coordinator = self.Coordinator(turn())
        def raising(_result): raise RuntimeError("visualizer unavailable")
        operator = BrowserPTTOperator(self.STT(), coordinator, VoiceLifecycle(),
                                      completed_turn_observer=raising)
        token = operator.begin(); result = operator.finish(token, self.wav())
        self.assertEqual(coordinator.calls, 1)
        self.assertEqual(result.turn_result.authoritative_response.text, "Validated response")
        token = operator.begin(); operator.cancel(token)
        self.assertEqual(coordinator.calls, 1)

    def test_ui_uses_snapshot_text_content_and_existing_control_allowlist(self):
        js = (ROOT / "graci" / "visualizer_ui" / "visualizer.js").read_text("utf-8")
        html = (ROOT / "graci" / "visualizer_ui" / "index.html").read_text("utf-8")
        css = (ROOT / "graci" / "visualizer_ui" / "visualizer.css").read_text("utf-8")
        backend = (ROOT / "graci" / "visualizer_backend.py").read_text("utf-8")
        self.assertIn("renderLatestTurn(s.latest_turn)", js)
        self.assertIn('$("operator-response").textContent=', js)
        self.assertNotIn('$("operator-response").innerHTML', js)
        self.assertIn("source.onopen", js)
        self.assertIn('"latest_turn_updated"', js)
        self.assertIn("refreshSnapshot()", js)
        self.assertIn('aria-labelledby="latest-turn-label"', html)
        self.assertIn("focus-visible", css)
        self.assertIn("prefers-reduced-motion:reduce", css)
        for path in ("/ptt/begin", "/ptt/chunk", "/ptt/finish", "/ptt/cancel", "/restart"):
            self.assertIn(path, backend)
        self.assertNotIn("/submit", backend)
        self.assertNotIn("WebSocket", backend)


if __name__ == "__main__":
    unittest.main()
