"""Phase 1A configuration with local-only safety constraints."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    endpoint: str = "http://127.0.0.1:8080/v1"
    model: str = "qwen3.8-27b-q4_k_m"
    provider: str = "local-llama-cpp"
    node: str = "3090-primary-localhost"
    run_directory: Path = Path("runs")
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.endpoint != "http://127.0.0.1:8080/v1":
            raise ValueError("Phase 1A endpoint must be local 3090 http://127.0.0.1:8080/v1")
        if self.provider != "local-llama-cpp" or self.node != "3090-primary-localhost":
            raise ValueError("Phase 1A provider and node identity are fixed to the local 3090")
        if not self.model.strip():
            raise ValueError("model must not be empty")
