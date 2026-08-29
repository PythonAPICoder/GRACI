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
    schema_version = result.get("schema_version")
    required = ({"schema_version", "status", "summary"}
                if schema_version == 1 else
                {"schema_version", "status", "summary", "user_response"})
    if set(result) != required:
        raise ValidationError(f"model result fields must be exactly {sorted(required)}")
    if type(schema_version) is not int or schema_version not in {1, 2}:
        raise ValidationError("schema_version must be integer 1 or 2")
    if result["status"] not in {"PASS", "FAIL"}:
        raise ValidationError("status must be PASS or FAIL")
    if not isinstance(result["summary"], str) or not result["summary"].strip():
        raise ValidationError("summary must be a non-empty string")
    if schema_version == 2:
        user_response = result["user_response"]
        if result["status"] == "PASS":
            if not isinstance(user_response, str) or not user_response.strip():
                raise ValidationError("PASS user_response must be a non-empty string")
        elif user_response is not None:
            raise ValidationError("FAIL user_response must be null")
    return result
