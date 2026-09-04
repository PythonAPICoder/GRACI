"""Bounded untrusted memory-context contract for ordinary GRACI turns.

This module validates a small, inert context payload.  It does not retrieve
memory, infer relevance, grant authority, or persist personal data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .memory import PersonalizedKind, _reject_obvious_secrets, validate_memory_id
from .memory_governance import validate_relevance_key


MEMORY_CONTEXT_SCHEMA_VERSION = 1
MEMORY_CONTEXT_CLASSIFICATION = "UNTRUSTED_CONTEXT_DATA"
MAX_MEMORY_CONTEXT_BYTES = 8_000
MAX_MEMORY_CONTEXT_RECORDS = 5
MAX_MEMORY_CONTEXT_RECORD_CONTENT_CHARS = 1_000
MAX_MEMORY_CONTEXT_REASON_CHARS = 160

AUTHORITY_DENIALS = (
    "grant_authority",
    "override_governance",
    "authorize_action",
    "expand_scope",
    "install_tool",
    "promote_code",
    "authorize_executable",
    "override_current_task",
    "modify_policy",
)

CONTEXT_FIELDS = frozenset({
    "schema_version",
    "classification",
    "authority_permitted",
    "memory_generation_id",
    "record_count",
    "records",
    "authority_denied",
})
RECORD_FIELDS = frozenset({"memory_id", "personalized_kind", "relevance_key", "content"})

STATUS_NOT_CONFIGURED = "not_configured"
STATUS_APPLIED = "applied"
STATUS_NO_APPLICABLE_MEMORY = "no_applicable_memory"
STATUS_MEMORY_CONFLICT = "memory_conflict"
STATUS_MEMORY_CORRUPT = "memory_corrupt"
STATUS_STALE_SOURCE = "stale_source"
STATUS_MEMORY_UNAVAILABLE = "memory_unavailable"
STATUS_INVALID_REQUEST = "invalid_request"
STATUS_PROVIDER_ERROR = "provider_error"
STATUS_CONTEXT_VALIDATION_FAILED = "context_validation_failed"
STATUS_CONTEXT_TOO_LARGE = "context_too_large"

ALLOWED_MEMORY_CONTEXT_STATUSES = frozenset({
    STATUS_NOT_CONFIGURED,
    STATUS_APPLIED,
    STATUS_NO_APPLICABLE_MEMORY,
    STATUS_MEMORY_CONFLICT,
    STATUS_MEMORY_CORRUPT,
    STATUS_STALE_SOURCE,
    STATUS_MEMORY_UNAVAILABLE,
    STATUS_INVALID_REQUEST,
    STATUS_PROVIDER_ERROR,
    STATUS_CONTEXT_VALIDATION_FAILED,
    STATUS_CONTEXT_TOO_LARGE,
})


@dataclass(frozen=True)
class MemoryContextResolution:
    context: dict[str, Any] | None
    status: str
    reason: str | None = None
    context_sha256: str | None = None


def _encoded_context(context: Mapping[str, Any]) -> bytes:
    return json.dumps(context, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def memory_context_sha256(context: Mapping[str, Any]) -> str:
    return hashlib.sha256(_encoded_context(context)).hexdigest()


def validate_memory_context(value: Any) -> dict[str, Any]:
    try:
        if not isinstance(value, Mapping) or set(value) != CONTEXT_FIELDS:
            raise ValueError("memory context fields are invalid")
        if type(value["schema_version"]) is not int or value["schema_version"] != MEMORY_CONTEXT_SCHEMA_VERSION:
            raise ValueError("memory context schema is invalid")
        if value["classification"] != MEMORY_CONTEXT_CLASSIFICATION:
            raise ValueError("memory context classification is invalid")
        if value["authority_permitted"] is not False:
            raise ValueError("memory context cannot permit authority")
        generation_id = value["memory_generation_id"]
        if generation_id is None:
            raise ValueError("memory generation ID is required")
        generation_id = validate_memory_id(generation_id)
        record_count = value["record_count"]
        if type(record_count) is not int or not 1 <= record_count <= MAX_MEMORY_CONTEXT_RECORDS:
            raise ValueError("memory context record count is invalid")
        records = value["records"]
        if not isinstance(records, list) or len(records) != record_count:
            raise ValueError("memory context records are invalid")
        denial = value["authority_denied"]
        if not isinstance(denial, list) or tuple(denial) != AUTHORITY_DENIALS:
            raise ValueError("memory context authority denial is invalid")
        canonical_records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, Mapping) or set(record) != RECORD_FIELDS:
                raise ValueError("memory context record fields are invalid")
            memory_id = validate_memory_id(record["memory_id"])
            if memory_id in seen:
                raise ValueError("memory context record IDs must be unique")
            seen.add(memory_id)
            canonical_records.append({
                "memory_id": memory_id,
                "personalized_kind": PersonalizedKind(record["personalized_kind"]).value,
                "relevance_key": validate_relevance_key(record["relevance_key"]),
                "content": _validate_record_content(record["content"]),
            })
        canonical = {
            "schema_version": MEMORY_CONTEXT_SCHEMA_VERSION,
            "classification": MEMORY_CONTEXT_CLASSIFICATION,
            "authority_permitted": False,
            "memory_generation_id": generation_id,
            "record_count": record_count,
            "records": canonical_records,
            "authority_denied": list(AUTHORITY_DENIALS),
        }
        if len(_encoded_context(canonical)) > MAX_MEMORY_CONTEXT_BYTES:
            raise ValueError("memory context exceeds the absolute byte limit")
        return canonical
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise ValueError("untrusted memory context is invalid") from exc


def _validate_record_content(content: Any) -> str:
    if (not isinstance(content, str) or not content.strip() or
            len(content) > MAX_MEMORY_CONTEXT_RECORD_CONTENT_CHARS):
        raise ValueError("memory context record content is invalid")
    _reject_obvious_secrets(content)
    return content


def _validate_reason(reason: Any) -> str | None:
    if reason is None:
        return None
    if (not isinstance(reason, str) or not 1 <= len(reason) <= MAX_MEMORY_CONTEXT_REASON_CHARS or
            reason != reason.strip() or any(ord(character) < 32 for character in reason)):
        raise ValueError("memory context reason is invalid")
    return reason


def validate_memory_context_resolution(value: Any) -> MemoryContextResolution:
    try:
        if value is None:
            return MemoryContextResolution(None, STATUS_NOT_CONFIGURED)
        if not isinstance(value, MemoryContextResolution):
            raise ValueError("memory context resolution is invalid")
        status = value.status
        if status not in ALLOWED_MEMORY_CONTEXT_STATUSES:
            raise ValueError("memory context status is invalid")
        reason = _validate_reason(value.reason)
        if value.context is None:
            if status == STATUS_APPLIED:
                raise ValueError("applied memory context is missing")
            if value.context_sha256 is not None:
                raise ValueError("memory context digest is invalid")
            return MemoryContextResolution(None, status, reason)
        if status != STATUS_APPLIED:
            raise ValueError("memory context status does not match its payload")
        if reason is not None:
            raise ValueError("applied memory context must not carry a diagnostic reason")
        context = validate_memory_context(value.context)
        expected = memory_context_sha256(context)
        if value.context_sha256 is not None and value.context_sha256 != expected:
            raise ValueError("memory context digest is invalid")
        return MemoryContextResolution(context, status, None, expected)
    except (ValueError, TypeError) as exc:
        raise ValueError("memory context resolution is invalid") from exc
