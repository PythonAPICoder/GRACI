"""Production composition and safe CLI projection for one explicit operator turn."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .audio_capture import WindowsWaveInCapture
from .browser_ptt import BrowserPTTOperator
from .controller import Controller
from .playback import PlaybackConfig, SubprocessWavePlayback
from .push_to_talk import PushToTalkController
from .speech import FasterWhisperConfig, FasterWhisperSubprocessSTT, TranscriptionResult
from .speech_presentation import SpeechPresentationResult, SpeechPresentationService
from .tts import AuthoritativeFinalResponse, KokoroConfig, KokoroSubprocessTTS
from .turn_coordinator import ExplicitTurnCoordinator, TurnResult
from .voice_lifecycle import VoiceLifecycle
from .visualizer_backend import VisualizerServer, VisualizerStateProvider
from .visualizer_runtime import VisualizerRuntimeObserver, VisualizerVoiceObserver

MAX_CLI_TEXT = 20_000
MAX_CLI_ERROR = 500


class GovernedSummaryResponseConstructor:
    """Select only the explicit validated user response for operator presentation."""

    def construct(self, governed_result: dict[str, Any]) -> AuthoritativeFinalResponse | None:
        validated = governed_result.get("validated_model_result")
        if not isinstance(validated, dict):
            return None
        if validated.get("schema_version") != 2 or validated.get("status") != "PASS":
            return None
        user_response = validated.get("user_response")
        if not isinstance(user_response, str) or not user_response.strip():
            return None
        return AuthoritativeFinalResponse(user_response)


@dataclass(frozen=True)
class OperatorComposition:
    coordinator: ExplicitTurnCoordinator
    provider: VisualizerStateProvider | None = None
    runtime_observer: VisualizerRuntimeObserver | None = None
    voice_lifecycle: VoiceLifecycle | None = None
    server: VisualizerServer | None = None
    browser_ptt: BrowserPTTOperator | None = None
    restart_runtime: Callable[[], None] | None = None


def build_operator_composition(repository_root: Path | None = None, *,
                               visualizer: bool = False,
                               browser_operator: bool = False) -> OperatorComposition:
    """Compose accepted local components without adding another runtime authority."""
    root = repository_root or Path(__file__).resolve().parents[1]
    provider = VisualizerStateProvider() if visualizer else None
    runtime_observer = VisualizerRuntimeObserver(provider) if provider is not None else None
    voice_observer = (VisualizerVoiceObserver(runtime_observer)
                      if runtime_observer is not None else None)
    lifecycle = VoiceLifecycle(voice_observer) if voice_observer is not None else VoiceLifecycle()
    stt = FasterWhisperSubprocessSTT(FasterWhisperConfig(
        root / "phase6a" / ".venv" / "Scripts" / "python.exe",
        root / "phase6b" / "stt_worker.py",
        model_cache=root / "phase6a" / "cache" / "huggingface",
    ))
    speech_python = root / "phase6a" / ".venv312" / "Scripts" / "python.exe"
    synthesizer = KokoroSubprocessTTS(KokoroConfig(
        speech_python,
        root / "phase6d" / "tts_worker.py",
        root / "phase6a" / "cache" / "kokoro-onnx" / "kokoro-v1.0.int8.onnx",
        root / "phase6a" / "cache" / "kokoro-onnx" / "voices-v1.0.bin",
    ))
    player = SubprocessWavePlayback(PlaybackConfig(
        speech_python, root / "phase6d" / "playback_worker.py"))
    presentation = SpeechPresentationService(synthesizer, player, lifecycle)
    push_to_talk = PushToTalkController(
        WindowsWaveInCapture(), stt, lifecycle=lifecycle,
        interrupt_speaking=presentation.interrupt_playback)
    coordinator = ExplicitTurnCoordinator(
        Controller(observer=runtime_observer), push_to_talk=push_to_talk,
        final_response_constructor=GovernedSummaryResponseConstructor(),
        speech_presentation=presentation,
    )
    if browser_operator and provider is None:
        raise ValueError("browser operator control requires the visualizer")
    browser_ptt = (BrowserPTTOperator(
        stt, coordinator, lifecycle,
        interrupt_speaking=presentation.interrupt_playback)
                   if browser_operator else None)
    def restart_runtime() -> None:
        presentation.interrupt_playback()
        if browser_ptt is not None:
            browser_ptt.close()
        lifecycle.reset()
        if runtime_observer is not None:
            runtime_observer.reset_transient()

    server = (VisualizerServer(provider, browser_ptt=browser_ptt,
                               restart_runtime=restart_runtime)
              if provider is not None else None)
    return OperatorComposition(coordinator, provider, runtime_observer, lifecycle, server,
                               browser_ptt, restart_runtime)


def build_operator_coordinator(repository_root: Path | None = None) -> ExplicitTurnCoordinator:
    """Backward-compatible production factory for an observer-free operator turn."""
    return build_operator_composition(repository_root).coordinator


def serialize_turn_result(result: TurnResult, *,
                          speech_requested: bool | None = None) -> dict[str, Any]:
    """Project typed Phase 7A values through an explicit bounded JSON boundary."""
    return {
        "schema_version": 1,
        "input": {
            "source": result.input_source.value,
            "outcome": result.input_outcome.value,
            "transcription": _transcription(result.transcription),
        },
        "governed": {
            "submitted": result.governed_submitted,
            "outcome": _governed_outcome(result),
            "result": _governed_result(result.governed_result),
        },
        "final_response": {
            "available": result.authoritative_response is not None,
            "text": (_bounded(result.authoritative_response.text, MAX_CLI_TEXT)
                     if result.authoritative_response is not None else None),
        },
        "presentation": {
            "requested": (result.speech_requested if speech_requested is None
                          else speech_requested),
            **_presentation(result.speech_presentation),
        },
        "terminal_disposition": result.disposition.value,
        "error": (_error(result.error_code, result.error_message)
                  if result.error_code is not None else None),
    }


def _transcription(value: TranscriptionResult | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "status": value.status.value,
        "backend": _bounded(value.backend, 200),
        "duration_seconds": value.duration_seconds,
        "text": _bounded(value.text, MAX_CLI_TEXT) if value.text is not None else None,
        "error": (_error(value.error_code, value.error_message)
                  if value.error_code is not None else None),
    }


def _governed_outcome(result: TurnResult) -> str | None:
    if not result.governed_submitted:
        return None
    if result.governed_result is None:
        return "ERROR"
    status = result.governed_result.get("status")
    return status if status in {"PASS", "FAIL"} else "ERROR"


def _governed_result(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    validated = value.get("validated_model_result")
    safe_validated = None
    if isinstance(validated, dict):
        safe_validated = {
            "schema_version": validated.get("schema_version"),
            "status": validated.get("status") if validated.get("status") in {"PASS", "FAIL"} else None,
            "summary": (_bounded(validated.get("summary"), MAX_CLI_TEXT)
                        if isinstance(validated.get("summary"), str) else None),
            "user_response": (_bounded(validated.get("user_response"), MAX_CLI_TEXT)
                              if isinstance(validated.get("user_response"), str) else None),
        }
    errors = value.get("errors")
    safe_errors = ([_bounded(item, MAX_CLI_ERROR) for item in errors[:20]
                    if isinstance(item, str)] if isinstance(errors, list) else [])
    return {
        "schema_version": value.get("schema_version"),
        "run_id": _bounded(value.get("run_id"), 200) if isinstance(value.get("run_id"), str) else None,
        "status": value.get("status") if value.get("status") in {"PASS", "FAIL"} else None,
        "http_status": value.get("http_status") if isinstance(value.get("http_status"), int) else None,
        "provider_response_model": (_bounded(value.get("provider_response_model"), 200)
                                    if isinstance(value.get("provider_response_model"), str) else None),
        "validated_model_result": safe_validated,
        "errors": safe_errors,
    }


def _presentation(value: SpeechPresentationResult | None) -> dict[str, Any]:
    if value is None:
        return {"status": None, "error": None}
    return {
        "status": value.status.value,
        "error": (_error(value.error_code, value.error_message)
                  if value.error_code is not None else None),
    }


def _error(code: str | None, message: str | None) -> dict[str, str | None]:
    return {"code": _bounded(code, 100) if code is not None else None,
            "message": _bounded(message, MAX_CLI_ERROR) if message is not None else None}


def _bounded(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]
