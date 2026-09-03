"""Synthetic-only trusted secret broker and capability-grant foundation.

The broker is deliberately absent from ordinary G.R.A.C.I. composition. It owns
an authenticated encrypted store, accepts only authenticated metadata requests,
and releases secret material only to an exact registered synthetic adapter. There
is no public raw-secret read, export, or general connector interface.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import secrets
import stat
import struct
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from pathlib import Path, PureWindowsPath
from typing import Any, Iterator

try:
    import msvcrt
except ImportError:  # pragma: no cover - the authorized foundation is Windows-only
    msvcrt = None  # type: ignore[assignment]

from .crypto import CryptoError, ProtectedBlob, SecretBuffer, WindowsCngAesGcm
from .protocol import (
    AuthenticatedLocalProtocol,
    ProtocolError,
    ProtocolRequest,
    request_digest,
    validate_freshness,
)
from .synthetic_adapter import (
    NOTICE_DELIVER_OPERATION,
    AdapterCode,
    AdapterOutcome,
    SecretMaterial,
    SyntheticAdapterRequest,
    SyntheticNoticeAdapter,
    SyntheticSecretAdapter,
    execute_synthetic_adapter,
)


STORE_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 1
AUDIT_SCHEMA_VERSION = 1
SYNTHETIC_MARKER = "synthetic-boundary.json"
MAX_SECRETS = 12
MAX_SECRET_BYTES = 4_096
MAX_PROPOSALS = 64
MAX_GRANTS = 64
MAX_REQUESTS = 256
MAX_AUDIT_EVENTS = 1_024
MAX_STATE_BYTES = 8_388_608
MAX_VAULT_FILE_BYTES = 262_144
MAX_STANDING_USES = 100
MAX_ONE_TIME_LIFETIME = timedelta(days=1)
MAX_STANDING_LIFETIME = timedelta(days=30)
REQUEST_MAX_AGE = timedelta(minutes=2)
REQUEST_FUTURE_SKEW = timedelta(seconds=10)
LOCK_TIMEOUT_SECONDS = 5.0

_UUID_NAMESPACE_PROPOSAL = uuid.UUID("4139d7cb-24ab-4c31-a58e-63d3e61bdbcb")
_UUID_NAMESPACE_GRANT = uuid.UUID("ddbcfe24-14c6-4c88-a9e9-71f23a6f7afe")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:/-]{0,127}$")
_SYNTHETIC_SCOPE = re.compile(
    r"\Asynthetic-(?:task|project):[a-z0-9]+(?:[._-][a-z0-9]+)*\Z",
    re.ASCII,
)
_SECRET_REF = re.compile(r"^sec_[0-9a-f]{32}$")
_AUDIT_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_VAULT_MAGIC = b"GRACI8F1"
_AUTH_MARKER = b"GRACI-PHASE8F-AUTH-V1"
_ZERO_PAD = bytes(MAX_SECRET_BYTES)
_MOVEFILE_REPLACE_EXISTING = 0x00000001
_MOVEFILE_WRITE_THROUGH = 0x00000008


class BrokerError(RuntimeError):
    """Fixed, non-echoing broker failure."""


class _CommitOutcomeUncertain(BrokerError):
    """The current pointer moved but post-selection verification failed."""

    def __init__(self, generation_id: str) -> None:
        super().__init__("broker commit outcome is uncertain")
        self.generation_id = generation_id


class GrantKind(str, Enum):
    ONE_TIME = "one_time"
    STANDING = "standing"


class GrantStatus(str, Enum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    REVOKED = "revoked"
    RECOVERY_HOLD = "recovery_hold"


class RequestStatus(str, Enum):
    RESERVED = "reserved"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RESOLVED_UNKNOWN = "resolved_unknown"


class BrokerCode(str, Enum):
    INITIALIZED = "INITIALIZED"
    SECRET_PROVISIONED = "SECRET_PROVISIONED"
    GRANT_PROPOSED = "GRANT_PROPOSED"
    GRANT_APPROVED = "GRANT_APPROVED"
    GRANT_REVOKED = "GRANT_REVOKED"
    SECRETS_ROLLED_BACK = "SECRETS_ROLLED_BACK"
    UNCERTAIN_REQUEST_CLOSED = "UNCERTAIN_REQUEST_CLOSED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    STALE_STATE = "STALE_STATE"
    CLOCK_UNTRUSTED = "CLOCK_UNTRUSTED"
    NOT_FOUND = "NOT_FOUND"
    APPROVAL_MISMATCH = "APPROVAL_MISMATCH"
    ALREADY_DECIDED = "ALREADY_DECIDED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    GRANT_NOT_YET_VALID = "GRANT_NOT_YET_VALID"
    GRANT_EXPIRED = "GRANT_EXPIRED"
    GRANT_REVIEW_REQUIRED = "GRANT_REVIEW_REQUIRED"
    GRANT_EXHAUSTED = "GRANT_EXHAUSTED"
    GRANT_RECOVERY_HOLD = "GRANT_RECOVERY_HOLD"
    REPLAY_CONFLICT = "REPLAY_CONFLICT"
    REPLAY_DENIED = "REPLAY_DENIED"
    OPERATION_SUCCEEDED = "OPERATION_SUCCEEDED"
    OPERATION_FAILED = "OPERATION_FAILED"
    RESERVATION_FAILED = "RESERVATION_FAILED"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"
    PENDING_OPERATION = "PENDING_OPERATION"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    LIMIT_REACHED = "LIMIT_REACHED"


class ApprovalChannel(str, Enum):
    TYPED_TURN = "typed_turn"
    PTT_RELEASE = "ptt_release"


@dataclass(frozen=True, slots=True)
class RegisteredAdapter:
    adapter_id: str
    operation_id: str
    destination_id: str
    resource_id: str
    adapter: SyntheticSecretAdapter

    def __post_init__(self) -> None:
        _validate_identifier(self.adapter_id)
        _validate_identifier(self.operation_id)
        _validate_identifier(self.destination_id)
        _validate_uuid(self.resource_id)
        if self.operation_id != NOTICE_DELIVER_OPERATION:
            raise BrokerError("registered operation is not allowed")
        if type(self.adapter) is not SyntheticNoticeAdapter:
            raise BrokerError("registered adapter is not allowed")
        if (self.adapter.destination != self.destination_id or
                self.adapter.resource_id != self.resource_id):
            raise BrokerError("registered adapter binding is invalid")

    def __repr__(self) -> str:
        return (
            "RegisteredAdapter("
            f"adapter_id={self.adapter_id!r}, operation_id={self.operation_id!r}, "
            f"destination_id={self.destination_id!r}, resource_id={self.resource_id!r}, "
            "adapter=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class SecretProvisionRequest:
    operation_id: str
    expected_generation_id: str
    provisioner_id: str
    adapter_id: str
    operation: str
    destination_id: str


@dataclass(frozen=True, slots=True)
class GrantProposalRequest:
    operation_id: str
    expected_generation_id: str
    grant_kind: str
    caller_id: str
    key_id: str
    scope_id: str
    resource_id: str
    secret_ref: str
    secret_version: int
    adapter_id: str
    operation: str
    destination_id: str
    not_before: datetime
    expires_at: datetime
    max_uses: int
    review_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExactGrantApproval:
    operation_id: str
    expected_generation_id: str
    proposal_id: str
    proposal_digest: str
    source_turn_id: str
    channel: str
    authority: str = "product_owner"
    decision: str = "approve_exact_grant"


@dataclass(frozen=True, slots=True)
class GrantRevocationApproval:
    operation_id: str
    expected_generation_id: str
    grant_id: str
    expected_grant_version: int
    source_turn_id: str
    channel: str
    authority: str = "product_owner"
    decision: str = "approve_exact_revocation"


@dataclass(frozen=True, slots=True)
class PendingResolutionApproval:
    operation_id: str
    expected_generation_id: str
    request_id: str
    source_turn_id: str
    channel: str
    authority: str = "product_owner"
    decision: str = "close_uncertain_without_retry"


@dataclass(frozen=True, slots=True)
class SecretRollbackApproval:
    operation_id: str
    expected_generation_id: str
    target_generation_id: str
    target_manifest_sha256: str
    source_turn_id: str
    channel: str
    authority: str = "product_owner"
    decision: str = "approve_exact_secret_rollback"


@dataclass(frozen=True, slots=True)
class MutationResult:
    accepted: bool
    code: BrokerCode
    generation_id: str | None = None
    secret_ref: str | None = None
    proposal_id: str | None = None
    grant_id: str | None = None
    grant_version: int | None = None
    proposal_digest: str | None = None
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class OperationResult:
    accepted: bool
    code: BrokerCode
    request_id: str | None = None
    generation_id: str | None = None
    grant_id: str | None = None
    grant_version: int | None = None
    receipt_notice_id: str | None = None
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class BrokerSnapshot:
    generation_id: str
    manifest_sha256: str
    secret_count: int
    proposal_count: int
    grant_count: int
    request_count: int
    audit_event_count: int
    last_trusted_at: str


def _mutation_boundary(method: Callable[..., MutationResult]) -> Callable[..., MutationResult]:
    """Convert an unexpected broker-boundary failure to one fixed typed result."""

    @wraps(method)
    def guarded(*args: Any, **kwargs: Any) -> MutationResult:
        try:
            return method(*args, **kwargs)
        except BrokerError:
            return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)

    return guarded


Clock = Callable[[], datetime]
IdFactory = Callable[[], str]
SecretRefFactory = Callable[[], str]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _new_secret_ref() -> str:
    return "sec_" + secrets.token_hex(16)


def _sha256(payload: bytes | bytearray | memoryview) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=True, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise BrokerError("broker state serialization failed") from None


def _json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2,
                       sort_keys=True) + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise BrokerError("broker state serialization failed") from None


def _validate_uuid(value: object) -> str:
    if type(value) is not str or _UUID.fullmatch(value) is None:
        raise BrokerError("identifier is invalid")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise BrokerError("identifier is invalid") from None
    if parsed.int == 0 or str(parsed) != value:
        raise BrokerError("identifier is invalid")
    return value


def _validate_sha256(value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise BrokerError("digest is invalid")
    return value


def _validate_identifier(value: object) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise BrokerError("identifier is invalid")
    return value


def _validate_synthetic_scope(value: object) -> str:
    scope = _validate_identifier(value)
    if _SYNTHETIC_SCOPE.fullmatch(scope) is None:
        raise BrokerError("synthetic scope is invalid")
    return scope


def _validate_secret_ref(value: object) -> str:
    if type(value) is not str or _SECRET_REF.fullmatch(value) is None:
        raise BrokerError("secret reference is invalid")
    return value


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise BrokerError("timestamp is invalid")
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError):
        raise BrokerError("timestamp is invalid") from None
    if offset is None:
        raise BrokerError("timestamp is invalid")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_stamp(value: object) -> datetime:
    if type(value) is not str:
        raise BrokerError("timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise BrokerError("timestamp is invalid") from None
    parsed = _utc(parsed)
    if _stamp(parsed) != value:
        raise BrokerError("timestamp is invalid")
    return parsed


def _zero(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


def _is_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _assert_plain_chain(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    for candidate in tuple(reversed(absolute.parents)) + (absolute,):
        if _is_reparse(candidate):
            raise BrokerError("reparse points are forbidden in the broker path")


def _windows_drive_type(path: Path) -> int:
    anchor = PureWindowsPath(str(path)).anchor
    if (len(anchor) != 3 or anchor[1:] != ":\\" or
            not anchor[0].isascii() or not anchor[0].isalpha()):
        raise BrokerError("broker root must use a local drive letter")
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_drive_type = kernel32.GetDriveTypeW
        get_drive_type.argtypes = [ctypes.c_wchar_p]
        get_drive_type.restype = ctypes.c_uint
        return int(get_drive_type(anchor))
    except (AttributeError, OSError, TypeError, ValueError):
        raise BrokerError("broker drive type is unavailable") from None


def _validate_root(root: Path, *, must_exist: bool) -> Path:
    candidate = Path(root)
    if not candidate.is_absolute():
        raise BrokerError("broker root must be absolute")
    raw = str(candidate)
    if raw.startswith(("\\\\", "//", "\\?\\", "\\.\\", "\\??\\")):
        raise BrokerError("UNC and device roots are forbidden")
    windows = PureWindowsPath(raw)
    if ":" in raw[len(windows.drive):]:
        raise BrokerError("alternate data stream roots are forbidden")
    if _windows_drive_type(candidate) != 3:
        raise BrokerError("broker root must be on a fixed local volume")
    try:
        _assert_plain_chain(candidate)
        resolved = candidate.resolve(strict=False)
        if must_exist and (not resolved.exists() or not resolved.is_dir()):
            raise BrokerError("broker root is unavailable")
    except BrokerError:
        raise
    except OSError:
        raise BrokerError("broker root is unavailable") from None
    return resolved


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_plain_chain(path.parent)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise BrokerError("exclusive broker state write failed") from None


def _read_regular(path: Path, *, maximum: int) -> bytes:
    try:
        if _is_reparse(path) or not path.is_file():
            raise BrokerError("broker state file is unavailable")
        before = path.stat()
        if before.st_size < 0 or before.st_size > maximum:
            raise BrokerError("broker state file is outside its size bound")
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns or
                len(payload) != after.st_size):
            raise BrokerError("broker state changed during read")
        return payload
    except OSError:
        raise BrokerError("broker state file is unavailable") from None


def _move_write_through(source: Path, destination: Path, *, replace: bool) -> None:
    """Move one local path atomically and request Windows write-through."""

    if os.name != "nt":
        raise BrokerError("Windows broker transaction support is unavailable")
    source = Path(os.path.abspath(source))
    destination = Path(os.path.abspath(destination))
    _assert_plain_chain(source)
    _assert_plain_chain(destination.parent)
    if not source.exists() or _is_reparse(source):
        raise BrokerError("broker transaction source is unavailable")
    if (replace and destination.exists() and
            (_is_reparse(destination) or not destination.is_file())):
        raise BrokerError("broker transaction destination is invalid")
    source_drive = PureWindowsPath(str(source)).drive.lower()
    destination_drive = PureWindowsPath(str(destination)).drive.lower()
    if not source_drive or source_drive != destination_drive:
        raise BrokerError("broker transaction paths must share a local volume")
    flags = _MOVEFILE_WRITE_THROUGH
    if replace:
        flags |= _MOVEFILE_REPLACE_EXISTING
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move = kernel32.MoveFileExW
        move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move.restype = ctypes.c_int
        moved = move(str(source), str(destination), flags)
    except (AttributeError, OSError):
        raise BrokerError("Windows broker transaction move failed") from None
    if not moved:
        raise BrokerError("Windows broker transaction move failed")


def _pack_vault(values: Mapping[str, bytearray],
                secret_records: Mapping[str, Mapping[str, Any]]) -> bytearray:
    if set(values) != set(secret_records) or len(values) > MAX_SECRETS:
        raise BrokerError("encrypted vault inventory is inconsistent")
    packed = bytearray(_VAULT_MAGIC)
    try:
        packed.extend(struct.pack(">H", len(values)))
        for secret_ref in sorted(values):
            _validate_secret_ref(secret_ref)
            record = secret_records[secret_ref]
            version = record.get("version")
            value = values[secret_ref]
            if (type(version) is not int or version < 1 or
                    type(value) is not bytearray or not value or
                    len(value) > MAX_SECRET_BYTES):
                raise BrokerError("encrypted vault record is invalid")
            reference = secret_ref.encode("ascii")
            packed.extend(struct.pack(">B", len(reference)))
            packed.extend(reference)
            packed.extend(struct.pack(">IH", version, len(value)))
            packed.extend(value)
            packed.extend(_ZERO_PAD[:MAX_SECRET_BYTES - len(value)])
        return packed
    except BaseException:
        _zero(packed)
        raise


def _unpack_vault(view: memoryview,
                  secret_records: Mapping[str, Mapping[str, Any]]) -> dict[str, bytearray]:
    values: dict[str, bytearray] = {}
    offset = 0
    try:
        if len(view) < len(_VAULT_MAGIC) + 2 or bytes(view[:len(_VAULT_MAGIC)]) != _VAULT_MAGIC:
            raise BrokerError("encrypted vault payload is invalid")
        offset += len(_VAULT_MAGIC)
        count = struct.unpack_from(">H", view, offset)[0]
        offset += 2
        if count != len(secret_records) or count > MAX_SECRETS:
            raise BrokerError("encrypted vault inventory is inconsistent")
        for _ in range(count):
            if offset + 1 > len(view):
                raise BrokerError("encrypted vault payload is invalid")
            ref_length = view[offset]
            offset += 1
            if ref_length != 36 or offset + ref_length + 6 + MAX_SECRET_BYTES > len(view):
                raise BrokerError("encrypted vault payload is invalid")
            try:
                secret_ref = bytes(view[offset:offset + ref_length]).decode("ascii")
            except UnicodeError:
                raise BrokerError("encrypted vault payload is invalid") from None
            offset += ref_length
            _validate_secret_ref(secret_ref)
            version, length = struct.unpack_from(">IH", view, offset)
            offset += 6
            if (secret_ref in values or secret_ref not in secret_records or
                    secret_records[secret_ref].get("version") != version or
                    not 1 <= length <= MAX_SECRET_BYTES):
                raise BrokerError("encrypted vault record is invalid")
            value = bytearray(view[offset:offset + length])
            padding = view[offset + length:offset + MAX_SECRET_BYTES]
            if any(padding):
                _zero(value)
                raise BrokerError("encrypted vault padding is invalid")
            values[secret_ref] = value
            offset += MAX_SECRET_BYTES
        if offset != len(view) or set(values) != set(secret_records):
            raise BrokerError("encrypted vault payload is invalid")
        return values
    except (BrokerError, IndexError, struct.error, ValueError, TypeError):
        for value in values.values():
            _zero(value)
        raise BrokerError("encrypted vault payload is invalid") from None
    except BaseException:
        for value in values.values():
            _zero(value)
        raise


def _zero_values(values: Mapping[str, bytearray]) -> None:
    for value in values.values():
        _zero(value)


class SyntheticSecretBroker:
    """Authenticated synthetic secret store and default-deny dispatcher."""

    def __init__(
        self,
        root: Path,
        *,
        cipher: WindowsCngAesGcm,
        protocol: AuthenticatedLocalProtocol,
        caller_id: str,
        key_id: str,
        adapters: Sequence[RegisteredAdapter],
        clock: Clock = _now,
        generation_id_factory: IdFactory = _new_id,
        secret_ref_factory: SecretRefFactory = _new_secret_ref,
    ) -> None:
        self.root = _validate_root(root, must_exist=True)
        if (type(cipher) is not WindowsCngAesGcm or cipher.closed or
                type(protocol) is not AuthenticatedLocalProtocol or
                protocol.closed):
            raise BrokerError("broker cryptographic configuration is invalid")
        normalized_caller = _validate_identifier(caller_id)
        normalized_key = _validate_identifier(key_id)
        if (protocol.caller_id != normalized_caller or
                protocol.key_id != normalized_key):
            raise BrokerError("broker protocol identity is invalid")
        self._cipher = cipher
        self._protocol = protocol
        self._caller_id = normalized_caller
        self._key_id = normalized_key
        self._clock = clock
        self._generation_id_factory = generation_id_factory
        self._secret_ref_factory = secret_ref_factory
        self._thread_lock = threading.RLock()
        self._store_lock_depth = 0
        self._adapters: dict[str, RegisteredAdapter] = {}
        if type(adapters) is not tuple:
            raise BrokerError("adapter registration set is invalid")
        for registration in adapters:
            if type(registration) is not RegisteredAdapter:
                raise BrokerError("adapter registration is invalid")
            if registration.adapter_id in self._adapters:
                raise BrokerError("adapter registration is duplicated")
            self._adapters[registration.adapter_id] = registration
        if not self._adapters:
            raise BrokerError("at least one synthetic adapter is required")
        self._marker = self._read_boundary_marker()
        self._ensure_lock_file()

    @classmethod
    def initialize(
        cls,
        root: Path,
        *,
        cipher: WindowsCngAesGcm,
        protocol: AuthenticatedLocalProtocol,
        caller_id: str,
        key_id: str,
        adapters: Sequence[RegisteredAdapter],
        clock: Clock = _now,
        generation_id_factory: IdFactory = _new_id,
        secret_ref_factory: SecretRefFactory = _new_secret_ref,
        store_id: str | None = None,
    ) -> "SyntheticSecretBroker":
        target = _validate_root(root, must_exist=False)
        if target.parent == target:
            raise BrokerError("broker initialization root is too broad")
        if target.exists():
            raise BrokerError("broker initialization target must not exist")
        identifier = _validate_uuid(store_id or _new_id())
        _validate_identifier(caller_id)
        _validate_identifier(key_id)
        if (type(cipher) is not WindowsCngAesGcm or
                type(protocol) is not AuthenticatedLocalProtocol):
            raise BrokerError("broker cryptographic configuration is invalid")
        if type(adapters) is not tuple:
            raise BrokerError("adapter registration set is invalid")
        registrations: dict[str, RegisteredAdapter] = {}
        for registration in adapters:
            if type(registration) is not RegisteredAdapter:
                raise BrokerError("adapter registration is invalid")
            if registration.adapter_id in registrations:
                raise BrokerError("adapter registration is duplicated")
            registrations[registration.adapter_id] = registration
        if not registrations:
            raise BrokerError("at least one synthetic adapter is required")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise BrokerError("broker initialization path is unavailable") from None
        stage = target.with_name(
            f".{target.name}.phase8f-init-{uuid.uuid4()}"
        )
        stage = _validate_root(stage, must_exist=False)
        if stage.exists():
            raise BrokerError("broker initialization staging root exists")
        try:
            stage.mkdir()
        except OSError:
            raise BrokerError("broker initialization path is unavailable") from None
        marker = {
            "schema_version": STORE_SCHEMA_VERSION,
            "classification": "SYNTHETIC_ONLY",
            "store_id": identifier,
            "real_credentials_permitted": False,
            "real_personal_data_permitted": False,
            "ordinary_runtime_integration_permitted": False,
            "live_ipc_permitted": False,
            "network_access_permitted": False,
            "deployment_permitted": False,
            "automatic_refresh_permitted": False,
            "key_persistence_permitted": False,
            "cipher": "AES-256-GCM-WINDOWS-CNG",
        }
        broker: SyntheticSecretBroker | None = None
        try:
            _write_exclusive(stage / SYNTHETIC_MARKER, _json_bytes(marker))
            _write_exclusive(stage / "broker.lock", b"\x00")
            broker = cls(
                stage, cipher=cipher, protocol=protocol, caller_id=caller_id,
                key_id=key_id, adapters=tuple(registrations.values()), clock=clock,
                generation_id_factory=generation_id_factory,
                secret_ref_factory=secret_ref_factory,
            )
            now = broker._trusted_now(None)
            state = {
                "schema_version": STATE_SCHEMA_VERSION,
                "classification": "SYNTHETIC_ONLY",
                "store_id": identifier,
                "last_trusted_at": _stamp(now),
                "secrets": {},
                "proposals": {},
                "grants": {},
                "requests": {},
                "nonces": {},
                "audit": [],
            }
            broker._append_audit(
                state, event_type="BROKER_INITIALIZED", occurred_at=now,
                operation_id=None, object_id=identifier,
                code=BrokerCode.INITIALIZED.value,
            )
            with broker._store_lock():
                try:
                    broker._commit_state(
                        state=state, secret_values={}, parent_generation_id=None,
                        rollback_source_generation_id=None,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    _, recovered_values, recovered = broker._load_current_state()
                    _zero_values(recovered_values)
                    if recovered.generation_id != uncertain.generation_id:
                        raise
            broker.current_snapshot()
            _move_write_through(stage, target, replace=False)
            broker.root = target
            return broker
        except BaseException:
            if broker is not None:
                broker.close()
            else:
                protocol.close()
                cipher.close()
            raise

    def close(self) -> None:
        """Close held cryptographic and protocol key material."""

        with self._thread_lock:
            try:
                self._protocol.close()
            finally:
                try:
                    self._cipher.close()
                finally:
                    for registration in self._adapters.values():
                        registration.adapter.close()

    def __enter__(self) -> "SyntheticSecretBroker":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass

    def current_snapshot(self) -> BrokerSnapshot:
        with self._store_lock():
            _, snapshot = self._load_current_metadata()
            return snapshot

    def audit_events(self) -> tuple[dict[str, Any], ...]:
        with self._store_lock():
            state, _ = self._load_current_metadata()
            return tuple(dict(event) for event in state["audit"])

    def grant_record(self, grant_id: str) -> dict[str, Any]:
        try:
            grant_id = _validate_uuid(grant_id)
        except BrokerError:
            raise BrokerError("grant is unavailable") from None
        with self._store_lock():
            state, _ = self._load_current_metadata()
            grant = state["grants"].get(grant_id)
            if grant is None:
                raise BrokerError("grant is unavailable")
            return dict(grant)

    @_mutation_boundary
    def provision_secret(
        self,
        request: SecretProvisionRequest,
        secret_value: bytearray,
    ) -> MutationResult:
        if type(secret_value) is not bytearray:
            if isinstance(secret_value, bytearray):
                try:
                    _zero(secret_value)
                except Exception:
                    pass
            raise TypeError("secret_value must be a bytearray")
        owned_value = bytearray()
        try:
            try:
                payload = self._validate_provision_request(request)
                if not secret_value or len(secret_value) > MAX_SECRET_BYTES:
                    raise BrokerError("secret material is invalid")
            except BrokerError:
                return MutationResult(False, BrokerCode.INVALID_REQUEST)
            owned_value = bytearray(secret_value)
            _zero(secret_value)
            try:
                with self._store_lock():
                    try:
                        state, values, snapshot = self._load_current_state()
                    except BrokerError:
                        return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
                    try:
                        if payload["expected_generation_id"] != snapshot.generation_id:
                            return MutationResult(False, BrokerCode.STALE_STATE,
                                                  snapshot.generation_id)
                        if self._operation_seen(state, payload["operation_id"]):
                            return MutationResult(
                                False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                snapshot.generation_id,
                            )
                        if len(state["secrets"]) >= MAX_SECRETS:
                            return MutationResult(False, BrokerCode.LIMIT_REACHED,
                                                  snapshot.generation_id)
                        secret_ref = _validate_secret_ref(self._secret_ref_factory())
                        if secret_ref in state["secrets"]:
                            return MutationResult(
                                False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                snapshot.generation_id,
                            )
                        try:
                            now = self._trusted_now(state)
                        except BrokerError:
                            return MutationResult(
                                False, BrokerCode.CLOCK_UNTRUSTED,
                                snapshot.generation_id,
                            )
                        state["secrets"][secret_ref] = {
                            "schema_version": 1,
                            "secret_ref": secret_ref,
                            "version": 1,
                            "status": "active",
                            "adapter_id": payload["adapter_id"],
                            "operation": payload["operation"],
                            "destination_id": payload["destination_id"],
                            "provisioner_id": payload["provisioner_id"],
                            "provisioned_at": _stamp(now),
                        }
                        values[secret_ref] = owned_value
                        state["last_trusted_at"] = _stamp(now)
                        self._append_audit(
                            state, event_type="SECRET_PROVISIONED", occurred_at=now,
                            operation_id=payload["operation_id"], object_id=secret_ref,
                            code=BrokerCode.SECRET_PROVISIONED.value,
                        )
                        try:
                            generation = self._commit_state(
                                state=state, secret_values=values,
                                parent_generation_id=snapshot.generation_id,
                                rollback_source_generation_id=None,
                            )
                        except _CommitOutcomeUncertain as uncertain:
                            return MutationResult(
                                False, BrokerCode.OUTCOME_UNCERTAIN,
                                uncertain.generation_id, secret_ref=secret_ref,
                            )
                        except BrokerError:
                            return MutationResult(
                                False, BrokerCode.STORAGE_UNAVAILABLE,
                                snapshot.generation_id,
                            )
                        return MutationResult(
                            True, BrokerCode.SECRET_PROVISIONED, generation,
                            secret_ref=secret_ref,
                        )
                    finally:
                        _zero_values(values)
            except BrokerError:
                return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
        finally:
            _zero(secret_value)
            _zero(owned_value)

    @_mutation_boundary
    def propose_grant(self, request: GrantProposalRequest) -> MutationResult:
        try:
            payload = self._grant_payload(request)
        except BrokerError:
            return MutationResult(False, BrokerCode.INVALID_REQUEST)
        with self._store_lock():
            try:
                state, values, snapshot = self._load_current_state()
            except BrokerError:
                return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
            try:
                proposal_id = str(uuid.uuid5(
                    _UUID_NAMESPACE_PROPOSAL, payload["operation_id"]
                ))
                digest = _sha256(_canonical_json(payload))
                existing = state["proposals"].get(proposal_id)
                if existing is not None:
                    comparable = {key: existing.get(key) for key in payload}
                    if comparable == payload and existing.get("proposal_digest") == digest:
                        return MutationResult(
                            True, BrokerCode.IDEMPOTENT_REPLAY, snapshot.generation_id,
                            proposal_id=proposal_id, grant_id=existing.get("grant_id"),
                            proposal_digest=digest,
                            idempotent_replay=True,
                        )
                    return MutationResult(False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                          snapshot.generation_id)
                if payload["expected_generation_id"] != snapshot.generation_id:
                    return MutationResult(False, BrokerCode.STALE_STATE,
                                          snapshot.generation_id)
                if (self._operation_seen(state, payload["operation_id"]) or
                        len(state["proposals"]) >= MAX_PROPOSALS):
                    code = (BrokerCode.LIMIT_REACHED if len(state["proposals"]) >= MAX_PROPOSALS
                            else BrokerCode.IDEMPOTENCY_CONFLICT)
                    return MutationResult(False, code, snapshot.generation_id)
                secret = state["secrets"].get(payload["secret_ref"])
                if secret is None or not self._secret_matches_grant(secret, payload):
                    return MutationResult(False, BrokerCode.CAPABILITY_DENIED,
                                          snapshot.generation_id)
                try:
                    now = self._trusted_now(state)
                except BrokerError:
                    return MutationResult(
                        False, BrokerCode.CLOCK_UNTRUSTED,
                        snapshot.generation_id,
                    )
                if _parse_stamp(payload["expires_at"]) <= now:
                    return MutationResult(False, BrokerCode.GRANT_EXPIRED,
                                          snapshot.generation_id)
                proposal = {
                    "schema_version": 1,
                    "proposal_id": proposal_id,
                    **payload,
                    "proposal_digest": digest,
                    "status": "pending",
                    "created_at": _stamp(now),
                    "approval": None,
                    "grant_id": None,
                }
                state["proposals"][proposal_id] = proposal
                state["last_trusted_at"] = _stamp(now)
                self._append_audit(
                    state, event_type="GRANT_PROPOSED", occurred_at=now,
                    operation_id=payload["operation_id"], object_id=proposal_id,
                    code=BrokerCode.GRANT_PROPOSED.value,
                )
                try:
                    generation = self._commit_state(
                        state=state, secret_values=values,
                        parent_generation_id=snapshot.generation_id,
                        rollback_source_generation_id=None,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    return MutationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN,
                        uncertain.generation_id, proposal_id=proposal_id,
                        proposal_digest=digest,
                    )
                except BrokerError:
                    return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE,
                                          snapshot.generation_id)
                return MutationResult(True, BrokerCode.GRANT_PROPOSED, generation,
                                      proposal_id=proposal_id,
                                      proposal_digest=digest)
            finally:
                _zero_values(values)

    @_mutation_boundary
    def approve_grant(self, approval: ExactGrantApproval) -> MutationResult:
        try:
            operation_id = _validate_uuid(approval.operation_id)
            expected_generation_id = _validate_uuid(approval.expected_generation_id)
            proposal_id = _validate_uuid(approval.proposal_id)
            proposal_digest = _validate_sha256(approval.proposal_digest)
            source_turn_id = _validate_uuid(approval.source_turn_id)
            channel = ApprovalChannel(approval.channel).value
            if (approval.authority != "product_owner" or
                    approval.decision != "approve_exact_grant"):
                raise BrokerError("grant approval is invalid")
        except (BrokerError, ValueError, TypeError, AttributeError):
            return MutationResult(False, BrokerCode.INVALID_REQUEST)
        approval_core = {
            "schema_version": 1,
            "operation_id": operation_id,
            "expected_generation_id": expected_generation_id,
            "proposal_id": proposal_id,
            "proposal_digest": proposal_digest,
            "source_turn_id": source_turn_id,
            "channel": channel,
            "authority": "product_owner",
            "decision": "approve_exact_grant",
        }
        with self._store_lock():
            try:
                state, values, snapshot = self._load_current_state()
            except BrokerError:
                return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
            try:
                proposal = state["proposals"].get(proposal_id)
                if proposal is None:
                    return MutationResult(False, BrokerCode.NOT_FOUND,
                                          snapshot.generation_id)
                grant_id = str(uuid.uuid5(_UUID_NAMESPACE_GRANT, operation_id))
                existing_grant = state["grants"].get(grant_id)
                if existing_grant is not None:
                    recorded = proposal.get("approval")
                    if self._approval_matches(recorded, approval_core):
                        return MutationResult(
                            True, BrokerCode.IDEMPOTENT_REPLAY, snapshot.generation_id,
                            proposal_id=proposal_id, grant_id=grant_id,
                            grant_version=existing_grant["version"],
                            idempotent_replay=True,
                        )
                    return MutationResult(False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                          snapshot.generation_id)
                if expected_generation_id != snapshot.generation_id:
                    return MutationResult(False, BrokerCode.STALE_STATE,
                                          snapshot.generation_id)
                if self._operation_seen(state, operation_id):
                    return MutationResult(False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                          snapshot.generation_id)
                if (proposal.get("status") != "pending" or
                        proposal.get("proposal_digest") != proposal_digest):
                    return MutationResult(False, BrokerCode.APPROVAL_MISMATCH,
                                          snapshot.generation_id)
                if len(state["grants"]) >= MAX_GRANTS:
                    return MutationResult(False, BrokerCode.LIMIT_REACHED,
                                          snapshot.generation_id)
                secret = state["secrets"].get(proposal["secret_ref"])
                if secret is None or not self._secret_matches_grant(secret, proposal):
                    return MutationResult(False, BrokerCode.CAPABILITY_DENIED,
                                          snapshot.generation_id)
                try:
                    now = self._trusted_now(state)
                except BrokerError:
                    return MutationResult(
                        False, BrokerCode.CLOCK_UNTRUSTED,
                        snapshot.generation_id,
                    )
                if _parse_stamp(proposal["expires_at"]) <= now:
                    return MutationResult(False, BrokerCode.GRANT_EXPIRED,
                                          snapshot.generation_id)
                approval_record = {
                    **approval_core,
                    "approved_at": _stamp(now),
                }
                grant = {
                    "schema_version": 1,
                    "grant_id": grant_id,
                    "version": 1,
                    "status": GrantStatus.ACTIVE.value,
                    "grant_kind": proposal["grant_kind"],
                    "caller_id": proposal["caller_id"],
                    "key_id": proposal["key_id"],
                    "scope_id": proposal["scope_id"],
                    "resource_id": proposal["resource_id"],
                    "secret_ref": proposal["secret_ref"],
                    "secret_version": proposal["secret_version"],
                    "adapter_id": proposal["adapter_id"],
                    "operation": proposal["operation"],
                    "destination_id": proposal["destination_id"],
                    "not_before": proposal["not_before"],
                    "expires_at": proposal["expires_at"],
                    "review_at": proposal["review_at"],
                    "max_uses": proposal["max_uses"],
                    "uses_reserved": 0,
                    "proposal_id": proposal_id,
                    "proposal_digest": proposal_digest,
                    "approval": approval_record,
                    "created_at": _stamp(now),
                    "updated_at": _stamp(now),
                }
                state["grants"][grant_id] = grant
                proposal = dict(proposal)
                proposal["status"] = "approved"
                proposal["approval"] = approval_record
                proposal["grant_id"] = grant_id
                state["proposals"][proposal_id] = proposal
                state["last_trusted_at"] = _stamp(now)
                self._append_audit(
                    state, event_type="GRANT_APPROVED", occurred_at=now,
                    operation_id=operation_id, object_id=grant_id,
                    code=BrokerCode.GRANT_APPROVED.value,
                    approval=approval_record,
                )
                try:
                    generation = self._commit_state(
                        state=state, secret_values=values,
                        parent_generation_id=snapshot.generation_id,
                        rollback_source_generation_id=None,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    return MutationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN,
                        uncertain.generation_id, proposal_id=proposal_id,
                        grant_id=grant_id, grant_version=1,
                    )
                except BrokerError:
                    return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE,
                                          snapshot.generation_id)
                return MutationResult(
                    True, BrokerCode.GRANT_APPROVED, generation,
                    proposal_id=proposal_id, grant_id=grant_id, grant_version=1,
                )
            finally:
                _zero_values(values)

    @_mutation_boundary
    def revoke_grant(self, approval: GrantRevocationApproval) -> MutationResult:
        try:
            operation_id = _validate_uuid(approval.operation_id)
            expected_generation_id = _validate_uuid(approval.expected_generation_id)
            grant_id = _validate_uuid(approval.grant_id)
            source_turn_id = _validate_uuid(approval.source_turn_id)
            channel = ApprovalChannel(approval.channel).value
            if (type(approval.expected_grant_version) is not int or
                    approval.expected_grant_version < 1 or
                    approval.authority != "product_owner" or
                    approval.decision != "approve_exact_revocation"):
                raise BrokerError("grant revocation is invalid")
        except (BrokerError, ValueError, TypeError, AttributeError):
            return MutationResult(False, BrokerCode.INVALID_REQUEST)
        approval_core = {
            "schema_version": 1,
            "operation_id": operation_id,
            "expected_generation_id": expected_generation_id,
            "grant_id": grant_id,
            "expected_grant_version": approval.expected_grant_version,
            "source_turn_id": source_turn_id,
            "channel": channel,
            "authority": "product_owner",
            "decision": "approve_exact_revocation",
        }
        with self._store_lock():
            try:
                state, values, snapshot = self._load_current_state()
            except BrokerError:
                return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
            try:
                grant = state["grants"].get(grant_id)
                if grant is None:
                    return MutationResult(False, BrokerCode.NOT_FOUND,
                                          snapshot.generation_id)
                matching_events = [
                    item for item in state["audit"]
                    if item["operation_id"] == operation_id
                ]
                if matching_events:
                    if (len(matching_events) == 1 and
                            matching_events[0]["event_type"] == "GRANT_REVOKED" and
                            matching_events[0]["object_id"] == grant_id and
                            self._approval_matches(
                                matching_events[0].get("approval"), approval_core
                            )):
                        return MutationResult(
                            True, BrokerCode.IDEMPOTENT_REPLAY, snapshot.generation_id,
                            grant_id=grant_id, grant_version=grant["version"],
                            idempotent_replay=True,
                        )
                    return MutationResult(False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                          snapshot.generation_id)
                if expected_generation_id != snapshot.generation_id:
                    return MutationResult(False, BrokerCode.STALE_STATE,
                                          snapshot.generation_id)
                if grant["version"] != approval.expected_grant_version:
                    return MutationResult(False, BrokerCode.STALE_STATE,
                                          snapshot.generation_id)
                if grant["status"] == GrantStatus.REVOKED.value:
                    return MutationResult(False, BrokerCode.ALREADY_DECIDED,
                                          snapshot.generation_id)
                try:
                    now = self._trusted_now(state)
                except BrokerError:
                    return MutationResult(
                        False, BrokerCode.CLOCK_UNTRUSTED,
                        snapshot.generation_id,
                    )
                approval_record = {
                    **approval_core,
                    "approved_at": _stamp(now),
                }
                grant = dict(grant)
                grant["status"] = GrantStatus.REVOKED.value
                grant["version"] += 1
                grant["updated_at"] = _stamp(now)
                state["grants"][grant_id] = grant
                state["last_trusted_at"] = _stamp(now)
                self._append_audit(
                    state, event_type="GRANT_REVOKED", occurred_at=now,
                    operation_id=operation_id, object_id=grant_id,
                    code=BrokerCode.GRANT_REVOKED.value,
                    approval=approval_record,
                )
                try:
                    generation = self._commit_state(
                        state=state, secret_values=values,
                        parent_generation_id=snapshot.generation_id,
                        rollback_source_generation_id=None,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    return MutationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN,
                        uncertain.generation_id, grant_id=grant_id,
                        grant_version=grant["version"],
                    )
                except BrokerError:
                    return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE,
                                          snapshot.generation_id)
                return MutationResult(
                    True, BrokerCode.GRANT_REVOKED, generation,
                    grant_id=grant_id, grant_version=grant["version"],
                )
            finally:
                _zero_values(values)

    def execute(self, encoded_request: bytes | bytearray) -> OperationResult:
        try:
            request = self._protocol.decode(encoded_request)
        except ProtocolError:
            return OperationResult(False, BrokerCode.AUTHENTICATION_FAILED)

        digest = request_digest(request)
        try:
            with self._store_lock():
                return self._execute_authenticated(request, digest)
        except BrokerError:
            return OperationResult(
                False, BrokerCode.STORAGE_UNAVAILABLE, request.request_id,
                grant_id=request.grant_id,
            )

    def _execute_authenticated(
        self, request: ProtocolRequest, digest: str,
    ) -> OperationResult:
        try:
            reservation = self._reserve_request(request, digest)
        except BrokerError:
            return OperationResult(
                False, BrokerCode.STORAGE_UNAVAILABLE, request.request_id,
                grant_id=request.grant_id,
            )
        if reservation.code in {
                BrokerCode.OPERATION_SUCCEEDED, BrokerCode.OPERATION_FAILED,
                BrokerCode.OUTCOME_UNCERTAIN}:
            return reservation
        if reservation.code is not BrokerCode.PENDING_OPERATION:
            return reservation

        transferred: bytearray | None = None
        material: SecretMaterial | None = None
        try:
            with self._store_lock():
                try:
                    state, values, snapshot = self._load_current_state()
                except BrokerError:
                    return OperationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                        reservation.generation_id, request.grant_id,
                        reservation.grant_version,
                    )
                try:
                    request_record = state["requests"].get(request.request_id)
                    secret = values.get(request.opaque_secret_ref)
                    if (request_record is None or
                            request_record.get("status") != RequestStatus.RESERVED.value or
                            request_record.get("request_digest") != digest or
                            snapshot.generation_id != reservation.generation_id or
                            secret is None):
                        return OperationResult(
                            False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                            snapshot.generation_id, request.grant_id,
                            request_record.get("resulting_grant_version")
                            if request_record else reservation.grant_version,
                        )
                    transferred = bytearray(secret)
                    registration = self._adapters[request.adapter_id]
                    adapter_request = SyntheticAdapterRequest(
                        request_id=request.request_id,
                        operation=request.operation_id,
                        destination=request.destination_id,
                        resource_id=request.resource_id,
                        payload=dict(request.payload),
                    )
                    try:
                        material = SecretMaterial(transferred)
                        transferred = None
                        outcome = execute_synthetic_adapter(
                            registration.adapter, adapter_request, material
                        )
                    except Exception:
                        outcome = AdapterOutcome(AdapterCode.ADAPTER_FAILURE)
                    finally:
                        if material is not None:
                            material.close()
                        if transferred is not None:
                            _zero(transferred)

                    return self._complete_request_locked(
                        state, values, snapshot, request, digest, outcome
                    )
                finally:
                    _zero_values(values)
        except BrokerError:
            return OperationResult(
                False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                reservation.generation_id, request.grant_id,
                reservation.grant_version,
            )
        finally:
            if material is not None:
                material.close()
            if transferred is not None:
                _zero(transferred)

    @_mutation_boundary
    def resolve_uncertain(
        self, approval: PendingResolutionApproval,
    ) -> MutationResult:
        try:
            operation_id = _validate_uuid(approval.operation_id)
            expected_generation_id = _validate_uuid(approval.expected_generation_id)
            request_id = _validate_uuid(approval.request_id)
            source_turn_id = _validate_uuid(approval.source_turn_id)
            channel = ApprovalChannel(approval.channel).value
            if (approval.authority != "product_owner" or
                    approval.decision != "close_uncertain_without_retry"):
                raise BrokerError("pending resolution is invalid")
        except (BrokerError, ValueError, TypeError, AttributeError):
            return MutationResult(False, BrokerCode.INVALID_REQUEST)
        approval_core = {
            "schema_version": 1,
            "operation_id": operation_id,
            "expected_generation_id": expected_generation_id,
            "request_id": request_id,
            "source_turn_id": source_turn_id,
            "channel": channel,
            "authority": "product_owner",
            "decision": "close_uncertain_without_retry",
        }
        with self._store_lock():
            try:
                state, values, snapshot = self._load_current_state()
            except BrokerError:
                return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
            try:
                record = state["requests"].get(request_id)
                if record is None:
                    return MutationResult(False, BrokerCode.NOT_FOUND,
                                          snapshot.generation_id)
                prior = [item for item in state["audit"]
                         if item["operation_id"] == operation_id]
                if prior:
                    if (len(prior) == 1 and
                            prior[0]["event_type"] == "UNCERTAIN_REQUEST_CLOSED" and
                            prior[0]["object_id"] == request_id and
                            self._approval_matches(
                                prior[0].get("approval"), approval_core
                            )):
                        return MutationResult(
                            True, BrokerCode.IDEMPOTENT_REPLAY,
                            snapshot.generation_id, grant_id=record["grant_id"],
                            idempotent_replay=True,
                        )
                    return MutationResult(False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                          snapshot.generation_id)
                if expected_generation_id != snapshot.generation_id:
                    return MutationResult(False, BrokerCode.STALE_STATE,
                                          snapshot.generation_id)
                if record["status"] != RequestStatus.RESERVED.value:
                    return MutationResult(False, BrokerCode.ALREADY_DECIDED,
                                          snapshot.generation_id)
                try:
                    now = self._trusted_now(state)
                except BrokerError:
                    return MutationResult(
                        False, BrokerCode.CLOCK_UNTRUSTED,
                        snapshot.generation_id,
                    )
                approval_record = {
                    **approval_core,
                    "approved_at": _stamp(now),
                }
                record = dict(record)
                record["status"] = RequestStatus.RESOLVED_UNKNOWN.value
                record["result_code"] = BrokerCode.OUTCOME_UNCERTAIN.value
                record["completed_at"] = _stamp(now)
                state["requests"][request_id] = record
                state["last_trusted_at"] = _stamp(now)
                self._append_audit(
                    state, event_type="UNCERTAIN_REQUEST_CLOSED", occurred_at=now,
                    operation_id=operation_id, object_id=request_id,
                    code=BrokerCode.UNCERTAIN_REQUEST_CLOSED.value,
                    approval=approval_record,
                )
                try:
                    generation = self._commit_state(
                        state=state, secret_values=values,
                        parent_generation_id=snapshot.generation_id,
                        rollback_source_generation_id=None,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    return MutationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN,
                        uncertain.generation_id, grant_id=record["grant_id"],
                    )
                except BrokerError:
                    return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE,
                                          snapshot.generation_id)
                return MutationResult(
                    True, BrokerCode.UNCERTAIN_REQUEST_CLOSED, generation,
                    grant_id=record["grant_id"],
                )
            finally:
                _zero_values(values)

    @_mutation_boundary
    def rollback_secrets(self, approval: SecretRollbackApproval) -> MutationResult:
        try:
            operation_id = _validate_uuid(approval.operation_id)
            expected_generation_id = _validate_uuid(approval.expected_generation_id)
            target_generation_id = _validate_uuid(approval.target_generation_id)
            target_manifest_sha256 = _validate_sha256(approval.target_manifest_sha256)
            source_turn_id = _validate_uuid(approval.source_turn_id)
            channel = ApprovalChannel(approval.channel).value
            if (approval.authority != "product_owner" or
                    approval.decision != "approve_exact_secret_rollback"):
                raise BrokerError("secret rollback is invalid")
        except (BrokerError, ValueError, TypeError, AttributeError):
            return MutationResult(False, BrokerCode.INVALID_REQUEST)
        approval_core = {
            "schema_version": 1,
            "operation_id": operation_id,
            "expected_generation_id": expected_generation_id,
            "target_generation_id": target_generation_id,
            "target_manifest_sha256": target_manifest_sha256,
            "source_turn_id": source_turn_id,
            "channel": channel,
            "authority": "product_owner",
            "decision": "approve_exact_secret_rollback",
        }
        with self._store_lock():
            try:
                current_state, current_values, current = self._load_current_state()
            except BrokerError:
                return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE)
            target_values: dict[str, bytearray] = {}
            try:
                prior = [item for item in current_state["audit"]
                         if item["operation_id"] == operation_id]
                if prior:
                    if (len(prior) == 1 and
                            prior[0]["event_type"] == "SECRETS_ROLLED_BACK" and
                            prior[0]["object_id"] == target_generation_id and
                            self._approval_matches(
                                prior[0].get("approval"), approval_core
                            )):
                        return MutationResult(
                            True, BrokerCode.IDEMPOTENT_REPLAY,
                            current.generation_id, idempotent_replay=True,
                        )
                    return MutationResult(False, BrokerCode.IDEMPOTENCY_CONFLICT,
                                          current.generation_id)
                if expected_generation_id != current.generation_id:
                    return MutationResult(False, BrokerCode.STALE_STATE,
                                          current.generation_id)
                if any(item["status"] == RequestStatus.RESERVED.value
                       for item in current_state["requests"].values()):
                    return MutationResult(False, BrokerCode.PENDING_OPERATION,
                                          current.generation_id)
                try:
                    target_state, target_values, target = self._load_generation_state(
                        target_generation_id
                    )
                except BrokerError:
                    return MutationResult(False, BrokerCode.NOT_FOUND,
                                          current.generation_id)
                if target.manifest_sha256 != target_manifest_sha256:
                    return MutationResult(False, BrokerCode.APPROVAL_MISMATCH,
                                          current.generation_id)
                if target_generation_id == current.generation_id:
                    return MutationResult(
                        False, BrokerCode.ALREADY_DECIDED,
                        current.generation_id,
                    )
                try:
                    now = self._trusted_now(current_state)
                except BrokerError:
                    return MutationResult(
                        False, BrokerCode.CLOCK_UNTRUSTED,
                        current.generation_id,
                    )
                approval_record = {
                    **approval_core,
                    "approved_at": _stamp(now),
                }
                restored_secrets = {
                    key: dict(value) for key, value in target_state["secrets"].items()
                }
                for grant_id, current_grant in tuple(current_state["grants"].items()):
                    if current_grant["status"] == GrantStatus.ACTIVE.value:
                        held = dict(current_grant)
                        held["status"] = GrantStatus.RECOVERY_HOLD.value
                        held["version"] += 1
                        held["updated_at"] = _stamp(now)
                        current_state["grants"][grant_id] = held
                current_state["secrets"] = restored_secrets
                current_state["last_trusted_at"] = _stamp(now)
                self._append_audit(
                    current_state, event_type="SECRETS_ROLLED_BACK",
                    occurred_at=now, operation_id=operation_id,
                    object_id=target_generation_id,
                    code=BrokerCode.SECRETS_ROLLED_BACK.value,
                    approval=approval_record,
                )
                try:
                    generation = self._commit_state(
                        state=current_state, secret_values=target_values,
                        parent_generation_id=current.generation_id,
                        rollback_source_generation_id=target_generation_id,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    return MutationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN,
                        uncertain.generation_id,
                    )
                except BrokerError:
                    return MutationResult(False, BrokerCode.STORAGE_UNAVAILABLE,
                                          current.generation_id)
                return MutationResult(True, BrokerCode.SECRETS_ROLLED_BACK, generation)
            finally:
                _zero_values(current_values)
                _zero_values(target_values)

    def _reserve_request(
        self, request: ProtocolRequest, digest: str,
    ) -> OperationResult:
        with self._store_lock():
            try:
                state, values, snapshot = self._load_current_state()
            except BrokerError:
                return OperationResult(False, BrokerCode.STORAGE_UNAVAILABLE,
                                       request.request_id)
            try:
                existing = state["requests"].get(request.request_id)
                if existing is not None:
                    if existing["request_digest"] != digest:
                        return OperationResult(False, BrokerCode.REPLAY_CONFLICT,
                                               request.request_id, snapshot.generation_id)
                    return self._result_from_request(existing, snapshot.generation_id,
                                                     idempotent=True)
                nonce_hash = _sha256(request.nonce.encode("ascii"))
                if nonce_hash in state["nonces"]:
                    return OperationResult(False, BrokerCode.REPLAY_DENIED,
                                           request.request_id, snapshot.generation_id)
                if request.expected_generation_id != snapshot.generation_id:
                    return OperationResult(False, BrokerCode.STALE_STATE,
                                           request.request_id, snapshot.generation_id)
                try:
                    now = self._trusted_now(state)
                    validate_freshness(
                        request, now=now, max_age=REQUEST_MAX_AGE,
                        max_future_skew=REQUEST_FUTURE_SKEW,
                    )
                except ProtocolError:
                    return OperationResult(False, BrokerCode.AUTHENTICATION_FAILED,
                                           request.request_id, snapshot.generation_id)
                except BrokerError:
                    return OperationResult(False, BrokerCode.CLOCK_UNTRUSTED,
                                           request.request_id, snapshot.generation_id)
                grant = state["grants"].get(request.grant_id)
                denial = self._evaluate_grant(request, grant, state, now)
                if denial is not None:
                    return OperationResult(False, denial, request.request_id,
                                           snapshot.generation_id, request.grant_id,
                                           (grant.get("version") if grant else None))
                registration = self._adapters.get(request.adapter_id)
                if registration is None or not self._registration_matches(
                        registration, request):
                    return OperationResult(False, BrokerCode.CAPABILITY_DENIED,
                                           request.request_id, snapshot.generation_id,
                                           request.grant_id, grant["version"])
                if not self._payload_is_exact(request):
                    return OperationResult(False, BrokerCode.CAPABILITY_DENIED,
                                           request.request_id, snapshot.generation_id,
                                           request.grant_id, grant["version"])
                if len(state["requests"]) >= MAX_REQUESTS:
                    return OperationResult(False, BrokerCode.LIMIT_REACHED,
                                           request.request_id, snapshot.generation_id,
                                           request.grant_id, grant["version"])
                grant = dict(grant)
                grant["uses_reserved"] += 1
                grant["version"] += 1
                grant["updated_at"] = _stamp(now)
                if grant["uses_reserved"] >= grant["max_uses"]:
                    grant["status"] = GrantStatus.EXHAUSTED.value
                state["grants"][request.grant_id] = grant
                state["requests"][request.request_id] = {
                    "schema_version": 1,
                    "request_id": request.request_id,
                    "request_digest": digest,
                    "nonce_sha256": nonce_hash,
                    "grant_id": request.grant_id,
                    "reserved_grant_version": request.grant_version,
                    "resulting_grant_version": grant["version"],
                    "status": RequestStatus.RESERVED.value,
                    "result_code": BrokerCode.OUTCOME_UNCERTAIN.value,
                    "receipt_notice_id": None,
                    "reserved_at": _stamp(now),
                    "completed_at": None,
                }
                state["nonces"][nonce_hash] = request.request_id
                state["last_trusted_at"] = _stamp(now)
                self._append_audit(
                    state, event_type="OPERATION_RESERVED", occurred_at=now,
                    operation_id=None, object_id=request.request_id,
                    code=BrokerCode.PENDING_OPERATION.value,
                )
                try:
                    generation = self._commit_state(
                        state=state, secret_values=values,
                        parent_generation_id=snapshot.generation_id,
                        rollback_source_generation_id=None,
                    )
                except _CommitOutcomeUncertain as uncertain:
                    return OperationResult(
                        False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                        uncertain.generation_id, request.grant_id,
                        grant["version"],
                    )
                except BrokerError:
                    return OperationResult(
                        False, BrokerCode.RESERVATION_FAILED, request.request_id,
                        snapshot.generation_id, request.grant_id, request.grant_version,
                    )
                return OperationResult(
                    False, BrokerCode.PENDING_OPERATION, request.request_id,
                    generation, request.grant_id, grant["version"],
                )
            finally:
                _zero_values(values)

    def _complete_request_locked(
        self,
        state: dict[str, Any],
        values: dict[str, bytearray],
        snapshot: BrokerSnapshot,
        request: ProtocolRequest,
        digest: str,
        outcome: AdapterOutcome,
    ) -> OperationResult:
        record = state["requests"].get(request.request_id)
        if (record is None or record["request_digest"] != digest or
                record["status"] != RequestStatus.RESERVED.value):
            return OperationResult(
                False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                snapshot.generation_id, request.grant_id,
                (record.get("resulting_grant_version") if record else None),
            )
        now = self._trusted_now(state)
        successful = (
            type(outcome) is AdapterOutcome and
            outcome.code is AdapterCode.DELIVERED and
            outcome.receipt is not None and
            outcome.receipt.request_id == request.request_id and
            outcome.receipt.notice_id == request.payload.get("notice_id")
        )
        record = dict(record)
        record["status"] = (
            RequestStatus.SUCCEEDED.value if successful
            else RequestStatus.FAILED.value
        )
        record["result_code"] = (
            BrokerCode.OPERATION_SUCCEEDED.value if successful
            else BrokerCode.OPERATION_FAILED.value
        )
        record["receipt_notice_id"] = (
            outcome.receipt.notice_id if successful else None
        )
        record["completed_at"] = _stamp(now)
        state["requests"][request.request_id] = record
        state["last_trusted_at"] = _stamp(now)
        self._append_audit(
            state,
            event_type=("OPERATION_SUCCEEDED" if successful else "OPERATION_FAILED"),
            occurred_at=now, operation_id=None, object_id=request.request_id,
            code=record["result_code"],
        )
        try:
            generation = self._commit_state(
                state=state, secret_values=values,
                parent_generation_id=snapshot.generation_id,
                rollback_source_generation_id=None,
            )
        except _CommitOutcomeUncertain as uncertain:
            return OperationResult(
                False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                uncertain.generation_id, request.grant_id,
                record["resulting_grant_version"],
            )
        except BrokerError:
            return OperationResult(
                False, BrokerCode.OUTCOME_UNCERTAIN, request.request_id,
                snapshot.generation_id, request.grant_id,
                record["resulting_grant_version"],
            )
        return self._result_from_request(record, generation, idempotent=False)

    def _validate_provision_request(
        self, request: SecretProvisionRequest,
    ) -> dict[str, Any]:
        if type(request) is not SecretProvisionRequest:
            raise BrokerError("secret provision request is invalid")
        payload = {
            "operation_id": _validate_uuid(request.operation_id),
            "expected_generation_id": _validate_uuid(request.expected_generation_id),
            "provisioner_id": _validate_identifier(request.provisioner_id),
            "adapter_id": _validate_identifier(request.adapter_id),
            "operation": _validate_identifier(request.operation),
            "destination_id": _validate_identifier(request.destination_id),
        }
        if payload["provisioner_id"] != "synthetic_fixture_maintainer":
            raise BrokerError("secret provisioner is not allowed")
        registration = self._adapters.get(payload["adapter_id"])
        if (registration is None or
                registration.operation_id != payload["operation"] or
                registration.destination_id != payload["destination_id"]):
            raise BrokerError("secret provision capability is not allowed")
        return payload

    def _grant_payload(self, request: GrantProposalRequest) -> dict[str, Any]:
        if type(request) is not GrantProposalRequest:
            raise BrokerError("grant proposal is invalid")
        operation_id = _validate_uuid(request.operation_id)
        expected_generation_id = _validate_uuid(request.expected_generation_id)
        try:
            kind = GrantKind(request.grant_kind)
        except (ValueError, TypeError):
            raise BrokerError("grant kind is invalid") from None
        caller_id = _validate_identifier(request.caller_id)
        key_id = _validate_identifier(request.key_id)
        scope_id = _validate_synthetic_scope(request.scope_id)
        resource_id = _validate_uuid(request.resource_id)
        secret_ref = _validate_secret_ref(request.secret_ref)
        if type(request.secret_version) is not int or request.secret_version != 1:
            raise BrokerError("secret version is invalid")
        adapter_id = _validate_identifier(request.adapter_id)
        operation = _validate_identifier(request.operation)
        destination_id = _validate_identifier(request.destination_id)
        not_before = _utc(request.not_before)
        expires_at = _utc(request.expires_at)
        review_at = None if request.review_at is None else _utc(request.review_at)
        if expires_at <= not_before:
            raise BrokerError("grant time window is invalid")
        lifetime = expires_at - not_before
        if caller_id != self._caller_id or key_id != self._key_id:
            raise BrokerError("grant caller identity is invalid")
        if kind is GrantKind.ONE_TIME:
            if (type(request.max_uses) is not int or request.max_uses != 1 or
                    review_at is not None or lifetime > MAX_ONE_TIME_LIFETIME):
                raise BrokerError("one-time grant bounds are invalid")
        else:
            if (type(request.max_uses) is not int or
                    not 2 <= request.max_uses <= MAX_STANDING_USES or
                    lifetime > MAX_STANDING_LIFETIME or review_at is None or
                    not not_before < review_at < expires_at):
                raise BrokerError("standing grant bounds are invalid")
        registration = self._adapters.get(adapter_id)
        if (registration is None or registration.operation_id != operation or
                registration.destination_id != destination_id or
                registration.resource_id != resource_id):
            raise BrokerError("grant adapter capability is not allowed")
        return {
            "operation_id": operation_id,
            "expected_generation_id": expected_generation_id,
            "grant_kind": kind.value,
            "caller_id": caller_id,
            "key_id": key_id,
            "scope_id": scope_id,
            "resource_id": resource_id,
            "secret_ref": secret_ref,
            "secret_version": request.secret_version,
            "adapter_id": adapter_id,
            "operation": operation,
            "destination_id": destination_id,
            "not_before": _stamp(not_before),
            "expires_at": _stamp(expires_at),
            "max_uses": request.max_uses,
            "review_at": None if review_at is None else _stamp(review_at),
        }

    @staticmethod
    def _secret_matches_grant(
        secret_record: Mapping[str, Any], grant: Mapping[str, Any],
    ) -> bool:
        return (
            secret_record.get("status") == "active" and
            secret_record.get("secret_ref") == grant.get("secret_ref") and
            secret_record.get("version") == grant.get("secret_version") and
            secret_record.get("adapter_id") == grant.get("adapter_id") and
            secret_record.get("operation") == grant.get("operation") and
            secret_record.get("destination_id") == grant.get("destination_id")
        )

    def _evaluate_grant(
        self,
        request: ProtocolRequest,
        grant: Mapping[str, Any] | None,
        state: Mapping[str, Any],
        now: datetime,
    ) -> BrokerCode | None:
        if grant is None:
            return BrokerCode.CAPABILITY_DENIED
        if grant.get("version") != request.grant_version:
            return BrokerCode.STALE_STATE
        exact = {
            "caller_id": request.caller_id,
            "key_id": request.key_id,
            "scope_id": request.scope_id,
            "resource_id": request.resource_id,
            "secret_ref": request.opaque_secret_ref,
            "adapter_id": request.adapter_id,
            "operation": request.operation_id,
            "destination_id": request.destination_id,
        }
        if any(grant.get(key) != value for key, value in exact.items()):
            return BrokerCode.CAPABILITY_DENIED
        status = grant.get("status")
        if status == GrantStatus.REVOKED.value:
            return BrokerCode.GRANT_REVOKED
        if status == GrantStatus.EXHAUSTED.value:
            return BrokerCode.GRANT_EXHAUSTED
        if status == GrantStatus.RECOVERY_HOLD.value:
            return BrokerCode.GRANT_RECOVERY_HOLD
        if status != GrantStatus.ACTIVE.value:
            return BrokerCode.CAPABILITY_DENIED
        secret_record = state["secrets"].get(request.opaque_secret_ref)
        if secret_record is None or not self._secret_matches_grant(secret_record, grant):
            return BrokerCode.CAPABILITY_DENIED
        not_before = _parse_stamp(grant["not_before"])
        if request.issued_at < not_before or now < not_before:
            return BrokerCode.GRANT_NOT_YET_VALID
        if now >= _parse_stamp(grant["expires_at"]):
            return BrokerCode.GRANT_EXPIRED
        review_at = grant.get("review_at")
        if review_at is not None and now >= _parse_stamp(review_at):
            return BrokerCode.GRANT_REVIEW_REQUIRED
        if grant.get("uses_reserved", 0) >= grant.get("max_uses", 0):
            return BrokerCode.GRANT_EXHAUSTED
        return None

    @staticmethod
    def _registration_matches(
        registration: RegisteredAdapter, request: ProtocolRequest,
    ) -> bool:
        return (
            registration.adapter_id == request.adapter_id and
            registration.operation_id == request.operation_id and
            registration.destination_id == request.destination_id and
            registration.resource_id == request.resource_id
        )

    @staticmethod
    def _payload_is_exact(request: ProtocolRequest) -> bool:
        if (request.operation_id != NOTICE_DELIVER_OPERATION or
                set(request.payload) != {"notice_id"}):
            return False
        try:
            _validate_uuid(request.payload["notice_id"])
        except BrokerError:
            return False
        return True

    @staticmethod
    def _result_from_request(
        record: Mapping[str, Any], generation_id: str, *, idempotent: bool,
    ) -> OperationResult:
        status = record["status"]
        if status == RequestStatus.SUCCEEDED.value:
            code = BrokerCode.OPERATION_SUCCEEDED
            accepted = True
        elif status == RequestStatus.FAILED.value:
            code = BrokerCode.OPERATION_FAILED
            accepted = False
        elif status in {RequestStatus.RESERVED.value,
                        RequestStatus.RESOLVED_UNKNOWN.value}:
            code = BrokerCode.OUTCOME_UNCERTAIN
            accepted = False
        else:
            code = BrokerCode.STORAGE_UNAVAILABLE
            accepted = False
        return OperationResult(
            accepted, code, record["request_id"], generation_id,
            record["grant_id"], record["resulting_grant_version"],
            record.get("receipt_notice_id") if accepted else None,
            idempotent,
        )

    @staticmethod
    def _operation_seen(state: Mapping[str, Any], operation_id: str) -> bool:
        return any(event.get("operation_id") == operation_id
                   for event in state["audit"])

    @staticmethod
    def _approval_matches(
        recorded: object, requested: Mapping[str, Any],
    ) -> bool:
        return (
            type(recorded) is dict and
            all(recorded.get(key) == value for key, value in requested.items())
        )

    def _trusted_now(self, state: Mapping[str, Any] | None) -> datetime:
        try:
            current = _utc(self._clock())
        except Exception:
            raise BrokerError("trusted clock is unavailable") from None
        if state is not None:
            previous = _parse_stamp(state["last_trusted_at"])
            if current < previous:
                raise BrokerError("trusted clock moved backward")
        return current

    @staticmethod
    def _append_audit(
        state: dict[str, Any], *, event_type: str, occurred_at: datetime,
        operation_id: str | None, object_id: str | None, code: str,
        approval: Mapping[str, Any] | None = None,
    ) -> None:
        if len(state["audit"]) >= MAX_AUDIT_EVENTS:
            raise BrokerError("audit limit reached")
        previous = (
            state["audit"][-1]["event_sha256"] if state["audit"] else None
        )
        if (_AUDIT_TOKEN.fullmatch(event_type) is None or
                _AUDIT_TOKEN.fullmatch(code) is None):
            raise BrokerError("audit token is invalid")
        event = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "sequence": len(state["audit"]) + 1,
            "event_type": event_type,
            "occurred_at": _stamp(occurred_at),
            "operation_id": operation_id,
            "object_id": object_id,
            "code": code,
            "approval": None if approval is None else dict(approval),
            "previous_event_sha256": previous,
        }
        event["event_sha256"] = _sha256(_canonical_json(event))
        state["audit"].append(event)

    def _read_boundary_marker(self) -> dict[str, Any]:
        try:
            marker = _strict_json(
                _read_regular(self.root / SYNTHETIC_MARKER, maximum=8_192)
            )
        except BrokerError:
            raise BrokerError("synthetic boundary marker is unavailable") from None
        required = {
            "schema_version", "classification", "store_id",
            "real_credentials_permitted", "real_personal_data_permitted",
            "ordinary_runtime_integration_permitted", "live_ipc_permitted",
            "network_access_permitted", "deployment_permitted",
            "automatic_refresh_permitted", "key_persistence_permitted", "cipher",
        }
        if (type(marker) is not dict or set(marker) != required or
                marker["schema_version"] != STORE_SCHEMA_VERSION or
                marker["classification"] != "SYNTHETIC_ONLY" or
                marker["cipher"] != "AES-256-GCM-WINDOWS-CNG" or
                any(marker[name] is not False for name in required
                    if name.endswith("_permitted"))):
            raise BrokerError("synthetic boundary marker is invalid")
        _validate_uuid(marker["store_id"])
        return marker

    def _ensure_lock_file(self) -> None:
        lock_path = self.root / "broker.lock"
        try:
            if _is_reparse(lock_path) or not lock_path.is_file() or lock_path.stat().st_size != 1:
                raise BrokerError("broker lock is invalid")
        except OSError:
            raise BrokerError("broker lock is invalid") from None

    @contextmanager
    def _store_lock(self) -> Iterator[None]:
        if msvcrt is None:
            raise BrokerError("Windows broker locking is unavailable")
        with self._thread_lock:
            if self._store_lock_depth:
                self._store_lock_depth += 1
                try:
                    yield
                finally:
                    self._store_lock_depth -= 1
                return
            self._ensure_lock_file()
            try:
                stream = (self.root / "broker.lock").open("r+b", buffering=0)
            except OSError:
                raise BrokerError("broker lock is unavailable") from None
            acquired = False
            deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
            try:
                while not acquired:
                    try:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        acquired = True
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise BrokerError("broker lock acquisition timed out") from None
                        time.sleep(0.01)
                self._store_lock_depth = 1
                yield
            finally:
                if acquired:
                    self._store_lock_depth = 0
                    try:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                stream.close()

    def _commit_state(
        self,
        *,
        state: Mapping[str, Any],
        secret_values: Mapping[str, bytearray],
        parent_generation_id: str | None,
        rollback_source_generation_id: str | None,
    ) -> str:
        if parent_generation_id is not None:
            _validate_uuid(parent_generation_id)
        if rollback_source_generation_id is not None:
            _validate_uuid(rollback_source_generation_id)
        generation_id = _validate_uuid(self._generation_id_factory())
        created_at = _stamp(_parse_stamp(state["last_trusted_at"]))
        generation_state = dict(state)
        generation_state.update({
            "generation_id": generation_id,
            "parent_generation_id": parent_generation_id,
            "rollback_source_generation_id": rollback_source_generation_id,
            "created_at": created_at,
        })
        self._validate_state(generation_state)
        state_payload = _json_bytes(generation_state)
        if len(state_payload) > MAX_STATE_BYTES:
            raise BrokerError("broker state capacity is exhausted")
        vault_plaintext = _pack_vault(secret_values, generation_state["secrets"])
        vault_aad = self._vault_aad(generation_id, state_payload)
        try:
            protected_vault = self._cipher.protect(vault_plaintext, vault_aad)
        except CryptoError:
            raise BrokerError("encrypted broker transaction failed") from None
        finally:
            _zero(vault_plaintext)
        vault_payload = _json_bytes(protected_vault.to_dict())

        staging_root = self.root / "staging"
        generations_root = self.root / "generations"
        stage = staging_root / generation_id
        target = generations_root / generation_id
        if stage.exists() or target.exists():
            raise BrokerError("generation identifier already exists")
        try:
            stage.mkdir(parents=True)
            _write_exclusive(stage / "state.json", state_payload)
            _write_exclusive(stage / "vault.json", vault_payload)
            entries = [
                {"path": "state.json", "sha256": _sha256(state_payload),
                 "bytes": len(state_payload)},
                {"path": "vault.json", "sha256": _sha256(vault_payload),
                 "bytes": len(vault_payload)},
            ]
            manifest = {
                "schema_version": STORE_SCHEMA_VERSION,
                "classification": "SYNTHETIC_ONLY",
                "complete": True,
                "store_id": self._marker["store_id"],
                "generation_id": generation_id,
                "parent_generation_id": parent_generation_id,
                "rollback_source_generation_id": rollback_source_generation_id,
                "created_at": created_at,
                "secret_count": len(generation_state["secrets"]),
                "proposal_count": len(generation_state["proposals"]),
                "grant_count": len(generation_state["grants"]),
                "request_count": len(generation_state["requests"]),
                "audit_event_count": len(generation_state["audit"]),
                "entries": entries,
            }
            manifest_payload = _json_bytes(manifest)
            manifest_hash = _sha256(manifest_payload)
            auth_plaintext = bytearray(_AUTH_MARKER)
            try:
                manifest_auth = self._cipher.protect(
                    auth_plaintext, self._manifest_aad(manifest_payload)
                )
            except CryptoError:
                raise BrokerError("manifest authentication failed") from None
            finally:
                _zero(auth_plaintext)
            _write_exclusive(stage / "manifest.json", manifest_payload)
            _write_exclusive(
                stage / "manifest.sha256", (manifest_hash + "\n").encode("ascii")
            )
            _write_exclusive(stage / "manifest.auth.json",
                             _json_bytes(manifest_auth.to_dict()))
            _, staged_values, staged_snapshot = self._load_generation_path(
                stage, expected_generation_id=generation_id
            )
            _zero_values(staged_values)
            if staged_snapshot.manifest_sha256 != manifest_hash:
                raise BrokerError("staged broker generation is inconsistent")
            generations_root.mkdir(parents=True, exist_ok=True)
            _move_write_through(stage, target, replace=False)
            _, final_values, final_snapshot = self._load_generation_path(
                target, expected_generation_id=generation_id
            )
            _zero_values(final_values)
            if final_snapshot.manifest_sha256 != manifest_hash:
                raise BrokerError("promoted broker generation is inconsistent")
            self._write_current_pointer(generation_id, manifest_hash)
            try:
                selected = self._read_current_pointer()
                if (selected["generation_id"] != generation_id or
                        selected["manifest_sha256"] != manifest_hash):
                    raise BrokerError("current broker pointer selection failed")
                _, selected_values, selected_snapshot = (
                    self._load_generation_state(generation_id)
                )
                _zero_values(selected_values)
                if selected_snapshot.manifest_sha256 != manifest_hash:
                    raise BrokerError("selected broker generation is inconsistent")
            except BrokerError:
                raise _CommitOutcomeUncertain(generation_id) from None
            return generation_id
        except _CommitOutcomeUncertain:
            raise
        except BrokerError:
            raise
        except OSError:
            raise BrokerError("broker state transaction failed") from None

    def _write_current_pointer(self, generation_id: str, manifest_hash: str) -> None:
        core = {
            "schema_version": STORE_SCHEMA_VERSION,
            "store_id": self._marker["store_id"],
            "generation_id": _validate_uuid(generation_id),
            "manifest_sha256": _validate_sha256(manifest_hash),
        }
        marker = bytearray(_AUTH_MARKER)
        try:
            auth = self._cipher.protect(marker, self._pointer_aad(core))
        except CryptoError:
            raise BrokerError("current pointer authentication failed") from None
        finally:
            _zero(marker)
        payload = _json_bytes({**core, "auth": auth.to_dict()})
        temporary = self.root / f".current.{generation_id}.tmp"
        try:
            _write_exclusive(temporary, payload)
            _move_write_through(
                temporary, self.root / "current.json", replace=True
            )
        except OSError:
            raise BrokerError("current broker pointer update failed") from None
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_current_state(
        self,
    ) -> tuple[dict[str, Any], dict[str, bytearray], BrokerSnapshot]:
        pointer = self._read_current_pointer()
        state, values, snapshot = self._load_generation_state(pointer["generation_id"])
        if snapshot.manifest_sha256 != pointer["manifest_sha256"]:
            _zero_values(values)
            raise BrokerError("current pointer does not match its generation")
        return state, values, snapshot

    def _load_current_metadata(self) -> tuple[dict[str, Any], BrokerSnapshot]:
        pointer = self._read_current_pointer()
        state, values, snapshot = self._load_generation_state(
            pointer["generation_id"], decrypt_vault=False
        )
        if values:
            _zero_values(values)
            raise BrokerError("metadata load returned secret material")
        if snapshot.manifest_sha256 != pointer["manifest_sha256"]:
            raise BrokerError("current pointer does not match its generation")
        return state, snapshot

    def _read_current_pointer(self) -> dict[str, Any]:
        try:
            pointer = _strict_json(
                _read_regular(self.root / "current.json", maximum=16_384)
            )
            if type(pointer) is not dict or set(pointer) != {
                    "schema_version", "store_id", "generation_id",
                    "manifest_sha256", "auth"}:
                raise BrokerError("current broker pointer is invalid")
            core = {key: pointer[key] for key in (
                "schema_version", "store_id", "generation_id", "manifest_sha256"
            )}
            if (core["schema_version"] != STORE_SCHEMA_VERSION or
                    core["store_id"] != self._marker["store_id"]):
                raise BrokerError("current broker pointer is invalid")
            _validate_uuid(core["generation_id"])
            _validate_sha256(core["manifest_sha256"])
            with self._cipher.unprotect(
                    ProtectedBlob.from_dict(pointer["auth"]),
                    self._pointer_aad(core)) as plaintext:
                view = plaintext.view()
                try:
                    if not secrets.compare_digest(view, _AUTH_MARKER):
                        raise BrokerError("current broker pointer is invalid")
                finally:
                    view.release()
            return core
        except (BrokerError, CryptoError):
            raise BrokerError("current broker pointer is unavailable") from None

    def _load_generation_state(
        self, generation_id: str, *, decrypt_vault: bool = True,
    ) -> tuple[dict[str, Any], dict[str, bytearray], BrokerSnapshot]:
        generation_id = _validate_uuid(generation_id)
        path = self.root / "generations" / generation_id
        if not path.is_dir() or _is_reparse(path):
            raise BrokerError("broker generation is unavailable")
        return self._load_generation_path(
            path,
            expected_generation_id=generation_id,
            decrypt_vault=decrypt_vault,
        )

    def _load_generation_path(
        self,
        path: Path,
        *,
        expected_generation_id: str,
        decrypt_vault: bool = True,
    ) -> tuple[dict[str, Any], dict[str, bytearray], BrokerSnapshot]:
        values: dict[str, bytearray] = {}
        try:
            _assert_plain_chain(path)
            children = tuple(path.iterdir())
            actual = {item.name for item in children}
            expected = {
                "state.json", "vault.json", "manifest.json",
                "manifest.sha256", "manifest.auth.json",
            }
            if (len(children) != len(expected) or actual != expected or
                    any(_is_reparse(item) or not item.is_file()
                        for item in children)):
                raise BrokerError("broker generation tree is invalid")
            manifest_payload = _read_regular(path / "manifest.json", maximum=262_144)
            digest_payload = _read_regular(path / "manifest.sha256", maximum=128)
            try:
                if len(digest_payload) != 65 or digest_payload[-1:] != b"\n":
                    raise BrokerError("broker generation manifest is invalid")
                digest = digest_payload[:64].decode("ascii")
            except UnicodeError:
                raise BrokerError("broker generation manifest is invalid") from None
            if not _SHA256.fullmatch(digest) or _sha256(manifest_payload) != digest:
                raise BrokerError("broker generation manifest was modified")
            manifest = _strict_json(manifest_payload)
            self._validate_manifest(manifest, expected_generation_id)
            auth = ProtectedBlob.from_dict(_strict_json(
                _read_regular(path / "manifest.auth.json", maximum=16_384)
            ))
            with self._cipher.unprotect(
                    auth, self._manifest_aad(manifest_payload)) as plaintext:
                view = plaintext.view()
                try:
                    if not secrets.compare_digest(view, _AUTH_MARKER):
                        raise BrokerError("broker generation manifest is invalid")
                finally:
                    view.release()
            entry_payloads: dict[str, bytes] = {}
            for entry in manifest["entries"]:
                maximum = (
                    MAX_STATE_BYTES
                    if entry["path"] == "state.json"
                    else MAX_VAULT_FILE_BYTES
                )
                payload = _read_regular(path / entry["path"], maximum=maximum)
                if len(payload) != entry["bytes"] or _sha256(payload) != entry["sha256"]:
                    raise BrokerError("broker generation entry was modified")
                entry_payloads[entry["path"]] = payload
            state_payload = entry_payloads["state.json"]
            state = _strict_json(state_payload)
            self._validate_state(state)
            if (state["generation_id"] != expected_generation_id or
                    state["store_id"] != self._marker["store_id"] or
                    state["created_at"] != manifest["created_at"] or
                    state["parent_generation_id"] != manifest["parent_generation_id"] or
                    state["rollback_source_generation_id"] !=
                    manifest["rollback_source_generation_id"]):
                raise BrokerError("broker generation state is inconsistent")
            protected_vault = ProtectedBlob.from_dict(
                _strict_json(entry_payloads["vault.json"])
            )
            if decrypt_vault:
                with self._cipher.unprotect(
                        protected_vault,
                        self._vault_aad(
                            expected_generation_id, state_payload
                        )) as plaintext:
                    view = plaintext.view()
                    try:
                        values = _unpack_vault(view, state["secrets"])
                    finally:
                        view.release()
            counts = {
                "secret_count": len(state["secrets"]),
                "proposal_count": len(state["proposals"]),
                "grant_count": len(state["grants"]),
                "request_count": len(state["requests"]),
                "audit_event_count": len(state["audit"]),
            }
            if any(manifest[key] != value for key, value in counts.items()):
                raise BrokerError("broker generation counts are inconsistent")
            snapshot = BrokerSnapshot(
                expected_generation_id, digest, counts["secret_count"],
                counts["proposal_count"], counts["grant_count"],
                counts["request_count"], counts["audit_event_count"],
                state["last_trusted_at"],
            )
            return state, values, snapshot
        except (BrokerError, CryptoError, OSError, ValueError, TypeError):
            _zero_values(values)
            raise BrokerError("broker generation is unavailable") from None
        except BaseException:
            _zero_values(values)
            raise

    def _validate_manifest(self, manifest: object, generation_id: str) -> None:
        required = {
            "schema_version", "classification", "complete", "store_id",
            "generation_id", "parent_generation_id",
            "rollback_source_generation_id", "created_at", "secret_count",
            "proposal_count", "grant_count", "request_count",
            "audit_event_count", "entries",
        }
        if (type(manifest) is not dict or set(manifest) != required or
                manifest["schema_version"] != STORE_SCHEMA_VERSION or
                manifest["classification"] != "SYNTHETIC_ONLY" or
                manifest["complete"] is not True or
                manifest["store_id"] != self._marker["store_id"] or
                manifest["generation_id"] != generation_id):
            raise BrokerError("broker generation manifest is invalid")
        _validate_uuid(manifest["generation_id"])
        if manifest["parent_generation_id"] is not None:
            _validate_uuid(manifest["parent_generation_id"])
        if manifest["rollback_source_generation_id"] is not None:
            _validate_uuid(manifest["rollback_source_generation_id"])
        _parse_stamp(manifest["created_at"])
        bounds = {
            "secret_count": MAX_SECRETS,
            "proposal_count": MAX_PROPOSALS,
            "grant_count": MAX_GRANTS,
            "request_count": MAX_REQUESTS,
            "audit_event_count": MAX_AUDIT_EVENTS,
        }
        for field, maximum in bounds.items():
            if type(manifest[field]) is not int or not 0 <= manifest[field] <= maximum:
                raise BrokerError("broker generation count is invalid")
        entries = manifest["entries"]
        if type(entries) is not list or len(entries) != 2:
            raise BrokerError("broker generation entries are invalid")
        paths: set[str] = set()
        for entry in entries:
            if (type(entry) is not dict or set(entry) != {"path", "sha256", "bytes"} or
                    entry.get("path") not in {"state.json", "vault.json"} or
                    entry["path"] in paths or
                    type(entry.get("bytes")) is not int or
                    not 0 <= entry["bytes"] <= (
                        MAX_STATE_BYTES if entry["path"] == "state.json"
                        else MAX_VAULT_FILE_BYTES
                    )):
                raise BrokerError("broker generation entry is invalid")
            _validate_sha256(entry.get("sha256"))
            paths.add(entry["path"])
        if paths != {"state.json", "vault.json"}:
            raise BrokerError("broker generation entries are incomplete")

    def _validate_state(self, state: object) -> None:
        required = {
            "schema_version", "classification", "store_id", "generation_id",
            "parent_generation_id", "rollback_source_generation_id", "created_at",
            "last_trusted_at", "secrets", "proposals", "grants", "requests",
            "nonces", "audit",
        }
        if (type(state) is not dict or set(state) != required or
                state["schema_version"] != STATE_SCHEMA_VERSION or
                state["classification"] != "SYNTHETIC_ONLY" or
                state["store_id"] != self._marker["store_id"]):
            raise BrokerError("broker state is invalid")
        _validate_uuid(state["store_id"])
        _validate_uuid(state["generation_id"])
        if state["parent_generation_id"] is not None:
            _validate_uuid(state["parent_generation_id"])
        if state["rollback_source_generation_id"] is not None:
            _validate_uuid(state["rollback_source_generation_id"])
        created_at = _parse_stamp(state["created_at"])
        trusted_at = _parse_stamp(state["last_trusted_at"])
        if created_at != trusted_at:
            raise BrokerError("broker trusted time is inconsistent")
        collections = (
            ("secrets", MAX_SECRETS), ("proposals", MAX_PROPOSALS),
            ("grants", MAX_GRANTS), ("requests", MAX_REQUESTS),
            ("nonces", MAX_REQUESTS),
        )
        for name, maximum in collections:
            if type(state[name]) is not dict or len(state[name]) > maximum:
                raise BrokerError("broker state collection is invalid")
        if type(state["audit"]) is not list or not 1 <= len(state["audit"]) <= MAX_AUDIT_EVENTS:
            raise BrokerError("broker audit is invalid")
        self._validate_secret_records(state["secrets"])
        self._validate_proposals(state["proposals"])
        self._validate_grants(state["grants"])
        self._validate_requests(state["requests"], state["nonces"])
        self._validate_audit(state["audit"])
        self._validate_state_relationships(state, created_at)

    @staticmethod
    def _validate_secret_records(records: Mapping[str, Any]) -> None:
        fields = {
            "schema_version", "secret_ref", "version", "status", "adapter_id",
            "operation", "destination_id", "provisioner_id", "provisioned_at",
        }
        for secret_ref, record in records.items():
            if (type(record) is not dict or set(record) != fields or
                    record["schema_version"] != 1 or
                    record["secret_ref"] != secret_ref or record["version"] != 1 or
                    record["status"] != "active" or
                    record["provisioner_id"] != "synthetic_fixture_maintainer"):
                raise BrokerError("secret metadata is invalid")
            _validate_secret_ref(secret_ref)
            _validate_identifier(record["adapter_id"])
            _validate_identifier(record["operation"])
            _validate_identifier(record["destination_id"])
            _parse_stamp(record["provisioned_at"])

    @staticmethod
    def _validate_proposals(proposals: Mapping[str, Any]) -> None:
        fields = {
            "schema_version", "proposal_id", "operation_id",
            "expected_generation_id", "grant_kind", "caller_id", "key_id",
            "scope_id", "resource_id", "secret_ref", "secret_version",
            "adapter_id", "operation", "destination_id", "not_before",
            "expires_at", "max_uses", "review_at", "proposal_digest", "status",
            "created_at", "approval", "grant_id",
        }
        for proposal_id, proposal in proposals.items():
            if (type(proposal) is not dict or set(proposal) != fields or
                    proposal["schema_version"] != 1 or
                    proposal["proposal_id"] != proposal_id or
                    proposal["status"] not in {"pending", "approved"}):
                raise BrokerError("grant proposal state is invalid")
            _validate_uuid(proposal_id)
            _validate_uuid(proposal["operation_id"])
            _validate_uuid(proposal["expected_generation_id"])
            _validate_sha256(proposal["proposal_digest"])
            _validate_identifier(proposal["caller_id"])
            _validate_identifier(proposal["key_id"])
            _validate_synthetic_scope(proposal["scope_id"])
            _validate_uuid(proposal["resource_id"])
            _validate_secret_ref(proposal["secret_ref"])
            if proposal["secret_version"] != 1:
                raise BrokerError("grant proposal secret version is invalid")
            for field in ("adapter_id", "operation", "destination_id"):
                _validate_identifier(proposal[field])
            not_before = _parse_stamp(proposal["not_before"])
            expires_at = _parse_stamp(proposal["expires_at"])
            _parse_stamp(proposal["created_at"])
            review_at = (
                None if proposal["review_at"] is None
                else _parse_stamp(proposal["review_at"])
            )
            kind = GrantKind(proposal["grant_kind"])
            max_uses = proposal["max_uses"]
            if expires_at <= not_before or type(max_uses) is not int:
                raise BrokerError("grant proposal use bound is invalid")
            if kind is GrantKind.ONE_TIME:
                if (max_uses != 1 or review_at is not None or
                        expires_at - not_before > MAX_ONE_TIME_LIFETIME):
                    raise BrokerError("one-time proposal bounds are invalid")
            elif (not 2 <= max_uses <= MAX_STANDING_USES or
                    expires_at - not_before > MAX_STANDING_LIFETIME or
                    review_at is None or
                    not not_before < review_at < expires_at):
                raise BrokerError("standing proposal bounds are invalid")
            payload = {
                key: proposal[key] for key in (
                    "operation_id", "expected_generation_id", "grant_kind",
                    "caller_id", "key_id", "scope_id", "resource_id",
                    "secret_ref", "secret_version", "adapter_id", "operation",
                    "destination_id", "not_before", "expires_at", "max_uses",
                    "review_at",
                )
            }
            if _sha256(_canonical_json(payload)) != proposal["proposal_digest"]:
                raise BrokerError("grant proposal digest is inconsistent")
            if proposal["status"] == "pending":
                if proposal["approval"] is not None or proposal["grant_id"] is not None:
                    raise BrokerError("pending grant proposal is invalid")
            else:
                SyntheticSecretBroker._validate_approval_record(proposal["approval"])
                _validate_uuid(proposal["grant_id"])
                if (proposal["approval"]["proposal_id"] != proposal_id or
                        proposal["approval"]["proposal_digest"] !=
                        proposal["proposal_digest"]):
                    raise BrokerError("grant proposal approval is inconsistent")

    @staticmethod
    def _validate_approval_record(approval: object) -> None:
        fields = {
            "schema_version", "operation_id", "expected_generation_id",
            "proposal_id", "proposal_digest", "authority", "decision",
            "source_turn_id", "channel", "approved_at",
        }
        if (type(approval) is not dict or set(approval) != fields or
                approval["schema_version"] != 1 or
                approval["authority"] != "product_owner" or
                approval["decision"] != "approve_exact_grant"):
            raise BrokerError("grant approval record is invalid")
        _validate_uuid(approval["operation_id"])
        _validate_uuid(approval["expected_generation_id"])
        _validate_uuid(approval["proposal_id"])
        _validate_uuid(approval["source_turn_id"])
        ApprovalChannel(approval["channel"])
        _validate_sha256(approval["proposal_digest"])
        _parse_stamp(approval["approved_at"])

    @staticmethod
    def _validate_grants(grants: Mapping[str, Any]) -> None:
        fields = {
            "schema_version", "grant_id", "version", "status", "grant_kind",
            "caller_id", "key_id", "scope_id", "resource_id", "secret_ref",
            "secret_version", "adapter_id", "operation", "destination_id",
            "not_before", "expires_at", "review_at", "max_uses", "uses_reserved",
            "proposal_id", "proposal_digest", "approval", "created_at", "updated_at",
        }
        for grant_id, grant in grants.items():
            if (type(grant) is not dict or set(grant) != fields or
                    grant["schema_version"] != 1 or grant["grant_id"] != grant_id or
                    type(grant["version"]) is not int or grant["version"] < 1 or
                    grant["status"] not in {item.value for item in GrantStatus}):
                raise BrokerError("grant state is invalid")
            _validate_uuid(grant_id)
            kind = GrantKind(grant["grant_kind"])
            for field in ("caller_id", "key_id", "scope_id", "adapter_id",
                          "operation", "destination_id"):
                _validate_identifier(grant[field])
            _validate_synthetic_scope(grant["scope_id"])
            _validate_uuid(grant["resource_id"])
            _validate_secret_ref(grant["secret_ref"])
            if grant["secret_version"] != 1:
                raise BrokerError("grant secret version is invalid")
            not_before = _parse_stamp(grant["not_before"])
            expires_at = _parse_stamp(grant["expires_at"])
            review_at = (
                None if grant["review_at"] is None
                else _parse_stamp(grant["review_at"])
            )
            if (type(grant["max_uses"]) is not int or grant["max_uses"] < 1 or
                    type(grant["uses_reserved"]) is not int or
                    not 0 <= grant["uses_reserved"] <= grant["max_uses"]):
                raise BrokerError("grant use state is invalid")
            if expires_at <= not_before:
                raise BrokerError("grant time window is invalid")
            if kind is GrantKind.ONE_TIME:
                if (grant["max_uses"] != 1 or review_at is not None or
                        expires_at - not_before > MAX_ONE_TIME_LIFETIME):
                    raise BrokerError("one-time grant bounds are invalid")
            elif (not 2 <= grant["max_uses"] <= MAX_STANDING_USES or
                    expires_at - not_before > MAX_STANDING_LIFETIME or
                    review_at is None or
                    not not_before < review_at < expires_at):
                raise BrokerError("standing grant bounds are invalid")
            if (grant["version"] < grant["uses_reserved"] + 1 or
                    (grant["status"] == GrantStatus.ACTIVE.value and
                     grant["uses_reserved"] >= grant["max_uses"]) or
                    (grant["status"] == GrantStatus.EXHAUSTED.value and
                     grant["uses_reserved"] != grant["max_uses"]) or
                    (grant["status"] == GrantStatus.RECOVERY_HOLD.value and
                     grant["uses_reserved"] >= grant["max_uses"])):
                raise BrokerError("grant status is inconsistent")
            _validate_uuid(grant["proposal_id"])
            _validate_sha256(grant["proposal_digest"])
            SyntheticSecretBroker._validate_approval_record(grant["approval"])
            if (grant["approval"]["proposal_id"] != grant["proposal_id"] or
                    grant["approval"]["proposal_digest"] !=
                    grant["proposal_digest"]):
                raise BrokerError("grant approval is inconsistent")
            _parse_stamp(grant["created_at"])
            _parse_stamp(grant["updated_at"])

    @staticmethod
    def _validate_requests(requests: Mapping[str, Any], nonces: Mapping[str, Any]) -> None:
        fields = {
            "schema_version", "request_id", "request_digest", "nonce_sha256",
            "grant_id", "reserved_grant_version", "resulting_grant_version",
            "status", "result_code", "receipt_notice_id", "reserved_at",
            "completed_at",
        }
        seen_nonces: set[str] = set()
        for request_id, record in requests.items():
            if (type(record) is not dict or set(record) != fields or
                    record["schema_version"] != 1 or record["request_id"] != request_id or
                    record["status"] not in {item.value for item in RequestStatus} or
                    record["result_code"] not in {item.value for item in BrokerCode}):
                raise BrokerError("operation request state is invalid")
            _validate_uuid(request_id)
            _validate_sha256(record["request_digest"])
            nonce_hash = _validate_sha256(record["nonce_sha256"])
            _validate_uuid(record["grant_id"])
            if (type(record["reserved_grant_version"]) is not int or
                    type(record["resulting_grant_version"]) is not int or
                    record["resulting_grant_version"] !=
                    record["reserved_grant_version"] + 1):
                raise BrokerError("operation grant revision is invalid")
            if record["receipt_notice_id"] is not None:
                _validate_uuid(record["receipt_notice_id"])
            _parse_stamp(record["reserved_at"])
            if record["completed_at"] is not None:
                _parse_stamp(record["completed_at"])
            if (record["status"] == RequestStatus.RESERVED.value) != (
                    record["completed_at"] is None):
                raise BrokerError("operation completion state is invalid")
            expected_results = {
                RequestStatus.RESERVED.value: (
                    BrokerCode.OUTCOME_UNCERTAIN.value, False
                ),
                RequestStatus.SUCCEEDED.value: (
                    BrokerCode.OPERATION_SUCCEEDED.value, True
                ),
                RequestStatus.FAILED.value: (
                    BrokerCode.OPERATION_FAILED.value, False
                ),
                RequestStatus.RESOLVED_UNKNOWN.value: (
                    BrokerCode.OUTCOME_UNCERTAIN.value, False
                ),
            }
            expected_code, receipt_required = expected_results[record["status"]]
            if (record["result_code"] != expected_code or
                    (record["receipt_notice_id"] is not None) != receipt_required):
                raise BrokerError("operation result state is inconsistent")
            if nonces.get(nonce_hash) != request_id or nonce_hash in seen_nonces:
                raise BrokerError("operation nonce state is invalid")
            seen_nonces.add(nonce_hash)
        if set(nonces) != seen_nonces:
            raise BrokerError("operation nonce inventory is invalid")
        for nonce_hash, request_id in nonces.items():
            _validate_sha256(nonce_hash)
            _validate_uuid(request_id)

    @staticmethod
    def _validate_state_relationships(
        state: Mapping[str, Any], created_at: datetime,
    ) -> None:
        audit_times = tuple(
            _parse_stamp(event["occurred_at"]) for event in state["audit"]
        )
        if (any(later < earlier for earlier, later in
                zip(audit_times, audit_times[1:])) or
                audit_times[-1] != created_at):
            raise BrokerError("broker audit chronology is invalid")

        for secret in state["secrets"].values():
            if _parse_stamp(secret["provisioned_at"]) > created_at:
                raise BrokerError("secret chronology is invalid")

        grant_fields = (
            "grant_kind", "caller_id", "key_id", "scope_id", "resource_id",
            "secret_ref", "secret_version", "adapter_id", "operation",
            "destination_id", "not_before", "expires_at", "review_at",
            "max_uses", "proposal_digest",
        )
        for proposal_id, proposal in state["proposals"].items():
            if _parse_stamp(proposal["created_at"]) > created_at:
                raise BrokerError("grant proposal chronology is invalid")
            if proposal["approval"] is not None and _parse_stamp(
                    proposal["approval"]["approved_at"]) > created_at:
                raise BrokerError("grant approval chronology is invalid")
            if proposal["status"] == "approved":
                grant = state["grants"].get(proposal["grant_id"])
                if (grant is None or grant["proposal_id"] != proposal_id or
                        grant["approval"] != proposal["approval"] or
                        any(grant[field] != proposal[field]
                            for field in grant_fields)):
                    raise BrokerError("grant proposal link is inconsistent")

        request_counts: dict[str, int] = {}
        for request in state["requests"].values():
            grant = state["grants"].get(request["grant_id"])
            if (grant is None or
                    request["resulting_grant_version"] > grant["version"]):
                raise BrokerError("operation grant link is inconsistent")
            request_counts[request["grant_id"]] = (
                request_counts.get(request["grant_id"], 0) + 1
            )
            reserved_at = _parse_stamp(request["reserved_at"])
            completed_at = (
                None if request["completed_at"] is None
                else _parse_stamp(request["completed_at"])
            )
            if (reserved_at > created_at or
                    (completed_at is not None and
                     (completed_at < reserved_at or completed_at > created_at))):
                raise BrokerError("operation chronology is invalid")

        for grant_id, grant in state["grants"].items():
            proposal = state["proposals"].get(grant["proposal_id"])
            if (proposal is None or proposal["grant_id"] != grant_id or
                    request_counts.get(grant_id, 0) != grant["uses_reserved"]):
                raise BrokerError("grant state link is inconsistent")
            created = _parse_stamp(grant["created_at"])
            updated = _parse_stamp(grant["updated_at"])
            approved = _parse_stamp(grant["approval"]["approved_at"])
            if not approved == created <= updated <= created_at:
                raise BrokerError("grant chronology is invalid")
            if grant["status"] == GrantStatus.ACTIVE.value:
                secret = state["secrets"].get(grant["secret_ref"])
                if (secret is None or not
                        SyntheticSecretBroker._secret_matches_grant(secret, grant)):
                    raise BrokerError("active grant secret link is inconsistent")

    @staticmethod
    def _validate_audit(events: Sequence[Mapping[str, Any]]) -> None:
        fields = {
            "schema_version", "sequence", "event_type", "occurred_at",
            "operation_id", "object_id", "code", "approval",
            "previous_event_sha256", "event_sha256",
        }
        previous: str | None = None
        for sequence, event in enumerate(events, start=1):
            if (type(event) is not dict or set(event) != fields or
                    event["schema_version"] != AUDIT_SCHEMA_VERSION or
                    event["sequence"] != sequence or
                    type(event["event_type"]) is not str or
                    _AUDIT_TOKEN.fullmatch(event["event_type"]) is None or
                    type(event["code"]) is not str or
                    _AUDIT_TOKEN.fullmatch(event["code"]) is None or
                    event["previous_event_sha256"] != previous):
                raise BrokerError("broker audit event is invalid")
            _parse_stamp(event["occurred_at"])
            if event["operation_id"] is not None:
                _validate_uuid(event["operation_id"])
            if event["object_id"] is not None:
                _validate_identifier(event["object_id"])
            approval = event["approval"]
            expected_decisions = {
                "GRANT_APPROVED": "approve_exact_grant",
                "GRANT_REVOKED": "approve_exact_revocation",
                "UNCERTAIN_REQUEST_CLOSED": "close_uncertain_without_retry",
                "SECRETS_ROLLED_BACK": "approve_exact_secret_rollback",
            }
            expected_decision = expected_decisions.get(event["event_type"])
            if expected_decision is None:
                if approval is not None:
                    raise BrokerError("broker audit approval is invalid")
            else:
                SyntheticSecretBroker._validate_audit_approval(
                    approval, expected_decision
                )
                if (approval["operation_id"] != event["operation_id"] or
                        (expected_decision == "approve_exact_grant" and
                         str(uuid.uuid5(
                             _UUID_NAMESPACE_GRANT, approval["operation_id"]
                         )) != event["object_id"]) or
                        (expected_decision == "approve_exact_revocation" and
                         approval["grant_id"] != event["object_id"]) or
                        (expected_decision == "close_uncertain_without_retry" and
                         approval["request_id"] != event["object_id"]) or
                        (expected_decision == "approve_exact_secret_rollback" and
                         approval["target_generation_id"] != event["object_id"])):
                    raise BrokerError("broker audit approval is inconsistent")
            digest = _validate_sha256(event["event_sha256"])
            unsigned = dict(event)
            del unsigned["event_sha256"]
            if _sha256(_canonical_json(unsigned)) != digest:
                raise BrokerError("broker audit authentication is invalid")
            previous = digest

    @staticmethod
    def _validate_audit_approval(approval: object, decision: str) -> None:
        common = {
            "schema_version", "operation_id", "expected_generation_id",
            "source_turn_id", "channel", "authority", "decision", "approved_at",
        }
        specific = {
            "approve_exact_grant": {"proposal_id", "proposal_digest"},
            "approve_exact_revocation": {"grant_id", "expected_grant_version"},
            "close_uncertain_without_retry": {"request_id"},
            "approve_exact_secret_rollback": {
                "target_generation_id", "target_manifest_sha256",
            },
        }
        if (decision not in specific or type(approval) is not dict or
                set(approval) != common | specific[decision] or
                approval["schema_version"] != 1 or
                approval["authority"] != "product_owner" or
                approval["decision"] != decision):
            raise BrokerError("broker audit approval is invalid")
        _validate_uuid(approval["operation_id"])
        _validate_uuid(approval["expected_generation_id"])
        _validate_uuid(approval["source_turn_id"])
        ApprovalChannel(approval["channel"])
        _parse_stamp(approval["approved_at"])
        if decision == "approve_exact_grant":
            _validate_uuid(approval["proposal_id"])
            _validate_sha256(approval["proposal_digest"])
        elif decision == "approve_exact_revocation":
            _validate_uuid(approval["grant_id"])
            if (type(approval["expected_grant_version"]) is not int or
                    approval["expected_grant_version"] < 1):
                raise BrokerError("broker audit approval is invalid")
        elif decision == "close_uncertain_without_retry":
            _validate_uuid(approval["request_id"])
        else:
            _validate_uuid(approval["target_generation_id"])
            _validate_sha256(approval["target_manifest_sha256"])

    def _vault_aad(self, generation_id: str, state_payload: bytes) -> bytes:
        return _canonical_json({
            "schema_version": STORE_SCHEMA_VERSION,
            "purpose": "phase8f.secret-vault",
            "store_id": self._marker["store_id"],
            "generation_id": generation_id,
            "state_sha256": _sha256(state_payload),
        })

    def _manifest_aad(self, manifest_payload: bytes) -> bytes:
        return _canonical_json({
            "schema_version": STORE_SCHEMA_VERSION,
            "purpose": "phase8f.generation-manifest",
            "store_id": self._marker["store_id"],
            "manifest_sha256": _sha256(manifest_payload),
        })

    def _pointer_aad(self, core: Mapping[str, Any]) -> bytes:
        return _canonical_json({
            "purpose": "phase8f.current-pointer",
            "pointer": dict(core),
        })

class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError
        value[key] = item
    return value


def _reject_json_constant(_value: str) -> None:
    raise ValueError


def _strict_json(payload: bytes) -> Any:
    try:
        text = payload.decode("ascii", errors="strict")
        return json.loads(
            text, object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, _DuplicateKeyError, ValueError):
        raise BrokerError("broker JSON is invalid") from None


__all__ = [
    "ApprovalChannel",
    "BrokerCode",
    "BrokerError",
    "BrokerSnapshot",
    "ExactGrantApproval",
    "GrantKind",
    "GrantProposalRequest",
    "GrantRevocationApproval",
    "GrantStatus",
    "MutationResult",
    "OperationResult",
    "PendingResolutionApproval",
    "RegisteredAdapter",
    "SecretProvisionRequest",
    "SecretRollbackApproval",
    "SyntheticSecretBroker",
]
