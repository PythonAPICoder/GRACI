"""Phase 4C deterministic applicability, lifecycle, and conflict governance.

Memory content is inert data.  This module performs no semantic comparison,
prompt construction, model inference, routing, tool execution, or network access.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .memory import (CorruptionDiagnostic, MemoryCollisionError, MemoryNotFoundError,
                     MemoryStatus, MemoryStorageError, MemoryStore, MemoryType,
                     MemoryValidationError, ProvenanceOrigin, ScopeKind,
                     GOVERNANCE_SCHEMA_VERSION, PERSONALIZED_SCHEMA_VERSION,
                     _parse_timestamp, _validate_scope, validate_memory_id)


DEFAULT_SELECTION_LIMIT = 25
MAX_SELECTION_LIMIT = 100
MAX_SELECTION_SCAN = 1000
MAX_RELEVANCE_KEYS = 50
MAX_RELEVANCE_KEY_LENGTH = 128
_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)*$")
_WRITE_FIELDS = {"operation_id", "scope", "memory_type", "content", "source_ref",
                 "relevance_key", "expires_at"}
_REPLACE_FIELDS = _WRITE_FIELDS | {"supersedes_memory_id"}
_SELECT_REQUIRED_FIELDS = {"context", "relevance_keys", "allowed_memory_types"}
_SELECT_FIELDS = _SELECT_REQUIRED_FIELDS | {"limit"}
_CONTEXT_FIELDS = {"kind", "project_id", "session_id", "include_global",
                   "include_project"}
_IDEMPOTENCY_NAMESPACE = uuid.UUID("d20b938b-699b-4cd7-a7d1-d03205bd6ec8")


def validate_relevance_key(value: Any) -> str:
    """Validate a canonical lowercase dotted key without interpreting it."""
    if (not isinstance(value, str) or not 1 <= len(value) <= MAX_RELEVANCE_KEY_LENGTH or
            not _KEY.fullmatch(value)):
        raise MemoryValidationError("relevance_key must be a bounded canonical lowercase dotted key")
    return value


@dataclass(frozen=True)
class GovernanceWriteResult:
    accepted: bool
    reason: str
    created: bool
    idempotent_replay: bool
    memory_id: str | None = None
    superseded_memory_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExclusionDiagnostic:
    memory_id: str
    reason: str
    relevance_key: str | None = None


@dataclass(frozen=True)
class ConflictDiagnostic:
    relevance_key: str
    memory_type: str
    scope_specificity: str
    memory_ids: tuple[str, ...]
    reason: str = "AMBIGUOUS_ACTIVE_CANDIDATES"


@dataclass(frozen=True)
class SelectionResult:
    accepted: bool
    reason: str
    records: tuple[dict[str, Any], ...]
    applicability: tuple[dict[str, Any], ...]
    exclusions: tuple[ExclusionDiagnostic, ...]
    conflicts: tuple[ConflictDiagnostic, ...]
    corruptions: tuple[CorruptionDiagnostic, ...]
    order: tuple[str, ...]
    count: int
    limit: int
    truncated: bool
    scanned: int
    scan_limit: int

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["records"] = list(self.records)
        value["applicability"] = list(self.applicability)
        value["exclusions"] = [asdict(item) for item in self.exclusions]
        value["conflicts"] = [{**asdict(item), "memory_ids": list(item.memory_ids)}
                              for item in self.conflicts]
        value["corruptions"] = [asdict(item) for item in self.corruptions]
        value["order"] = list(self.order)
        return value


class MemoryGovernance:
    """Governed schema-v2 writes and deterministic bounded selection."""

    ORDER = ("scope_specificity_desc", "updated_at_desc", "created_at_desc",
             "memory_id_asc")

    def __init__(self, store: MemoryStore):
        self.store = store

    def write_explicit_user(self, request: Mapping[str, Any]) -> GovernanceWriteResult:
        return self._write(request, "explicit_user", "explicit_user")

    def write_runtime_observation(self, request: Mapping[str, Any]) -> GovernanceWriteResult:
        return self._write(request, "runtime", "runtime_observation")

    def write_model_proposal(self, request: Mapping[str, Any]) -> GovernanceWriteResult:
        return self._write(request, "model", "model_generated")

    def write_imported(self, request: Mapping[str, Any]) -> GovernanceWriteResult:
        return self._write(request, "imported", "imported_external")

    def replace_explicit_user(self, request: Mapping[str, Any]) -> GovernanceWriteResult:
        return self._write(request, "explicit_user_replace", "explicit_user", replacement=True)

    def replace_runtime_observation(self, request: Mapping[str, Any]) -> GovernanceWriteResult:
        return self._write(request, "runtime_replace", "runtime_observation", replacement=True)

    def _write(self, request: Mapping[str, Any], capability: str, origin: str,
               *, replacement: bool = False) -> GovernanceWriteResult:
        created_id: str | None = None
        try:
            expected = _REPLACE_FIELDS if replacement else _WRITE_FIELDS
            if not isinstance(request, Mapping) or set(request) != expected:
                raise MemoryValidationError("governance write fields do not match the strict contract")
            operation_id = validate_memory_id(request["operation_id"])
            scope = _validate_scope(request["scope"])
            relevance_key = validate_relevance_key(request["relevance_key"])
            try:
                memory_type = MemoryType(request["memory_type"]).value
            except (TypeError, ValueError) as exc:
                raise MemoryValidationError("invalid memory_type") from exc
            expires_at = request["expires_at"]
            if expires_at is not None:
                _parse_timestamp(expires_at, "expires_at")
            supersedes = None
            prior = None
            if replacement:
                supersedes = validate_memory_id(request["supersedes_memory_id"])
                prior = self.store.get(supersedes)
                if prior.get("schema_version") != GOVERNANCE_SCHEMA_VERSION:
                    raise MemoryValidationError(
                        "generic replacement cannot change personalized schema-v3 memory"
                    )
                if prior["status"] not in (MemoryStatus.ACTIVE.value,
                                           MemoryStatus.SUPERSEDED.value):
                    raise MemoryValidationError("superseded record must be active")
                if (prior["scope"] != scope or prior["relevance_key"] != relevance_key or
                        prior["memory_type"] != memory_type):
                    raise MemoryValidationError("supersession scope, key, and type must match")
                self._reject_cycle(prior)
            memory_id = str(uuid.uuid5(_IDEMPOTENCY_NAMESPACE,
                                       f"{capability}:{operation_id}"))
            proposed = self.store.new_record(
                scope=scope, memory_type=memory_type, content=request["content"],
                provenance={"origin": origin, "source_ref": request["source_ref"]},
                memory_id=memory_id, relevance_key=relevance_key,
                expires_at=expires_at, supersedes_memory_id=supersedes)
            if replacement and prior is not None and prior["status"] == MemoryStatus.SUPERSEDED.value:
                try:
                    existing = self.store.get(memory_id)
                except MemoryNotFoundError as exc:
                    raise MemoryValidationError("retired target permits only exact replacement replay") from exc
                comparable = ("scope", "memory_type", "content", "provenance",
                              "relevance_key", "expires_at", "supersedes_memory_id")
                if all(existing.get(key) == proposed.get(key) for key in comparable):
                    return GovernanceWriteResult(True, "IDEMPOTENT_REPLAY", False, True,
                                                 memory_id, supersedes)
                return GovernanceWriteResult(False, "IDEMPOTENCY_CONFLICT", False, False)
            try:
                stored = self.store.create(proposed)
                created_id = stored["memory_id"]
            except MemoryCollisionError:
                existing = self.store.get(memory_id)
                comparable = ("scope", "memory_type", "content", "provenance",
                              "relevance_key", "expires_at", "supersedes_memory_id")
                if not all(existing.get(key) == proposed.get(key) for key in comparable):
                    return GovernanceWriteResult(False, "IDEMPOTENCY_CONFLICT", False, False)
                if replacement and prior is not None and prior["status"] == MemoryStatus.ACTIVE.value:
                    self.store.update(prior["memory_id"], status=MemoryStatus.SUPERSEDED.value)
                return GovernanceWriteResult(True, "IDEMPOTENT_REPLAY", False, True,
                                             memory_id, supersedes)
            if replacement and prior is not None:
                try:
                    self.store.update(prior["memory_id"], status=MemoryStatus.SUPERSEDED.value)
                except Exception:
                    # The newly created half-transaction has never been returned as
                    # accepted; remove it and leave the prior canonical record intact.
                    self.store._path(created_id).unlink(missing_ok=True)
                    raise
            return GovernanceWriteResult(True, "REPLACED" if replacement else "CREATED",
                                         True, False, stored["memory_id"], supersedes)
        except MemoryValidationError:
            return GovernanceWriteResult(False, "INVALID_REQUEST", False, False)
        except (MemoryStorageError, MemoryNotFoundError, OSError):
            if created_id is not None:
                try:
                    self.store._path(created_id).unlink(missing_ok=True)
                except OSError:
                    pass
            return GovernanceWriteResult(False, "STORAGE_ERROR", False, False)

    def _reject_cycle(self, prior: Mapping[str, Any]) -> None:
        seen = {prior["memory_id"]}
        cursor = prior.get("supersedes_memory_id")
        while cursor is not None:
            if cursor in seen:
                raise MemoryValidationError("supersession cycle detected")
            seen.add(cursor)
            ancestor = self.store.get(cursor)
            cursor = ancestor.get("supersedes_memory_id")

    def select(self, request: Mapping[str, Any]) -> SelectionResult:
        try:
            context, keys, types, limit = self._validate_selection(request)
            # Time is obtained only from the host-configured store clock; it is not
            # part of the selection request and therefore cannot be model supplied.
            now = self.store.clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise MemoryValidationError("trusted current time must be timezone-aware")
            now = now.astimezone(timezone.utc)
        except MemoryValidationError:
            return self._failure("INVALID_REQUEST")
        try:
            listing = self.store.enumerate(limit=MAX_SELECTION_SCAN)
        except (MemoryStorageError, OSError):
            return self._failure("STORAGE_ERROR", limit=limit)
        exclusions: list[ExclusionDiagnostic] = []
        eligible: list[tuple[int, dict[str, Any], str]] = []
        for record in listing.records:
            key = record.get("relevance_key")
            if record.get("schema_version") not in (
                    GOVERNANCE_SCHEMA_VERSION, PERSONALIZED_SCHEMA_VERSION):
                exclusions.append(ExclusionDiagnostic(record["memory_id"],
                                                       "NO_RELEVANCE_METADATA"))
                continue
            if key not in keys:
                exclusions.append(ExclusionDiagnostic(record["memory_id"],
                                                       "RELEVANCE_KEY_NOT_REQUESTED", key))
                continue
            if types is not None and record["memory_type"] not in types:
                exclusions.append(ExclusionDiagnostic(record["memory_id"],
                                                       "MEMORY_TYPE_NOT_ALLOWED", key))
                continue
            specificity, reason = self._applicability(record["scope"], context)
            if specificity < 0:
                exclusions.append(ExclusionDiagnostic(record["memory_id"], reason, key))
                continue
            if record["status"] != MemoryStatus.ACTIVE.value:
                exclusions.append(ExclusionDiagnostic(record["memory_id"],
                                                       f"LIFECYCLE_{record['status'].upper()}", key))
                continue
            expires_at = record["expires_at"]
            if expires_at is not None and _parse_timestamp(expires_at, "expires_at") <= now:
                exclusions.append(ExclusionDiagnostic(record["memory_id"], "EXPIRED_AT_READ", key))
                continue
            eligible.append((specificity, record, reason))

        # Explicit replacement relationships deterministically retire referenced
        # candidates even if a prior interrupted writer left an active status.
        replaced_ids = {record["supersedes_memory_id"] for _, record, _ in eligible
                        if record["supersedes_memory_id"] is not None}
        if replaced_ids:
            kept = []
            for item in eligible:
                if item[1]["memory_id"] in replaced_ids:
                    exclusions.append(ExclusionDiagnostic(item[1]["memory_id"],
                                                           "EXPLICITLY_SUPERSEDED", item[1]["relevance_key"]))
                else:
                    kept.append(item)
            eligible = kept

        grouped: dict[tuple[str, str], list[tuple[int, dict[str, Any], str]]] = {}
        for item in eligible:
            record = item[1]
            grouped.setdefault((record["relevance_key"], record["memory_type"]), []).append(item)
        usable: list[tuple[int, dict[str, Any], str]] = []
        conflicts: list[ConflictDiagnostic] = []
        for (key, memory_type), candidates in sorted(grouped.items()):
            highest = max(item[0] for item in candidates)
            top = [item for item in candidates if item[0] == highest]
            for lower in candidates:
                if lower[0] < highest:
                    exclusions.append(ExclusionDiagnostic(lower[1]["memory_id"],
                                                           "LESS_SPECIFIC_SCOPE", key))
            if len(top) == 1:
                usable.append(top[0])
            else:
                ids = tuple(sorted(item[1]["memory_id"] for item in top))
                conflicts.append(ConflictDiagnostic(key, memory_type,
                                                     self._specificity_name(highest), ids))
                exclusions.extend(ExclusionDiagnostic(item[1]["memory_id"],
                                                       "AMBIGUOUS_CONFLICT", key) for item in top)
        usable.sort(key=lambda item: item[1]["memory_id"])
        usable.sort(key=lambda item: _parse_timestamp(item[1]["created_at"], "created_at"),
                    reverse=True)
        usable.sort(key=lambda item: _parse_timestamp(item[1]["updated_at"], "updated_at"),
                    reverse=True)
        usable.sort(key=lambda item: item[0], reverse=True)
        truncated = len(usable) > limit or listing.has_more
        selected = usable[:limit]
        applicability = tuple({"memory_id": item[1]["memory_id"],
                               "reason": item[2],
                               "specificity": self._specificity_name(item[0])}
                              for item in selected)
        records = tuple(item[1] for item in selected)
        reason = "CONFLICT" if conflicts else ("OK" if records else "NO_MATCH")
        return SelectionResult(True, reason, records, applicability, tuple(exclusions),
                               tuple(conflicts), listing.corruptions, self.ORDER,
                               len(records), limit, truncated,
                               len(listing.records) + len(listing.corruptions),
                               MAX_SELECTION_SCAN)

    @staticmethod
    def _validate_selection(request: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...], set[str] | None, int]:
        if (not isinstance(request, Mapping) or
                not _SELECT_REQUIRED_FIELDS <= set(request) <= _SELECT_FIELDS):
            raise MemoryValidationError("selection fields do not match the strict contract")
        context = request["context"]
        if not isinstance(context, Mapping) or set(context) != _CONTEXT_FIELDS:
            raise MemoryValidationError("context fields do not match the strict contract")
        context = dict(context)
        try:
            kind = ScopeKind(context["kind"]).value
        except (TypeError, ValueError) as exc:
            raise MemoryValidationError("invalid context kind") from exc
        if type(context["include_global"]) is not bool or type(context["include_project"]) is not bool:
            raise MemoryValidationError("composition flags must be booleans")
        project_id, session_id = context["project_id"], context["session_id"]
        if kind == "global":
            if project_id is not None or session_id is not None or context["include_global"] or context["include_project"]:
                raise MemoryValidationError("global context cannot compose narrower scopes")
        elif kind == "project":
            _validate_scope({"kind": "project", "id": project_id})
            if session_id is not None or context["include_project"]:
                raise MemoryValidationError("project context cannot carry a session or include_project")
        else:
            _validate_scope({"kind": "project", "id": project_id})
            _validate_scope({"kind": "session", "id": session_id})
        raw_keys = request["relevance_keys"]
        if (not isinstance(raw_keys, Sequence) or isinstance(raw_keys, (str, bytes)) or
                not 1 <= len(raw_keys) <= MAX_RELEVANCE_KEYS):
            raise MemoryValidationError("relevance_keys count is invalid")
        keys = tuple(validate_relevance_key(key) for key in raw_keys)
        if len(set(keys)) != len(keys):
            raise MemoryValidationError("relevance_keys must be unique")
        raw_types = request["allowed_memory_types"]
        types = None
        if raw_types is not None:
            if (not isinstance(raw_types, Sequence) or isinstance(raw_types, (str, bytes)) or
                    not 1 <= len(raw_types) <= len(MemoryType)):
                raise MemoryValidationError("allowed_memory_types is invalid")
            try:
                types = {MemoryType(item).value for item in raw_types}
            except (TypeError, ValueError) as exc:
                raise MemoryValidationError("allowed_memory_types is invalid") from exc
            if len(types) != len(raw_types):
                raise MemoryValidationError("allowed_memory_types must be unique")
        limit = request.get("limit", DEFAULT_SELECTION_LIMIT)
        if type(limit) is not int or not 1 <= limit <= MAX_SELECTION_LIMIT:
            raise MemoryValidationError("selection limit is invalid")
        return context, keys, types, limit

    @staticmethod
    def _applicability(scope: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[int, str]:
        kind = context["kind"]
        if scope["kind"] == "global":
            if kind == "global" or context["include_global"]:
                return 0, "APPLICABLE_GLOBAL"
            return -1, "GLOBAL_NOT_INCLUDED"
        if scope["kind"] == "project":
            if kind in ("project", "session") and scope["id"] == context["project_id"]:
                if kind == "project" or context["include_project"]:
                    return 1, "APPLICABLE_MATCHING_PROJECT"
            return -1, "PROJECT_SCOPE_MISMATCH"
        if kind == "session" and scope["id"] == context["session_id"]:
            return 2, "APPLICABLE_MATCHING_SESSION"
        return -1, "SESSION_SCOPE_MISMATCH"

    @staticmethod
    def _specificity_name(value: int) -> str:
        return ("session", "project", "global")[2 - value]

    @classmethod
    def _failure(cls, reason: str, *, limit: int = DEFAULT_SELECTION_LIMIT) -> SelectionResult:
        return SelectionResult(False, reason, (), (), (), (), (), cls.ORDER, 0,
                               limit, False, 0, MAX_SELECTION_SCAN)
