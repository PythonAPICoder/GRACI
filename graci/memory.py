"""Phase 4A durable, local, governed persistent-memory storage.

Memory content is untrusted data.  This module stores and validates it; it does
not interpret it, route it to a model, or grant it authority.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping


SCHEMA_VERSION = 1
MAX_ENUMERATION_LIMIT = 1000
DEFAULT_ENUMERATION_LIMIT = 100
_FIELDS = {"schema_version", "memory_id", "created_at", "updated_at", "scope",
           "memory_type", "content", "provenance", "status", "version"}
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_SCOPE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|password|auth[_-]?token|access[_-]?token|secret)\s*[:=]\s*\S+"),
)


class MemoryValidationError(ValueError):
    """The proposed or stored record is not valid canonical memory."""


class MemoryStorageError(RuntimeError):
    """A truthful filesystem/storage operation failure."""


class MemoryNotFoundError(KeyError):
    pass


class MemoryCollisionError(FileExistsError):
    pass


class ScopeKind(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    SESSION = "session"


class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    CONTEXT = "context"
    WORKFLOW = "workflow"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    TOMBSTONED = "tombstoned"


class ProvenanceOrigin(str, Enum):
    USER = "explicit_user"
    RUNTIME = "runtime_observation"
    MODEL = "model_generated"
    IMPORTED = "imported_external"


@dataclass(frozen=True)
class CorruptionDiagnostic:
    memory_id_hint: str
    error: str


@dataclass(frozen=True)
class EnumerationResult:
    records: tuple[dict[str, Any], ...]
    corruptions: tuple[CorruptionDiagnostic, ...]
    offset: int
    limit: int
    has_more: bool


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MemoryValidationError("clock must return a timezone-aware timestamp")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise MemoryValidationError(f"{field} must be a non-empty timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryValidationError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MemoryValidationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_memory_id(memory_id: Any) -> str:
    if not isinstance(memory_id, str) or not _UUID.fullmatch(memory_id):
        raise MemoryValidationError("memory_id must be a canonical lowercase UUID")
    try:
        if str(uuid.UUID(memory_id)) != memory_id:
            raise ValueError
    except ValueError as exc:
        raise MemoryValidationError("memory_id is invalid") from exc
    return memory_id


def _enum(value: Any, enum_type: type[Enum], field: str) -> str:
    if not isinstance(value, str):
        raise MemoryValidationError(f"{field} must be a string")
    try:
        return enum_type(value).value  # type: ignore[call-arg,return-value]
    except ValueError as exc:
        raise MemoryValidationError(f"invalid {field}: {value!r}") from exc


def _validate_scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "id"}:
        raise MemoryValidationError("scope fields must be exactly kind and id")
    kind = _enum(value["kind"], ScopeKind, "scope kind")
    scope_id = value["id"]
    if kind == ScopeKind.GLOBAL.value:
        if scope_id is not None:
            raise MemoryValidationError("global scope id must be null")
    elif not isinstance(scope_id, str) or not _SCOPE_ID.fullmatch(scope_id):
        raise MemoryValidationError("bounded scope id is invalid")
    return {"kind": kind, "id": scope_id}


def _validate_provenance(value: Any) -> dict[str, str | None]:
    if not isinstance(value, dict) or set(value) != {"origin", "source_ref"}:
        raise MemoryValidationError("provenance fields must be exactly origin and source_ref")
    origin = _enum(value["origin"], ProvenanceOrigin, "provenance origin")
    source = value["source_ref"]
    if source is not None and (not isinstance(source, str) or not source.strip() or len(source) > 256):
        raise MemoryValidationError("provenance source_ref must be null or a bounded non-empty string")
    if source is not None:
        _reject_obvious_secrets(source)
    return {"origin": origin, "source_ref": source}


def _reject_obvious_secrets(content: str) -> None:
    if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
        raise MemoryValidationError("content matches bounded secret-material policy")


def validate_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached canonical record; never silently repair."""
    if not isinstance(record, Mapping) or set(record) != _FIELDS:
        missing = sorted(_FIELDS - set(record)) if isinstance(record, Mapping) else sorted(_FIELDS)
        extra = sorted(set(record) - _FIELDS) if isinstance(record, Mapping) else []
        raise MemoryValidationError(f"record fields mismatch; missing={missing}, extra={extra}")
    if type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise MemoryValidationError(f"unsupported schema_version: {record['schema_version']!r}")
    memory_id = validate_memory_id(record["memory_id"])
    created = _parse_timestamp(record["created_at"], "created_at")
    updated = _parse_timestamp(record["updated_at"], "updated_at")
    if updated < created:
        raise MemoryValidationError("updated_at cannot precede created_at")
    if type(record["version"]) is not int or record["version"] < 1:
        raise MemoryValidationError("version must be a positive integer")
    content = record["content"]
    if not isinstance(content, str) or not content.strip():
        raise MemoryValidationError("content must be a non-empty string")
    _reject_obvious_secrets(content)
    return {
        "schema_version": SCHEMA_VERSION, "memory_id": memory_id,
        "created_at": record["created_at"], "updated_at": record["updated_at"],
        "scope": _validate_scope(record["scope"]),
        "memory_type": _enum(record["memory_type"], MemoryType, "memory_type"),
        "content": content, "provenance": _validate_provenance(record["provenance"]),
        "status": _enum(record["status"], MemoryStatus, "status"),
        "version": record["version"],
    }


