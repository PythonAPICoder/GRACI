"""Strict Phase 1A model-result contract validation."""

import json
from typing import Any


class ValidationError(ValueError):
    pass


def validate_model_result(content: str) -> dict[str, Any]:
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"model output is not valid JSON: {exc.msg}") from exc
    if not isinstance(result, dict):
        raise ValidationError("model result must be a JSON object")
    required = {"schema_version", "status", "summary"}
    if set(result) != required:
        raise ValidationError(f"model result fields must be exactly {sorted(required)}")
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise ValidationError("schema_version must be integer 1")
    if result["status"] not in {"PASS", "FAIL"}:
        raise ValidationError("status must be PASS or FAIL")
    if not isinstance(result["summary"], str) or not result["summary"].strip():
        raise ValidationError("summary must be a non-empty string")
    return result
