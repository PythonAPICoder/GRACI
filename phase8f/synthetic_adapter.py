"""Isolated synthetic adapter for one secret-bearing notice operation.

The adapter has no transport, file, model, memory, resident, or ordinary-runtime
dependency. Secret material is accepted only through an owned mutable wrapper and
is never part of an outcome, receipt, recorded call, exception, or representation.
"""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable
from uuid import UUID


NOTICE_DELIVER_OPERATION = "synthetic.notice.deliver"
MAX_SECRET_BYTES = 4_096

_DESTINATION = re.compile(
    r"\Asynthetic://notice/[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?\Z",
    re.ASCII,
)


class SecretMaterialError(RuntimeError):
    """A fixed, non-echoing secret-material boundary failure."""


class AdapterCode(str, Enum):
    DELIVERED = "DELIVERED"
    REQUEST_DENIED = "REQUEST_DENIED"
    OPERATION_DENIED = "OPERATION_DENIED"
    DESTINATION_DENIED = "DESTINATION_DENIED"
    SCOPE_DENIED = "SCOPE_DENIED"
    PAYLOAD_DENIED = "PAYLOAD_DENIED"
    SECRET_DENIED = "SECRET_DENIED"
    ADAPTER_CLOSED = "ADAPTER_CLOSED"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"
    ADAPTER_PROTOCOL_ERROR = "ADAPTER_PROTOCOL_ERROR"


class SecretMaterial:
    """Own mutable secret bytes and erase the owned buffer on close.

    The caller transfers ownership of ``material``. Closing this object therefore
    also clears the caller's original bytearray. Python and operating-system copies
    outside this buffer cannot be guaranteed erased.
    """

    __slots__ = ("_buffer", "_closed")

    def __init__(self, material: bytearray):
        if (type(material) is not bytearray or not material or
                len(material) > MAX_SECRET_BYTES):
            raise SecretMaterialError("secret material is unavailable")
        self._buffer = material
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def _view(self) -> memoryview:
        if self._closed:
            raise SecretMaterialError("secret material is unavailable")
        return memoryview(self._buffer).toreadonly()

    def close(self) -> None:
        if self._closed:
            return
        for index in range(len(self._buffer)):
            self._buffer[index] = 0
        self._closed = True

    def __enter__(self) -> "SecretMaterial":
        if self._closed:
            raise SecretMaterialError("secret material is unavailable")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass

    def __repr__(self) -> str:
        return f"SecretMaterial(<redacted>, closed={self._closed})"

    __str__ = __repr__


@dataclass(frozen=True, repr=False, slots=True)
class SyntheticAdapterRequest:
    request_id: str
    operation: str
    destination: str
    resource_id: str
    payload: Mapping[str, object]

    def __repr__(self) -> str:
        return "SyntheticAdapterRequest(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False, slots=True)
class SyntheticNoticeReceipt:
    request_id: str
    notice_id: str

    def __post_init__(self) -> None:
        if (_canonical_uuid(self.request_id) is None or
                _canonical_uuid(self.notice_id) is None):
            raise ValueError("receipt identifiers are invalid")

    def __repr__(self) -> str:
        return (
            "SyntheticNoticeReceipt("
            f"request_id={self.request_id!r}, notice_id={self.notice_id!r})"
        )

    __str__ = __repr__


@dataclass(frozen=True, repr=False, slots=True)
class AdapterOutcome:
    code: AdapterCode
    receipt: SyntheticNoticeReceipt | None = None

    def __repr__(self) -> str:
        code = self.code.value if type(self.code) is AdapterCode else "INVALID"
        receipt = repr(self.receipt) if type(self.receipt) is SyntheticNoticeReceipt else None
        return f"AdapterOutcome(code={code!r}, receipt={receipt})"

    __str__ = __repr__


@runtime_checkable
class SyntheticSecretAdapter(Protocol):
    """Narrow protocol implemented by synthetic secret-consuming adapters."""

    def execute(
        self,
        request: SyntheticAdapterRequest,
        secret: SecretMaterial,
    ) -> AdapterOutcome:
        """Execute one request without exposing secret material."""


