"""Windows CNG authenticated encryption for the synthetic Phase 8F boundary.

The backend accepts key and plaintext material only through mutable buffers so the
caller-visible buffers and native plaintext copies can be cleared best-effort. It
does not persist keys, expose plaintext bytes, log values, or provide a fallback
when Windows CNG is unavailable.
"""

from __future__ import annotations

import base64
import binascii
import ctypes
import os
import re
import secrets
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping


ALGORITHM = "AES-256-GCM"
BLOB_SCHEMA_VERSION = 1
KEY_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_SECRET_BYTES = 65_536
MAX_AAD_BYTES = 65_536

_AES_ALGORITHM = "AES"
_CHAINING_MODE = "ChainingMode"
_CHAIN_MODE_GCM = "ChainingModeGCM"
_OBJECT_LENGTH = "ObjectLength"
_AUTH_TAG_LENGTH = "AuthTagLength"
_AUTH_MODE_INFO_VERSION = 1
_USE_SYSTEM_PREFERRED_RNG = 0x00000002
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_B64 = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")

_UCHAR = ctypes.c_ubyte
_ULONG = ctypes.c_uint32
_ULONGLONG = ctypes.c_uint64
_NTSTATUS = ctypes.c_int32
_HANDLE = ctypes.c_void_p


class _AuthenticatedCipherModeInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", _ULONG),
        ("dwInfoVersion", _ULONG),
        ("pbNonce", ctypes.c_void_p),
        ("cbNonce", _ULONG),
        ("pbAuthData", ctypes.c_void_p),
        ("cbAuthData", _ULONG),
        ("pbTag", ctypes.c_void_p),
        ("cbTag", _ULONG),
        ("pbMacContext", ctypes.c_void_p),
        ("cbMacContext", _ULONG),
        ("cbAAD", _ULONG),
        ("cbData", _ULONGLONG),
        ("dwFlags", _ULONG),
    ]


class _KeyLengths(ctypes.Structure):
    _fields_ = [
        ("dwMinLength", _ULONG),
        ("dwMaxLength", _ULONG),
        ("dwIncrement", _ULONG),
    ]


_ERROR_MESSAGES = {
    "BACKEND_UNAVAILABLE": "Windows authenticated encryption is unavailable",
    "BACKEND_CLOSED": "authenticated encryption backend is closed",
    "INVALID_KEY": "authenticated encryption key configuration is invalid",
    "INVALID_AAD": "authenticated encryption associated data is invalid",
    "INVALID_PLAINTEXT": "authenticated encryption plaintext input is invalid",
    "INVALID_BLOB": "protected value is invalid",
    "NONCE_FAILURE": "authenticated encryption nonce generation failed",
    "NONCE_REUSE": "authenticated encryption nonce reuse was rejected",
    "AUTHENTICATION_FAILED": "protected value authentication failed",
    "CRYPTO_FAILURE": "authenticated encryption operation failed",
    "SECRET_BUFFER_CLOSED": "secret buffer is closed",
}


class CryptoError(RuntimeError):
    """A fixed, non-echoing cryptographic failure."""

    def __init__(self, code: str):
        if code not in _ERROR_MESSAGES:
            code = "CRYPTO_FAILURE"
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


def _wipe_bytearray(value: bytearray) -> None:
    try:
        for index in range(len(value)):
            value[index] = 0
    except Exception:
        pass


def _wipe_ctypes(value: Any) -> None:
    if value is None:
        return
    try:
        ctypes.memset(ctypes.addressof(value), 0, ctypes.sizeof(value))
    except Exception:
        pass


def _validate_key_id(value: Any) -> str:
    if not isinstance(value, str) or not _KEY_ID.fullmatch(value):
        raise CryptoError("INVALID_KEY")
    return value


def _validate_aad(value: Any) -> bytes:
    if type(value) is not bytes or not 1 <= len(value) <= MAX_AAD_BYTES:
        raise CryptoError("INVALID_AAD")
    return value


def _decode_b64(value: Any, expected_size: int | None = None) -> bytes:
    if (not isinstance(value, str) or len(value) > ((MAX_SECRET_BYTES + 2) // 3) * 4 + 8
            or not _B64.fullmatch(value)):
        raise CryptoError("INVALID_BLOB")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError, UnicodeError):
        raise CryptoError("INVALID_BLOB") from None
    if base64.b64encode(decoded).decode("ascii") != value:
        raise CryptoError("INVALID_BLOB")
    if expected_size is not None and len(decoded) != expected_size:
        raise CryptoError("INVALID_BLOB")
    return decoded