class MemoryStore:
    """Canonical file store rooted at a host-selected directory."""

    def __init__(self, root: Path, *, clock: Clock = _now):
        root = Path(root)
        if not root.is_absolute():
            raise MemoryValidationError("memory root must be an absolute host-selected path")
        self.root = root.resolve(strict=False)
        self.clock = clock

    def new_record(self, *, scope: Mapping[str, Any], memory_type: str, content: str,
                   provenance: Mapping[str, Any], memory_id: str | None = None) -> dict[str, Any]:
        stamp = _stamp(self.clock())
        return validate_record({
            "schema_version": SCHEMA_VERSION,
            "memory_id": memory_id or str(uuid.uuid4()),
            "created_at": stamp, "updated_at": stamp, "scope": dict(scope),
            "memory_type": memory_type, "content": content,
            "provenance": dict(provenance), "status": MemoryStatus.ACTIVE.value,
            "version": 1,
        })

    def create(self, record: Mapping[str, Any]) -> dict[str, Any]:
        canonical = validate_record(record)
        path = self._path(canonical["memory_id"])
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise MemoryCollisionError(canonical["memory_id"])
            self._atomic_write(path, canonical, replace=False)
        except (MemoryCollisionError, MemoryStorageError):
            raise
        except OSError as exc:
            raise MemoryStorageError(f"memory create failed: {exc}") from exc
        return dict(canonical)

    def get(self, memory_id: str) -> dict[str, Any]:
        path = self._path(memory_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise MemoryNotFoundError(memory_id) from exc
        except OSError as exc:
            raise MemoryStorageError(f"memory read failed: {exc}") from exc
        return self._decode(raw, memory_id)

    def update(self, memory_id: str, *, content: str | None = None,
               status: str | None = None) -> dict[str, Any]:
        current = self.get(memory_id)
        updated = dict(current)
        if content is not None:
            updated["content"] = content
        if status is not None:
            updated["status"] = status
        updated["version"] = current["version"] + 1
        candidate_time = self.clock()
        prior_time = _parse_timestamp(current["updated_at"], "updated_at")
        if candidate_time.tzinfo is None or candidate_time.utcoffset() is None:
            raise MemoryValidationError("clock must return a timezone-aware timestamp")
        if candidate_time.astimezone(timezone.utc) <= prior_time:
            candidate_time = prior_time + timedelta(microseconds=1)
        updated["updated_at"] = _stamp(candidate_time)
        canonical = validate_record(updated)
        try:
            self._atomic_write(self._path(memory_id), canonical, replace=True)
        except MemoryStorageError:
            raise
        except OSError as exc:
            raise MemoryStorageError(f"memory update failed: {exc}") from exc
        return dict(canonical)

    def enumerate(self, *, offset: int = 0,
                  limit: int = DEFAULT_ENUMERATION_LIMIT) -> EnumerationResult:
        if type(offset) is not int or offset < 0:
            raise MemoryValidationError("offset must be a non-negative integer")
        if type(limit) is not int or not 1 <= limit <= MAX_ENUMERATION_LIMIT:
            raise MemoryValidationError(f"limit must be between 1 and {MAX_ENUMERATION_LIMIT}")
        try:
            paths = sorted(self.root.glob("*.json"), key=lambda item: item.name) if self.root.exists() else []
        except OSError as exc:
            raise MemoryStorageError(f"memory enumeration failed: {exc}") from exc
        selected = paths[offset:offset + limit]
        records: list[dict[str, Any]] = []
        corruptions: list[CorruptionDiagnostic] = []
        for path in selected:
            hint = path.stem
            try:
                validate_memory_id(hint)
                record = self.get(hint)
                if record["memory_id"] != hint:
                    raise MemoryValidationError("filename and record identity differ")
                records.append(record)
            except (MemoryValidationError, MemoryStorageError, MemoryNotFoundError) as exc:
                corruptions.append(CorruptionDiagnostic(hint, f"{type(exc).__name__}: {exc}"))
        records.sort(key=lambda item: item["memory_id"])
        return EnumerationResult(tuple(records), tuple(corruptions), offset, limit,
                                 offset + limit < len(paths))

    def _path(self, memory_id: str) -> Path:
        validated = validate_memory_id(memory_id)
        candidate = self.root / f"{validated}.json"
        if candidate.parent != self.root:
            raise MemoryValidationError("memory path escaped configured root")
        return candidate

    @staticmethod
    def _decode(raw: bytes, identity: str) -> dict[str, Any]:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MemoryValidationError(f"stored record {identity} is malformed") from exc
        record = validate_record(value)
        if record["memory_id"] != identity:
            raise MemoryValidationError("stored record identity mismatch")
        return record

    def _atomic_write(self, destination: Path, record: Mapping[str, Any], *, replace: bool) -> None:
        temporary = self.root / f".{record['memory_id']}.{uuid.uuid4().hex}.tmp"
        payload = (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                os.replace(temporary, destination)
            else:
                try:
                    os.link(temporary, destination)
                except FileExistsError as exc:
                    raise MemoryCollisionError(record["memory_id"]) from exc
        except MemoryCollisionError:
            raise
        except OSError as exc:
            raise MemoryStorageError(f"atomic memory write failed: {exc}") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
