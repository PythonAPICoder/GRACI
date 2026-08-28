"""Bounded, governed autonomous repair state machine (Phases 2A and 2B)."""
from __future__ import annotations

import hashlib, json, os, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .config import Config
from .provider import LocalLlamaCppProvider, ProviderError
from .memory_execution import prepare_execution_memory
from .observation import ObservationKind, observe
from .tools import ToolLayer
from .validation import ValidationError

def _timestamp(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

@dataclass(frozen=True)
class LoopLimits:
    max_iterations: int = 12
    max_model_calls: int = 12
    max_file_inspections: int = 6
    max_file_modifications: int = 4
    max_repairs: int = 2
    command_timeout_seconds: float = 30.0
    max_context_characters: int = 12000
    max_recent_cycles: int = 6
    max_identical_actions: int = 2
    def __post_init__(self):
        for name in ("max_iterations", "max_model_calls", "max_file_inspections",
                     "max_file_modifications", "max_repairs", "max_context_characters",
                     "max_recent_cycles", "max_identical_actions"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.command_timeout_seconds, (int, float)) or self.command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be positive")

def validate_repair_decision(content: str) -> dict[str, Any]:
    try: decision = json.loads(content)
    except json.JSONDecodeError as exc: raise ValidationError(f"model decision is not valid JSON: {exc.msg}") from exc
    if not isinstance(decision, dict): raise ValidationError("model decision must be a JSON object")
    fields = {
        "list_files": {"schema_version", "action", "rationale"},
        "inspect_file": {"schema_version", "action", "target_path", "rationale"},
        "write_text": {"schema_version", "action", "target_path", "content", "rationale"},
        "run_tests": {"schema_version", "action", "rationale"},
        "finish": {"schema_version", "action", "rationale"}}
    action = decision.get("action")
    if action not in fields: raise ValidationError("action must be list_files, inspect_file, write_text, run_tests, or finish")
    if set(decision) != fields[action]: raise ValidationError(f"fields for {action} must be exactly {sorted(fields[action])}")
    if type(decision["schema_version"]) is not int or decision["schema_version"] != 1: raise ValidationError("schema_version must be integer 1")
    if not isinstance(decision["rationale"], str) or not decision["rationale"].strip(): raise ValidationError("rationale must be a non-empty string")
    if "target_path" in decision and (not isinstance(decision["target_path"], str) or not decision["target_path"].strip()): raise ValidationError("target_path must be a non-empty string")
    if action == "write_text" and not isinstance(decision["content"], str): raise ValidationError("content must be a string")
    return decision

class AutonomousRepairController:
    """One explicitly validated model decision per bounded cycle."""
    def __init__(self, workspace: Path | str, *, readable_files: Sequence[str], editable_files: Sequence[str],
                 test_directory="tests", limits=None, config=None, provider=None, tools=None,
                 memory_governance=None, memory_request=None, observer=None,
                 publish_terminal=True):
        self.config, self.limits = config or Config(), limits or LoopLimits()
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir(): raise ValueError("workspace must be an existing directory")
        if (self.workspace / ".git").exists(): raise ValueError("autonomous workspace must not be a Git repository root")
        self.tools, self.provider = tools or ToolLayer(self.workspace), provider or LocalLlamaCppProvider(self.config)
        self.memory_governance, self.memory_request = memory_governance, memory_request
        self.observer, self.publish_terminal = observer, publish_terminal
        self.test_directory = test_directory
        if not self.tools._resolve(test_directory).is_dir(): raise ValueError("test_directory must be an existing workspace directory")
        self.readable_files = self._normalize(readable_files, "readable_files")
        self.editable_files = self._normalize(editable_files, "editable_files")
        if not self.editable_files or not self.editable_files.issubset(self.readable_files): raise ValueError("editable_files must be a non-empty subset of readable_files")

    def _normalize(self, paths, name):
        result = set()
        for path in paths:
            resolved = self.tools._resolve(path)
            if not resolved.is_file(): raise ValueError(f"{name} entries must be existing regular files")
            result.add(resolved.relative_to(self.workspace).as_posix())
        return frozenset(result)

    def _allowed(self, path, allowed):
        relative = self.tools._resolve(path).relative_to(self.workspace).as_posix()
        if relative not in allowed: raise PermissionError("target is not in the explicitly configured file allowlist")
        return relative

    def _budgets(self, record):
        used, limits = record["budget_usage"], record["limits"]
        keys = ("iterations", "model_calls", "file_inspections", "file_modifications", "repairs")
        return {"consumed": dict(used), "remaining": {key: limits["max_" + key] - used[key] for key in keys}}

    def _bounded(self, value, record):
        if value is None: return None
        result, limit = json.loads(json.dumps(value)), self.limits.max_context_characters
        owners = [(result, "content")]
        if isinstance(result.get("command_result"), dict): owners += [(result["command_result"], "stdout"), (result["command_result"], "stderr")]
        for owner, field in owners:
            if isinstance(owner.get(field), str) and len(owner[field]) > limit:
                owner[field] = owner[field][:limit]
                record["context_events"].append({"at": _timestamp(), "kind": "truncated", "field": field, "limit": limit})
        return result

    def _context(self, record, memory_envelope=None):
        completed = [c for c in record["cycles"] if c["ended_at"]]
        recent = [{"iteration": c["iteration"], "decision": c["model_decision"], "tool_result": self._bounded(c["tool_result"], record)}
                  for c in completed[-self.limits.max_recent_cycles:]]
        return {"readable_files": sorted(self.readable_files), "editable_files": sorted(self.editable_files),
                "test_directory": self.test_directory, "budget_state": self._budgets(record), "recent_cycles": recent,
                "memory_context": memory_envelope}

    @staticmethod
    def _passed(result):
        command = result.get("command_result")
        return bool(result.get("success") is True and result.get("status") == "PASS" and isinstance(command, dict)
                    and command.get("success") is True and command.get("exit_code") == 0 and command.get("timed_out") is False)

    def run(self, task):
        if not isinstance(task, str) or not task.strip(): raise ValueError("task must be a non-empty string")
        names = ("max_iterations", "max_model_calls", "max_file_inspections", "max_file_modifications", "max_repairs",
                 "command_timeout_seconds", "max_context_characters", "max_recent_cycles", "max_identical_actions")
        record = {"schema_version": 3, "run_id": str(uuid.uuid4()), "submitted_task": task, "started_at": _timestamp(), "ended_at": None,
            "execution": {"provider": self.config.provider, "node": self.config.node, "endpoint": self.config.endpoint, "model": self.config.model, "workspace": str(self.workspace)},
            "limits": {n: getattr(self.limits, n) for n in names},
            "policy": {"allowed_actions": ["list_files", "inspect_file", "write_text", "run_tests", "finish"], "readable_files": sorted(self.readable_files), "editable_files": sorted(self.editable_files), "test_directory": self.test_directory},
            "cycles": [], "budget_usage": {"iterations": 0, "model_calls": 0, "file_inspections": 0, "file_modifications": 0, "repairs": 0},
            "budget_state": None, "repair_attempts": 0, "inspected_paths": [], "modified_paths": [], "test_results": [], "context_events": [], "progress_guard_events": [], "last_test_result": None,
            "deterministic_verification": {"status": "NOT_RUN", "basis": None}, "terminal_reason": None, "status": "RUNNING", "errors": []}
        observe(self.observer, ObservationKind.TASK_STARTED, record["run_id"],
                summary="GRACI runtime task")
        observe(self.observer, ObservationKind.PLANNING_STARTED, record["run_id"])
        observe(self.observer, ObservationKind.MEMORY_STARTED, record["run_id"])
        memory = prepare_execution_memory(self.memory_governance, self.memory_request)
        record["memory"] = memory.evidence
        observe(self.observer, ObservationKind.MEMORY_COMPLETED, record["run_id"],
                requested=memory.evidence["requested"], mode=memory.evidence["mode"],
                relevance_keys=tuple(memory.evidence["requested_relevance_keys"]),
                status=memory.evidence["status"],
                selected_ids=tuple(memory.evidence["selected_memory_ids"]),
                supplied_ids=tuple(memory.evidence["supplied_memory_ids"]),
                supplied_count=len(memory.evidence["supplied_memory_ids"]),
                context_characters=memory.evidence["context_character_count"],
                conflict_count=len(memory.evidence["conflicts"]),
                corruption_count=len(memory.evidence["corruptions"]))
        if memory.accepted and memory.evidence["status"] in {
                "MEMORY_UNAVAILABLE", "MEMORY_CONTEXT_REJECTED"}:
            observe(self.observer, ObservationKind.TASK_WARNING, record["run_id"],
                    reason=memory.evidence["status"])
        if not memory.accepted:
            record["terminal_reason"], record["status"] = "required_memory_unavailable", "FAIL"
            record["deterministic_verification"] = {"status": "FAIL", "basis": "required memory failed closed before inference"}
            record["ended_at"] = _timestamp(); self._persist(record)
            observe(self.observer, ObservationKind.TASK_FAILED, record["run_id"],
                    category="required_memory", reason=record["terminal_reason"])
            return record
        fingerprints, failed, changes = [], False, 0
        self._persist(record)
        try:
            for iteration in range(1, self.limits.max_iterations + 1):
                cycle = {"iteration": iteration, "started_at": _timestamp(), "ended_at": None, "http_status": None, "provider_response_model": None, "raw_model_response": None, "model_decision": None,
                         "schema_validation": {"status": "NOT_RUN", "error": None}, "action_validation": {"status": "NOT_RUN", "error": None}, "workspace_validation": {"status": "NOT_RUN", "error": None},
                         "policy_validation": {"status": "NOT_RUN", "error": None}, "budget_validation": {"status": "NOT_RUN", "error": None}, "budget_before": self._budgets(record), "budget_after": None,
                         "repair_attempt": record["repair_attempts"], "tool_result": None}
                record["cycles"].append(cycle); record["budget_usage"]["iterations"] += 1; self._persist(record)
                try:
                    if record["budget_usage"]["model_calls"] >= self.limits.max_model_calls:
                        record["terminal_reason"] = "model_call_budget_exhausted"; cycle["budget_validation"] = {"status": "FAIL", "error": "model call budget exhausted"}; raise RuntimeError("model call budget exhausted")
                    record["budget_usage"]["model_calls"] += 1
                    observe(self.observer, ObservationKind.MODEL_STARTED, record["run_id"],
                            role="implementer", model=self.config.model, node=self.config.node)
                    response = self.provider.propose_repair_decision(task, self._context(record, memory.envelope))
                    cycle["http_status"], cycle["provider_response_model"], cycle["raw_model_response"] = response.http_status, response.response_model, response.content
                    if response.response_model != self.config.model: raise ValidationError(f"provider response model must be {self.config.model!r}, got {response.response_model!r}")
                    decision = validate_repair_decision(response.content); cycle["model_decision"] = decision; cycle["schema_validation"]["status"] = "PASS"
                    observe(self.observer, ObservationKind.MODEL_COMPLETED, record["run_id"],
                            role="implementer", model=self.config.model, node=self.config.node,
                            success=True)
                    action = decision["action"]; cycle["action_validation"]["status"] = "PASS"; target = None
                    if action == "inspect_file": target = self._allowed(decision["target_path"], self.readable_files)
                    elif action == "write_text": target = self._allowed(decision["target_path"], self.editable_files)
                    cycle["workspace_validation"]["status"] = cycle["policy_validation"]["status"] = "PASS"
                    budget = {"inspect_file": "file_inspections", "write_text": "file_modifications"}.get(action)
                    if budget and record["budget_usage"][budget] >= record["limits"]["max_" + budget]:
                        record["terminal_reason"] = budget[:-1] + "_budget_exhausted"; cycle["budget_validation"] = {"status": "FAIL", "error": record["terminal_reason"]}; raise RuntimeError(record["terminal_reason"])
                    if action == "write_text" and failed and record["budget_usage"]["repairs"] >= self.limits.max_repairs:
                        record["terminal_reason"] = "repair_budget_exhausted"; cycle["budget_validation"] = {"status": "FAIL", "error": "repair budget exhausted"}; raise RuntimeError("repair budget exhausted")
                    cycle["budget_validation"]["status"] = "PASS"
                    material = {k: v for k, v in decision.items() if k != "rationale"}; fingerprint = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
                    if len(fingerprints) >= self.limits.max_identical_actions and all(x == fingerprint for x in fingerprints[-self.limits.max_identical_actions:]):
                        record["progress_guard_events"].append({"at": _timestamp(), "kind": "repeated_identical_action"}); record["terminal_reason"] = "repeated_identical_action"; raise RuntimeError("identical action repeated without progress")
                    if action == "run_tests" and failed and changes == 0:
                        record["progress_guard_events"].append({"at": _timestamp(), "kind": "retest_without_change"}); record["terminal_reason"] = "retest_without_change"; raise RuntimeError("tests repeated after failure without modification")
                    if action == "finish":
                        record["progress_guard_events"].append({"at": _timestamp(), "kind": "premature_finish"}); record["terminal_reason"] = "model_finished_without_passing_tests"; raise RuntimeError("finish cannot establish PASS without successful tests")
                    fingerprints.append(fingerprint)
                    category = {"list_files": "inspect", "inspect_file": "read", "write_text": "edit", "run_tests": "test"}.get(action)
                    if category:
                        if action == "run_tests": observe(self.observer, ObservationKind.TESTS_STARTED, record["run_id"])
                        else: observe(self.observer, ObservationKind.TOOL_STARTED, record["run_id"], category=category, action=action, target=target)
                    if action == "list_files": cycle["tool_result"] = {"tool": "list_allowed_files", "success": True, "entries": [{"path": p, "editable": p in self.editable_files} for p in sorted(self.readable_files)], "started_at": _timestamp(), "ended_at": _timestamp(), "error": None}
                    elif action == "inspect_file":
                        record["budget_usage"]["file_inspections"] += 1; record["inspected_paths"].append(target); cycle["tool_result"] = self.tools.read_text(target)
                    elif action == "write_text":
                        record["budget_usage"]["file_modifications"] += 1; record["repair_attempts"] += 1
                        if failed: record["budget_usage"]["repairs"] += 1
                        cycle["repair_attempt"] = record["repair_attempts"]; record["modified_paths"].append(target); cycle["tool_result"] = self.tools.write_text(target, decision["content"], replace=True); changes += 1
                    elif action == "run_tests":
                        cycle["tool_result"] = self.tools.run_tests(start_directory=self.test_directory, timeout_seconds=self.limits.command_timeout_seconds)
                        record["last_test_result"] = cycle["tool_result"]; record["test_results"].append(cycle["tool_result"])
                        if self._passed(cycle["tool_result"]): record["deterministic_verification"] = {"status": "PASS", "basis": "governed test command exited successfully"}; record["terminal_reason"], record["status"] = "tests_passed", "PASS"
                        elif cycle["tool_result"].get("success") is True: record["terminal_reason"] = "deterministic_verification_failure"; raise RuntimeError("test result did not contain consistent deterministic PASS evidence")
                        else:
                            failed, changes = True, 0
                    if action == "run_tests":
                        observe(self.observer, ObservationKind.TESTS_COMPLETED, record["run_id"],
                                passed=self._passed(cycle["tool_result"]),
                                reason=cycle["tool_result"].get("error"))
                    elif category:
                        observe(self.observer, ObservationKind.TOOL_COMPLETED, record["run_id"],
                                action=action, success=cycle["tool_result"]["success"],
                                error_code=cycle["tool_result"].get("error_classification"),
                                reason=cycle["tool_result"].get("error"))
                    if cycle["tool_result"] is not None and not cycle["tool_result"]["success"] and action != "run_tests": record["terminal_reason"] = "tool_failure"; raise RuntimeError(f"controlled tool failed: {cycle['tool_result']['error']}")
                except ProviderError as exc: cycle["http_status"], record["terminal_reason"] = exc.http_status, "provider_failure"; raise
                except ValidationError as exc: cycle["schema_validation"] = {"status": "FAIL", "error": str(exc)}; record["terminal_reason"] = "schema_validation_failure"; raise
                except PermissionError as exc: cycle["workspace_validation"] = cycle["policy_validation"] = {"status": "FAIL", "error": str(exc)}; record["terminal_reason"] = "policy_violation"; raise
                finally: cycle["budget_after"], cycle["ended_at"] = self._budgets(record), _timestamp(); self._persist(record)
                if record["status"] == "PASS": break
            if record["status"] != "PASS" and record["terminal_reason"] is None: record["terminal_reason"] = "iteration_budget_exhausted"; raise RuntimeError("iteration budget exhausted")
        except Exception as exc:
            if record["terminal_reason"] is None:
                record["terminal_reason"] = "execution_failure"
            record["status"] = "FAIL"; record["deterministic_verification"] = {"status": "FAIL", "basis": record["terminal_reason"] or "execution failure"}; record["errors"].append(f"{type(exc).__name__}: {exc}")
        finally: record["budget_state"], record["ended_at"] = self._budgets(record), _timestamp(); self._persist(record)
        if self.publish_terminal:
            observe(self.observer, (ObservationKind.TASK_COMPLETED if record["status"] == "PASS"
                                    else ObservationKind.TASK_FAILED), record["run_id"],
                    category=None if record["status"] == "PASS" else "execution",
                    reason=record["terminal_reason"])
        return record

    def _persist(self, record):
        directory = self.config.run_directory; directory.mkdir(parents=True, exist_ok=True)
        destination, temporary = directory / f"{record['run_id']}.json", directory / f".{record['run_id']}.tmp"
        temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"); os.replace(temporary, destination); return destination