@dataclass(frozen=True, repr=False)
class ProtectedBlob:
    """One strict AES-GCM envelope containing no plaintext metadata."""

    schema_version: int
    algorithm: str
    key_id: str
    nonce: bytes
    ciphertext: bytes
    tag: bytes

    def __post_init__(self) -> None:
        if (type(self.schema_version) is not int or
                self.schema_version != BLOB_SCHEMA_VERSION or
                self.algorithm != ALGORITHM or
                not isinstance(self.key_id, str) or not _KEY_ID.fullmatch(self.key_id) or
                type(self.nonce) is not bytes or len(self.nonce) != NONCE_BYTES or
                type(self.ciphertext) is not bytes or
                len(self.ciphertext) > MAX_SECRET_BYTES or
                type(self.tag) is not bytes or len(self.tag) != TAG_BYTES):
            raise CryptoError("INVALID_BLOB")

    @property
    def metadata(self) -> dict[str, str]:
        return {"algorithm": self.algorithm, "key_id": self.key_id}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "nonce": base64.b64encode(self.nonce).decode("ascii"),
            "ciphertext": base64.b64encode(self.ciphertext).decode("ascii"),
            "tag": base64.b64encode(self.tag).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProtectedBlob":
        expected = {"schema_version", "algorithm", "key_id", "nonce", "ciphertext", "tag"}
        try:
            if not isinstance(value, Mapping) or set(value) != expected:
                raise CryptoError("INVALID_BLOB")
            return cls(
                schema_version=value["schema_version"],
                algorithm=value["algorithm"],
                key_id=value["key_id"],
                nonce=_decode_b64(value["nonce"], NONCE_BYTES),
                ciphertext=_decode_b64(value["ciphertext"]),
                tag=_decode_b64(value["tag"], TAG_BYTES),
            )
        except CryptoError:
            raise
        except Exception:
            raise CryptoError("INVALID_BLOB") from None

    def __repr__(self) -> str:
        return f"<ProtectedBlob algorithm={self.algorithm!r} key_id={self.key_id!r}>"

    __str__ = __repr__


_SECRET_BUFFER_TOKEN = object()


class SecretBuffer:
    """Mutable, redacted plaintext storage with explicit best-effort clearing."""

    __slots__ = ("_data", "_closed")

    def __init__(self, data: bytearray, *, _token: object):
        if _token is not _SECRET_BUFFER_TOKEN or type(data) is not bytearray:
            raise CryptoError("CRYPTO_FAILURE")
        self._data = data
        self._closed = False

    @classmethod
    def _take(cls, data: bytearray) -> "SecretBuffer":
        return cls(data, _token=_SECRET_BUFFER_TOKEN)

    @property
    def closed(self) -> bool:
        return self._closed

    def view(self) -> memoryview:
        if self._closed:
            raise CryptoError("SECRET_BUFFER_CLOSED")
        return memoryview(self._data)

    def close(self) -> None:
        if self._closed:
            return
        _wipe_bytearray(self._data)
        self._closed = True

    def __enter__(self) -> "SecretBuffer":
        if self._closed:
            raise CryptoError("SECRET_BUFFER_CLOSED")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return "<SecretBuffer redacted>"

    __str__ = __repr__

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


NonceFactory = Callable[[int], bytes | bytearray]


