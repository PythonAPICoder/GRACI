"""Phase 3B registry-routed implementer, read-only review, and adjudication."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .autonomous import AutonomousRepairController, LoopLimits, _timestamp
from .provider import LocalLlamaCppProvider
from .model_lifecycle import PrimaryModelLifecycle
from .observation import ObservationKind, observe
from .registry import ModelRole, Registry
from .review import adjudicate, validate_review
from .routing import Phase3BRoleRouter, RoleBinding
from .validation import ValidationError


class Phase3BController:
    """Run Qwen implementation followed by one required GLM evidence review."""

    def __init__(self, workspace: Path | str, *, registry: Registry,
                 readable_files: Sequence[str], editable_files: Sequence[str],
                 test_directory: str = "tests", limits: LoopLimits | None = None,
                 run_directory: Path = Path("runs"), implementer_provider: Any = None,
                 reviewer_provider: Any = None, memory_governance: Any = None,
                 memory_request: Any = None, observer: Any = None,
                 model_lifecycle: PrimaryModelLifecycle | None = None):
        router = Phase3BRoleRouter(registry)
        self.implementer_binding = router.resolve(ModelRole.IMPLEMENTER)
        self.reviewer_binding = router.resolve(ModelRole.REVIEWER)
        self.verifier_binding = router.resolve(ModelRole.VERIFIER)
        self.run_directory = run_directory
        self.observer = observer
        implementer_config = self._config(self.implementer_binding, run_directory)
        reviewer_config = self._config(self.reviewer_binding, run_directory)
        lifecycle = model_lifecycle or PrimaryModelLifecycle(
            self.implementer_binding.endpoint,
            timeout_seconds=max(implementer_config.timeout_seconds,
                                reviewer_config.timeout_seconds))
        self.controller = AutonomousRepairController(
            workspace, readable_files=readable_files, editable_files=editable_files,
            test_directory=test_directory, limits=limits, config=implementer_config,
            provider=implementer_provider or LocalLlamaCppProvider(
                implementer_config, model_lifecycle=lifecycle),
            memory_governance=memory_governance, memory_request=memory_request,
            observer=observer, publish_terminal=False)
        self.reviewer_provider = reviewer_provider or LocalLlamaCppProvider(
            reviewer_config, model_lifecycle=lifecycle)
        self._initial_files = self._file_snapshot()

    @staticmethod
    def _config(binding: RoleBinding, run_directory: Path) -> "RoutedConfig":
        return RoutedConfig(endpoint=binding.endpoint, model=binding.model,
                            provider=binding.provider, node=binding.node_id,
                            run_directory=run_directory)

    def _file_snapshot(self) -> dict[str, str]:
        result = {}
        limit = self.controller.limits.max_context_characters
        for relative in sorted(self.controller.readable_files):
            text = self.controller.tools.read_text(relative)
            if text.get("success"):
                result[relative] = text["content"][:limit]
        return result

    def _review_context(self, task: str, record: dict[str, Any]) -> dict[str, Any]:
        limit = self.controller.limits.max_context_characters
        modifications = []
        for cycle in record["cycles"]:
            decision = cycle.get("model_decision")
            if isinstance(decision, dict) and decision.get("action") == "write_text":
                modifications.append({"iteration": cycle["iteration"],
                                      "target_path": decision["target_path"],
                                      "rationale": decision["rationale"][:limit]})
        last_test = record.get("last_test_result") or {}
        bounded_test = {key: last_test.get(key) for key in
                        ("success", "status", "exit_code", "timed_out", "command")}
        command = last_test.get("command_result")
        if isinstance(command, dict):
            bounded_test["command_result"] = {
                "success": command.get("success"), "exit_code": command.get("exit_code"),
                "timed_out": command.get("timed_out"),
                "stdout": str(command.get("stdout", ""))[:limit],
                "stderr": str(command.get("stderr", ""))[:limit]}
        return {
            "schema_version": 1, "task": task[:limit],
            "scope": {"readable_files": sorted(self.controller.readable_files),
                      "editable_files": sorted(self.controller.editable_files)},
            "initial_files": self._initial_files, "modifications": modifications,
            "final_files": self._file_snapshot(), "deterministic_test": bounded_test,
            "deterministic_verification": record["deterministic_verification"],
            "implementer_history": [{"iteration": c["iteration"],
                                     "action": (c.get("model_decision") or {}).get("action")}
                                    for c in record["cycles"]],
            "budget_state": record["budget_state"], "terminal_reason": record["terminal_reason"],
            "memory_usage": {"status": record["memory"]["status"],
                             "selected_memory_ids": record["memory"]["selected_memory_ids"],
                             "supplied_memory_ids": record["memory"]["supplied_memory_ids"],
                             "content_supplied_to_reviewer": False},
        }

    def run(self, task: str) -> dict[str, Any]:
        record = self.controller.run(task)
        deterministic_pass = record["deterministic_verification"]["status"] == "PASS"
        record["role_routing"] = {
            "implementer": self.implementer_binding.evidence(),
            "reviewer": self.reviewer_binding.evidence(),
            "verifier": self.verifier_binding.evidence(),
            "policy": "phase3b-primary-node-only"}
        review = {"required": True, "read_only": True, "started_at": None,
                  "ended_at": None, "invocation_status": "NOT_INVOKED",
                  "context_metadata": None, "http_status": None,
                  "provider_response_model": None, "raw_result": None,
                  "parsed_result": None, "verdict": None, "findings": [], "error": None}
        record["review"] = review
        if deterministic_pass:
            context = self._review_context(task, record)
            encoded = json.dumps(context, ensure_ascii=False)
            review["context_metadata"] = {"schema_version": 1,
                                          "character_count": len(encoded),
                                          "files": sorted(self.controller.readable_files),
                                          "bounded_per_field_characters": self.controller.limits.max_context_characters}
            review["started_at"] = _timestamp()
            review["invocation_status"] = "IN_PROGRESS"
            observe(self.observer, ObservationKind.REVIEW_STARTED, record["run_id"],
                    role="reviewer", model=self.reviewer_binding.model,
                    node=self.reviewer_binding.node_id)
            self._persist(record)
            try:
                response = self.reviewer_provider.review(context)
                review["http_status"] = response.http_status
                review["provider_response_model"] = response.response_model
                review["raw_result"] = response.content[:self.controller.limits.max_context_characters]
                if response.response_model != self.reviewer_binding.model:
                    raise ValidationError(
                        f"reviewer response model must be {self.reviewer_binding.model!r}, "
                        f"got {response.response_model!r}")
                parsed = validate_review(response.content)
                review["parsed_result"], review["verdict"] = parsed, parsed["verdict"]
                review["findings"] = parsed["findings"]
                review["invocation_status"] = "COMPLETE"
            except Exception as exc:
                review["invocation_status"] = "ERROR"
                review["error"] = f"{type(exc).__name__}: {exc}"
                record["errors"].append("review_error: " + review["error"])
            finally:
                review["ended_at"] = _timestamp()
                observe(self.observer, ObservationKind.REVIEW_COMPLETED, record["run_id"],
                        role="reviewer", model=self.reviewer_binding.model,
                        node=self.reviewer_binding.node_id,
                        status=review["invocation_status"], verdict=review["verdict"],
                        finding_count=len(review["findings"]))
        observe(self.observer, ObservationKind.ADJUDICATION_STARTED, record["run_id"])
        status, reason = adjudicate(deterministic_pass, review["invocation_status"],
                                    review["verdict"])
        record["adjudication"] = {
            "at": _timestamp(), "inputs": {"deterministic_tests_passed": deterministic_pass,
                                            "review_invocation_status": review["invocation_status"],
                                            "reviewer_verdict": review["verdict"]},
            "result": status, "reason": reason}
        record["status"], record["terminal_reason"] = status, reason
        observe(self.observer, ObservationKind.ADJUDICATION_COMPLETED, record["run_id"],
                result=status, reason=reason)
        observe(self.observer, (ObservationKind.TASK_COMPLETED if status == "PASS"
                                else ObservationKind.TASK_FAILED), record["run_id"],
                category=None if status == "PASS" else "adjudication", reason=reason)
        record["ended_at"] = _timestamp()
        self._persist(record)
        return record

    def _persist(self, record: dict[str, Any]) -> Path:
        self.run_directory.mkdir(parents=True, exist_ok=True)
        destination = self.run_directory / f"{record['run_id']}.json"
        temporary = self.run_directory / f".{record['run_id']}.tmp"
        temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        os.replace(temporary, destination)
        return destination


@dataclass(frozen=True)
class RoutedConfig:
    """Provider configuration created only from a resolved immutable binding."""

    endpoint: str
    model: str
    provider: str
    node: str
    run_directory: Path
    timeout_seconds: float = 120.0
