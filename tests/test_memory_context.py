"""Bounded untrusted memory-context contract tests."""

import unittest

from graci.memory_context import (ALLOWED_MEMORY_CONTEXT_STATUSES,
                                  AUTHORITY_DENIALS,
                                  MAX_MEMORY_CONTEXT_BYTES,
                                  MAX_MEMORY_CONTEXT_RECORDS,
                                  MemoryContextResolution,
                                  memory_context_sha256,
                                  validate_memory_context,
                                  validate_memory_context_resolution)


MEMORY_ID = "01020304-0506-4000-8000-010203040506"
GENERATION_ID = "09080706-0504-4000-8000-090807060504"


def valid_context(record_count: int = 1, content: str = "Synthetic context only.") -> dict:
    records = [{
        "memory_id": f"{MEMORY_ID[:7]}{index:01x}-0506-4000-8000-010203040506",
        "personalized_kind": "preference",
        "relevance_key": "user.synthetic.test",
        "content": content,
    } for index in range(record_count)]
    return {
        "schema_version": 1,
        "classification": "UNTRUSTED_CONTEXT_DATA",
        "authority_permitted": False,
        "memory_generation_id": GENERATION_ID,
        "record_count": len(records),
        "records": records,
        "authority_denied": list(AUTHORITY_DENIALS),
    }


class MemoryContextTests(unittest.TestCase):
    def test_valid_context_is_canonicalized_and_hashed(self):
        context = validate_memory_context(valid_context())
        self.assertEqual(context["record_count"], 1)
        self.assertEqual(context["authority_permitted"], False)
        self.assertEqual(memory_context_sha256(context),
                         memory_context_sha256(valid_context()))

    def test_context_requires_exact_untrusted_classification(self):
        context = valid_context()
        context["classification"] = "TRUSTED_CONTEXT_DATA"
        with self.assertRaises(ValueError):
            validate_memory_context(context)

    def test_context_cannot_permit_authority(self):
        context = valid_context()
        context["authority_permitted"] = True
        with self.assertRaises(ValueError):
            validate_memory_context(context)

    def test_context_requires_exact_authority_denial(self):
        context = valid_context()
        context["authority_denied"] = list(AUTHORITY_DENIALS[:-1])
        with self.assertRaises(ValueError):
            validate_memory_context(context)

    def test_context_record_count_must_match_records(self):
        context = valid_context()
        context["record_count"] = 2
        with self.assertRaises(ValueError):
            validate_memory_context(context)

    def test_context_records_must_be_unique_and_bounded(self):
        duplicate = valid_context(2, "Synthetic duplicate.")
        duplicate["records"][1]["memory_id"] = duplicate["records"][0]["memory_id"]
        with self.assertRaises(ValueError):
            validate_memory_context(duplicate)

    def test_context_rejects_secret_material(self):
        context = valid_context(content="password=secret")
        with self.assertRaises(ValueError):
            validate_memory_context(context)

    def test_applied_context_requires_memory_generation_id(self):
        context = valid_context()
        context["memory_generation_id"] = None
        with self.assertRaises(ValueError):
            validate_memory_context_resolution(
                MemoryContextResolution(context, "applied", None, None))

    def test_applied_context_rejects_invalid_memory_generation_id(self):
        context = valid_context()
        context["memory_generation_id"] = "not-a-canonical-uuid"
        with self.assertRaises(ValueError):
            validate_memory_context_resolution(
                MemoryContextResolution(context, "applied", None, None))

    def test_context_enforces_absolute_byte_limit(self):
        context = valid_context(MAX_MEMORY_CONTEXT_RECORDS, "x" * 1_000)
        self.assertLessEqual(len(
            __import__("json").dumps(context, ensure_ascii=True, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")),
            MAX_MEMORY_CONTEXT_BYTES)
        oversized = valid_context(MAX_MEMORY_CONTEXT_RECORDS, "é" * 1_000)
        with self.assertRaises(ValueError):
            validate_memory_context(oversized)

    def test_resolution_applied_requires_context_and_digest(self):
        context = validate_memory_context(valid_context())
        digest = memory_context_sha256(context)
        resolved = validate_memory_context_resolution(
            MemoryContextResolution(context, "applied", None, digest))
        self.assertEqual(resolved.status, "applied")
        self.assertEqual(resolved.context_sha256, digest)

    def test_resolution_failure_does_not_require_context(self):
        resolved = validate_memory_context_resolution(
            MemoryContextResolution(None, "provider_error",
                                    "memory context provider failed"))
        self.assertIsNone(resolved.context)
        self.assertIsNone(resolved.context_sha256)

    def test_resolution_rejects_applied_without_context(self):
        with self.assertRaises(ValueError):
            validate_memory_context_resolution(
                MemoryContextResolution(None, "applied", None, None))

    def test_resolution_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            validate_memory_context_resolution(
                MemoryContextResolution(None, "unknown_status", None))

    def test_allowed_statuses_are_bounded(self):
        self.assertEqual(len(ALLOWED_MEMORY_CONTEXT_STATUSES), 11)
        self.assertIn("applied", ALLOWED_MEMORY_CONTEXT_STATUSES)
        self.assertIn("provider_error", ALLOWED_MEMORY_CONTEXT_STATUSES)


if __name__ == "__main__":
    unittest.main()
