"""Synthetic authenticated local protocol contract for Phase 8F Stage 1.

The module intentionally provides framing and authentication only. It creates no
socket, file, process, model, memory, runtime, or logging integration. Protocol
payloads are bounded non-secret string scalars. A secret can be named only by an
opaque reference and is never carried in an envelope.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any


SCHEMA_VERSION = 1
MAX_ENVELOPE_BYTES = 8_192
MAX_IDENTIFIER_LENGTH = 128
MAX_PAYLOAD_ENTRIES = 12
MAX_PAYLOAD_KEY_LENGTH = 48
MAX_PAYLOAD_VALUE_LENGTH = 256
MAX_PAYLOAD_BYTES = 1_024
NONCE_BYTES = 24
MIN_KEY_BYTES = 32
MAX_KEY_BYTES = 64
MAX_GRANT_VERSION = 2_147_483_647

AUTHENTICATION_FAILURE = "protocol authentication failed"
DECODE_FAILURE = "invalid protocol envelope"
VALIDATION_FAILURE = "invalid protocol request"
FRESHNESS_FAILURE = "protocol request outside freshness window"
CLOSED_FAILURE = "protocol authenticator is closed"

_AUTHENTICATION_DOMAIN = b"GRACI-PHASE8F-LOCAL-PROTOCOL-V1\x00"
_IDENTIFIER = re.compile(r"^[a-z0-9]+(?:[._:-][a-z0-9]+)*$")
_SYNTHETIC_DESTINATION = re.compile(
    r"\Asynthetic://notice/[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?\Z",
    re.ASCII,
)
_PAYLOAD_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_PAYLOAD_PARTS = frozenset(
    {
        "api",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "key",
        "password",
        "passwd",
        "private",
        "raw",
        "secret",
        "token",
    }
)
_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "grant_id",
        "grant_version",
        "expected_generation_id",
        "caller_id",
        "key_id",
        "adapter_id",
        "operation_id",
        "destination_id",
        "scope_id",
        "resource_id",
        "opaque_secret_ref",
        "issued_at",
        "nonce",
        "payload",
    }
)
_ENVELOPE_FIELDS = frozenset({"mac", "request"})


class ProtocolError(Exception):
    """Base class for fixed, non-echoing protocol failures."""


class ProtocolValidationError(ProtocolError):
    """Raised when trusted caller input violates the request contract."""


class ProtocolDecodeError(ProtocolError):
    """Raised when an envelope is malformed or non-canonical."""


class ProtocolAuthenticationError(ProtocolError):
    """Raised for every caller, key, or MAC authentication failure."""


class ProtocolFreshnessError(ProtocolError):
    """Raised when an authenticated request is stale or too far in the future."""


class ProtocolClosedError(ProtocolError):
    """Raised after an authenticator has discarded its key material."""


class _DuplicateKeyError(ValueError):
    pass


def _validation_error() -> ProtocolValidationError:
    return ProtocolValidationError(VALIDATION_FAILURE)


def _decode_error() -> ProtocolDecodeError:
    return ProtocolDecodeError(DECODE_FAILURE)


def _zero(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_non_json_constant(_value: str) -> None:
    raise ValueError


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _decode_error() from None


def _canonical_uuid(value: object) -> str:
    if type(value) is not str:
        raise _validation_error()
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError):
        raise _validation_error() from None
    if parsed.int == 0 or str(parsed) != value:
        raise _validation_error()
    return value


def _fixed_identifier(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > MAX_IDENTIFIER_LENGTH
        or _IDENTIFIER.fullmatch(value) is None
    ):
        raise _validation_error()
    return value


def _fixed_destination(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > MAX_IDENTIFIER_LENGTH
        or (
            _IDENTIFIER.fullmatch(value) is None
            and _SYNTHETIC_DESTINATION.fullmatch(value) is None
        )
    ):
        raise _validation_error()
    return value


def _utc_timestamp(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _validation_error()
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError):
        raise _validation_error() from None
    if offset is None:
        raise _validation_error()
    return value.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return _utc_timestamp(value).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _parse_timestamp(value: object) -> datetime:
    if type(value) is not str:
        raise _validation_error()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        raise _validation_error() from None
    parsed = _utc_timestamp(parsed)
    if _format_timestamp(parsed) != value:
        raise _validation_error()
    return parsed


def generate_nonce() -> str:
    """Return a fixed-size, cryptographically random URL-safe nonce."""

    return secrets.token_urlsafe(NONCE_BYTES)


def _validate_nonce(value: object) -> str:
    if type(value) is not str or len(value) != 32:
        raise _validation_error()
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
    except (binascii.Error, ValueError):
        raise _validation_error() from None
    if (
        len(decoded) != NONCE_BYTES
        or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value
    ):
        raise _validation_error()
    return value


def _payload_key_is_sensitive(key: str) -> bool:
    parts = frozenset(part for part in re.split(r"[._-]+", key) if part)
    return bool(parts & _SENSITIVE_PAYLOAD_PARTS)


def _freeze_payload(value: object) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > MAX_PAYLOAD_ENTRIES:
        raise _validation_error()
    payload: dict[str, str] = {}
    for key, item in value.items():
        if (
            type(key) is not str
            or not key
            or len(key) > MAX_PAYLOAD_KEY_LENGTH
            or _PAYLOAD_KEY.fullmatch(key) is None
            or _payload_key_is_sensitive(key)
            or type(item) is not str
            or len(item) > MAX_PAYLOAD_VALUE_LENGTH
            or any(ord(character) < 32 or ord(character) == 127 for character in item)
        ):
            raise _validation_error()
        payload[key] = item
    if len(_canonical_json(payload)) > MAX_PAYLOAD_BYTES:
        raise _validation_error()
    return MappingProxyType(payload)


@dataclass(frozen=True, slots=True)
class ProtocolRequest:
    """One authenticated, scope-bound request containing no raw secret value."""

    schema_version: int
    request_id: str
    grant_id: str
    grant_version: int
    expected_generation_id: str
    caller_id: str
    key_id: str
    adapter_id: str
    operation_id: str
    destination_id: str
    scope_id: str
    resource_id: str
    opaque_secret_ref: str
    issued_at: datetime
    nonce: str
    payload: Mapping[str, str]

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != SCHEMA_VERSION
        ):
            raise _validation_error()
        _canonical_uuid(self.request_id)
        _canonical_uuid(self.grant_id)
        if (
            type(self.grant_version) is not int
            or self.grant_version < 1
            or self.grant_version > MAX_GRANT_VERSION
        ):
            raise _validation_error()
        _canonical_uuid(self.expected_generation_id)
        for value in (
            self.caller_id,
            self.key_id,
            self.adapter_id,
            self.operation_id,
            self.scope_id,
            self.resource_id,
            self.opaque_secret_ref,
        ):
            _fixed_identifier(value)
        _fixed_destination(self.destination_id)
        object.__setattr__(self, "issued_at", _utc_timestamp(self.issued_at))
        _validate_nonce(self.nonce)
        object.__setattr__(self, "payload", _freeze_payload(self.payload))


def _request_object(request: ProtocolRequest) -> dict[str, Any]:
    if not isinstance(request, ProtocolRequest):
        raise _validation_error()
    return {
        "schema_version": request.schema_version,
        "request_id": request.request_id,
        "grant_id": request.grant_id,
        "grant_version": request.grant_version,
        "expected_generation_id": request.expected_generation_id,
        "caller_id": request.caller_id,
        "key_id": request.key_id,
        "adapter_id": request.adapter_id,
        "operation_id": request.operation_id,
        "destination_id": request.destination_id,
        "scope_id": request.scope_id,
        "resource_id": request.resource_id,
        "opaque_secret_ref": request.opaque_secret_ref,
        "issued_at": _format_timestamp(request.issued_at),
        "nonce": request.nonce,
        "payload": dict(request.payload),
    }


def _request_from_object(value: object) -> ProtocolRequest:
    if type(value) is not dict or frozenset(value) != _REQUEST_FIELDS:
        raise _validation_error()
    return ProtocolRequest(
        schema_version=value["schema_version"],
        request_id=value["request_id"],
        grant_id=value["grant_id"],
        grant_version=value["grant_version"],
        expected_generation_id=value["expected_generation_id"],
        caller_id=value["caller_id"],
        key_id=value["key_id"],
        adapter_id=value["adapter_id"],
        operation_id=value["operation_id"],
        destination_id=value["destination_id"],
        scope_id=value["scope_id"],
        resource_id=value["resource_id"],
        opaque_secret_ref=value["opaque_secret_ref"],
        issued_at=_parse_timestamp(value["issued_at"]),
        nonce=value["nonce"],
        payload=value["payload"],
    )


def request_digest(request: ProtocolRequest) -> str:
    """Return the SHA-256 digest of the exact canonical request body."""

    return hashlib.sha256(_canonical_json(_request_object(request))).hexdigest()


def validate_freshness(
    request: ProtocolRequest,
    *,
    now: datetime,
    max_age: timedelta = timedelta(minutes=2),
    max_future_skew: timedelta = timedelta(seconds=10),
) -> None:
    """Fail closed when an authenticated request falls outside its time window."""

    if not isinstance(request, ProtocolRequest):
        raise _validation_error()
    current = _utc_timestamp(now)
    if (
        not isinstance(max_age, timedelta)
        or not isinstance(max_future_skew, timedelta)
        or max_age <= timedelta(0)
        or max_future_skew < timedelta(0)
    ):
        raise _validation_error()
    if (
        request.issued_at < current - max_age
        or request.issued_at > current + max_future_skew
    ):
        raise ProtocolFreshnessError(FRESHNESS_FAILURE)


class AuthenticatedLocalProtocol:
    """Canonical HMAC-SHA256 framing for one fixed synthetic caller and key."""

    def __init__(
        self,
        *,
        caller_id: str,
        key_id: str,
        key_material: bytearray,
    ) -> None:
        if type(key_material) is not bytearray:
            raise TypeError("key_material must be a bytearray")
        owned_key = bytearray(key_material)
        _zero(key_material)
        try:
            self._caller_id = _fixed_identifier(caller_id)
            self._key_id = _fixed_identifier(key_id)
            if not MIN_KEY_BYTES <= len(owned_key) <= MAX_KEY_BYTES:
                raise _validation_error()
        except BaseException:
            _zero(owned_key)
            raise
        self._key = owned_key
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def caller_id(self) -> str:
        return self._caller_id

    @property
    def key_id(self) -> str:
        return self._key_id

    def _require_open(self) -> None:
        if self._closed:
            raise ProtocolClosedError(CLOSED_FAILURE)

    def _mac(self, request_bytes: bytes) -> str:
        self._require_open()
        return hmac.new(
            self._key,
            _AUTHENTICATION_DOMAIN + request_bytes,
            hashlib.sha256,
        ).hexdigest()

    def encode(self, request: ProtocolRequest) -> bytes:
        """Encode and authenticate one request for this exact caller and key."""

        self._require_open()
        if not isinstance(request, ProtocolRequest):
            raise _validation_error()
        if request.caller_id != self._caller_id or request.key_id != self._key_id:
            raise ProtocolAuthenticationError(AUTHENTICATION_FAILURE)
        request_object = _request_object(request)
        request_bytes = _canonical_json(request_object)
        envelope = {
            "mac": self._mac(request_bytes),
            "request": request_object,
        }
        encoded = _canonical_json(envelope)
        if len(encoded) > MAX_ENVELOPE_BYTES:
            raise _validation_error()
        return encoded

    def decode(self, encoded: bytes | bytearray) -> ProtocolRequest:
        """Strictly decode and authenticate a canonical protocol envelope."""

        self._require_open()
        if type(encoded) not in (bytes, bytearray):
            raise _decode_error()
        wire = bytes(encoded)
        if not wire or len(wire) > MAX_ENVELOPE_BYTES:
            raise _decode_error()
        try:
            text = wire.decode("utf-8", errors="strict")
            envelope = json.loads(
                text,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_non_json_constant,
            )
        except (UnicodeError, json.JSONDecodeError, _DuplicateKeyError, ValueError):
            raise _decode_error() from None
        if type(envelope) is not dict or frozenset(envelope) != _ENVELOPE_FIELDS:
            raise _decode_error()
        if _canonical_json(envelope) != wire:
            raise _decode_error()
        request_object = envelope["request"]
        if (
            type(request_object) is not dict
            or frozenset(request_object) != _REQUEST_FIELDS
        ):
            raise _decode_error()
        request_bytes = _canonical_json(request_object)
        candidate_mac = envelope["mac"]
        mac_shape_ok = (
            type(candidate_mac) is str
            and _LOWER_HEX_SHA256.fullmatch(candidate_mac) is not None
        )
        comparable_mac = candidate_mac if mac_shape_ok else "0" * 64
        mac_ok = hmac.compare_digest(comparable_mac, self._mac(request_bytes))
        caller_ok = _constant_text_equal(request_object.get("caller_id"), self._caller_id)
        key_ok = _constant_text_equal(request_object.get("key_id"), self._key_id)
        if not (mac_shape_ok and mac_ok and caller_ok and key_ok):
            raise ProtocolAuthenticationError(AUTHENTICATION_FAILURE)
        try:
            return _request_from_object(request_object)
        except ProtocolValidationError:
            raise ProtocolDecodeError(DECODE_FAILURE) from None

    def close(self) -> None:
        """Best-effort zero the authenticator-owned synthetic key buffer."""

        if not self._closed:
            _zero(self._key)
            self._closed = True

    def __enter__(self) -> AuthenticatedLocalProtocol:
        self._require_open()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass


def _constant_text_equal(candidate: object, expected: str) -> bool:
    if type(candidate) is not str:
        candidate_bytes = b""
    else:
        try:
            candidate_bytes = candidate.encode("utf-8", errors="strict")
        except UnicodeError:
            candidate_bytes = b""
    return hmac.compare_digest(candidate_bytes, expected.encode("utf-8"))


__all__ = [
    "AUTHENTICATION_FAILURE",
    "AuthenticatedLocalProtocol",
    "CLOSED_FAILURE",
    "DECODE_FAILURE",
    "FRESHNESS_FAILURE",
    "ProtocolAuthenticationError",
    "ProtocolClosedError",
    "ProtocolDecodeError",
    "ProtocolError",
    "ProtocolFreshnessError",
    "ProtocolRequest",
    "ProtocolValidationError",
    "SCHEMA_VERSION",
    "VALIDATION_FAILURE",
    "generate_nonce",
    "request_digest",
    "validate_freshness",
]