class WindowsCngAesGcm:
    """A single-key Windows CNG AES-256-GCM boundary."""

    def __init__(self, key: bytearray, *, key_id: str,
                 nonce_factory: NonceFactory | None = None):
        self._lock = threading.RLock()
        self._bcrypt: Any = None
        self._algorithm_handle = _HANDLE()
        self._key_handle = _HANDLE()
        self._key_object = bytearray()
        self._seen_nonces: set[bytes] = set()
        self._nonce_factory = nonce_factory
        self._closed = False
        key_copy = bytearray()
        try:
            if not isinstance(key, bytearray):
                raise CryptoError("INVALID_KEY")
            key_copy = bytearray(key)
            _wipe_bytearray(key)
            if len(key_copy) != KEY_BYTES:
                raise CryptoError("INVALID_KEY")
            self._key_id = _validate_key_id(key_id)
            self._initialize(key_copy)
        except CryptoError:
            self._release_native()
            self._closed = True
            raise
        except Exception:
            self._release_native()
            self._closed = True
            raise CryptoError("BACKEND_UNAVAILABLE") from None
        finally:
            if isinstance(key, bytearray):
                _wipe_bytearray(key)
            _wipe_bytearray(key_copy)

    @property
    def algorithm(self) -> str:
        return ALGORITHM

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def metadata(self) -> dict[str, str]:
        return {"algorithm": ALGORITHM, "key_id": self._key_id}

    def _initialize(self, key: bytearray) -> None:
        if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
            raise CryptoError("BACKEND_UNAVAILABLE")
        try:
            self._bcrypt = ctypes.WinDLL("bcrypt.dll", use_last_error=True)
            _configure_bcrypt(self._bcrypt)
        except Exception:
            raise CryptoError("BACKEND_UNAVAILABLE") from None

        algorithm = _HANDLE()
        if self._bcrypt.BCryptOpenAlgorithmProvider(
                ctypes.byref(algorithm), _AES_ALGORITHM, None, 0) != 0:
            raise CryptoError("BACKEND_UNAVAILABLE")
        self._algorithm_handle = algorithm

        chaining_mode = ctypes.create_unicode_buffer(_CHAIN_MODE_GCM)
        if self._bcrypt.BCryptSetProperty(
                self._algorithm_handle, _CHAINING_MODE,
                ctypes.addressof(chaining_mode), ctypes.sizeof(chaining_mode), 0) != 0:
            raise CryptoError("BACKEND_UNAVAILABLE")

        object_length = self._get_ulong_property(_OBJECT_LENGTH)
        if not 1 <= object_length <= 1_048_576:
            raise CryptoError("BACKEND_UNAVAILABLE")
        tag_lengths = self._get_tag_lengths()
        increment = tag_lengths.dwIncrement
        if (not tag_lengths.dwMinLength <= TAG_BYTES <= tag_lengths.dwMaxLength or
                (increment and (TAG_BYTES - tag_lengths.dwMinLength) % increment)):
            raise CryptoError("BACKEND_UNAVAILABLE")

        self._key_object = bytearray(object_length)
        key_object_buffer = (_UCHAR * object_length).from_buffer(self._key_object)
        key_material_buffer = (_UCHAR * len(key)).from_buffer(key)
        generated_key = _HANDLE()
        if self._bcrypt.BCryptGenerateSymmetricKey(
                self._algorithm_handle, ctypes.byref(generated_key),
                ctypes.addressof(key_object_buffer), object_length,
                ctypes.addressof(key_material_buffer), len(key), 0) != 0:
            raise CryptoError("BACKEND_UNAVAILABLE")
        self._key_handle = generated_key

    def _get_ulong_property(self, name: str) -> int:
        value = _ULONG()
        written = _ULONG()
        if (self._bcrypt.BCryptGetProperty(
                self._algorithm_handle, name, ctypes.byref(value), ctypes.sizeof(value),
                ctypes.byref(written), 0) != 0 or written.value != ctypes.sizeof(value)):
            raise CryptoError("BACKEND_UNAVAILABLE")
        return int(value.value)

    def _get_tag_lengths(self) -> _KeyLengths:
        value = _KeyLengths()
        written = _ULONG()
        if (self._bcrypt.BCryptGetProperty(
                self._algorithm_handle, _AUTH_TAG_LENGTH, ctypes.byref(value),
                ctypes.sizeof(value), ctypes.byref(written), 0) != 0 or
                written.value != ctypes.sizeof(value)):
            raise CryptoError("BACKEND_UNAVAILABLE")
        return value

    def protect(self, plaintext: bytearray, aad: bytes) -> ProtectedBlob:
        if not isinstance(plaintext, bytearray):
            raise CryptoError("INVALID_PLAINTEXT")
        native_plaintext: Any = None
        native_ciphertext: Any = None
        try:
            canonical_aad = _validate_aad(aad)
            if len(plaintext) > MAX_SECRET_BYTES:
                raise CryptoError("INVALID_PLAINTEXT")
            with self._lock:
                self._ensure_open()
                nonce = self._next_nonce()
                native_plaintext = (_UCHAR * max(1, len(plaintext)))()
                if plaintext:
                    source = (_UCHAR * len(plaintext)).from_buffer(plaintext)
                    ctypes.memmove(native_plaintext, source, len(plaintext))
                    _wipe_bytearray(plaintext)
                native_ciphertext = (_UCHAR * max(1, len(plaintext)))()
                nonce_buffer = (_UCHAR * NONCE_BYTES).from_buffer_copy(nonce)
                aad_buffer = (_UCHAR * len(canonical_aad)).from_buffer_copy(canonical_aad)
                tag_buffer = (_UCHAR * TAG_BYTES)()
                auth_info = _auth_info(nonce_buffer, aad_buffer, tag_buffer)
                written = _ULONG()
                status = self._bcrypt.BCryptEncrypt(
                    self._key_handle,
                    ctypes.addressof(native_plaintext) if plaintext else None,
                    len(plaintext), ctypes.byref(auth_info), None, 0,
                    ctypes.addressof(native_ciphertext) if plaintext else None,
                    len(plaintext), ctypes.byref(written), 0,
                )
                if status != 0 or written.value != len(plaintext):
                    raise CryptoError("CRYPTO_FAILURE")
                ciphertext = bytes(native_ciphertext[:len(plaintext)])
                tag = bytes(tag_buffer)
                return ProtectedBlob(BLOB_SCHEMA_VERSION, ALGORITHM, self._key_id,
                                     nonce, ciphertext, tag)
        except CryptoError:
            raise
        except Exception:
            raise CryptoError("CRYPTO_FAILURE") from None
        finally:
            _wipe_ctypes(native_plaintext)
            _wipe_ctypes(native_ciphertext)
            _wipe_bytearray(plaintext)

    def unprotect(self, blob: ProtectedBlob | Mapping[str, Any], aad: bytes) -> SecretBuffer:
        native_plaintext: Any = None
        native_ciphertext: Any = None
        try:
            canonical_aad = _validate_aad(aad)
            protected = _coerce_blob(blob)
            with self._lock:
                self._ensure_open()
                if not secrets.compare_digest(protected.key_id, self._key_id):
                    raise CryptoError("AUTHENTICATION_FAILED")
                native_ciphertext = (_UCHAR * max(1, len(protected.ciphertext)))()
                if protected.ciphertext:
                    source = (_UCHAR * len(protected.ciphertext)).from_buffer_copy(
                        protected.ciphertext
                    )
                    ctypes.memmove(native_ciphertext, source, len(protected.ciphertext))
                native_plaintext = (_UCHAR * max(1, len(protected.ciphertext)))()
                nonce_buffer = (_UCHAR * NONCE_BYTES).from_buffer_copy(protected.nonce)
                aad_buffer = (_UCHAR * len(canonical_aad)).from_buffer_copy(canonical_aad)
                tag_buffer = (_UCHAR * TAG_BYTES).from_buffer_copy(protected.tag)
                auth_info = _auth_info(nonce_buffer, aad_buffer, tag_buffer)
                written = _ULONG()
                status = self._bcrypt.BCryptDecrypt(
                    self._key_handle,
                    ctypes.addressof(native_ciphertext) if protected.ciphertext else None,
                    len(protected.ciphertext), ctypes.byref(auth_info), None, 0,
                    ctypes.addressof(native_plaintext) if protected.ciphertext else None,
                    len(protected.ciphertext), ctypes.byref(written), 0,
                )
                if status != 0 or written.value != len(protected.ciphertext):
                    raise CryptoError("AUTHENTICATION_FAILED")
                owned = bytearray(len(protected.ciphertext))
                transferred = False
                try:
                    if owned:
                        destination = (_UCHAR * len(owned)).from_buffer(owned)
                        ctypes.memmove(destination, native_plaintext, len(owned))
                    secret = SecretBuffer._take(owned)
                    transferred = True
                    return secret
                finally:
                    if not transferred:
                        _wipe_bytearray(owned)
        except CryptoError:
            raise
        except Exception:
            raise CryptoError("AUTHENTICATION_FAILED") from None
        finally:
            _wipe_ctypes(native_plaintext)
            _wipe_ctypes(native_ciphertext)

    def _next_nonce(self) -> bytes:
        try:
            if self._nonce_factory is not None:
                generated = self._nonce_factory(NONCE_BYTES)
                if type(generated) not in {bytes, bytearray} or len(generated) != NONCE_BYTES:
                    raise CryptoError("NONCE_FAILURE")
                nonce = bytes(generated)
            else:
                buffer = (_UCHAR * NONCE_BYTES)()
                if self._bcrypt.BCryptGenRandom(
                        None, buffer, NONCE_BYTES, _USE_SYSTEM_PREFERRED_RNG) != 0:
                    raise CryptoError("NONCE_FAILURE")
                nonce = bytes(buffer)
        except CryptoError:
            raise
        except Exception:
            raise CryptoError("NONCE_FAILURE") from None
        if nonce in self._seen_nonces:
            raise CryptoError("NONCE_REUSE")
        self._seen_nonces.add(nonce)
        return nonce

    def _ensure_open(self) -> None:
        if self._closed or not self._key_handle.value or not self._algorithm_handle.value:
            raise CryptoError("BACKEND_CLOSED")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._release_native()
            self._closed = True

    def _release_native(self) -> None:
        bcrypt = self._bcrypt
        key_handle = self._key_handle
        algorithm_handle = self._algorithm_handle
        self._key_handle = _HANDLE()
        self._algorithm_handle = _HANDLE()
        if bcrypt is not None and key_handle.value:
            try:
                bcrypt.BCryptDestroyKey(key_handle)
            except Exception:
                pass
        if bcrypt is not None and algorithm_handle.value:
            try:
                bcrypt.BCryptCloseAlgorithmProvider(algorithm_handle, 0)
            except Exception:
                pass
        _wipe_bytearray(self._key_object)
        self._key_object = bytearray()
        self._seen_nonces.clear()

    def __enter__(self) -> "WindowsCngAesGcm":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _coerce_blob(value: ProtectedBlob | Mapping[str, Any]) -> ProtectedBlob:
    if isinstance(value, ProtectedBlob):
        try:
            return ProtectedBlob(value.schema_version, value.algorithm, value.key_id,
                                 value.nonce, value.ciphertext, value.tag)
        except CryptoError:
            raise
        except Exception:
            raise CryptoError("INVALID_BLOB") from None
    return ProtectedBlob.from_dict(value)


