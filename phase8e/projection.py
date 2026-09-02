"""Deterministic, local-only Phase 8E review projection exporter.

The exporter is intentionally outside the ordinary GRACI runtime package. It reads
exactly cataloged Git blobs and explicitly named memory records, treats all rendered
text as untrusted, and promotes only a complete hash-verified generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import stat
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


EXPORTER_VERSION = "1.1.0-personalized-synthetic"
MANIFEST_SCHEMA_VERSION = 1
CATALOG_VERSION = 2
MAX_REPOSITORY_SOURCE_BYTES = 1_048_576
MAX_MEMORY_SOURCE_BYTES = 65_536
MAX_GENERATED_FILE_BYTES = 2_097_152
MAX_CATALOG_SOURCES = 256
MAX_MEMORY_RECORDS = 100
MAX_RELATIVE_PATH_CHARACTERS = 240
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_ABBREVIATED_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_SAFE_GENERATED_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RECORDED_COMMIT = re.compile(
    r"^> (?:Verified at commit|Verified against|Designed against):[^\r\n]*?"
    r"(?<![0-9a-f])`?([0-9a-f]{7,40})`?(?![0-9a-f])[^\r\n]*$",
    re.MULTILINE,
)
_UUID_FILE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.json$"
)
_MEMORY_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_MEMORY_SCOPE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MEMORY_RELEVANCE_KEY = re.compile(
    r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)*$"
)
_MEMORY_BASE_FIELDS = {
    "schema_version", "memory_id", "created_at", "updated_at", "scope",
    "memory_type", "content", "provenance", "status", "version",
}
_MEMORY_V2_FIELDS = _MEMORY_BASE_FIELDS | {
    "relevance_key", "expires_at", "supersedes_memory_id",
}
_MEMORY_V3_FIELDS = _MEMORY_V2_FIELDS | {"personalized_kind", "approval"}
_MEMORY_APPROVAL_FIELDS = {
    "approval_id", "proposal_id", "authority", "channel", "source_turn_id",
    "approved_at", "proposal_digest",
}
_RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL", "CLOCK$",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(
        rb"(?i)\b(?:api[_-]?key|password|auth[_-]?token|access[_-]?token|secret)\s*[:=]\s*\S+"
    ),
)
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]\r\n]*)\]\(([^)\r\n]*)\)")
_MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]\r\n]+)\]\(([^)\r\n]+)\)")
_WIKI_EMBED = re.compile(r"!\[\[([^\]\r\n]+)\]\]")
_WIKI_LINK = re.compile(r"(?<!!)\[\[([^\]\r\n]+)\]\]")
_ACTIVE_URI = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?:https?|ftp|ftps|mailto|smb|file|javascript|data|vbscript|"
    r"obsidian|shell):[^\s<>()\[\]]+"
)
_MANIFEST_ENTRY_FIELDS = {
    "kind", "source", "source_version", "source_hash", "output_path",
    "output_hash", "source_type", "review_classification", "authority_class",
    "view_status", "freshness", "conflict", "content_included", "diagnostic",
}


class ProjectionError(RuntimeError):
    """A projection input, generation, promotion, or verification failed closed."""


class _MemoryRecordError(ValueError):
    """A synthetic memory source failed equivalent read-only validation."""


def _validate_relative_path(value: str, *, suffix: str | None = None) -> PurePosixPath:
    if (not isinstance(value, str) or not value or value != value.strip() or
            len(value) > MAX_RELATIVE_PATH_CHARACTERS):
        raise ProjectionError("paths must be bounded non-empty strings")
    if any(ord(character) < 32 for character in value):
        raise ProjectionError("control characters are forbidden in paths")
    windows = PureWindowsPath(value)
    if (value.startswith(("/", "\\", "//", "\\\\", "\\?\\", "\\.\\", "\\??\\")) or
            windows.is_absolute() or windows.drive or windows.root or ":" in value or "\\" in value):
        raise ProjectionError("absolute, UNC, device, alternate-stream, and backslash paths are forbidden")
    candidate = PurePosixPath(value)
    if (candidate.is_absolute() or candidate.as_posix() != value or
            any(part in ("", ".", "..") for part in candidate.parts)):
        raise ProjectionError("path traversal and ambiguous path segments are forbidden")
    for part in candidate.parts:
        if not _SAFE_GENERATED_SEGMENT.fullmatch(part):
            raise ProjectionError("path contains an unsupported segment")
        if part.rstrip(" .") != part:
            raise ProjectionError("Windows-normalized trailing spaces and dots are forbidden")
        if part.split(".", 1)[0].upper() in _RESERVED_WINDOWS_NAMES:
            raise ProjectionError("Windows device names are forbidden")
    if suffix is not None and candidate.suffix.lower() != suffix:
        raise ProjectionError(f"path must end in {suffix}")
    return candidate


class SourceType(str, Enum):
    GOVERNANCE = "Governance"
    DECISION = "Decision"
    ACCEPTANCE = "Acceptance"
    CURRENT_STATE = "Current state"
    ARCHITECTURE = "Architecture"
    HISTORICAL_EVIDENCE = "Historical evidence"
    WORKFLOW_GUIDANCE = "Workflow guidance"
    GOVERNED_MEMORY = "Governed memory"
    FUTURE_RAG = "Future RAG"
    CORRECTIVE_LESSON = "Corrective lesson"
    NAVIGATION = "Navigation"


class ReviewClassification(str, Enum):
    PRODUCT_OWNER_REVIEW = "ProductOwnerReview"
    SENSITIVE_LOCAL = "SensitiveLocal"
    EXCLUDED = "Excluded"


class AuthorityClass(str, Enum):
    CANONICAL_GOVERNANCE = "Canonical governance"
    ACCEPTED_DECISION_RECORD = "Accepted decision record"
    SCOPED_ACCEPTANCE_RECORD = "Scoped acceptance record"
    DESCRIPTIVE_CURRENT_SOURCE = "Descriptive current source"
    CANONICAL_GOVERNED_MEMORY = "Canonical governed memory"
    HISTORICAL_SOURCE = "Historical source"
    WORKFLOW_GUIDANCE = "Workflow guidance"
    FUTURE_PLACEHOLDER = "Future placeholder"
    DERIVED_NAVIGATION = "Derived navigation"


class FreshnessState(str, Enum):
    VERIFIED_AT_SOURCE_COMMIT = "Verified at source commit"
    CHANGED_SINCE_RECORDED_VERIFICATION = "Changed since recorded verification"
    NO_RECORDED_VERIFICATION = "No recorded verification"
    HISTORICAL = "Historical"
    FUTURE_NOT_IMPLEMENTED = "Future capability not implemented"
    PROJECTION_STALE = "Projection stale"
    UNKNOWN = "Unknown"


class ConflictState(str, Enum):
    NONE = "None"
    REPORTED = "Reported"
    CORRUPT = "Corrupt"
    UNSUPPORTED = "Unsupported"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class RepositorySource:
    source_path: str
    output_path: str
    source_type: SourceType
    classification: ReviewClassification
    authority_class: AuthorityClass
    conflict: ConflictState = ConflictState.NONE
    historical: bool = False
    future_placeholder: bool = False

    def __post_init__(self) -> None:
        _validate_relative_path(self.source_path, suffix=".md")
        _validate_relative_path(self.output_path, suffix=".md")
        if self.classification is ReviewClassification.EXCLUDED:
            raise ProjectionError("excluded repository sources cannot be cataloged for rendering")
        if self.historical and self.future_placeholder:
            raise ProjectionError("a source cannot be both historical and a future placeholder")


@dataclass(frozen=True)
class MemoryProjectionRequest:
    root: Path
    memory_ids: tuple[str, ...]
    approved_content_ids: frozenset[str] = frozenset()
    conflicts: Mapping[str, ConflictState] | None = None

    def __post_init__(self) -> None:
        try:
            ids = tuple(_validate_memory_id(value) for value in self.memory_ids)
            approved = frozenset(_validate_memory_id(value) for value in self.approved_content_ids)
        except _MemoryRecordError as exc:
            raise ProjectionError("memory IDs must be canonical lowercase UUIDs") from exc
        if not ids:
            raise ProjectionError("a memory projection request must name at least one exact ID")
        if len(ids) > MAX_MEMORY_RECORDS:
            raise ProjectionError("memory projection request exceeds the exact-ID limit")
        if len(ids) != len(set(ids)):
            raise ProjectionError("memory IDs must be unique")
        if not approved <= set(ids):
            raise ProjectionError("approved-content IDs must be an exact subset of requested IDs")
        conflicts = dict(self.conflicts or {})
        conflict_keys = set(conflicts)
        if not conflict_keys <= set(ids):
            raise ProjectionError("memory conflict labels must reference requested IDs")
        if any(not isinstance(value, ConflictState) for value in conflicts.values()):
            raise ProjectionError("memory conflict labels must be typed ConflictState values")
        object.__setattr__(self, "memory_ids", ids)
        object.__setattr__(self, "approved_content_ids", approved)
        object.__setattr__(self, "conflicts", MappingProxyType(conflicts))


INITIAL_REPOSITORY_CATALOG: tuple[RepositorySource, ...] = (
    RepositorySource("governance/CURRENT_POLICY.md", "governance/current-policy.md",
                     SourceType.GOVERNANCE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.CANONICAL_GOVERNANCE),
    RepositorySource("governance/POLICY_INDEX.md", "governance/policy-index.md",
                     SourceType.GOVERNANCE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.CANONICAL_GOVERNANCE),
    RepositorySource("governance/CHANGE_PROCESS.md", "governance/change-process.md",
                     SourceType.GOVERNANCE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.CANONICAL_GOVERNANCE),
    RepositorySource("AGENTS.md", "workflow/agents.md", SourceType.WORKFLOW_GUIDANCE,
                     ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.WORKFLOW_GUIDANCE),
    RepositorySource("docs/INDEX.md", "workflow/documentation-index.md",
                     SourceType.WORKFLOW_GUIDANCE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.WORKFLOW_GUIDANCE),
    RepositorySource("docs/DEVELOPMENT.md", "workflow/development.md",
                     SourceType.WORKFLOW_GUIDANCE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.WORKFLOW_GUIDANCE),
    RepositorySource("docs/PRODUCT.md", "current/product.md", SourceType.CURRENT_STATE,
                     ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE),
    RepositorySource("CURRENT_ARCHITECTURE.md", "current/architecture.md",
                     SourceType.ARCHITECTURE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE),
    RepositorySource("CURRENT_STATUS.md", "current/status.md", SourceType.CURRENT_STATE,
                     ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE),
    RepositorySource("docs/KNOWN_ISSUES.md", "current/known-issues.md",
                     SourceType.CURRENT_STATE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE),
    RepositorySource("docs/CAPABILITY_MATRIX.md", "current/capability-matrix.md",
                     SourceType.CURRENT_STATE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE),
    RepositorySource("docs/ROADMAP.md", "current/roadmap.md", SourceType.CURRENT_STATE,
                     ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE),
    RepositorySource("docs/decisions/DECISION_INDEX.md", "decisions/index.md",
                     SourceType.DECISION, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.ACCEPTED_DECISION_RECORD),
    RepositorySource("docs/acceptance/ACCEPTANCE_INDEX.md", "acceptance/index.md",
                     SourceType.ACCEPTANCE, ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.SCOPED_ACCEPTANCE_RECORD),
    *tuple(
        RepositorySource(f"docs/acceptance/ACC-000{number}-{name}.md",
                         f"acceptance/acc-000{number}.md", SourceType.ACCEPTANCE,
                         ReviewClassification.PRODUCT_OWNER_REVIEW,
                         AuthorityClass.SCOPED_ACCEPTANCE_RECORD)
        for number, name in (
            (1, "phase8-ui-baseline"),
            (2, "memory-foundation"),
            (3, "phase8d-cold-start"),
            (4, "4090-llama-upgrade"),
            (5, "4090-certificate-remoting"),
            (6, "4090-telemetry"),
            (7, "phase8e-stage1"),
            (8, "phase8e-stage2-windows"),
            (9, "phase8e-stage3-obsidian"),
        )
    ),
    RepositorySource("docs/history/PHASE_INDEX.md", "history/phase-index.md",
                     SourceType.HISTORICAL_EVIDENCE,
                     ReviewClassification.PRODUCT_OWNER_REVIEW,
                     AuthorityClass.HISTORICAL_SOURCE, historical=True),
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_memory_id(value: Any) -> str:
    if not isinstance(value, str) or not _MEMORY_UUID.fullmatch(value):
        raise _MemoryRecordError("invalid memory ID")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except ValueError as exc:
        raise _MemoryRecordError("invalid memory ID") from exc
    return value


def _memory_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise _MemoryRecordError(f"invalid {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _MemoryRecordError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _MemoryRecordError(f"invalid {field}")
    return parsed.astimezone(timezone.utc)


def _validate_memory_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _MemoryRecordError("memory record must be an object")
    schema = value.get("schema_version")
    if type(schema) is not int:
        raise _MemoryRecordError("unsupported or malformed memory schema")
    fields = (_MEMORY_BASE_FIELDS if schema == 1 else
              _MEMORY_V2_FIELDS if schema == 2 else
              _MEMORY_V3_FIELDS if schema == 3 else None)
    if fields is None or set(value) != fields:
        raise _MemoryRecordError("unsupported or malformed memory schema")
    memory_id = _validate_memory_id(value["memory_id"])
    created = _memory_timestamp(value["created_at"], "created_at")
    updated = _memory_timestamp(value["updated_at"], "updated_at")
    if updated < created:
        raise _MemoryRecordError("memory timestamps are inconsistent")
    if type(value["version"]) is not int or value["version"] < 1:
        raise _MemoryRecordError("invalid memory version")
    scope = value["scope"]
    if not isinstance(scope, dict) or set(scope) != {"kind", "id"}:
        raise _MemoryRecordError("invalid memory scope")
    if scope["kind"] == "global":
        if scope["id"] is not None:
            raise _MemoryRecordError("invalid global memory scope")
    elif (scope["kind"] not in {"project", "session"} or
          not isinstance(scope["id"], str) or
          not _MEMORY_SCOPE_ID.fullmatch(scope["id"])):
        raise _MemoryRecordError("invalid bounded memory scope")
    if value["memory_type"] not in {"fact", "preference", "decision", "context", "workflow"}:
        raise _MemoryRecordError("invalid memory type")
    if value["status"] not in {"active", "superseded", "expired", "tombstoned"}:
        raise _MemoryRecordError("invalid memory status")
    content = value["content"]
    if not isinstance(content, str) or not content.strip():
        raise _MemoryRecordError("invalid memory content")
    try:
        content_bytes = content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _MemoryRecordError("invalid memory content") from exc
    if len(content_bytes) > 16_384:
        raise _MemoryRecordError("memory content exceeds its accepted bound")
    _reject_secret_material(content_bytes)
    provenance = value["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {"origin", "source_ref"}:
        raise _MemoryRecordError("invalid memory provenance")
    if provenance["origin"] not in {
        "explicit_user", "runtime_observation", "model_generated", "imported_external",
    }:
        raise _MemoryRecordError("invalid memory provenance origin")
    source_ref = provenance["source_ref"]
    if source_ref is not None:
        if not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 256:
            raise _MemoryRecordError("invalid memory source reference")
        try:
            source_ref_bytes = source_ref.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise _MemoryRecordError("invalid memory source reference") from exc
        _reject_secret_material(source_ref_bytes)
    if schema == 2:
        relevance_key = value["relevance_key"]
        if (not isinstance(relevance_key, str) or not 1 <= len(relevance_key) <= 128 or
                not _MEMORY_RELEVANCE_KEY.fullmatch(relevance_key)):
            raise _MemoryRecordError("invalid memory relevance key")
        if value["expires_at"] is not None:
            _memory_timestamp(value["expires_at"], "expires_at")
        supersedes = value["supersedes_memory_id"]
        if supersedes is not None and _validate_memory_id(supersedes) == memory_id:
            raise _MemoryRecordError("memory cannot supersede itself")
    if schema == 3:
        relevance_key = value["relevance_key"]
        if (not isinstance(relevance_key, str) or not 1 <= len(relevance_key) <= 128 or
                not _MEMORY_RELEVANCE_KEY.fullmatch(relevance_key)):
            raise _MemoryRecordError("invalid memory relevance key")
        if value["expires_at"] is not None:
            _memory_timestamp(value["expires_at"], "expires_at")
        supersedes = value["supersedes_memory_id"]
        if supersedes is not None and _validate_memory_id(supersedes) == memory_id:
            raise _MemoryRecordError("memory cannot supersede itself")
        if value["personalized_kind"] not in {
                "preference", "working_method", "task_procedure", "correction", "lesson"}:
            raise _MemoryRecordError("invalid personalized memory kind")
        approval = value["approval"]
        if not isinstance(approval, dict) or set(approval) != _MEMORY_APPROVAL_FIELDS:
            raise _MemoryRecordError("invalid personalized memory approval")
        for field in ("approval_id", "proposal_id", "source_turn_id"):
            _validate_memory_id(approval[field])
        if approval["authority"] != "product_owner":
            raise _MemoryRecordError("invalid personalized memory approval authority")
        if approval["channel"] not in {"typed_turn", "ptt_release"}:
            raise _MemoryRecordError("invalid personalized memory approval channel")
        approved = _memory_timestamp(approval["approved_at"], "approved_at")
        if approved > created:
            raise _MemoryRecordError("personalized memory approval follows creation")
        if (not isinstance(approval["proposal_digest"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", approval["proposal_digest"])):
            raise _MemoryRecordError("invalid personalized memory approval digest")
    return value


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _validate_generation_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProjectionError("generation ID must be a canonical lowercase UUID") from exc
    if str(parsed) != value:
        raise ProjectionError("generation ID must be a canonical lowercase UUID")
    return value


def _is_reparse_point(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _assert_no_reparse_chain(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    chain = tuple(reversed(absolute.parents)) + (absolute,)
    for candidate in chain:
        if _is_reparse_point(candidate):
            raise ProjectionError(f"reparse point is forbidden: {candidate.name or candidate}")


def _validated_root(root: Path, *, must_exist: bool) -> Path:
    raw = str(root)
    if raw.startswith(("\\\\", "//", "\\?\\", "\\.\\", "\\??\\")):
        raise ProjectionError("UNC and device roots are forbidden")
    candidate = Path(root)
    if not candidate.is_absolute():
        raise ProjectionError("configured roots must be absolute")
    windows = PureWindowsPath(raw)
    if ":" in raw[len(windows.drive):]:
        raise ProjectionError("alternate data streams are forbidden in configured roots")
    _assert_no_reparse_chain(candidate)
    resolved = candidate.resolve(strict=False)
    if must_exist and (not resolved.exists() or not resolved.is_dir()):
        raise ProjectionError("configured source root must be an existing directory")
    return resolved


def _path_within(root: Path, relative: str, *, must_exist: bool) -> Path:
    clean = _validate_relative_path(relative)
    root = _validated_root(root, must_exist=True)
    candidate = root.joinpath(*clean.parts)
    _assert_no_reparse_chain(candidate)
    resolved = candidate.resolve(strict=False)
    if resolved == root or not resolved.is_relative_to(root):
        raise ProjectionError("path escaped its configured root")
    if must_exist and not resolved.is_file():
        raise ProjectionError("required source is not a regular file")
    return resolved


def _roots_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _reject_secret_material(payload: bytes) -> None:
    if any(pattern.search(payload) for pattern in _SECRET_PATTERNS):
        raise ProjectionError("source rejected by bounded secret-material scan")


def _read_stable_regular_file(path: Path, *, maximum_bytes: int) -> bytes:
    _assert_no_reparse_chain(path)
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or _is_reparse_point(path):
            raise ProjectionError("source must be a non-reparse regular file")
        if before.st_size > maximum_bytes:
            raise ProjectionError("source exceeds the bounded byte limit")
        payload = path.read_bytes()
        after = path.lstat()
    except ProjectionError:
        raise
    except OSError as exc:
        raise ProjectionError("bounded local source read failed") from exc
    identity_before = (
        before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
        getattr(before, "st_file_attributes", 0),
    )
    identity_after = (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
        getattr(after, "st_file_attributes", 0),
    )
    if identity_before != identity_after or len(payload) != after.st_size or _is_reparse_point(path):
        raise ProjectionError("source changed during its bounded read")
    return payload


def _walk_regular_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    directories = [root]
    while directories:
        directory = directories.pop()
        try:
            entries = tuple(os.scandir(directory))
        except OSError as exc:
            raise ProjectionError("generation tree enumeration failed") from exc
        for entry in entries:
            try:
                details = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ProjectionError("generation tree inspection failed") from exc
            attributes = getattr(details, "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if stat.S_ISLNK(details.st_mode) or attributes & reparse_flag:
                raise ProjectionError("reparse point found inside generation")
            path = Path(entry.path)
            if stat.S_ISDIR(details.st_mode):
                directories.append(path)
            elif stat.S_ISREG(details.st_mode):
                files.append(path)
            else:
                raise ProjectionError("generation contains a non-regular filesystem entry")
    return tuple(files)


class _GitReader:
    def __init__(self, repository_root: Path, commit: str):
        self.root = _validated_root(repository_root, must_exist=True)
        if not _COMMIT.fullmatch(commit):
            raise ProjectionError("source commit must be a full lowercase SHA-1 commit ID")
        top = self._run(("rev-parse", "--show-toplevel"), text=True).strip()
        if Path(top).resolve(strict=True) != self.root.resolve(strict=True):
            raise ProjectionError("repository root must be the exact Git worktree root")
        resolved = self._run(("rev-parse", "--verify", f"{commit}^{{commit}}"), text=True).strip()
        if resolved != commit:
            raise ProjectionError("source commit did not resolve exactly")
        self.commit = commit

    def _run(self, arguments: Sequence[str], *, text: bool = False,
             check: bool = True) -> bytes | str | subprocess.CompletedProcess[bytes]:
        environment = os.environ.copy()
        environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
        try:
            completed = subprocess.run(
                ("git", "-C", str(self.root), *arguments), check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectionError("bounded local Git read failed") from exc
        if check and completed.returncode != 0:
            raise ProjectionError("bounded local Git read failed")
        if not check:
            return completed
        if text:
            try:
                return completed.stdout.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ProjectionError("Git metadata was not valid UTF-8") from exc
        return completed.stdout

    def read_blob(self, source_path: str) -> bytes:
        clean = _validate_relative_path(source_path, suffix=".md").as_posix()
        listing = self._run(("ls-tree", self.commit, "--", clean))
        if not isinstance(listing, bytes):
            raise ProjectionError("Git tree read returned an invalid result type")
        lines = listing.splitlines()
        if len(lines) != 1 or b"\t" not in lines[0]:
            raise ProjectionError("cataloged Git source is missing or ambiguous")
        metadata, returned_path = lines[0].split(b"\t", 1)
        fields = metadata.split()
        try:
            exact_returned_path = returned_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProjectionError("cataloged Git path was not valid UTF-8") from exc
        if fields[:2] != [b"100644", b"blob"] or exact_returned_path != clean:
            raise ProjectionError("cataloged Git source must be one non-executable regular blob")
        size_text = self._run(("cat-file", "-s", f"{self.commit}:{clean}"), text=True)
        if not isinstance(size_text, str):
            raise ProjectionError("Git size read returned an invalid result type")
        try:
            size = int(size_text.strip())
        except ValueError as exc:
            raise ProjectionError("Git reported an invalid source size") from exc
        if not 0 <= size <= MAX_REPOSITORY_SOURCE_BYTES:
            raise ProjectionError("repository source exceeds the bounded byte limit")
        payload = self._run(("show", f"{self.commit}:{clean}"))
        if not isinstance(payload, bytes):
            raise ProjectionError("Git blob read returned an invalid result type")
        if len(payload) != size:
            raise ProjectionError("Git source size changed during its bounded read")
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProjectionError("repository source must be UTF-8") from exc
        _reject_secret_material(payload)
        return payload

    def freshness(self, source: RepositorySource, payload: bytes) -> FreshnessState:
        if source.historical:
            return FreshnessState.HISTORICAL
        if source.future_placeholder:
            return FreshnessState.FUTURE_NOT_IMPLEMENTED
        match = _RECORDED_COMMIT.search(payload.decode("utf-8"))
        if match is None:
            return FreshnessState.NO_RECORDED_VERIFICATION
        recorded = match.group(1)
        if not _ABBREVIATED_COMMIT.fullmatch(recorded):
            return FreshnessState.UNKNOWN
        resolved = self._run(("rev-parse", "--verify", f"{recorded}^{{commit}}"),
                             text=True, check=False)
        if not isinstance(resolved, subprocess.CompletedProcess):
            return FreshnessState.UNKNOWN
        if resolved.returncode != 0:
            return FreshnessState.UNKNOWN
        full_recorded = resolved.stdout.decode("ascii").strip()
        ancestor = self._run(("merge-base", "--is-ancestor", full_recorded, self.commit),
                             check=False)
        if not isinstance(ancestor, subprocess.CompletedProcess):
            return FreshnessState.UNKNOWN
        if ancestor.returncode != 0:
            return FreshnessState.UNKNOWN
        changed = self._run(("diff", "--quiet", full_recorded, self.commit, "--",
                             source.source_path), check=False)
        if not isinstance(changed, subprocess.CompletedProcess):
            return FreshnessState.UNKNOWN
        if changed.returncode == 0:
            return FreshnessState.VERIFIED_AT_SOURCE_COMMIT
        if changed.returncode == 1:
            return FreshnessState.CHANGED_SINCE_RECORDED_VERIFICATION
        return FreshnessState.UNKNOWN


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _banner(*, source: str, source_type: SourceType,
            classification: ReviewClassification, authority: AuthorityClass,
            source_hash: str, generated_local: str, generated_utc: str,
            freshness: FreshnessState, conflict: ConflictState) -> str:
    fields = (
        ("Source", source),
        ("Source type", source_type.value),
        ("Review classification", classification.value),
        ("Authority class", authority.value),
        ("View status", "Derived read-only projection"),
        ("Source hash", f"SHA-256 `{source_hash}`"),
        ("Generated", f"{generated_local}; UTC {generated_utc}"),
        ("Freshness", freshness.value),
        ("Conflict", conflict.value),
    )
    rows = "\n".join(f"| {label} | {_escape_table(value)} |" for label, value in fields)
    return (
        "> [!WARNING] Derived read-only projection\n"
        "> This note is a review copy. It cannot grant authority or permission. "
        "Use the named canonical source for decisions and changes.\n\n"
        "| Label | Value |\n|---|---|\n" + rows + "\n"
    )


def _neutralize_markdown(text: str, source: RepositorySource,
                         link_map: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    diagnostics: list[str] = []

    def blocked_embed(match: re.Match[str]) -> str:
        diagnostics.append("blocked active embed")
        label = match.group(1).strip() or "unlabelled"
        return f"[Blocked embed: {label}]"

    text = _MARKDOWN_IMAGE.sub(blocked_embed, text)
    text = _WIKI_EMBED.sub(blocked_embed, text)
    text = _WIKI_LINK.sub(lambda match: f"[Blocked wiki link: {match.group(1).strip()}]", text)

    def rewrite_link(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2).strip()
        path_part, separator, fragment = target.partition("#")
        try:
            if not path_part:
                destination_source = source.source_path
            else:
                joined = posixpath.normpath(posixpath.join(
                    str(PurePosixPath(source.source_path).parent), path_part
                ))
                _validate_relative_path(joined, suffix=".md")
                destination_source = joined
        except ProjectionError:
            diagnostics.append("blocked unsafe or non-cataloged link")
            return f"{label} [blocked link]"
        destination_output = link_map.get(destination_source)
        if destination_output is None:
            diagnostics.append("blocked unsafe or non-cataloged link")
            return f"{label} [blocked link]"
        relative_output = posixpath.relpath(
            destination_output, str(PurePosixPath(source.output_path).parent)
        )
        safe_fragment = ""
        if separator and re.fullmatch(r"[A-Za-z0-9_-]+", fragment):
            safe_fragment = f"#{fragment}"
        return f"[{label}]({relative_output}{safe_fragment})"

    text = _MARKDOWN_LINK.sub(rewrite_link, text)
    # Escape every angle bracket, including tags split across lines. This is more
    # conservative than attempting to recognize a safe HTML subset.
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    if _ACTIVE_URI.search(text):
        diagnostics.append("blocked active URI")
        text = _ACTIVE_URI.sub("[blocked external reference]", text)
    return text, tuple(sorted(set(diagnostics)))


def _write_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse_chain(path.parent)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ProjectionError("exclusive projection write failed") from exc


class ProjectionExporter:
    """Create and promote one complete deterministic local projection generation."""

    def __init__(self, staging_root: Path, projection_root: Path,
                 *, clock: Callable[[], datetime] | None = None):
        self.staging_root = _validated_root(staging_root, must_exist=False)
        self.projection_root = _validated_root(projection_root, must_exist=False)
        if _roots_overlap(self.staging_root, self.projection_root):
            raise ProjectionError("staging and projection roots must be separate")
        self.clock = clock or (lambda: datetime.now().astimezone())

    def export(self, *, repository_root: Path, source_commit: str,
               catalog: Sequence[RepositorySource], generation_id: str,
               memory: MemoryProjectionRequest | None = None) -> Path:
        generation_id = _validate_generation_id(generation_id)
        repository_root = _validated_root(repository_root, must_exist=True)
        roots = (repository_root, self.staging_root, self.projection_root)
        if memory is not None:
            memory_root = _validated_root(memory.root, must_exist=True)
            roots += (memory_root,)
        for index, first in enumerate(roots):
            for second in roots[index + 1:]:
                if _roots_overlap(first, second):
                    raise ProjectionError("source, staging, projection, and memory roots must not overlap")
        catalog = self._validate_catalog(catalog)
        generated = self.clock()
        if generated.tzinfo is None or generated.utcoffset() is None:
            raise ProjectionError("generation clock must return a timezone-aware time")
        generated_local = generated.isoformat()
        generated_utc = generated.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        git = _GitReader(repository_root, source_commit)
        stage = self.staging_root / generation_id
        target = self.projection_root / "generations" / generation_id
        if stage.exists() or target.exists():
            raise ProjectionError("generation ID already exists")
        source_snapshots: dict[str, bytes] = {}
        memory_snapshots: dict[str, bytes] = {}
        entries: list[dict[str, Any]] = []
        link_diagnostics: list[dict[str, Any]] = []
        promoted = False
        try:
            self.staging_root.mkdir(parents=True, exist_ok=True)
            _assert_no_reparse_chain(self.staging_root)
            stage.mkdir()
            link_map = {item.source_path: item.output_path for item in catalog}
            for item in catalog:
                payload = git.read_blob(item.source_path)
                source_snapshots[item.source_path] = payload
                freshness = git.freshness(item, payload)
                rendered_body, diagnostics = _neutralize_markdown(
                    payload.decode("utf-8"), item, link_map
                )
                source_hash = _sha256(payload)
                note = (
                    f"# {PurePosixPath(item.source_path).stem.replace('-', ' ').replace('_', ' ')}\n\n"
                    + _banner(source=f"{item.source_path} at {source_commit}",
                              source_type=item.source_type,
                              classification=item.classification,
                              authority=item.authority_class,
                              source_hash=source_hash,
                              generated_local=generated_local,
                              generated_utc=generated_utc,
                              freshness=freshness,
                              conflict=item.conflict)
                    + "\n## Source content\n\n" + rendered_body.rstrip() + "\n"
                ).encode("utf-8")
                output = _path_within(stage, item.output_path, must_exist=False)
                _write_file(output, note)
                entries.append(self._entry(
                    kind="repository", source=item.source_path,
                    source_version=source_commit, source_hash=source_hash,
                    output_path=item.output_path, output_hash=_sha256(note),
                    source_type=item.source_type, classification=item.classification,
                    authority=item.authority_class, freshness=freshness,
                    conflict=item.conflict, content_included=True,
                    diagnostic="included from exact Git commit",
                ))
                if diagnostics:
                    link_diagnostics.append({"source": item.source_path,
                                             "diagnostics": list(diagnostics)})
            if memory is not None:
                catalog_outputs = {item.output_path.casefold() for item in catalog}
                memory_outputs = {f"memory/{memory_id}.md".casefold()
                                  for memory_id in memory.memory_ids}
                if catalog_outputs & memory_outputs:
                    raise ProjectionError("catalog output collides with a memory-note output")
                for memory_id in memory.memory_ids:
                    raw = self._read_memory(memory.root, memory_id)
                    memory_snapshots[memory_id] = raw
                    entry, note = self._render_memory(
                        raw, memory_id, memory_id in memory.approved_content_ids,
                        (memory.conflicts or {}).get(memory_id, ConflictState.NONE),
                        generated_local, generated_utc,
                    )
                    output_path = f"memory/{memory_id}.md"
                    output = _path_within(stage, output_path, must_exist=False)
                    _write_file(output, note)
                    entry["output_path"] = output_path
                    entry["output_hash"] = _sha256(note)
                    entries.append(entry)
            catalog_hash = _sha256(_json_bytes([
                {"source_path": item.source_path, "output_path": item.output_path,
                 "source_type": item.source_type.value,
                 "classification": item.classification.value,
                 "authority_class": item.authority_class.value,
                 "conflict": item.conflict.value,
                 "historical": item.historical,
                 "future_placeholder": item.future_placeholder}
                for item in catalog
            ]))
            home = self._render_home(catalog, memory, source_commit, catalog_hash,
                                     generated_local, generated_utc)
            _write_file(_path_within(stage, "Home.md", must_exist=False), home)
            entries.append(self._entry(
                kind="generated", source="typed source catalog",
                source_version=str(CATALOG_VERSION), source_hash=catalog_hash,
                output_path="Home.md", output_hash=_sha256(home),
                source_type=SourceType.NAVIGATION,
                classification=ReviewClassification.PRODUCT_OWNER_REVIEW,
                authority=AuthorityClass.DERIVED_NAVIGATION,
                freshness=FreshnessState.NO_RECORDED_VERIFICATION,
                conflict=ConflictState.NONE, content_included=True,
                diagnostic="generated navigation only",
            ))
            self._before_source_recheck()
            for source_path, before in source_snapshots.items():
                if git.read_blob(source_path) != before:
                    raise ProjectionError("repository source race detected")
            if memory is not None:
                for memory_id, before in memory_snapshots.items():
                    if self._read_memory(memory.root, memory_id) != before:
                        raise ProjectionError("memory source race detected")
            prior_generation = self._current_generation_id()
            manifest = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "complete": True,
                "exporter_version": EXPORTER_VERSION,
                "catalog_version": CATALOG_VERSION,
                "generation_id": generation_id,
                "source_commit": source_commit,
                "generated_local": generated_local,
                "generated_utc": generated_utc,
                "prior_generation_id": prior_generation,
                "entries": entries,
                "link_diagnostics": link_diagnostics,
                "validation_results": [
                    "typed catalog validated",
                    "source roots and paths contained",
                    "active content and unsafe links neutralized",
                    "source hashes stable after rendering",
                    "all output hashes recorded",
                ],
                "exclusions": [],
            }
            manifest_payload = _json_bytes(manifest)
            manifest_hash = _sha256(manifest_payload)
            _write_file(stage / "manifest.json", manifest_payload)
            _write_file(stage / "manifest.sha256", (manifest_hash + "\n").encode("ascii"))
            ProjectionVerifier.verify_generation(stage, expected_generation_id=generation_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            _assert_no_reparse_chain(target.parent)
            try:
                os.replace(stage, target)
            except OSError as exc:
                raise ProjectionError("complete-generation promotion failed") from exc
            promoted = True
            ProjectionVerifier.verify_generation(target, expected_generation_id=generation_id)
            self._write_current_pointer(generation_id, manifest_hash)
            ProjectionVerifier(self.projection_root).verify_current()
            return target
        except Exception:
            if not promoted and stage.exists():
                self._remove_failed_stage(stage)
            raise

    @staticmethod
    def _validate_catalog(catalog: Sequence[RepositorySource]) -> tuple[RepositorySource, ...]:
        if (not isinstance(catalog, Sequence) or isinstance(catalog, (str, bytes)) or
                not 1 <= len(catalog) <= MAX_CATALOG_SOURCES):
            raise ProjectionError("source catalog must contain typed repository sources")
        items = tuple(catalog)
        if any(not isinstance(item, RepositorySource) for item in items):
            raise ProjectionError("source catalog entries must be RepositorySource values")
        enum_fields = (
            ("source_type", SourceType),
            ("classification", ReviewClassification),
            ("authority_class", AuthorityClass),
            ("conflict", ConflictState),
        )
        if any(not isinstance(getattr(item, field), enum_type)
               for item in items for field, enum_type in enum_fields):
            raise ProjectionError("source catalog classification fields must use typed enums")
        sources = [item.source_path for item in items]
        outputs = [item.output_path for item in items]
        if (len(sources) != len(set(sources)) or
                len(outputs) != len({path.casefold() for path in outputs})):
            raise ProjectionError("catalog source and output paths must be unique")
        reserved = {"home.md", "manifest.json", "manifest.sha256"}
        if any(path.casefold() in reserved for path in outputs):
            raise ProjectionError("catalog output collides with generated control files")
        return items

    @staticmethod
    def _entry(*, kind: str, source: str, source_version: str, source_hash: str,
               output_path: str, output_hash: str, source_type: SourceType,
               classification: ReviewClassification, authority: AuthorityClass,
               freshness: FreshnessState, conflict: ConflictState,
               content_included: bool, diagnostic: str) -> dict[str, Any]:
        return {
            "kind": kind, "source": source, "source_version": source_version,
            "source_hash": source_hash, "output_path": output_path,
            "output_hash": output_hash, "source_type": source_type.value,
            "review_classification": classification.value,
            "authority_class": authority.value,
            "view_status": "Derived read-only projection",
            "freshness": freshness.value, "conflict": conflict.value,
            "content_included": content_included, "diagnostic": diagnostic,
        }

    @staticmethod
    def _read_memory(root: Path, memory_id: str) -> bytes:
        try:
            memory_id = _validate_memory_id(memory_id)
        except _MemoryRecordError as exc:
            raise ProjectionError("memory ID must be a canonical lowercase UUID") from exc
        name = f"{memory_id}.json"
        if not _UUID_FILE.fullmatch(name):
            raise ProjectionError("memory source must be a direct canonical UUID JSON file")
        path = _path_within(root, name, must_exist=True)
        if path.parent != _validated_root(root, must_exist=True):
            raise ProjectionError("memory source must be a direct child of its configured root")
        return _read_stable_regular_file(path, maximum_bytes=MAX_MEMORY_SOURCE_BYTES)

    @classmethod
    def _render_memory(cls, raw: bytes, memory_id: str, include_content: bool,
                       requested_conflict: ConflictState, generated_local: str,
                       generated_utc: str) -> tuple[dict[str, Any], bytes]:
        source_hash = _sha256(raw)
        conflict = requested_conflict
        diagnostic = "validated canonical memory metadata"
        record: dict[str, Any] | None = None
        unsupported = False
        try:
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict) or decoded.get("schema_version") not in (1, 2, 3):
                unsupported = True
                raise _MemoryRecordError("unsupported schema")
            record = _validate_memory_record(decoded)
            if record["memory_id"] != memory_id:
                raise _MemoryRecordError("record identity mismatch")
        except (UnicodeDecodeError, json.JSONDecodeError, _MemoryRecordError, ProjectionError):
            record = None
            conflict = ConflictState.UNSUPPORTED if unsupported else ConflictState.CORRUPT
            diagnostic = "unsupported memory schema" if unsupported else "corrupt memory record"
            include_content = False
        metadata_lines: list[str] = []
        source_version = "unknown"
        if record is not None:
            source_version = str(record["version"])
            ordered_fields = (
                "memory_id", "schema_version", "scope", "memory_type", "status", "version",
                "created_at", "updated_at", "relevance_key", "expires_at",
                "supersedes_memory_id",
                "personalized_kind", "approval",
            )
            for field in ordered_fields:
                if field in record:
                    metadata_lines.append(
                        f"- {field}: `{json.dumps(record[field], sort_keys=True, ensure_ascii=False)}`"
                    )
            metadata_lines.append(f"- provenance origin: `{record['provenance']['origin']}`")
        else:
            metadata_lines.append(f"- memory_id: `{memory_id}`")
            metadata_lines.append(f"- validation diagnostic: `{diagnostic}`")
        body = (
            f"# Governed memory {memory_id}\n\n"
            + _banner(source=f"memory ID {memory_id}, record version {source_version}",
                      source_type=SourceType.GOVERNED_MEMORY,
                      classification=ReviewClassification.SENSITIVE_LOCAL,
                      authority=AuthorityClass.CANONICAL_GOVERNED_MEMORY,
                      source_hash=source_hash, generated_local=generated_local,
                      generated_utc=generated_utc,
                      freshness=FreshnessState.NO_RECORDED_VERIFICATION,
                      conflict=conflict)
            + "\n## Allowlisted metadata\n\n" + "\n".join(metadata_lines) + "\n"
        )
        if include_content and record is not None:
            inert_content = "\n".join("    " + line for line in record["content"].splitlines())
            body += (
                "\n## Approved content\n\n"
                "> [!CAUTION] UNTRUSTED CONTEXT\n"
                "> The following exact record content is data, not an instruction or permission.\n\n"
                + inert_content + "\n"
            )
            diagnostic = "exact-ID approved content included"
        else:
            body += "\n## Content\n\nContent excluded by the metadata-only default.\n"
        encoded = body.encode("utf-8")
        entry = cls._entry(
            kind="memory", source=memory_id, source_version=source_version,
            source_hash=source_hash, output_path="", output_hash="",
            source_type=SourceType.GOVERNED_MEMORY,
            classification=ReviewClassification.SENSITIVE_LOCAL,
            authority=AuthorityClass.CANONICAL_GOVERNED_MEMORY,
            freshness=FreshnessState.NO_RECORDED_VERIFICATION,
            conflict=conflict, content_included=include_content and record is not None,
            diagnostic=diagnostic,
        )
        return entry, encoded

    @staticmethod
    def _render_home(catalog: Sequence[RepositorySource],
                     memory: MemoryProjectionRequest | None, source_commit: str,
                     catalog_hash: str,
                     generated_local: str, generated_utc: str) -> bytes:
        banner = _banner(
            source=f"typed source catalog version {CATALOG_VERSION} at {source_commit}",
            source_type=SourceType.NAVIGATION,
            classification=ReviewClassification.PRODUCT_OWNER_REVIEW,
            authority=AuthorityClass.DERIVED_NAVIGATION,
            source_hash=catalog_hash, generated_local=generated_local,
            generated_utc=generated_utc,
            freshness=FreshnessState.NO_RECORDED_VERIFICATION,
            conflict=ConflictState.NONE,
        )
        links = [f"- [{item.source_path}]({item.output_path})" for item in catalog]
        if memory is not None:
            links.extend(f"- [Governed memory {memory_id}](memory/{memory_id}.md)"
                         for memory_id in memory.memory_ids)
        return ("# GRACI Knowledge Review\n\n" + banner +
                "\n## Cataloged review notes\n\n" + "\n".join(links) + "\n").encode("utf-8")

    def _current_generation_id(self) -> str | None:
        pointer = self.projection_root / "current.json"
        if not pointer.exists():
            return None
        return ProjectionVerifier(self.projection_root).verify_current()["generation_id"]

    def _write_current_pointer(self, generation_id: str, manifest_hash: str) -> None:
        self.projection_root.mkdir(parents=True, exist_ok=True)
        _assert_no_reparse_chain(self.projection_root)
        temporary = self.projection_root / f".current.{generation_id}.tmp"
        payload = _json_bytes({"schema_version": 1, "generation_id": generation_id,
                               "manifest_sha256": manifest_hash})
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.projection_root / "current.json")
        except OSError as exc:
            raise ProjectionError("current-generation pointer update failed") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _before_source_recheck(self) -> None:
        """Test seam invoked after rendering and before mandatory source rechecks."""

    def _remove_failed_stage(self, stage: Path) -> None:
        resolved = stage.resolve(strict=False)
        if resolved.parent != self.staging_root or not resolved.name:
            raise ProjectionError("refused to remove an uncontained staging path")
        _assert_no_reparse_chain(resolved)
        _walk_regular_files(resolved)
        shutil.rmtree(resolved)


class ProjectionVerifier:
    """Read-only verifier for immutable generations and the current pointer."""

    def __init__(self, projection_root: Path):
        self.projection_root = _validated_root(projection_root, must_exist=True)

    @staticmethod
    def verify_generation(generation_root: Path,
                          *, expected_generation_id: str | None = None) -> dict[str, Any]:
        root = _validated_root(generation_root, must_exist=True)
        _assert_no_reparse_chain(root)
        manifest_path = _path_within(root, "manifest.json", must_exist=True)
        digest_path = _path_within(root, "manifest.sha256", must_exist=True)
        manifest_payload = _read_stable_regular_file(
            manifest_path, maximum_bytes=MAX_GENERATED_FILE_BYTES
        )
        try:
            recorded_digest = _read_stable_regular_file(
                digest_path, maximum_bytes=1024
            ).decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise ProjectionError("manifest digest file is malformed") from exc
        if not re.fullmatch(r"[0-9a-f]{64}", recorded_digest):
            raise ProjectionError("manifest digest file is malformed")
        if _sha256(manifest_payload) != recorded_digest:
            raise ProjectionError("manifest tampering detected")
        try:
            manifest = json.loads(manifest_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectionError("manifest is malformed") from exc
        required = {
            "schema_version", "complete", "exporter_version", "catalog_version",
            "generation_id", "source_commit", "generated_local", "generated_utc",
            "prior_generation_id", "entries", "link_diagnostics",
            "validation_results", "exclusions",
        }
        if not isinstance(manifest, dict) or set(manifest) != required:
            raise ProjectionError("manifest fields do not match the strict schema")
        if (type(manifest["schema_version"]) is not int or
                manifest["schema_version"] != MANIFEST_SCHEMA_VERSION or
                manifest["complete"] is not True):
            raise ProjectionError("manifest does not describe a complete supported generation")
        if (manifest["exporter_version"] != EXPORTER_VERSION or
                type(manifest["catalog_version"]) is not int or
                manifest["catalog_version"] != CATALOG_VERSION):
            raise ProjectionError("manifest exporter or catalog version is unsupported")
        generation_id = _validate_generation_id(manifest["generation_id"])
        if expected_generation_id is not None and generation_id != expected_generation_id:
            raise ProjectionError("generation identity mismatch")
        if root.name != generation_id:
            raise ProjectionError("generation directory and manifest identity differ")
        if (not isinstance(manifest["source_commit"], str) or
                not _COMMIT.fullmatch(manifest["source_commit"])):
            raise ProjectionError("manifest source commit is invalid")
        if manifest["prior_generation_id"] is not None:
            _validate_generation_id(manifest["prior_generation_id"])
        for field in ("generated_local", "generated_utc"):
            try:
                value = datetime.fromisoformat(manifest[field].replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise ProjectionError("manifest generation time is invalid") from exc
            if value.tzinfo is None or value.utcoffset() is None:
                raise ProjectionError("manifest generation time is not timezone-aware")
        if (not isinstance(manifest["link_diagnostics"], list) or
                not isinstance(manifest["validation_results"], list) or
                not all(isinstance(value, str) and value
                        for value in manifest["validation_results"]) or
                not isinstance(manifest["exclusions"], list)):
            raise ProjectionError("manifest diagnostics and validation results are invalid")
        if not isinstance(manifest["entries"], list) or not manifest["entries"]:
            raise ProjectionError("manifest entries are incomplete")
        expected_files = {"manifest.json", "manifest.sha256"}
        seen_outputs: set[str] = set()
        for entry in manifest["entries"]:
            if not isinstance(entry, dict) or set(entry) != _MANIFEST_ENTRY_FIELDS:
                raise ProjectionError("manifest entry is malformed")
            output_path = entry.get("output_path")
            output_hash = entry.get("output_hash")
            _validate_relative_path(output_path, suffix=".md")
            normalized_output = output_path.casefold()
            if (normalized_output in seen_outputs or
                    normalized_output in {path.casefold() for path in expected_files}):
                raise ProjectionError("manifest contains duplicate or reserved output")
            if not isinstance(output_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", output_hash):
                raise ProjectionError("manifest output hash is malformed")
            if (not isinstance(entry["source_hash"], str) or
                    not re.fullmatch(r"[0-9a-f]{64}", entry["source_hash"])):
                raise ProjectionError("manifest source hash is malformed")
            if entry["view_status"] != "Derived read-only projection":
                raise ProjectionError("manifest view status is invalid")
            try:
                SourceType(entry["source_type"])
                ReviewClassification(entry["review_classification"])
                AuthorityClass(entry["authority_class"])
                FreshnessState(entry["freshness"])
                ConflictState(entry["conflict"])
            except (TypeError, ValueError) as exc:
                raise ProjectionError("manifest entry labels are invalid") from exc
            if type(entry["content_included"]) is not bool:
                raise ProjectionError("manifest content-inclusion value is invalid")
            if (entry["kind"] not in {"repository", "memory", "generated"} or
                    not all(isinstance(entry[field], str) and entry[field]
                            for field in ("source", "source_version", "diagnostic"))):
                raise ProjectionError("manifest entry source metadata is invalid")
            output = _path_within(root, output_path, must_exist=True)
            output_payload = _read_stable_regular_file(
                output, maximum_bytes=MAX_GENERATED_FILE_BYTES
            )
            if _sha256(output_payload) != output_hash:
                raise ProjectionError("projected-note tampering detected")
            seen_outputs.add(normalized_output)
            expected_files.add(output_path)
        if "home.md" not in seen_outputs:
            raise ProjectionError("generation is missing its required Home note")
        actual_files = {
            path.relative_to(root).as_posix() for path in _walk_regular_files(root)
        }
        if actual_files != expected_files:
            raise ProjectionError("generation contains missing or unmanifested files")
        return manifest

    def verify_current(self) -> dict[str, Any]:
        pointer_path = _path_within(self.projection_root, "current.json", must_exist=True)
        try:
            pointer_payload = _read_stable_regular_file(pointer_path, maximum_bytes=65_536)
            pointer = json.loads(pointer_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectionError("current-generation pointer is malformed") from exc
        if (not isinstance(pointer, dict) or
                set(pointer) != {"schema_version", "generation_id", "manifest_sha256"} or
                type(pointer["schema_version"]) is not int or pointer["schema_version"] != 1):
            raise ProjectionError("current-generation pointer fields are invalid")
        generation_id = _validate_generation_id(pointer["generation_id"])
        generation = _path_within(
            self.projection_root, f"generations/{generation_id}", must_exist=False
        )
        if not generation.is_dir():
            raise ProjectionError("current generation is missing")
        manifest = self.verify_generation(generation, expected_generation_id=generation_id)
        actual_manifest_hash = _sha256(_read_stable_regular_file(
            generation / "manifest.json", maximum_bytes=MAX_GENERATED_FILE_BYTES
        ))
        if pointer["manifest_sha256"] != actual_manifest_hash:
            raise ProjectionError("current pointer does not match the generation manifest")
        return manifest
