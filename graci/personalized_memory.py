"""Synthetic-only personalized-memory approval and lifecycle foundation.

This module is deliberately absent from ordinary operator composition. It stores
only explicitly labelled synthetic fixtures, requires an exact Product Owner
approval attestation before canonical memory changes, and treats every retrieved
memory as untrusted context rather than authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Mapping, Sequence

from .memory import (MemoryStatus, MemoryStore, MemoryType, MemoryValidationError,
                     PersonalizedKind, _parse_timestamp, _stamp,
                     _validate_provenance, _validate_scope, validate_memory_id,
                     validate_record)
from .memory_governance import MemoryGovernance, validate_relevance_key


STORE_SCHEMA_VERSION = 1
PROPOSAL_SCHEMA_VERSION = 1
AUDIT_SCHEMA_VERSION = 1
SYNTHETIC_MARKER = "synthetic-boundary.json"
MAX_EVIDENCE_REFS = 16
MAX_AUDIT_EVENTS = 10_000
MAX_PROPOSALS = 1_000
MAX_PERSONALIZED_MEMORIES = 1_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PROPOSAL_NAMESPACE = uuid.UUID("dd976d62-e944-4f45-9eea-75eef5d7999c")
_APPROVAL_NAMESPACE = uuid.UUID("6388e30c-1ff2-4833-9e34-45f31cc70131")
_MEMORY_NAMESPACE = uuid.UUID("9cd52931-dc60-40ec-9c32-a5d2df593fcf")


class PersonalizedMemoryError(RuntimeError):
    """The synthetic repository or a requested transition failed closed."""


class ProposalAction(str, Enum):
    CREATE = "create"
    CORRECT = "correct"
    RETIRE = "retire"


class ProposalOrigin(str, Enum):
    PRODUCT_OWNER_DIRECT = "product_owner_direct"
    GRACI_AFTER_VERIFIED_WORK = "graci_after_verified_work"


class SourceBoundary(str, Enum):
    TYPED_TURN = "typed_turn"
    PTT_RELEASE = "ptt_release"
    VERIFIED_WORK = "verified_work"


class ApprovalChannel(str, Enum):
    TYPED_TURN = "typed_turn"
    PTT_RELEASE = "ptt_release"


_KIND_TO_MEMORY_TYPE = {
    PersonalizedKind.PREFERENCE.value: MemoryType.PREFERENCE.value,
    PersonalizedKind.WORKING_METHOD.value: MemoryType.WORKFLOW.value,
    PersonalizedKind.TASK_PROCEDURE.value: MemoryType.WORKFLOW.value,
    PersonalizedKind.CORRECTION.value: MemoryType.CONTEXT.value,
    PersonalizedKind.LESSON.value: MemoryType.FACT.value,
}


@dataclass(frozen=True)
class ProposalRequest:
    operation_id: str
    action: str
    personalized_kind: str
    scope: Mapping[str, Any]
    relevance_key: str
    content: str
    source_ref: str
    source_turn_id: str
    proposal_origin: str
    source_boundary: str
    evidence_refs: tuple[str, ...] = ()
    target_memory_id: str | None = None
    expected_target_version: int | None = None
    expires_at: str | None = None
    data_classification: str = "synthetic_fixture"


@dataclass(frozen=True)
class ExactApproval:
    operation_id: str
    proposal_id: str
    proposal_digest: str
    source_turn_id: str
    channel: str
    authority: str = "product_owner"
    decision: str = "approve_exact"


@dataclass(frozen=True)
class RollbackApproval:
    operation_id: str
    target_generation_id: str
    target_manifest_sha256: str
    source_turn_id: str
    channel: str
    authority: str = "product_owner"
    decision: str = "approve_exact_rollback"


@dataclass(frozen=True)
class PersonalizedRetrievalRequest:
    context: Mapping[str, Any]
    relevance_keys: tuple[str, ...]
    allowed_kinds: tuple[str, ...]
    limit: int = 25
    expected_generation_id: str | None = None


@dataclass(frozen=True)
class MutationResult:
    accepted: bool
    reason: str
    generation_id: str | None = None
    proposal_id: str | None = None
    memory_id: str | None = None
    idempotent_replay: bool = False


@dataclass(frozen=True)
class PersonalizedRetrievalResult:
    accepted: bool
    reason: str
    records: tuple[dict[str, Any], ...]
    conflicts: tuple[dict[str, Any], ...]
    corruptions: tuple[dict[str, Any], ...]
    evidence: dict[str, Any]


@dataclass(frozen=True)
class RepositorySnapshot:
    generation_id: str
    generation_root: Path
    memory_root: Path
    memory_ids: tuple[str, ...]
    manifest_sha256: str


Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _is_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _assert_plain_chain(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    for candidate in tuple(reversed(absolute.parents)) + (absolute,):
        if _is_reparse(candidate):
            raise PersonalizedMemoryError("reparse points are forbidden in the synthetic repository path")


def _validate_root(root: Path, *, must_exist: bool) -> Path:
    candidate = Path(root)
    if not candidate.is_absolute():
        raise PersonalizedMemoryError("synthetic personalized-memory root must be absolute")
    raw = str(candidate)
    if raw.startswith(("\\\\", "//", "\\?\\", "\\.\\", "\\??\\")):
        raise PersonalizedMemoryError("UNC and device roots are forbidden")
    windows = PureWindowsPath(raw)
    if ":" in raw[len(windows.drive):]:
        raise PersonalizedMemoryError("alternate data stream paths are forbidden")
    _assert_plain_chain(candidate)
    resolved = candidate.resolve(strict=False)
    if must_exist and (not resolved.exists() or not resolved.is_dir()):
        raise PersonalizedMemoryError("synthetic personalized-memory root is missing")
    return resolved


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_plain_chain(path.parent)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise PersonalizedMemoryError("exclusive synthetic state write failed") from exc


def _bounded_text(value: Any, field_name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise MemoryValidationError(f"{field_name} must be bounded non-empty text")
    return value


def _validate_generation_id(value: Any) -> str:
    try:
        return validate_memory_id(value)
    except MemoryValidationError as exc:
        raise PersonalizedMemoryError("generation ID must be a canonical lowercase UUID") from exc


def _proposal_payload(request: ProposalRequest) -> dict[str, Any]:
    operation_id = validate_memory_id(request.operation_id)
    action = ProposalAction(request.action).value
    kind = PersonalizedKind(request.personalized_kind).value
    scope = _validate_scope(request.scope)
    relevance_key = validate_relevance_key(request.relevance_key)
    content = _bounded_text(request.content, "proposal content", maximum=16_384)
    if len(content.encode("utf-8")) > 16_384:
        raise MemoryValidationError("proposal content exceeds the canonical UTF-8 byte limit")
    provenance = _validate_provenance({"origin": "explicit_user",
                                       "source_ref": request.source_ref})
    if not provenance["source_ref"].startswith("synthetic:"):
        raise MemoryValidationError("synthetic proposals require a synthetic: source reference")
    source_turn_id = validate_memory_id(request.source_turn_id)
    origin = ProposalOrigin(request.proposal_origin).value
    boundary = SourceBoundary(request.source_boundary).value
    if origin == ProposalOrigin.PRODUCT_OWNER_DIRECT.value and boundary not in {
            SourceBoundary.TYPED_TURN.value, SourceBoundary.PTT_RELEASE.value}:
        raise MemoryValidationError("direct Product Owner proposals require an explicit turn boundary")
    if origin == ProposalOrigin.GRACI_AFTER_VERIFIED_WORK.value and boundary != SourceBoundary.VERIFIED_WORK.value:
        raise MemoryValidationError("GRACI proposals require a verified-work source boundary")
    refs = request.evidence_refs
    if (not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or
            len(refs) > MAX_EVIDENCE_REFS):
        raise MemoryValidationError("evidence references exceed the bounded list")
    evidence_refs = tuple(_bounded_text(item, "evidence reference") for item in refs)
    if origin == ProposalOrigin.GRACI_AFTER_VERIFIED_WORK.value and not evidence_refs:
        raise MemoryValidationError("a GRACI proposal requires verified-work evidence")
    if any(not item.startswith("synthetic:") for item in evidence_refs):
        raise MemoryValidationError("synthetic proposals require synthetic: evidence references")
    target = request.target_memory_id
    expected_version = request.expected_target_version
    if action == ProposalAction.CREATE.value:
        if target is not None or expected_version is not None:
            raise MemoryValidationError("create proposals cannot name a target memory")
    else:
        target = validate_memory_id(target)
        if type(expected_version) is not int or expected_version < 1:
            raise MemoryValidationError("correction and retirement require an exact target version")
    expires_at = request.expires_at
    if expires_at is not None:
        _parse_timestamp(expires_at, "expires_at")
    if request.data_classification != "synthetic_fixture":
        raise MemoryValidationError("only synthetic_fixture data is authorized")
    return {
        "operation_id": operation_id,
        "action": action,
        "personalized_kind": kind,
        "scope": scope,
        "memory_type": _KIND_TO_MEMORY_TYPE[kind],
        "relevance_key": relevance_key,
        "content": content,
        "source_ref": provenance["source_ref"],
        "source_turn_id": source_turn_id,
        "proposal_origin": origin,
        "source_boundary": boundary,
        "evidence_refs": list(evidence_refs),
        "target_memory_id": target,
        "expected_target_version": expected_version,
        "expires_at": expires_at,
        "data_classification": "synthetic_fixture",
    }


def _proposal_digest(payload: Mapping[str, Any]) -> str:
    return _sha256(_canonical_json(dict(payload)))


class SyntheticPersonalizedMemoryRepository:
    """Immutable-generation repository for synthetic personalized-memory fixtures."""

    def __init__(self, root: Path, *, clock: Clock = _now,
                 generation_id_factory: IdFactory = _new_id):
        self.root = _validate_root(root, must_exist=True)
        self.clock = clock
        self.generation_id_factory = generation_id_factory
        self._verify_boundary_marker()

    @classmethod
    def initialize(cls, root: Path, *, clock: Clock = _now,
                   generation_id_factory: IdFactory = _new_id) -> "SyntheticPersonalizedMemoryRepository":
        target = _validate_root(root, must_exist=False)
        if target.exists() and any(target.iterdir()):
            raise PersonalizedMemoryError("synthetic repository initialization requires an empty root")
        target.mkdir(parents=True, exist_ok=True)
        marker = {
            "schema_version": 1,
            "classification": "SYNTHETIC_ONLY",
            "real_personal_data_permitted": False,
            "deployment_permitted": False,
            "automatic_refresh_permitted": False,
        }
        _write_exclusive(target / SYNTHETIC_MARKER, _json_bytes(marker))
        repository = cls(target, clock=clock, generation_id_factory=generation_id_factory)
        initialized_at = repository._timestamp()
        repository._commit_state(
            proposals={}, memories={}, audit=[repository._audit_event(
                sequence=1, event_type="SYNTHETIC_REPOSITORY_INITIALIZED",
                occurred_at=initialized_at, operation_id=None,
                details={"classification": "SYNTHETIC_ONLY"},
            )], parent_generation_id=None,
        )
        return repository

    def propose(self, request: ProposalRequest) -> MutationResult:
        try:
            payload = _proposal_payload(request)
        except (MemoryValidationError, ValueError, TypeError, UnicodeEncodeError):
            return MutationResult(False, "INVALID_PROPOSAL")
        proposals, memories, audit, snapshot = self._load_current_state()
        proposal_id = str(uuid.uuid5(_PROPOSAL_NAMESPACE, payload["operation_id"]))
        digest = _proposal_digest(payload)
        existing = proposals.get(proposal_id)
        if existing is not None:
            comparable = {key: existing[key] for key in payload}
            if comparable == payload and existing["proposal_digest"] == digest:
                return MutationResult(True, "IDEMPOTENT_REPLAY", snapshot.generation_id,
                                      proposal_id, existing.get("result_memory_id"), True)
            return MutationResult(False, "IDEMPOTENCY_CONFLICT", proposal_id=proposal_id)
        if any(event.get("operation_id") == payload["operation_id"] for event in audit):
            return MutationResult(False, "IDEMPOTENCY_CONFLICT", proposal_id=proposal_id)
        if len(proposals) >= MAX_PROPOSALS:
            return MutationResult(False, "PROPOSAL_LIMIT")
        if payload["target_memory_id"] is not None:
            target = memories.get(payload["target_memory_id"])
            if target is None:
                return MutationResult(False, "TARGET_NOT_FOUND")
            if (target.get("schema_version") != 3 or
                    target["version"] != payload["expected_target_version"] or
                    target["status"] != MemoryStatus.ACTIVE.value):
                return MutationResult(False, "STALE_TARGET")
            if (target["scope"] != payload["scope"] or
                    target["relevance_key"] != payload["relevance_key"] or
                    target["personalized_kind"] != payload["personalized_kind"]):
                return MutationResult(False, "TARGET_MISMATCH")
        now = self._timestamp()
        proposal = {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "proposal_id": proposal_id,
            **payload,
            "proposal_digest": digest,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "approval": None,
            "result_memory_id": None,
        }
        proposals[proposal_id] = proposal
        audit.append(self._audit_event(
            sequence=len(audit) + 1, event_type="PROPOSAL_CREATED",
            occurred_at=now, operation_id=payload["operation_id"],
            details={"proposal_id": proposal_id, "proposal_digest": digest,
                     "action": payload["action"], "target_memory_id": payload["target_memory_id"]},
        ))
        generation = self._commit_state(proposals=proposals, memories=memories,
                                        audit=audit, parent_generation_id=snapshot.generation_id)
        return MutationResult(True, "PROPOSED", generation, proposal_id)

    def approve(self, approval: ExactApproval) -> MutationResult:
        try:
            operation_id = validate_memory_id(approval.operation_id)
            proposal_id = validate_memory_id(approval.proposal_id)
            source_turn_id = validate_memory_id(approval.source_turn_id)
            channel = ApprovalChannel(approval.channel).value
            if (approval.authority != "product_owner" or
                    approval.decision != "approve_exact" or
                    not _SHA256.fullmatch(approval.proposal_digest)):
                raise MemoryValidationError("approval attestation is not exact")
        except (MemoryValidationError, ValueError, TypeError):
            return MutationResult(False, "INVALID_APPROVAL")
        proposals, memories, audit, snapshot = self._load_current_state()
        proposal = proposals.get(proposal_id)
        prior_operation = [event for event in audit
                           if event.get("operation_id") == operation_id]
        if proposal is None:
            reason = "IDEMPOTENCY_CONFLICT" if prior_operation else "PROPOSAL_NOT_FOUND"
            return MutationResult(False, reason, proposal_id=proposal_id)
        approval_id = str(uuid.uuid5(_APPROVAL_NAMESPACE, operation_id))
        prior_approval = proposal.get("approval")
        if proposal["status"] == "approved":
            if (prior_approval is not None and prior_approval["approval_id"] == approval_id and
                    prior_approval["proposal_digest"] == approval.proposal_digest):
                return MutationResult(True, "IDEMPOTENT_REPLAY", snapshot.generation_id,
                                      proposal_id, proposal["result_memory_id"], True)
            return MutationResult(False, "ALREADY_DECIDED", proposal_id=proposal_id)
        if prior_operation:
            return MutationResult(False, "IDEMPOTENCY_CONFLICT", proposal_id=proposal_id)
        if (proposal["status"] != "pending" or
                proposal["proposal_digest"] != approval.proposal_digest):
            return MutationResult(False, "APPROVAL_MISMATCH", proposal_id=proposal_id)
        target = None
        if proposal["target_memory_id"] is not None:
            target = memories.get(proposal["target_memory_id"])
            if target is None:
                return MutationResult(False, "TARGET_NOT_FOUND", proposal_id=proposal_id)
            if (target["status"] != MemoryStatus.ACTIVE.value or
                    target["version"] != proposal["expected_target_version"]):
                return MutationResult(False, "STALE_TARGET", proposal_id=proposal_id)
        approved_at = self._timestamp()
        attestation = {
            "approval_id": approval_id,
            "proposal_id": proposal_id,
            "authority": "product_owner",
            "channel": channel,
            "source_turn_id": source_turn_id,
            "approved_at": approved_at,
            "proposal_digest": approval.proposal_digest,
        }
        action = proposal["action"]
        result_memory_id: str | None
        if action in {ProposalAction.CREATE.value, ProposalAction.CORRECT.value}:
            if len(memories) >= MAX_PERSONALIZED_MEMORIES:
                return MutationResult(False, "MEMORY_LIMIT", proposal_id=proposal_id)
            result_memory_id = str(uuid.uuid5(_MEMORY_NAMESPACE, operation_id))
            if result_memory_id in memories:
                return MutationResult(False, "IDEMPOTENCY_CONFLICT", proposal_id=proposal_id)
            builder = MemoryStore(self.root / ".record-builder", clock=self.clock)
            record = builder.new_record(
                scope=proposal["scope"], memory_type=proposal["memory_type"],
                content=proposal["content"],
                provenance={"origin": "explicit_user",
                            "source_ref": f"synthetic:proposal:{proposal_id}"},
                memory_id=result_memory_id,
                relevance_key=proposal["relevance_key"],
                expires_at=proposal["expires_at"],
                supersedes_memory_id=(target["memory_id"] if target is not None else None),
                personalized_kind=proposal["personalized_kind"], approval=attestation,
            )
            memories[result_memory_id] = record
            if target is not None:
                memories[target["memory_id"]] = self._transition_record(
                    target, MemoryStatus.SUPERSEDED.value
                )
        else:
            if target is None:
                return MutationResult(False, "TARGET_NOT_FOUND", proposal_id=proposal_id)
            result_memory_id = target["memory_id"]
            memories[result_memory_id] = self._transition_record(
                target, MemoryStatus.TOMBSTONED.value
            )
        proposal = dict(proposal)
        proposal.update({"status": "approved", "updated_at": approved_at,
                         "approval": attestation, "result_memory_id": result_memory_id})
        proposals[proposal_id] = proposal
        event_type = {
            ProposalAction.CREATE.value: "MEMORY_CREATED",
            ProposalAction.CORRECT.value: "MEMORY_CORRECTED",
            ProposalAction.RETIRE.value: "MEMORY_RETIRED",
        }[action]
        audit.append(self._audit_event(
            sequence=len(audit) + 1, event_type=event_type,
            occurred_at=approved_at, operation_id=operation_id,
            details={"proposal_id": proposal_id, "approval_id": approval_id,
                     "proposal_digest": approval.proposal_digest,
                     "memory_id": result_memory_id,
                     "target_memory_id": proposal["target_memory_id"],
                     "authority": "product_owner", "channel": channel},
        ))
        try:
            generation = self._commit_state(
                proposals=proposals, memories=memories, audit=audit,
                parent_generation_id=snapshot.generation_id,
            )
        except PersonalizedMemoryError:
            return MutationResult(False, "STORAGE_ERROR", proposal_id=proposal_id)
        return MutationResult(True, event_type, generation, proposal_id, result_memory_id)

    def retrieve(self, request: PersonalizedRetrievalRequest) -> PersonalizedRetrievalResult:
        try:
            if (not request.relevance_keys or not request.allowed_kinds or
                    len(set(request.allowed_kinds)) != len(request.allowed_kinds)):
                raise MemoryValidationError("retrieval lists must be non-empty and unique")
            keys = tuple(validate_relevance_key(item) for item in request.relevance_keys)
            kinds = tuple(PersonalizedKind(item).value for item in request.allowed_kinds)
            if request.expected_generation_id is not None:
                _validate_generation_id(request.expected_generation_id)
        except (MemoryValidationError, ValueError, TypeError):
            return self._retrieval_failure("INVALID_REQUEST")
        try:
            snapshot = self.current_snapshot()
        except PersonalizedMemoryError:
            return self._retrieval_failure("MEMORY_UNAVAILABLE")
        evidence = self._retrieval_evidence(snapshot, request, keys, kinds)
        if (request.expected_generation_id is not None and
                request.expected_generation_id != snapshot.generation_id):
            evidence["status"] = "STALE_SOURCE"
            return PersonalizedRetrievalResult(False, "STALE_SOURCE", (), (), (), evidence)
        memory_types = tuple(sorted({_KIND_TO_MEMORY_TYPE[item] for item in kinds}))
        governance = MemoryGovernance(MemoryStore(snapshot.memory_root, clock=self.clock))
        selection = governance.select({
            "context": dict(request.context), "relevance_keys": list(keys),
            "allowed_memory_types": list(memory_types), "limit": request.limit,
        })
        conflicts = tuple({"relevance_key": item.relevance_key,
                           "memory_type": item.memory_type,
                           "scope_specificity": item.scope_specificity,
                           "memory_ids": list(item.memory_ids), "reason": item.reason}
                          for item in selection.conflicts)
        corruptions = tuple({"memory_id_hint": item.memory_id_hint, "reason": item.error}
                            for item in selection.corruptions)
        records = tuple(record for record in selection.records
                        if record.get("personalized_kind") in kinds)
        evidence.update({
            "selection_reason": selection.reason,
            "selected_memory_ids": [record["memory_id"] for record in records],
            "conflict_count": len(conflicts), "corruption_count": len(corruptions),
            "selection_truncated": selection.truncated,
        })
        if not selection.accepted:
            evidence["status"] = "MEMORY_UNAVAILABLE"
            return PersonalizedRetrievalResult(False, "MEMORY_UNAVAILABLE", (),
                                               conflicts, corruptions, evidence)
        if conflicts:
            evidence["status"] = "MEMORY_CONFLICT"
            return PersonalizedRetrievalResult(False, "MEMORY_CONFLICT", (),
                                               conflicts, corruptions, evidence)
        if corruptions:
            evidence["status"] = "MEMORY_CORRUPT"
            return PersonalizedRetrievalResult(False, "MEMORY_CORRUPT", (),
                                               conflicts, corruptions, evidence)
        reason = "MEMORY_APPLIED" if records else "NO_APPLICABLE_MEMORY"
        evidence["status"] = reason
        return PersonalizedRetrievalResult(True, reason, records, conflicts,
                                           corruptions, evidence)

    def rollback(self, approval: RollbackApproval) -> MutationResult:
        try:
            operation_id = validate_memory_id(approval.operation_id)
            target_id = _validate_generation_id(approval.target_generation_id)
            source_turn_id = validate_memory_id(approval.source_turn_id)
            channel = ApprovalChannel(approval.channel).value
            if (approval.authority != "product_owner" or
                    approval.decision != "approve_exact_rollback" or
                    not _SHA256.fullmatch(approval.target_manifest_sha256)):
                raise MemoryValidationError("rollback approval is not exact")
        except (MemoryValidationError, PersonalizedMemoryError, ValueError, TypeError):
            return MutationResult(False, "INVALID_APPROVAL")
        _, _, current_audit, current = self._load_current_state()
        prior_operation = [event for event in current_audit
                           if event.get("operation_id") == operation_id]
        if prior_operation:
            expected_details = {
                "target_generation_id": target_id,
                "target_manifest_sha256": approval.target_manifest_sha256,
                "authority": "product_owner",
                "channel": channel,
                "source_turn_id": source_turn_id,
            }
            if (len(prior_operation) == 1 and
                    prior_operation[0].get("event_type") == "STATE_ROLLED_BACK" and
                    all(prior_operation[0].get("details", {}).get(key) == value
                        for key, value in expected_details.items())):
                return MutationResult(True, "IDEMPOTENT_REPLAY", current.generation_id,
                                      idempotent_replay=True)
            return MutationResult(False, "IDEMPOTENCY_CONFLICT")
        try:
            target = self._verify_generation(target_id)
        except PersonalizedMemoryError:
            return MutationResult(False, "TARGET_GENERATION_INVALID")
        if target.manifest_sha256 != approval.target_manifest_sha256:
            return MutationResult(False, "APPROVAL_MISMATCH")
        if target_id == current.generation_id:
            return MutationResult(True, "IDEMPOTENT_REPLAY", current.generation_id,
                                  idempotent_replay=True)
        target_proposals, target_memories, _ = self._read_generation_state(target)
        now = self._timestamp()
        current_audit.append(self._audit_event(
            sequence=len(current_audit) + 1, event_type="STATE_ROLLED_BACK",
            occurred_at=now, operation_id=operation_id,
            details={"from_generation_id": current.generation_id,
                     "target_generation_id": target_id,
                     "target_manifest_sha256": target.manifest_sha256,
                     "authority": "product_owner", "channel": channel,
                     "source_turn_id": source_turn_id},
        ))
        try:
            generation = self._commit_state(
                proposals=target_proposals, memories=target_memories,
                audit=current_audit, parent_generation_id=current.generation_id,
                rollback_source_generation_id=target_id,
            )
        except PersonalizedMemoryError:
            return MutationResult(False, "STORAGE_ERROR")
        return MutationResult(True, "STATE_ROLLED_BACK", generation)

    def current_snapshot(self) -> RepositorySnapshot:
        pointer_path = self.root / "current.json"
        try:
            pointer = json.loads(pointer_path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PersonalizedMemoryError("current synthetic state pointer is unavailable") from exc
        if (not isinstance(pointer, dict) or
                set(pointer) != {"schema_version", "generation_id", "manifest_sha256"} or
                pointer["schema_version"] != STORE_SCHEMA_VERSION or
                not _SHA256.fullmatch(pointer.get("manifest_sha256", ""))):
            raise PersonalizedMemoryError("current synthetic state pointer is malformed")
        snapshot = self._verify_generation(pointer["generation_id"])
        if snapshot.manifest_sha256 != pointer["manifest_sha256"]:
            raise PersonalizedMemoryError("current pointer does not match its generation")
        return snapshot

    def snapshot(self, generation_id: str) -> RepositorySnapshot:
        """Verify and return one exact immutable synthetic generation."""
        return self._verify_generation(generation_id)

    def read_proposal(self, proposal_id: str) -> dict[str, Any]:
        proposal_id = validate_memory_id(proposal_id)
        proposals, _, _, _ = self._load_current_state()
        if proposal_id not in proposals:
            raise PersonalizedMemoryError("proposal is not present in current synthetic state")
        return dict(proposals[proposal_id])

    def audit_events(self) -> tuple[dict[str, Any], ...]:
        _, _, audit, _ = self._load_current_state()
        return tuple(dict(event) for event in audit)

    def _verify_boundary_marker(self) -> None:
        try:
            marker = json.loads((self.root / SYNTHETIC_MARKER).read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PersonalizedMemoryError("synthetic-only boundary marker is missing") from exc
        expected = {
            "schema_version": 1, "classification": "SYNTHETIC_ONLY",
            "real_personal_data_permitted": False, "deployment_permitted": False,
            "automatic_refresh_permitted": False,
        }
        if marker != expected:
            raise PersonalizedMemoryError("synthetic-only boundary marker is invalid")

    def _timestamp(self) -> str:
        try:
            return _stamp(self.clock())
        except MemoryValidationError as exc:
            raise PersonalizedMemoryError("repository clock must be timezone-aware") from exc

    @staticmethod
    def _audit_event(*, sequence: int, event_type: str, occurred_at: str,
                     operation_id: str | None, details: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "sequence": sequence,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "operation_id": operation_id,
            "details": dict(details),
        }

    def _transition_record(self, record: Mapping[str, Any], status: str) -> dict[str, Any]:
        updated = dict(record)
        updated["status"] = status
        updated["version"] = record["version"] + 1
        now = self.clock()
        prior = _parse_timestamp(record["updated_at"], "updated_at")
        if now.tzinfo is None or now.utcoffset() is None:
            raise PersonalizedMemoryError("repository clock must be timezone-aware")
        if now.astimezone(timezone.utc) <= prior:
            now = prior + timedelta(microseconds=1)
        updated["updated_at"] = _stamp(now)
        return validate_record(updated)

    @staticmethod
    def _retrieval_failure(reason: str) -> PersonalizedRetrievalResult:
        return PersonalizedRetrievalResult(False, reason, (), (), (), {
            "schema_version": 1, "classification": "UNTRUSTED_CONTEXT_DATA",
            "status": reason, "selected_memory_ids": [],
        })

    @staticmethod
    def _retrieval_evidence(snapshot: RepositorySnapshot,
                            request: PersonalizedRetrievalRequest,
                            keys: Sequence[str], kinds: Sequence[str]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "classification": "UNTRUSTED_CONTEXT_DATA",
            "authority": {
                "is_instruction": False,
                "cannot_grant": ["permission", "governance_change", "scope_expansion",
                                 "tool_installation", "code_promotion", "executable_action"],
                "cannot_override": ["current_task", "system_instructions",
                                    "controller_policy", "tool_policy"],
            },
            "source_generation_id": snapshot.generation_id,
            "source_manifest_sha256": snapshot.manifest_sha256,
            "requested_relevance_keys": list(keys),
            "allowed_personalized_kinds": list(kinds),
            "context": dict(request.context),
            "status": None,
            "selected_memory_ids": [],
        }

    def _load_current_state(self) -> tuple[dict[str, dict[str, Any]],
                                           dict[str, dict[str, Any]],
                                           list[dict[str, Any]], RepositorySnapshot]:
        snapshot = self.current_snapshot()
        proposals, memories, audit = self._read_generation_state(snapshot)
        return proposals, memories, audit, snapshot

    def _read_generation_state(self, snapshot: RepositorySnapshot) -> tuple[
            dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
        proposals: dict[str, dict[str, Any]] = {}
        for path in sorted((snapshot.generation_root / "proposals").glob("*.json")):
            value = json.loads(path.read_text("utf-8"))
            proposals[path.stem] = value
        memories: dict[str, dict[str, Any]] = {}
        for path in sorted(snapshot.memory_root.glob("*.json")):
            value = validate_record(json.loads(path.read_text("utf-8")))
            memories[path.stem] = value
        audit = [json.loads(line) for line in
                 (snapshot.generation_root / "audit.jsonl").read_text("utf-8").splitlines()]
        return proposals, memories, audit

    def _commit_state(self, *, proposals: Mapping[str, Mapping[str, Any]],
                      memories: Mapping[str, Mapping[str, Any]],
                      audit: Sequence[Mapping[str, Any]],
                      parent_generation_id: str | None,
                      rollback_source_generation_id: str | None = None) -> str:
        if len(proposals) > MAX_PROPOSALS or len(memories) > MAX_PERSONALIZED_MEMORIES:
            raise PersonalizedMemoryError("synthetic state exceeds its bounded record limit")
        if not 1 <= len(audit) <= MAX_AUDIT_EVENTS:
            raise PersonalizedMemoryError("synthetic audit exceeds its bounded event limit")
        generation_id = _validate_generation_id(self.generation_id_factory())
        staging_root = self.root / "staging"
        generations_root = self.root / "generations"
        stage = staging_root / generation_id
        target = generations_root / generation_id
        if stage.exists() or target.exists():
            raise PersonalizedMemoryError("generation ID already exists")
        entries: list[dict[str, Any]] = []
        promoted = False
        try:
            stage.mkdir(parents=True)
            for proposal_id, proposal in sorted(proposals.items()):
                validate_memory_id(proposal_id)
                if proposal.get("proposal_id") != proposal_id:
                    raise PersonalizedMemoryError("proposal identity mismatch")
                payload = _json_bytes(proposal)
                relative = f"proposals/{proposal_id}.json"
                _write_exclusive(stage / relative, payload)
                entries.append({"path": relative, "sha256": _sha256(payload), "bytes": len(payload)})
            for memory_id, record in sorted(memories.items()):
                validate_memory_id(memory_id)
                canonical = validate_record(record)
                if canonical["memory_id"] != memory_id or canonical["schema_version"] != 3:
                    raise PersonalizedMemoryError("personalized memory record is invalid")
                payload = _json_bytes(canonical)
                relative = f"memory/{memory_id}.json"
                _write_exclusive(stage / relative, payload)
                entries.append({"path": relative, "sha256": _sha256(payload), "bytes": len(payload)})
            audit_payload = b"".join(_canonical_json(event) + b"\n" for event in audit)
            _write_exclusive(stage / "audit.jsonl", audit_payload)
            entries.append({"path": "audit.jsonl", "sha256": _sha256(audit_payload),
                            "bytes": len(audit_payload)})
            manifest = {
                "schema_version": STORE_SCHEMA_VERSION,
                "classification": "SYNTHETIC_ONLY",
                "complete": True,
                "generation_id": generation_id,
                "parent_generation_id": parent_generation_id,
                "rollback_source_generation_id": rollback_source_generation_id,
                "created_at": self._timestamp(),
                "proposal_count": len(proposals),
                "memory_count": len(memories),
                "audit_event_count": len(audit),
                "entries": entries,
            }
            manifest_payload = _json_bytes(manifest)
            manifest_hash = _sha256(manifest_payload)
            _write_exclusive(stage / "manifest.json", manifest_payload)
            _write_exclusive(stage / "manifest.sha256", (manifest_hash + "\n").encode("ascii"))
            self._verify_generation_path(stage, expected_generation_id=generation_id)
            generations_root.mkdir(parents=True, exist_ok=True)
            os.replace(stage, target)
            promoted = True
            self._verify_generation_path(target, expected_generation_id=generation_id)
            self._write_current_pointer(generation_id, manifest_hash)
            self.current_snapshot()
            return generation_id
        except PersonalizedMemoryError:
            if not promoted and stage.exists():
                self._remove_stage(stage)
            raise
        except (OSError, MemoryValidationError, UnicodeError, ValueError, TypeError) as exc:
            if not promoted and stage.exists():
                self._remove_stage(stage)
            raise PersonalizedMemoryError("synthetic state transaction failed") from exc

    def _write_current_pointer(self, generation_id: str, manifest_hash: str) -> None:
        payload = _json_bytes({"schema_version": STORE_SCHEMA_VERSION,
                               "generation_id": generation_id,
                               "manifest_sha256": manifest_hash})
        temporary = self.root / f".current.{generation_id}.tmp"
        try:
            _write_exclusive(temporary, payload)
            os.replace(temporary, self.root / "current.json")
        except OSError as exc:
            raise PersonalizedMemoryError("current synthetic state pointer update failed") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _verify_generation(self, generation_id: str) -> RepositorySnapshot:
        generation_id = _validate_generation_id(generation_id)
        generation = self.root / "generations" / generation_id
        if not generation.is_dir():
            raise PersonalizedMemoryError("synthetic state generation is missing")
        return self._verify_generation_path(generation, expected_generation_id=generation_id)

    def _verify_generation_path(self, generation: Path, *,
                                expected_generation_id: str) -> RepositorySnapshot:
        _assert_plain_chain(generation)
        try:
            manifest_payload = (generation / "manifest.json").read_bytes()
            digest = (generation / "manifest.sha256").read_text("ascii").strip()
            manifest = json.loads(manifest_payload.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PersonalizedMemoryError("synthetic generation manifest is unreadable") from exc
        if not _SHA256.fullmatch(digest) or _sha256(manifest_payload) != digest:
            raise PersonalizedMemoryError("synthetic generation manifest was modified")
        required = {"schema_version", "classification", "complete", "generation_id",
                    "parent_generation_id", "rollback_source_generation_id", "created_at",
                    "proposal_count", "memory_count", "audit_event_count", "entries"}
        if (not isinstance(manifest, dict) or set(manifest) != required or
                manifest["schema_version"] != STORE_SCHEMA_VERSION or
                manifest["classification"] != "SYNTHETIC_ONLY" or
                manifest["complete"] is not True or
                manifest["generation_id"] != expected_generation_id):
            raise PersonalizedMemoryError("synthetic generation manifest is invalid")
        _parse_timestamp(manifest["created_at"], "created_at")
        expected_files = {"manifest.json", "manifest.sha256"}
        memory_ids: list[str] = []
        if not isinstance(manifest["entries"], list):
            raise PersonalizedMemoryError("synthetic generation entries are invalid")
        for entry in manifest["entries"]:
            if (not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"} or
                    not isinstance(entry["path"], str) or ".." in Path(entry["path"]).parts or
                    Path(entry["path"]).is_absolute() or not _SHA256.fullmatch(entry["sha256"]) or
                    type(entry["bytes"]) is not int or entry["bytes"] < 0):
                raise PersonalizedMemoryError("synthetic generation entry is malformed")
            path = generation / entry["path"]
            if not path.is_file() or _is_reparse(path):
                raise PersonalizedMemoryError("synthetic generation entry is missing")
            payload = path.read_bytes()
            if len(payload) != entry["bytes"] or _sha256(payload) != entry["sha256"]:
                raise PersonalizedMemoryError("synthetic generation entry was modified")
            expected_files.add(entry["path"])
            if entry["path"].startswith("memory/"):
                memory_ids.append(validate_memory_id(Path(entry["path"]).stem))
        actual_files = {path.relative_to(generation).as_posix()
                        for path in generation.rglob("*") if path.is_file()}
        if actual_files != expected_files:
            raise PersonalizedMemoryError("synthetic generation contains unmanifested files")
        proposal_count = len([item for item in expected_files if item.startswith("proposals/")])
        if (proposal_count != manifest["proposal_count"] or
                len(memory_ids) != manifest["memory_count"]):
            raise PersonalizedMemoryError("synthetic generation counts are inconsistent")
        audit_path = generation / "audit.jsonl"
        audit_lines = audit_path.read_text("utf-8").splitlines()
        if len(audit_lines) != manifest["audit_event_count"]:
            raise PersonalizedMemoryError("synthetic audit count is inconsistent")
        for index, line in enumerate(audit_lines, start=1):
            event = json.loads(line)
            if (not isinstance(event, dict) or event.get("sequence") != index or
                    event.get("schema_version") != AUDIT_SCHEMA_VERSION):
                raise PersonalizedMemoryError("synthetic audit sequence is invalid")
        return RepositorySnapshot(expected_generation_id, generation,
                                  generation / "memory", tuple(sorted(memory_ids)), digest)

    def _remove_stage(self, stage: Path) -> None:
        resolved = stage.resolve(strict=False)
        staging = (self.root / "staging").resolve(strict=False)
        if resolved.parent != staging:
            raise PersonalizedMemoryError("refused to remove an uncontained staging directory")
        shutil.rmtree(resolved)
