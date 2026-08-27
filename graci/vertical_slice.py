"""Phase 1C bounded model-to-tool vertical slice."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .provider import LocalLlamaCppProvider, ProviderError
from .tools import ToolLayer
from .validation import ValidationError


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_text_action(content: str) -> dict[str, Any]:
    try:
        action = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"model action is not valid JSON: {exc.msg}") from exc
    if not isinstance(action, dict):
        raise ValidationError("model action must be a JSON object")
    required = {"schema_version", "action", "target_path", "content", "rationale"}
    if set(action) != required:
        raise ValidationError(f"model action fields must be exactly {sorted(required)}")
    if type(action["schema_version"]) is not int or action["schema_version"] != 1:
        raise ValidationError("schema_version must be integer 1")
    if action["action"] != "write_text":
        raise ValidationError("action must be write_text")
    if not isinstance(action["target_path"], str) or not action["target_path"].strip():
        raise ValidationError("target_path must be a non-empty string")
    if not isinstance(action["content"], str):
        raise ValidationError("content must be a string")
    if not isinstance(action["rationale"], str) or not action["rationale"].strip():
        raise ValidationError("rationale must be a non-empty string")
    return action


class VerticalSliceController:
    """Execute exactly one configured text-file action and verify it independently."""

    def __init__(self, workspace: Path | str, allowed_target: str, *,
                 config: Config | None = None, provider: Any = None,
                 tools: ToolLayer | None = None):
        self.config = config or Config()
        self.workspace = Path(workspace).resolve(strict=True)
        if (self.workspace / ".git").exists():
            raise ValueError("Phase 1C workspace must not be a Git repository root")
        self.allowed_target = allowed_target
        self.tools = tools or ToolLayer(self.workspace)
        self.provider = provider or LocalLlamaCppProvider(self.config)
        resolved = self.tools._resolve(allowed_target)
        if resolved == self.workspace or not allowed_target.strip():
            raise ValueError("allowed_target must identify a workspace-contained file")

    def run(self, task: str) -> dict[str, Any]:
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        record: dict[str, Any] = {
            "schema_version": 1, "run_id": str(uuid.uuid4()),
            "submitted_task": task, "started_at": _timestamp(), "ended_at": None,
            "execution": {"provider": self.config.provider, "node": self.config.node,
                          "endpoint": self.config.endpoint, "model": self.config.model,
                          "workspace": str(self.workspace), "allowed_target": self.allowed_target},
            "http_status": None, "provider_response_model": None,
            "proposed_action": None,
            "validation": {"schema": "NOT_RUN", "policy": "NOT_RUN", "error": None},
            "tool_result": None, "verification": {"status": "NOT_RUN", "matches": False,
                                                    "expected_content": None,
                                                    "observed_content": None, "error": None},
            "status": "RUNNING", "errors": [],
        }
        self._persist(record)
        try:
            response = self.provider.propose_text_action(task, self.allowed_target)
            record["http_status"] = response.http_status
            record["provider_response_model"] = response.response_model
            if response.response_model != self.config.model:
                raise ValidationError(
                    f"provider response model must be {self.config.model!r}, got {response.response_model!r}")
            action = validate_text_action(response.content)
            record["proposed_action"] = action
            record["validation"]["schema"] = "PASS"
            proposed = self.tools._resolve(action["target_path"])
            allowed = self.tools._resolve(self.allowed_target)
            if proposed != allowed:
                raise PermissionError("proposed target does not equal the explicitly allowed target")
            record["validation"]["policy"] = "PASS"
            record["verification"]["expected_content"] = action["content"]
            record["tool_result"] = self.tools.write_text(
                action["target_path"], action["content"], replace=proposed.exists())
            if not record["tool_result"]["success"]:
                raise RuntimeError(f"controlled tool failed: {record['tool_result']['error']}")
            observed = self.tools.read_text(action["target_path"])
            if not observed["success"]:
                raise RuntimeError(f"verification read failed: {observed['error']}")
            record["verification"]["observed_content"] = observed["content"]
            record["verification"]["matches"] = observed["content"] == action["content"]
            record["verification"]["status"] = "PASS" if record["verification"]["matches"] else "FAIL"
            if not record["verification"]["matches"]:
                raise RuntimeError("deterministic verification content mismatch")
            record["status"] = "PASS"
        except ProviderError as exc:
            record["http_status"] = exc.http_status
            self._fail(record, "provider_error", exc)
        except ValidationError as exc:
            record["validation"]["schema"] = "FAIL"
            record["validation"]["error"] = str(exc)
            self._fail(record, "validation_error", exc)
        except PermissionError as exc:
            record["validation"]["policy"] = "FAIL"
            record["validation"]["error"] = str(exc)
            self._fail(record, "policy_error", exc)
        except Exception as exc:
            if record["verification"]["status"] == "NOT_RUN" and record["tool_result"] is not None:
                record["verification"]["status"] = "FAIL"
                record["verification"]["error"] = str(exc)
            self._fail(record, "execution_error", exc)
        finally:
            record["ended_at"] = _timestamp()
            self._persist(record)
        return record

    @staticmethod
    def _fail(record: dict[str, Any], category: str, exc: Exception) -> None:
        record["status"] = "FAIL"
        record["errors"].append(f"{category}: {type(exc).__name__}: {exc}")

    def _persist(self, record: dict[str, Any]) -> Path:
        directory = self.config.run_directory
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{record['run_id']}.json"
        temporary = directory / f".{record['run_id']}.tmp"
        temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
        return destination
