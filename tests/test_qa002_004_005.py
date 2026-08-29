"""Focused production visualizer/runtime/voice composition regression coverage."""

import contextlib
import http.client
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graci.__main__ import main
from graci.config import Config
from graci.controller import Controller
from graci.observation import ObservationKind
from graci.operator_cli import (OperatorComposition, build_operator_composition,
                                build_operator_coordinator)
from graci.provider import ProviderResponse
from graci.turn_coordinator import (ExplicitTurnCoordinator, InputOutcome, InputSource,
                                    TurnDisposition, TurnResult)
from graci.visualizer import EventType, SystemState
from graci.visualizer_backend import BASE_PATH, VisualizerServer, VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver, VisualizerVoiceObserver
from graci.voice_lifecycle import VoiceLifecycle


class Runtime:
    def __init__(self):
        self.observer = None

    def run(self, task):
        return {"status": "PASS"}


class Capture:
    pass


class STT:
    pass


class TTS:
    pass


class Player:
    pass


class SuccessfulProvider:
    def execute(self, task):
        content = json.dumps({"schema_version": 2, "status": "PASS",
                              "summary": "completed", "user_response": "Done."})
        return ProviderResponse(200, content, "qwen3.8-27b-q4_k_m")


class FailingObserver:
    def observe(self, event):
        raise RuntimeError("observer unavailable")


class ProductionCompositionTests(unittest.TestCase):
    def composition(self, enabled):
        runtime = Runtime()
        with patch("graci.operator_cli.Controller", return_value=runtime) as controller, \
             patch("graci.operator_cli.WindowsWaveInCapture", return_value=Capture()), \
             patch("graci.operator_cli.FasterWhisperSubprocessSTT", return_value=STT()), \
             patch("graci.operator_cli.KokoroSubprocessTTS", return_value=TTS()), \
             patch("graci.operator_cli.SubprocessWavePlayback", return_value=Player()):
            result = build_operator_composition(visualizer=enabled)
        runtime.observer = controller.call_args.kwargs.get("observer")
        return result, runtime

    def test_shared_provider_is_created_only_when_explicitly_requested(self):
        disabled, disabled_runtime = self.composition(False)
        self.assertIsNone(disabled.provider)
        self.assertIsNone(disabled.server)
        self.assertIsNone(disabled.runtime_observer)
        self.assertIsNone(disabled_runtime.observer)

        enabled, enabled_runtime = self.composition(True)
        self.assertIs(enabled.runtime_observer.provider, enabled.provider)
        self.assertIs(enabled.server.provider, enabled.provider)
        self.assertIs(enabled_runtime.observer, enabled.runtime_observer)
        self.assertIs(enabled.voice_lifecycle._observer.runtime_observer,
                      enabled.runtime_observer)

    def test_controller_publishes_real_typed_lifecycle_and_observer_fails_open(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        with tempfile.TemporaryDirectory() as directory:
            config = Config(run_directory=Path(directory))
            record = Controller(config, SuccessfulProvider(), observer).run("private task text")
        self.assertEqual(record["status"], "PASS")
        types = [event.event_type for event in provider.events()]
        self.assertEqual(types, [EventType.TASK_STARTED, EventType.QWEN_STARTED,
                                 EventType.QWEN_COMPLETED, EventType.TASK_COMPLETED])
        self.assertIs(provider.snapshot().system_state, SystemState.COMPLETED)
        self.assertNotIn("private task text", json.dumps(
            [event.message for event in provider.events()]))

        with tempfile.TemporaryDirectory() as directory:
            config = Config(run_directory=Path(directory))
            failed_open = Controller(config, SuccessfulProvider(), FailingObserver()).run("task")
        self.assertEqual(failed_open["status"], "PASS")

    def test_voice_lifecycle_uses_same_stream_and_late_close_cannot_overwrite(self):
        provider = VisualizerStateProvider()
        runtime_observer = VisualizerRuntimeObserver(provider)
        lifecycle = VoiceLifecycle(VisualizerVoiceObserver(runtime_observer))
        listening = lifecycle.enter(SystemState.LISTENING)
        rejected = lifecycle.enter(SystemState.SPEAKING)
        rejected.close()
        listening.close()
        self.assertEqual([event.event_type for event in provider.events()],
                         [EventType.VOICE_LISTENING, EventType.SYSTEM_IDLE])
        self.assertIs(provider.snapshot().system_state, SystemState.IDLE)

        speaking = lifecycle.enter(SystemState.SPEAKING)
        speaking.close()
        listening.close()  # stale, already-closed lease cannot overwrite newer state
        self.assertEqual([event.event_type for event in provider.events()][-2:],
                         [EventType.VOICE_SPEAKING, EventType.SYSTEM_IDLE])
        self.assertIs(provider.snapshot().system_state, SystemState.IDLE)

    def test_server_exposes_shared_provider_and_no_mutation_route(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        lifecycle = VoiceLifecycle(VisualizerVoiceObserver(observer))
        lifecycle.enter(SystemState.LISTENING).close()
        server = VisualizerServer(provider, port=0)
        server.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.bound_port, timeout=2)
            connection.request("GET", f"{BASE_PATH}/events")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(len(json.loads(response.read())), 2)
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", server.bound_port, timeout=2)
            connection.request("POST", f"{BASE_PATH}/submit-task", body=b"task")
            response = connection.getresponse()
            self.assertEqual(response.status, 405)
            response.read(); connection.close()
        finally:
            server.stop()

    def test_legacy_factory_remains_observer_free(self):
        composition, _ = self.composition(False)
        with patch("graci.operator_cli.build_operator_composition",
                   return_value=composition) as factory:
            self.assertIs(build_operator_coordinator(), composition.coordinator)
        factory.assert_called_once_with(None)


class CLIVisualizerTests(unittest.TestCase):
    def test_visualizer_option_starts_holds_and_stops_bounded_server(self):
        result = TurnResult(InputSource.TYPED, InputOutcome.ACCEPTED, None, True,
                            {"status": "PASS"}, None, False, None,
                            TurnDisposition.GOVERNED_PASS)
        coordinator = unittest.mock.Mock(spec=ExplicitTurnCoordinator)
        coordinator.run_typed.return_value = result
        provider = VisualizerStateProvider()
        server = VisualizerServer(provider, port=0)
        composition = OperatorComposition(coordinator, provider, None, None, server)
        prompts = []
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(["task", "--visualizer", "--visualizer-hold"],
                        composition_factory=lambda **kwargs: composition,
                        input_fn=lambda prompt: prompts.append(prompt) or "")
        self.assertEqual(code, 0)
        coordinator.run_typed.assert_called_once_with("task", present_speech=False)
        self.assertEqual(prompts, ["Visualizer is live. Press Enter to close it."])
        self.assertIn("http://127.0.0.1:", errors.getvalue())
        with self.assertRaises(RuntimeError):
            _ = server.bound_port


if __name__ == "__main__":
    unittest.main()