class SyntheticNoticeAdapter:
    """Fake destination adapter for exactly one configured notice capability."""

    __slots__ = (
        "_destination",
        "_resource_id",
        "_expected_secret",
        "_receipts",
        "_closed",
    )

    def __init__(
        self,
        *,
        destination: str,
        resource_id: str,
        expected_secret: bytearray,
    ):
        owned_secret = SecretMaterial(expected_secret)
        try:
            if type(destination) is not str or _DESTINATION.fullmatch(destination) is None:
                raise ValueError("synthetic notice destination is invalid")
            if _canonical_uuid(resource_id) is None:
                raise ValueError("synthetic notice resource is invalid")
        except Exception:
            owned_secret.close()
            raise
        self._destination = destination
        self._resource_id = resource_id
        self._expected_secret = owned_secret
        self._receipts: list[SyntheticNoticeReceipt] = []
        self._closed = False

    @property
    def recorded_calls(self) -> tuple[SyntheticNoticeReceipt, ...]:
        return tuple(self._receipts)

    @property
    def destination(self) -> str:
        return self._destination

    @property
    def resource_id(self) -> str:
        return self._resource_id

    def execute(
        self,
        request: SyntheticAdapterRequest,
        secret: SecretMaterial,
    ) -> AdapterOutcome:
        if self._closed:
            return AdapterOutcome(AdapterCode.ADAPTER_CLOSED)
        if type(request) is not SyntheticAdapterRequest:
            return AdapterOutcome(AdapterCode.REQUEST_DENIED)
        if _canonical_uuid(request.request_id) is None:
            return AdapterOutcome(AdapterCode.REQUEST_DENIED)
        if request.operation != NOTICE_DELIVER_OPERATION:
            return AdapterOutcome(AdapterCode.OPERATION_DENIED)
        if request.destination != self._destination:
            return AdapterOutcome(AdapterCode.DESTINATION_DENIED)
        if request.resource_id != self._resource_id:
            return AdapterOutcome(AdapterCode.SCOPE_DENIED)
        notice_id = _validated_notice_id(request.payload)
        if notice_id is None:
            return AdapterOutcome(AdapterCode.PAYLOAD_DENIED)
        if type(secret) is not SecretMaterial or secret.closed:
            return AdapterOutcome(AdapterCode.SECRET_DENIED)

        supplied_view: memoryview | None = None
        expected_view: memoryview | None = None
        try:
            supplied_view = secret._view()
            expected_view = self._expected_secret._view()
            matches = hmac.compare_digest(supplied_view, expected_view)
        except (SecretMaterialError, TypeError, ValueError):
            return AdapterOutcome(AdapterCode.SECRET_DENIED)
        finally:
            if supplied_view is not None:
                supplied_view.release()
            if expected_view is not None:
                expected_view.release()
        if not matches:
            return AdapterOutcome(AdapterCode.SECRET_DENIED)

        receipt = SyntheticNoticeReceipt(request.request_id, notice_id)
        self._receipts.append(receipt)
        return AdapterOutcome(AdapterCode.DELIVERED, receipt)

    def close(self) -> None:
        if self._closed:
            return
        self._expected_secret.close()
        self._closed = True

    def __enter__(self) -> "SyntheticNoticeAdapter":
        if self._closed:
            raise RuntimeError("synthetic adapter is closed")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"SyntheticNoticeAdapter(closed={self._closed})"

    __str__ = __repr__


def execute_synthetic_adapter(
    adapter: SyntheticSecretAdapter,
    request: SyntheticAdapterRequest,
    secret: SecretMaterial,
) -> AdapterOutcome:
    """Invoke an adapter, sanitize its result, and always close supplied material."""

    if type(secret) is not SecretMaterial:
        return AdapterOutcome(AdapterCode.SECRET_DENIED)
    try:
        try:
            outcome = adapter.execute(request, secret)
        except Exception:
            return AdapterOutcome(AdapterCode.ADAPTER_FAILURE)
        return _sanitize_outcome(outcome, request)
    finally:
        try:
            secret.close()
        except Exception:
            pass


def _sanitize_outcome(outcome: object, request: object) -> AdapterOutcome:
    if type(outcome) is not AdapterOutcome or type(outcome.code) is not AdapterCode:
        return AdapterOutcome(AdapterCode.ADAPTER_PROTOCOL_ERROR)
    if outcome.code is AdapterCode.DELIVERED:
        if (type(request) is not SyntheticAdapterRequest or
                type(outcome.receipt) is not SyntheticNoticeReceipt):
            return AdapterOutcome(AdapterCode.ADAPTER_PROTOCOL_ERROR)
        notice_id = _validated_notice_id(request.payload)
        if (notice_id is None or
                outcome.receipt.request_id != request.request_id or
                outcome.receipt.notice_id != notice_id):
            return AdapterOutcome(AdapterCode.ADAPTER_PROTOCOL_ERROR)
        return outcome
    if outcome.receipt is not None:
        return AdapterOutcome(AdapterCode.ADAPTER_PROTOCOL_ERROR)
    return outcome


def _canonical_uuid(value: object) -> str | None:
    if type(value) is not str or len(value) != 36:
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    canonical = str(parsed)
    return canonical if canonical == value else None


def _validated_notice_id(payload: object) -> str | None:
    if type(payload) is not dict or len(payload) != 1 or set(payload) != {"notice_id"}:
        return None
    return _canonical_uuid(payload.get("notice_id"))
