"""Phase 2A bounded, single-agent autonomous repair loop."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .config import Config
from .provider import LocalLlamaCppProvider, ProviderError
from .tools import ToolLayer
from .validation import ValidationError


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LoopLimits:
    max_iterations: int = 8
    max_repairs: int = 2
    command_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if type(self.max_iterations) is not int or self.max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")
        if type(self.max_repairs) is not int or self.max_repairs < 1:
            raise ValueError("max_repairs must be a positive integer")
        if not isinstance(self.command_timeout_seconds, (int, float)) or self.command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be positive")


def validate_repair_decision(content: str) -> dict[str, Any]:
    try:
        decision = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"model decision is not valid JSON: {exc.msg}") from exc
    if not isinstance(decision, dict):
        raise ValidationError("model decision must be a JSON object")
    action = decision.get("action")
    fields = {
        "inspect_file": {"schema_version", "action", "target_path", "rationale"},
        "write_text": {"schema_version", "action", "target_path", "content", "rationale"},
        "run_tests": {"schema_version", "action", "rationale"},
        "finish": {"schema_version", "action", "rationale"},
    }
    if action not in fields:
        raise ValidationError("action must be inspect_file, write_text, run_tests, or finish")
    if set(decision) != fields[action]:
        raise ValidationError(f"fields for {action} must be exactly {sorted(fields[action])}")
    if type(decision["schema_version"]) is not int or decision["schema_version"] != 1:
        raise ValidationError("schema_version must be integer 1")
    if not isinstance(decision["rationale"], str) or not decision["rationale"].strip():
        raise ValidationError("rationale must be a non-empty string")
    if "target_path" in decision and (
            not isinstance(decision["target_path"], str) or not decision["target_path"].strip()):
        raise ValidationError("target_path must be a non-empty string")
    if action == "write_text" and not isinstance(decision["content"], str):
        raise ValidationError("content must be a string")
    return decision


class AutonomousRepairController:
    """Run a bounded inspect/repair/test loop inside one disposable workspace."""

    def __init__(self, workspace: Path | str, *, readable_files: Sequence[str],
                 editable_files: Sequence[str], test_directory: str = "tests",
                 limits: LoopLimits | None = None, config: Config | None = None,
                 provider: Any = None, tools: ToolLayer | None = None):
        self.config = config or Config()
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        if (self.workspace / ".git").exists():
            raise ValueError("Phase 2A workspace must not be a Git repository root")
        self.tools = tools or ToolLayer(self.workspace)
        self.provider = provider or LocalLlamaCppProvider(self.config)
        self.limits = limits or LoopLimits()
        self.test_directory = test_directory
        self._test_path = self.tools._resolve(test_directory)
        if not self._test_path.is_dir():
            raise ValueError("test_directory must be an existing workspace directory")
        self.readable_files = self._normalize_files(readable_files, "readable_files")
        self.editable_files = self._normalize_files(editable_files, "editable_files")
        if not self.editable_files or not self.editable_files.issubset(self.readable_files):
            raise ValueError("editable_files must be a non-empty subset of readable_files")

    def _normalize_files(self, paths: Sequence[str], name: str) -> frozenset[str]:
        normalized: set[str] = set()
        for path in paths:
            resolved = self.tools._resolve(path)
            if not resolved.is_file():
                raise ValueError(f"{name} entries must be existing regular files")
            normalized.add(resolved.relative_to(self.workspace).as_posix())
        return frozenset(normalized)

    def _relative_allowed(self, path: str, allowed: frozenset[str]) -> str:
        resolved = self.tools._resolve(path)
        relative = resolved.relative_to(self.workspace).as_posix()
        if relative not in allowed:
            raise PermissionError("target is not in the explicitly configured file allowlist")
        return relative

    def _context(self, record: dict[str, Any]) -> dict[str, Any]:
        recent = []
        completed_cycles = [cycle for cycle in record["cycles"] if cycle["ended_at"] is not None]
        for cycle in completed_cycles[-3:]:
            recent.append({
                "iteration": cycle["iteration"], "decision": cycle["model_decision"],
                "tool_result": self._bounded_tool_result(cycle["tool_result"]),
            })
        return {
            "readable_files": sorted(self.readable_files),
            "editable_files": sorted(self.editable_files),
            "test_directory": self.test_directory,
            "remaining_iterations": self.limits.max_iterations - len(record["cycles"]),
            "remaining_repairs": self.limits.max_repairs - record["repair_attempts"],
            "recent_cycles": recent,
        }

    @staticmethod
    def _bounded_tool_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
        """Limit evidence sent back to the model while retaining full durable evidence."""
        if result is None:
            return None
        bounded = json.loads(json.dumps(result))
        if isinstance(bounded.get("content"), str):
            bounded["content"] = bounded["content"][:12000]
        command = bounded.get("command_result")
        if isinstance(command, dict):
            for stream in ("stdout", "stderr"):
                if isinstance(command.get(stream), str):
                    command[stream] = command[stream][:12000]
        return bounded

    @staticmethod
    def _tests_passed(result: dict[str, Any]) -> bool:
        command = result.get("command_result")
        return bool(
            result.get("success") is True and result.get("status") == "PASS" and
            isinstance(command, dict) and command.get("success") is True and
            command.get("exit_code") == 0 and command.get("timed_out") is False
        )

    def run(self, task: str) -> dict[str, Any]:
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        record: dict[str, Any] = {
            "schema_version": 2, "run_id": str(uuid.uuid4()), "submitted_task": task,
            "started_at": _timestamp(), "ended_at": None,
            "execution": {"provider": self.config.provider, "node": self.config.node,
                          "endpoint": self.config.endpoint, "model": self.config.model,
                          "workspace": str(self.workspace)},
            "limits": {"max_iterations": self.limits.max_iterations,
                       "max_repairs": self.limits.max_repairs,
                       "command_timeout_seconds": self.limits.command_timeout_seconds},
            "policy": {"allowed_actions": ["inspect_file", "write_text", "run_tests", "finish"],
                       "readable_files": sorted(self.readable_files),
                       "editable_files": sorted(self.editable_files),
                       "test_directory": self.test_directory},
            "cycles": [], "repair_attempts": 0, "last_test_result": None,
            "deterministic_verification": {"status": "NOT_RUN", "basis": None},
            "terminal_reason": None, "status": "RUNNING", "errors": [],
        }
        self._persist(record)
        try:
            for iteration in range(1, self.limits.max_iterations + 1):
                cycle = {"iteration": iteration, "started_at": _timestamp(), "ended_at": None,
                         "http_status": None, "provider_response_model": None,
                         "raw_model_response": None, "model_decision": None,
                         "schema_validation": {"status": "NOT_RUN", "error": None},
                         "policy_validation": {"status": "NOT_RUN", "error": None},
                         "repair_attempt": record["repair_attempts"], "tool_result": None}
                record["cycles"].append(cycle)
                self._persist(record)
                try:
                    response = self.provider.propose_repair_decision(task, self._context(record))
                    cycle["http_status"] = response.http_status
                    cycle["provider_response_model"] = response.response_model
                    cycle["raw_model_response"] = response.content
                    if response.response_model != self.config.model:
                        raise ValidationError(
                            f"provider response model must be {self.config.model!r}, got {response.response_model!r}")
                    decision = validate_repair_decision(response.content)
                    cycle["model_decision"] = decision
                    cycle["schema_validation"]["status"] = "PASS"
                    action = decision["action"]
                    if action == "inspect_file":
                        target = self._relative_allowed(decision["target_path"], self.readable_files)
                    elif action == "write_text":
                        if record["repair_attempts"] >= self.limits.max_repairs:
                            record["terminal_reason"] = "repair_budget_exhausted"
                            cycle["policy_validation"] = {
                                "status": "FAIL", "error": "repair budget exhausted"}
                            raise RuntimeError("repair budget exhausted")
                        target = self._relative_allowed(decision["target_path"], self.editable_files)
                    else:
                        target = None
                    cycle["policy_validation"]["status"] = "PASS"
                    if action == "inspect_file":
                        cycle["tool_result"] = self.tools.read_text(target)
                    elif action == "write_text":
                        record["repair_attempts"] += 1
                        cycle["repair_attempt"] = record["repair_attempts"]
                        cycle["tool_result"] = self.tools.write_text(target, decision["content"], replace=True)
                    elif action == "run_tests":
                        cycle["tool_result"] = self.tools.run_tests(
                            start_directory=self.test_directory,
                            timeout_seconds=self.limits.command_timeout_seconds)
                        record["last_test_result"] = cycle["tool_result"]
                        if self._tests_passed(cycle["tool_result"]):
                            record["deterministic_verification"] = {
                                "status": "PASS", "basis": "governed test command exited successfully"}
                            record["terminal_reason"] = "tests_passed"
                            record["status"] = "PASS"
                        elif cycle["tool_result"].get("success") is True:
                            record["terminal_reason"] = "deterministic_verification_failure"
                            raise RuntimeError("test result did not contain consistent deterministic PASS evidence")
                    else:
                        record["terminal_reason"] = "model_finished_without_passing_tests"
                        raise RuntimeError("finish cannot establish PASS without successful tests")
                    if cycle["tool_result"] is not None and not cycle["tool_result"]["success"]:
                        if action == "run_tests":
                            if record["repair_attempts"] >= self.limits.max_repairs:
                                record["terminal_reason"] = "repair_budget_exhausted"
                                raise RuntimeError("tests failed and repair budget is exhausted")
                        else:
                            record["terminal_reason"] = "tool_failure"
                            raise RuntimeError(f"controlled tool failed: {cycle['tool_result']['error']}")
                except ProviderError as exc:
                    cycle["http_status"] = exc.http_status
                    record["terminal_reason"] = "provider_failure"
                    raise
                except ValidationError as exc:
                    cycle["schema_validation"] = {"status": "FAIL", "error": str(exc)}
                    record["terminal_reason"] = "schema_validation_failure"
                    raise
                except PermissionError as exc:
                    cycle["policy_validation"] = {"status": "FAIL", "error": str(exc)}
                    record["terminal_reason"] = "policy_violation"
                    raise
                finally:
                    cycle["ended_at"] = _timestamp()
                    self._persist(record)
                if record["status"] == "PASS":
                    break
            if record["status"] != "PASS" and record["terminal_reason"] is None:
                record["terminal_reason"] = "iteration_budget_exhausted"
                raise RuntimeError("iteration budget exhausted")
        except Exception as exc:
            record["status"] = "FAIL"
            record["deterministic_verification"] = {
                "status": "FAIL", "basis": record["terminal_reason"] or "execution failure"}
            record["errors"].append(f"{type(exc).__name__}: {exc}")
        finally:
            record["ended_at"] = _timestamp()
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