def _auth_info(nonce: Any, aad: Any, tag: Any) -> _AuthenticatedCipherModeInfo:
    value = _AuthenticatedCipherModeInfo()
    value.cbSize = ctypes.sizeof(_AuthenticatedCipherModeInfo)
    value.dwInfoVersion = _AUTH_MODE_INFO_VERSION
    value.pbNonce = ctypes.addressof(nonce)
    value.cbNonce = NONCE_BYTES
    value.pbAuthData = ctypes.addressof(aad)
    value.cbAuthData = ctypes.sizeof(aad)
    value.pbTag = ctypes.addressof(tag)
    value.cbTag = TAG_BYTES
    return value


def _configure_bcrypt(bcrypt: Any) -> None:
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(_HANDLE), ctypes.c_wchar_p, ctypes.c_wchar_p, _ULONG,
    ]
    bcrypt.BCryptOpenAlgorithmProvider.restype = _NTSTATUS
    bcrypt.BCryptSetProperty.argtypes = [
        _HANDLE, ctypes.c_wchar_p, ctypes.c_void_p, _ULONG, _ULONG,
    ]
    bcrypt.BCryptSetProperty.restype = _NTSTATUS
    bcrypt.BCryptGetProperty.argtypes = [
        _HANDLE, ctypes.c_wchar_p, ctypes.c_void_p, _ULONG,
        ctypes.POINTER(_ULONG), _ULONG,
    ]
    bcrypt.BCryptGetProperty.restype = _NTSTATUS
    bcrypt.BCryptGenerateSymmetricKey.argtypes = [
        _HANDLE, ctypes.POINTER(_HANDLE), ctypes.c_void_p, _ULONG,
        ctypes.c_void_p, _ULONG, _ULONG,
    ]
    bcrypt.BCryptGenerateSymmetricKey.restype = _NTSTATUS
    operation_args = [
        _HANDLE, ctypes.c_void_p, _ULONG, ctypes.c_void_p,
        ctypes.c_void_p, _ULONG, ctypes.c_void_p, _ULONG,
        ctypes.POINTER(_ULONG), _ULONG,
    ]
    bcrypt.BCryptEncrypt.argtypes = operation_args
    bcrypt.BCryptEncrypt.restype = _NTSTATUS
    bcrypt.BCryptDecrypt.argtypes = operation_args
    bcrypt.BCryptDecrypt.restype = _NTSTATUS
    bcrypt.BCryptGenRandom.argtypes = [
        _HANDLE, ctypes.c_void_p, _ULONG, _ULONG,
    ]
    bcrypt.BCryptGenRandom.restype = _NTSTATUS
    bcrypt.BCryptDestroyKey.argtypes = [_HANDLE]
    bcrypt.BCryptDestroyKey.restype = _NTSTATUS
    bcrypt.BCryptCloseAlgorithmProvider.argtypes = [_HANDLE, _ULONG]
    bcrypt.BCryptCloseAlgorithmProvider.restype = _NTSTATUS
