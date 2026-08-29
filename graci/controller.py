"""Task execution and durable run-state persistence."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .observation import ObservationKind, observe
from .provider import LocalLlamaCppProvider, ProviderError
from .validation import ValidationError, validate_model_result


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Controller:
    def __init__(self, config: Config | None = None, provider: Any = None,
                 observer: Any = None):
        self.config = config or Config()
        self.provider = provider or LocalLlamaCppProvider(self.config)
        self.observer = observer

    def run(self, task: str) -> dict[str, Any]:
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        record: dict[str, Any] = {
            "schema_version": 1,
            "run_id": str(uuid.uuid4()),
            "submitted_task": task,
            "started_at": _timestamp(),
            "ended_at": None,
            "execution": {
                "provider": self.config.provider,
                "node": self.config.node,
                "endpoint": self.config.endpoint,
                "model": self.config.model,
            },
            "status": "RUNNING",
            "http_status": None,
            "provider_response_model": None,
            "validated_model_result": None,
            "errors": [],
        }
        observe(self.observer, ObservationKind.TASK_STARTED, record["run_id"],
                summary="Explicit local operator turn")
        observe(self.observer, ObservationKind.MODEL_STARTED, record["run_id"],
                role="implementer", model=self.config.model, node=self.config.node)
        try:
            response = self.provider.execute(task)
            observe(self.observer, ObservationKind.MODEL_COMPLETED, record["run_id"],
                    role="implementer", model=self.config.model, node=self.config.node,
                    success=True)
            record["http_status"] = response.http_status
            record["provider_response_model"] = response.response_model
            if response.response_model != self.config.model:
                raise ValidationError(
                    f"provider response model must be {self.config.model!r}, got {response.response_model!r}"
                )
            validated = validate_model_result(response.content)
            record["validated_model_result"] = validated
            record["status"] = validated["status"]
            if validated["status"] == "FAIL":
                record["errors"].append(f"model reported failure: {validated['summary']}")
        except ProviderError as exc:
            record["http_status"] = exc.http_status
            record["status"] = "FAIL"
            record["errors"].append(f"provider_error: {exc}")
        except ValidationError as exc:
            record["status"] = "FAIL"
            record["errors"].append(f"validation_error: {exc}")
        except Exception as exc:
            record["status"] = "FAIL"
            record["errors"].append(f"unexpected_error: {type(exc).__name__}: {exc}")
        finally:
            record["ended_at"] = _timestamp()
            if record["status"] == "PASS":
                observe(self.observer, ObservationKind.TASK_COMPLETED, record["run_id"],
                        success=True)
            else:
                observe(self.observer, ObservationKind.TASK_FAILED, record["run_id"],
                        category="governed_runtime", reason=(record["errors"][-1]
                        if record["errors"] else "governed runtime failed"), success=False)
            self._persist(record)
        return record

    def _persist(self, record: dict[str, Any]) -> Path:
        directory = self.config.run_directory
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{record['run_id']}.json"
        temporary = directory / f".{record['run_id']}.tmp"
        temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
        return destination
