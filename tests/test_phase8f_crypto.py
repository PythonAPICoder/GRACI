"""Focused tests for the isolated Phase 8F Windows CNG boundary."""

import ast
import json
import secrets
import unittest
from dataclasses import replace
from pathlib import Path

from phase8f.crypto import (ALGORITHM, CryptoError, ProtectedBlob,
                            WindowsCngAesGcm)


def wipe(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


class WindowsCngAesGcmTests(unittest.TestCase):
    def setUp(self):
        key = bytearray(secrets.token_bytes(32))
        self.backend = WindowsCngAesGcm(key, key_id="synthetic-key-v1")
        self.assertTrue(all(value == 0 for value in key))
        self.aad = json.dumps(
            {"purpose": "phase8f.synthetic", "schema_version": 1},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")

    def tearDown(self):
        self.backend.close()

    def protected(self) -> tuple[ProtectedBlob, bytearray]:
        plaintext = bytearray(secrets.token_bytes(64))
        expected = bytearray(plaintext)
        blob = self.backend.protect(plaintext, self.aad)
        self.assertTrue(all(value == 0 for value in plaintext))
        return blob, expected

    def test_round_trip_uses_redacted_mutable_secret_buffer(self):
        blob, expected = self.protected()
        try:
            serialized = json.dumps(blob.to_dict(), sort_keys=True).encode("utf-8")
            self.assertEqual(serialized.find(expected), -1)
            self.assertEqual(blob.metadata, {
                "algorithm": ALGORITHM, "key_id": "synthetic-key-v1",
            })
            with self.backend.unprotect(blob.to_dict(), self.aad) as secret:
                self.assertEqual(str(secret), "<SecretBuffer redacted>")
                self.assertEqual(repr(secret), "<SecretBuffer redacted>")
                with secret.view() as view:
                    self.assertTrue(secrets.compare_digest(view, expected))
            self.assertTrue(secret.closed)
            with self.assertRaisesRegex(CryptoError, "secret buffer is closed"):
                secret.view()
        finally:
            wipe(expected)

    def test_ciphertext_tag_nonce_and_aad_tampering_fail_without_echo(self):
        blob, expected = self.protected()
        try:
            changes = []
            ciphertext = bytearray(blob.ciphertext)
            ciphertext[0] ^= 1
            changes.append(replace(blob, ciphertext=bytes(ciphertext)))
            tag = bytearray(blob.tag)
            tag[-1] ^= 1
            changes.append(replace(blob, tag=bytes(tag)))
            nonce = bytearray(blob.nonce)
            nonce[0] ^= 1
            changes.append(replace(blob, nonce=bytes(nonce)))
            for case, candidate in zip(("ciphertext", "tag", "nonce"), changes):
                with self.subTest(case=case), self.assertRaises(CryptoError) as caught:
                    self.backend.unprotect(candidate, self.aad)
                self.assertEqual(caught.exception.code, "AUTHENTICATION_FAILED")
                self.assertEqual(
                    str(caught.exception), "protected value authentication failed",
                )
            with self.assertRaises(CryptoError) as caught:
                self.backend.unprotect(blob, self.aad + b" ")
            self.assertEqual(caught.exception.code, "AUTHENTICATION_FAILED")
        finally:
            wipe(expected)

    def test_random_nonces_are_unique(self):
        first, first_expected = self.protected()
        second, second_expected = self.protected()
        try:
            self.assertNotEqual(first.nonce, second.nonce)
            self.assertEqual(len(first.nonce), 12)
            self.assertEqual(len(first.tag), 16)
        finally:
            wipe(first_expected)
            wipe(second_expected)

    def test_empty_plaintext_can_authenticate_canonical_metadata(self):
        blob = self.backend.protect(bytearray(), self.aad)
        self.assertEqual(blob.ciphertext, b"")
        with self.backend.unprotect(blob, self.aad) as secret:
            with secret.view() as view:
                self.assertEqual(len(view), 0)

    def test_duplicate_injected_nonce_fails_closed(self):
        key = bytearray(secrets.token_bytes(32))
        nonce = secrets.token_bytes(12)
        backend = WindowsCngAesGcm(
            key, key_id="synthetic-collision-key", nonce_factory=lambda size: nonce,
        )
        try:
            first = bytearray(secrets.token_bytes(32))
            backend.protect(first, self.aad)
            second = bytearray(secrets.token_bytes(32))
            with self.assertRaises(CryptoError) as caught:
                backend.protect(second, self.aad)
            self.assertEqual(caught.exception.code, "NONCE_REUSE")
            self.assertTrue(all(value == 0 for value in second))
        finally:
            backend.close()

    def test_malformed_blob_is_rejected_with_fixed_errors(self):
        blob, expected = self.protected()
        try:
            valid = blob.to_dict()
            malformed = [
                {key: value for key, value in valid.items() if key != "tag"},
                {**valid, "extra": True},
                {**valid, "algorithm": "AES-CBC"},
                {**valid, "nonce": "not-base64"},
                {**valid, "tag": "AA=="},
            ]
            for value in malformed:
                with self.subTest(fields=sorted(value)), self.assertRaises(CryptoError) as caught:
                    self.backend.unprotect(value, self.aad)
                self.assertEqual(caught.exception.code, "INVALID_BLOB")
                self.assertEqual(str(caught.exception), "protected value is invalid")
        finally:
            wipe(expected)

    def test_secret_buffer_close_zeroes_existing_view_and_is_idempotent(self):
        blob, expected = self.protected()
        try:
            secret = self.backend.unprotect(blob, self.aad)
            view = secret.view()
            self.assertTrue(secrets.compare_digest(view, expected))
            secret.close()
            self.assertTrue(all(value == 0 for value in view))
            view.release()
            secret.close()
            self.assertEqual(str(secret), "<SecretBuffer redacted>")
        finally:
            wipe(expected)

    def test_backend_close_destroys_use_and_context_manager_closes(self):
        blob, expected = self.protected()
        try:
            key_object = self.backend._key_object
            self.backend.close()
            self.assertFalse(self.backend._key_handle.value)
            self.assertFalse(self.backend._algorithm_handle.value)
            self.assertTrue(all(value == 0 for value in key_object))
            plaintext = bytearray(secrets.token_bytes(8))
            with self.assertRaises(CryptoError) as caught:
                self.backend.protect(plaintext, self.aad)
            self.assertEqual(caught.exception.code, "BACKEND_CLOSED")
            self.assertTrue(all(value == 0 for value in plaintext))
            with self.assertRaises(CryptoError) as caught:
                self.backend.unprotect(blob, self.aad)
            self.assertEqual(caught.exception.code, "BACKEND_CLOSED")

            context_key = bytearray(secrets.token_bytes(32))
            with WindowsCngAesGcm(
                    context_key, key_id="synthetic-context-key") as context_backend:
                self.assertFalse(context_backend._closed)
            self.assertTrue(context_backend._closed)
        finally:
            wipe(expected)

    def test_invalid_key_is_zeroed_and_no_plaintext_fallback_exists(self):
        invalid = bytearray(secrets.token_bytes(31))
        with self.assertRaises(CryptoError) as caught:
            WindowsCngAesGcm(invalid, key_id="synthetic-invalid")
        self.assertEqual(caught.exception.code, "INVALID_KEY")
        self.assertTrue(all(value == 0 for value in invalid))

    def test_crypto_module_has_no_network_process_log_model_or_memory_imports(self):
        source_path = Path(__import__("phase8f.crypto", fromlist=["x"]).__file__)
        tree = ast.parse(source_path.read_text("utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or ""
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        forbidden = {
            "socket", "subprocess", "logging", "urllib", "requests", "http",
            "openai", "provider", "controller", "operator_cli", "memory", "phase8e",
            "hashlib", "hmac", "pathlib",
        }
        imported_parts = {
            part for imported in imports for part in imported.split(".")
        }
        self.assertTrue(forbidden.isdisjoint(imported_parts))


if __name__ == "__main__":
    unittest.main()
