"""Synthetic-only adapter from personalized memory to bounded ordinary-turn context.

This adapter retrieves only explicitly labelled synthetic records, validates them as
inert context, and fails closed whenever the request, source, or serialized context
cannot be bounded. It never grants authority, persists data, or infers relevance.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .memory import (MemoryValidationError, PersonalizedKind, ScopeKind,
                     _validate_scope, validate_memory_id)
from .memory_context import (AUTHORITY_DENIALS, MAX_MEMORY_CONTEXT_BYTES,
                             MAX_MEMORY_CONTEXT_RECORDS,
                             MEMORY_CONTEXT_CLASSIFICATION,
                             MEMORY_CONTEXT_SCHEMA_VERSION,
                             MemoryContextResolution, memory_context_sha256,
                             validate_memory_context)
from .memory_governance import validate_relevance_key as _validate_relevance_key
from .personalized_memory import (PersonalizedRetrievalRequest,
                                  SyntheticPersonalizedMemoryRepository)


_CONTEXT_FIELDS = frozenset({
    "kind", "project_id", "session_id", "include_global", "include_project",
})

_REASONS = {
    "invalid_request": "memory context request is invalid",
    "memory_unavailable": "synthetic memory is unavailable",
    "memory_conflict": "synthetic memory candidates conflict",
    "memory_corrupt": "synthetic memory candidate is corrupt",
    "stale_source": "synthetic memory source is stale",
    "no_applicable_memory": "no applicable synthetic memory",
    "provider_error": "memory context provider failed",
    "context_validation_failed": "memory context failed closed validation",
    "context_too_large": "memory context exceeds the absolute byte limit",
}

_FAILURE_STATUS = {
    "INVALID_REQUEST": "invalid_request",
    "MEMORY_UNAVAILABLE": "memory_unavailable",
    "MEMORY_CONFLICT": "memory_conflict",
    "MEMORY_CORRUPT": "memory_corrupt",
    "STALE_SOURCE": "stale_source",
    "NO_APPLICABLE_MEMORY": "no_applicable_memory",
}


def _validate_request(provider: "SyntheticPersonalizedMemoryContextProvider") -> None:
    repository = provider.repository
    if not isinstance(repository, SyntheticPersonalizedMemoryRepository):
        raise MemoryValidationError("repository must be synthetic personalized memory")
    context = provider.context
    if not isinstance(context, Mapping) or set(context) != _CONTEXT_FIELDS:
        raise MemoryValidationError("memory context fields are invalid")
    if type(context["include_global"]) is not bool or type(context["include_project"]) is not bool:
        raise MemoryValidationError("memory context flags must be booleans")
    kind = context["kind"]
    if kind == ScopeKind.GLOBAL.value:
        if (context["project_id"] is not None or context["session_id"] is not None or
                context["include_global"] or context["include_project"]):
            raise MemoryValidationError("global memory context cannot compose narrower scopes")
    elif kind == ScopeKind.PROJECT.value:
        _validate_scope({"kind": "project", "id": context["project_id"]})
        if context["session_id"] is not None or context["include_project"]:
            raise MemoryValidationError("project memory context cannot carry a session scope")
    elif kind == ScopeKind.SESSION.value:
        _validate_scope({"kind": "project", "id": context["project_id"]})
        _validate_scope({"kind": "session", "id": context["session_id"]})
    else:
        raise MemoryValidationError("memory context kind is invalid")
    relevance_keys = provider.relevance_keys
    if (not isinstance(relevance_keys, Sequence) or isinstance(relevance_keys, (str, bytes)) or
            not 1 <= len(relevance_keys) <= 50 or len(set(relevance_keys)) != len(relevance_keys)):
        raise MemoryValidationError("relevance keys must be a bounded unique sequence")
    for key in relevance_keys:
        _validate_relevance_key(key)
    allowed_kinds = provider.allowed_kinds
    if (not isinstance(allowed_kinds, Sequence) or isinstance(allowed_kinds, (str, bytes)) or
            not 1 <= len(allowed_kinds) <= 5 or len(set(allowed_kinds)) != len(allowed_kinds)):
        raise MemoryValidationError("allowed kinds must be a bounded unique sequence")
    for kind_value in allowed_kinds:
        PersonalizedKind(kind_value)
    limit = provider.limit
    if type(limit) is not int or not 1 <= limit <= MAX_MEMORY_CONTEXT_RECORDS:
        raise MemoryValidationError("memory context limit is invalid")
    expected = provider.expected_generation_id
    if expected is not None:
        validate_memory_id(expected)


class SyntheticPersonalizedMemoryContextProvider:
    """Resolve one synthetic repository retrieval into a bounded inert context."""

    def __init__(self, repository: SyntheticPersonalizedMemoryRepository, *,
                 context: Mapping[str, Any],
                 relevance_keys: Sequence[str],
                 allowed_kinds: Sequence[str],
                 limit: int = 5,
                 expected_generation_id: str | None = None):
        self.repository = repository
        self.context = context
        self.relevance_keys = relevance_keys
        self.allowed_kinds = allowed_kinds
        self.limit = limit
        self.expected_generation_id = expected_generation_id

    def resolve(self) -> MemoryContextResolution:
        try:
            _validate_request(self)
        except Exception:
            return MemoryContextResolution(None, "invalid_request",
                                           _REASONS["invalid_request"])
        try:
            result = self.repository.retrieve(PersonalizedRetrievalRequest(
                context=dict(self.context),
                relevance_keys=tuple(self.relevance_keys),
                allowed_kinds=tuple(self.allowed_kinds),
                limit=self.limit,
                expected_generation_id=self.expected_generation_id,
            ))
        except Exception:
            return MemoryContextResolution(None, "provider_error",
                                           _REASONS["provider_error"])
        if not result.accepted:
            status = _FAILURE_STATUS.get(result.reason, "provider_error")
            return MemoryContextResolution(None, status, _REASONS[status])
        if not result.records:
            return MemoryContextResolution(None, "no_applicable_memory",
                                           _REASONS["no_applicable_memory"])
        if not 1 <= len(result.records) <= MAX_MEMORY_CONTEXT_RECORDS:
            return MemoryContextResolution(None, "context_validation_failed",
                                           _REASONS["context_validation_failed"])
        generation_id = result.evidence.get("source_generation_id")
        try:
            if generation_id is None:
                raise MemoryValidationError("synthetic memory source generation is unavailable")
            generation_id = validate_memory_id(generation_id)
        except (MemoryValidationError, TypeError, ValueError):
            return MemoryContextResolution(None, "memory_unavailable",
                                           _REASONS["memory_unavailable"])
        if (self.expected_generation_id is not None and
                generation_id != self.expected_generation_id):
            return MemoryContextResolution(None, "stale_source",
                                           _REASONS["stale_source"])
        records: list[dict[str, Any]] = []
        for record in result.records:
            try:
                content = record["content"]
                if not isinstance(content, str):
                    raise MemoryValidationError("record content must be a string")
                records.append({
                    "memory_id": validate_memory_id(record["memory_id"]),
                    "personalized_kind": PersonalizedKind(record["personalized_kind"]).value,
                    "relevance_key": _validate_relevance_key(record["relevance_key"]),
                    "content": content,
                })
            except (MemoryValidationError, TypeError, ValueError, KeyError, UnicodeEncodeError):
                return MemoryContextResolution(
                    None, "context_validation_failed",
                    _REASONS["context_validation_failed"])
        candidate = {
            "schema_version": MEMORY_CONTEXT_SCHEMA_VERSION,
            "classification": MEMORY_CONTEXT_CLASSIFICATION,
            "authority_permitted": False,
            "memory_generation_id": generation_id,
            "record_count": len(records),
            "records": records,
            "authority_denied": list(AUTHORITY_DENIALS),
        }
        try:
            encoded = json.dumps(candidate, ensure_ascii=True, sort_keys=True,
                                separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError):
            return MemoryContextResolution(
                None, "context_validation_failed",
                _REASONS["context_validation_failed"])
        if len(encoded) > MAX_MEMORY_CONTEXT_BYTES:
            return MemoryContextResolution(None, "context_too_large",
                                           _REASONS["context_too_large"])
        try:
            context = validate_memory_context(candidate)
        except (ValueError, TypeError):
            return MemoryContextResolution(
                None, "context_validation_failed",
                _REASONS["context_validation_failed"])
        return MemoryContextResolution(context, "applied", None,
                                       memory_context_sha256(context))
