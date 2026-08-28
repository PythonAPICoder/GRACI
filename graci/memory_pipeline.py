"""Phase 4B governed durable-memory ingress and exact bounded retrieval.

Memory remains untrusted data.  Nothing in this module executes or interprets
content, changes routing/policy, or supplies memory to a model.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

from .memory import (MAX_CONTENT_BYTES, CorruptionDiagnostic, MemoryCollisionError,
                     MemoryNotFoundError, MemoryStatus, MemoryStorageError,
                     MemoryStore, MemoryType, MemoryValidationError,
                     ProvenanceOrigin, _parse_timestamp, _validate_provenance,
                     _validate_scope, validate_memory_id)


DEFAULT_RETRIEVAL_LIMIT = 25
MAX_RETRIEVAL_LIMIT = 100
MAX_RETRIEVAL_SCAN = 1000
_WRITE_FIELDS = {"operation_id", "scope", "memory_type", "content", "source_ref"}
_QUERY_FIELDS = {"memory_id", "scope", "memory_type", "provenance", "status",
                 "created_at_gte", "created_at_lte", "updated_at_gte",
                 "updated_at_lte", "limit"}
_IDEMPOTENCY_NAMESPACE = uuid.UUID("5a2bc00c-d11d-4b53-8db4-a6b8401cd45a")


@dataclass(frozen=True)
class WriteResult:
    accepted: bool
    reason: str
    created: bool
    idempotent_replay: bool
    memory_id: str | None = None
    version: int | None = None
    scope: dict[str, Any] | None = None
    memory_type: str | None = None
    provenance: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    accepted: bool
    reason: str
    records: tuple[dict[str, Any], ...]
    applied_filters: dict[str, Any]
    order: tuple[str, ...]
    count: int
    limit: int
    truncated: bool
    diagnostics: tuple[CorruptionDiagnostic, ...]
    scanned: int
    scan_limit: int

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["order"] = list(self.order)
        value["records"] = list(self.records)
        value["diagnostics"] = [asdict(item) for item in self.diagnostics]
        return value


class MemoryPipeline:
    """Explicit write capabilities plus deterministic exact retrieval."""

    ORDER = ("updated_at_desc", "created_at_desc", "memory_id_asc")

    def __init__(self, store: MemoryStore):
        self.store = store

    def write_explicit_user(self, request: Mapping[str, Any]) -> WriteResult:
        return self._write(request, "trusted_explicit_user", ProvenanceOrigin.USER.value)

    def write_runtime_observation(self, request: Mapping[str, Any]) -> WriteResult:
        return self._write(request, "trusted_runtime", ProvenanceOrigin.RUNTIME.value)

    def write_model_proposal(self, request: Mapping[str, Any]) -> WriteResult:
        return self._write(request, "model_proposal", ProvenanceOrigin.MODEL.value)

    def write_imported(self, request: Mapping[str, Any]) -> WriteResult:
        return self._write(request, "trusted_import", ProvenanceOrigin.IMPORTED.value)

    def _write(self, request: Mapping[str, Any], capability: str, origin: str) -> WriteResult:
        try:
            if not isinstance(request, Mapping) or set(request) != _WRITE_FIELDS:
                raise MemoryValidationError("write request fields do not match the strict contract")
            operation_id = validate_memory_id(request["operation_id"])
            scope = _validate_scope(request["scope"])
            if not isinstance(request["memory_type"], str):
                raise MemoryValidationError("memory_type must be a string")
            try:
                memory_type = MemoryType(request["memory_type"]).value
            except ValueError as exc:
                raise MemoryValidationError("invalid memory_type") from exc
            content = request["content"]
            if not isinstance(content, str) or not content.strip():
                raise MemoryValidationError("content must be a non-empty string")
            try:
                content_bytes = content.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise MemoryValidationError("content must be valid UTF-8 text") from exc
            if len(content_bytes) > MAX_CONTENT_BYTES:
                raise MemoryValidationError(f"content exceeds {MAX_CONTENT_BYTES} UTF-8 bytes")
            provenance = _validate_provenance({"origin": origin,
                                               "source_ref": request["source_ref"]})
            memory_id = str(uuid.uuid5(_IDEMPOTENCY_NAMESPACE,
                                       f"{capability}:{operation_id}"))
            proposed = self.store.new_record(scope=scope, memory_type=memory_type,
                                             content=content, provenance=provenance,
                                             memory_id=memory_id)
            try:
                stored = self.store.create(proposed)
                return self._write_success(stored, created=True, replay=False)
            except MemoryCollisionError:
                existing = self.store.get(memory_id)
                comparable = ("scope", "memory_type", "content", "provenance")
                if all(existing[key] == proposed[key] for key in comparable):
                    return self._write_success(existing, created=False, replay=True)
                return WriteResult(False, "IDEMPOTENCY_CONFLICT", False, False)
        except MemoryValidationError:
            return WriteResult(False, "INVALID_REQUEST", False, False)
        except (MemoryStorageError, MemoryNotFoundError, OSError):
            return WriteResult(False, "STORAGE_ERROR", False, False)

    @staticmethod
    def _write_success(record: Mapping[str, Any], *, created: bool,
                       replay: bool) -> WriteResult:
        return WriteResult(True, "CREATED" if created else "IDEMPOTENT_REPLAY",
                           created, replay, record["memory_id"], record["version"],
                           dict(record["scope"]), record["memory_type"],
                           record["provenance"]["origin"])

    def retrieve(self, criteria: Mapping[str, Any]) -> RetrievalResult:
        try:
            filters, limit = self._validate_query(criteria)
        except MemoryValidationError:
            return self._retrieval_failure("INVALID_QUERY")
        try:
            if "memory_id" in filters:
                diagnostics: tuple[CorruptionDiagnostic, ...] = ()
                try:
                    candidates = [self.store.get(filters["memory_id"])]
                except MemoryNotFoundError:
                    candidates = []
                except MemoryValidationError as exc:
                    candidates = []
                    diagnostics = (CorruptionDiagnostic(filters["memory_id"],
                                   f"MemoryValidationError: {exc}"),)
                scan_truncated = False
            else:
                listing = self.store.enumerate(limit=MAX_RETRIEVAL_SCAN)
                candidates = list(listing.records)
                diagnostics = listing.corruptions
                scan_truncated = listing.has_more
            matched = [item for item in candidates if self._matches(item, filters)]
            matched.sort(key=lambda item: item["memory_id"])
            matched.sort(key=lambda item: _parse_timestamp(item["created_at"], "created_at"),
                         reverse=True)
            matched.sort(key=lambda item: _parse_timestamp(item["updated_at"], "updated_at"),
                         reverse=True)
            result_truncated = len(matched) > limit
            selected = tuple(matched[:limit])
            return RetrievalResult(True, "OK" if selected else "NO_MATCH", selected,
                                   filters, self.ORDER, len(selected), limit,
                                   result_truncated or scan_truncated, diagnostics,
                                   len(candidates), MAX_RETRIEVAL_SCAN)
        except (MemoryStorageError, OSError):
            return self._retrieval_failure("STORAGE_ERROR", filters, limit)

    def _validate_query(self, criteria: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
        if not isinstance(criteria, Mapping) or not set(criteria) <= _QUERY_FIELDS:
            raise MemoryValidationError("retrieval fields do not match the strict contract")
        filters = dict(criteria)
        limit = filters.pop("limit", DEFAULT_RETRIEVAL_LIMIT)
        if type(limit) is not int or not 1 <= limit <= MAX_RETRIEVAL_LIMIT:
            raise MemoryValidationError("retrieval limit is outside the allowed range")
        if "memory_id" in filters:
            filters["memory_id"] = validate_memory_id(filters["memory_id"])
        if "scope" not in filters:
            raise MemoryValidationError("explicit scope is required")
        filters["scope"] = _validate_scope(filters["scope"])
        if "memory_type" in filters:
            try:
                filters["memory_type"] = MemoryType(filters["memory_type"]).value
            except (TypeError, ValueError) as exc:
                raise MemoryValidationError("invalid memory_type") from exc
        if "provenance" in filters:
            try:
                filters["provenance"] = ProvenanceOrigin(filters["provenance"]).value
            except (TypeError, ValueError) as exc:
                raise MemoryValidationError("invalid provenance") from exc
        if "status" in filters:
            try:
                filters["status"] = MemoryStatus(filters["status"]).value
            except (TypeError, ValueError) as exc:
                raise MemoryValidationError("invalid status") from exc
        else:
            filters["status"] = MemoryStatus.ACTIVE.value
        for field in ("created_at_gte", "created_at_lte", "updated_at_gte", "updated_at_lte"):
            if field in filters:
                _parse_timestamp(filters[field], field)
        for prefix in ("created_at", "updated_at"):
            low, high = filters.get(f"{prefix}_gte"), filters.get(f"{prefix}_lte")
            if low and high and _parse_timestamp(low, prefix) > _parse_timestamp(high, prefix):
                raise MemoryValidationError("time lower bound exceeds upper bound")
        return filters, limit

    @staticmethod
    def _matches(record: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        if "memory_id" in filters and record["memory_id"] != filters["memory_id"]:
            return False
        if record["scope"] != filters["scope"]:
            return False
        for key in ("memory_type", "status"):
            if key in filters and record[key] != filters[key]:
                return False
        if "provenance" in filters and record["provenance"]["origin"] != filters["provenance"]:
            return False
        for field in ("created_at", "updated_at"):
            observed = _parse_timestamp(record[field], field)
            if (f"{field}_gte" in filters and
                    observed < _parse_timestamp(filters[f"{field}_gte"], f"{field}_gte")):
                return False
            if (f"{field}_lte" in filters and
                    observed > _parse_timestamp(filters[f"{field}_lte"], f"{field}_lte")):
                return False
        return True

    @classmethod
    def _retrieval_failure(cls, reason: str, filters: dict[str, Any] | None = None,
                           limit: int = DEFAULT_RETRIEVAL_LIMIT) -> RetrievalResult:
        return RetrievalResult(False, reason, (), filters or {}, cls.ORDER, 0, limit,
                               False, (), 0, MAX_RETRIEVAL_SCAN)
