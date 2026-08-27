import json
import time
import urllib.request
from pathlib import Path


ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "qwen3.8-27b-q4_k_m"
OUTPUT_DIR = Path(__file__).resolve().parent

request_body = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "Return only one valid JSON object with exactly four fields: "
                "gate, status, message, model. Do not use markdown fences."
            ),
        },
        {
            "role": "user",
            "content": (
                "Report gate G0.9 as PASS. State in message that local llama.cpp "
                "inference succeeded. Identify the model as qwen3.8-27b-q4_k_m."
            ),
        },
    ],
    "temperature": 0,
    "max_tokens": 512,
    "response_format": {"type": "json_object"},
    "chat_template_kwargs": {"enable_thinking": False},
}

started = time.perf_counter()
http_status = None
assistant_content = None
parsed = None
errors = []

try:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        http_status = response.status
        response_body = json.loads(response.read().decode("utf-8"))
    assistant_content = response_body["choices"][0]["message"]["content"]
    parsed = json.loads(assistant_content)
except Exception as exc:
    errors.append(f"request_or_parse_error: {type(exc).__name__}: {exc}")

elapsed_seconds = round(time.perf_counter() - started, 3)
required_fields = {"gate", "status", "message", "model"}

if parsed is not None:
    if set(parsed) != required_fields:
        errors.append(
            "field_set_mismatch: expected "
            + repr(sorted(required_fields))
            + ", got "
            + repr(sorted(parsed))
        )
    if parsed.get("gate") != "G0.9":
        errors.append("gate_mismatch")
    if parsed.get("status") != "PASS":
        errors.append("status_mismatch")
    if parsed.get("model") != MODEL:
        errors.append("model_mismatch")
    message = parsed.get("message")
    if not isinstance(message, str) or not message.strip():
        errors.append("message_missing_or_empty")
    elif "local" not in message.lower() or "succeed" not in message.lower():
        errors.append("message_does_not_confirm_local_success")

passed = http_status == 200 and parsed is not None and not errors
result = {
    "gate": "G0.9",
    "status": "PASS" if passed else "FAIL",
    "local_ai_delegation": "PROVEN" if passed else "NOT PROVEN",
    "endpoint": ENDPOINT,
    "requested_model": MODEL,
    "http_status": http_status,
    "elapsed_seconds": elapsed_seconds,
    "parse_result": "PASS" if parsed is not None else "FAIL",
    "validation_result": "PASS" if passed else "FAIL",
    "validated_response": parsed,
    "errors": errors,
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "result.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)

report_lines = [
    "# GRACI Gate 0.9 — Local AI Delegation Proof",
    "",
    f"- Result: **{result['status']}**",
    f"- Local AI delegation: **{result['local_ai_delegation']}**",
    f"- Endpoint: `{ENDPOINT}`",
    f"- Requested model: `{MODEL}`",
    f"- HTTP status: `{http_status}`",
    f"- Elapsed time: `{elapsed_seconds:.3f} seconds`",
    f"- JSON parse: **{result['parse_result']}**",
    f"- Field/value validation: **{result['validation_result']}**",
    "",
    "## Validated model response",
    "",
    "```json",
    json.dumps(parsed, indent=2, ensure_ascii=False),
    "```",
    "",
    "The request used only the local 3090 llama.cpp endpoint. No raw environment context or credentials were stored.",
]
if errors:
    report_lines.extend(["", "## Validation errors", "", *[f"- {item}" for item in errors]])
(OUTPUT_DIR / "README.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

print(json.dumps(result, indent=2, ensure_ascii=False))
raise SystemExit(0 if passed else 1)
