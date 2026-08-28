"""Strict reviewer contract and deterministic Phase 3B adjudication."""

import json
from typing import Any

from .validation import ValidationError


def validate_review(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"review is not valid JSON: {exc.msg}") from exc
    required = {"schema_version", "verdict", "findings", "rationale"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValidationError(f"review fields must be exactly {sorted(required)}")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValidationError("review schema_version must be integer 1")
    if value["verdict"] not in {"PASS", "FAIL"}:
        raise ValidationError("review verdict must be PASS or FAIL")
    if (not isinstance(value["rationale"], str) or not value["rationale"].strip()
            or len(value["rationale"]) > 4000):
        raise ValidationError("review rationale must be a non-empty string of at most 4000 characters")
    findings = value["findings"]
    if not isinstance(findings, list) or len(findings) > 10:
        raise ValidationError("review findings must be an array of at most 10 items")
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"severity", "message"}:
            raise ValidationError("each finding must contain exactly severity and message")
        if any(not isinstance(finding[key], str) or not finding[key].strip()
               or len(finding[key]) > 1000
               for key in ("severity", "message")):
            raise ValidationError("finding values must be non-empty strings of at most 1000 characters")
    return value


def adjudicate(tests_passed: bool, review_state: str,
               review_verdict: str | None) -> tuple[str, str]:
    if not tests_passed:
        return "FAIL", "deterministic_tests_failed"
    if review_state != "COMPLETE":
        return "REVIEW_ERROR", "required_review_unavailable_or_invalid"
    if review_verdict == "PASS":
        return "PASS", "tests_passed_and_review_passed"
    if review_verdict == "FAIL":
        return "REVIEW_REJECTED", "tests_passed_but_review_failed"
    return "REVIEW_ERROR", "required_review_verdict_invalid"
