"""GRACI minimal local controller and controlled tool interfaces."""

from .config import Config
from .controller import Controller
from .autonomous import AutonomousRepairController, LoopLimits
from .tools import ToolLayer
from .vertical_slice import VerticalSliceController
from .registry import build_phase3a_registry, evaluate_eligibility
from .phase3b import Phase3BController
from .routing import Phase3BRoleRouter
from .availability import (
    MO2_PROCESS_NAME,
    MO2_STATUS_URL,
    Mo2State,
    Mo2StatusResult,
    Phase3CEligibilityReason,
    Phase3CEligibilityResult,
    check_4090_mo2_status,
    evaluate_4090_eligibility,
)
from .distributed import (DistributedRoutingError, Phase3DDistributedRouter,
                          RoutedResponse)
from .memory import (EnumerationResult, MemoryCollisionError, MemoryNotFoundError,
                     MemoryStatus, MemoryStorageError, MemoryStore, MemoryType,
                     MemoryValidationError, ProvenanceOrigin, ScopeKind)
from .memory_pipeline import (DEFAULT_RETRIEVAL_LIMIT, MAX_RETRIEVAL_LIMIT,
                              MemoryPipeline, RetrievalResult, WriteResult)
from .memory_governance import (DEFAULT_SELECTION_LIMIT, MAX_SELECTION_LIMIT,
                                ConflictDiagnostic, MemoryGovernance,
                                SelectionResult, validate_relevance_key)
from .memory_execution import (MAX_EXECUTION_MEMORY_CONTEXT_CHARACTERS,
                               MAX_EXECUTION_MEMORY_CONTENT_CHARACTERS,
                               MAX_EXECUTION_MEMORY_RECORDS, MemoryPreparation,
                               MemoryRequirement, prepare_execution_memory,
                               serialize_memory_envelope)
from .audio_capture import (AudioCaptureConfig, AudioCaptureError,
                            WindowsWaveInCapture)
from .push_to_talk import (PushToTalkController, PushToTalkLifecycleError,
                           PushToTalkState)
from .speech import (CapturedAudio, FasterWhisperConfig,
                     FasterWhisperSubprocessSTT, TranscriptionResult,
                     TranscriptionStatus)
from .speech_runtime import (GovernedRuntime, SpeechRuntimeAdapter,
                             TranscriptSubmissionError)
from .tts import (AuthoritativeFinalResponse, KokoroConfig, KokoroSubprocessTTS,
                  SynthesizedAudio, TTSRequest, TTSResult, TTSStatus)
from .playback import (PlaybackConfig, PlaybackResult, PlaybackStatus,
                       SubprocessWavePlayback)
from .speech_presentation import (PresentationStatus, SpeechPresentationResult,
                                  SpeechPresentationService)

__all__ = [
    "AutonomousRepairController", "Config", "Controller", "LoopLimits",
    "MO2_PROCESS_NAME", "MO2_STATUS_URL", "Mo2State", "Mo2StatusResult",
    "Phase3BController", "Phase3BRoleRouter", "Phase3CEligibilityReason",
    "Phase3CEligibilityResult", "ToolLayer", "VerticalSliceController",
    "DistributedRoutingError", "Phase3DDistributedRouter", "RoutedResponse",
    "EnumerationResult", "MemoryCollisionError", "MemoryNotFoundError",
    "MemoryStatus", "MemoryStorageError", "MemoryStore", "MemoryType",
    "MemoryValidationError", "ProvenanceOrigin", "ScopeKind",
    "DEFAULT_RETRIEVAL_LIMIT", "MAX_RETRIEVAL_LIMIT", "MemoryPipeline",
    "RetrievalResult", "WriteResult",
    "DEFAULT_SELECTION_LIMIT", "MAX_SELECTION_LIMIT", "ConflictDiagnostic",
    "MemoryGovernance", "SelectionResult", "validate_relevance_key",
    "MAX_EXECUTION_MEMORY_CONTEXT_CHARACTERS", "MAX_EXECUTION_MEMORY_CONTENT_CHARACTERS",
    "MAX_EXECUTION_MEMORY_RECORDS", "MemoryPreparation", "MemoryRequirement",
    "prepare_execution_memory", "serialize_memory_envelope",
    "build_phase3a_registry", "check_4090_mo2_status", "evaluate_4090_eligibility",
    "evaluate_eligibility",
    "AudioCaptureConfig", "AudioCaptureError", "WindowsWaveInCapture",
    "PushToTalkController", "PushToTalkLifecycleError", "PushToTalkState",
    "CapturedAudio", "FasterWhisperConfig", "FasterWhisperSubprocessSTT",
    "TranscriptionResult", "TranscriptionStatus",
    "GovernedRuntime", "SpeechRuntimeAdapter", "TranscriptSubmissionError",
    "AuthoritativeFinalResponse", "KokoroConfig", "KokoroSubprocessTTS",
    "SynthesizedAudio", "TTSRequest", "TTSResult", "TTSStatus",
    "PlaybackConfig", "PlaybackResult", "PlaybackStatus", "SubprocessWavePlayback",
    "PresentationStatus", "SpeechPresentationResult", "SpeechPresentationService",
]
