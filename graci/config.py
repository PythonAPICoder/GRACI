"""Phase 1A configuration with local-only safety constraints."""

from dataclasses import dataclass
from pathlib import Path

from .registry import LOCAL_PROVIDER_ID, PRIMARY_BASE_URL, QWEN_MODEL_ID


@dataclass(frozen=True)
class Config:
    endpoint: str = PRIMARY_BASE_URL
    model: str = QWEN_MODEL_ID
    provider: str = LOCAL_PROVIDER_ID
    node: str = "3090-primary-localhost"
    run_directory: Path = Path("runs")
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.endpoint != PRIMARY_BASE_URL:
            raise ValueError("Phase 1A endpoint must be local 3090 http://127.0.0.1:8080/v1")
        if self.provider != LOCAL_PROVIDER_ID or self.node != "3090-primary-localhost":
            raise ValueError("Phase 1A provider and node identity are fixed to the local 3090")
        if self.model != QWEN_MODEL_ID:
            raise ValueError("Phase 1 model must be qwen3.8-27b-q4_k_m")
