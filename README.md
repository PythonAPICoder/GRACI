# GRACI minimal local core

Submit a task with Python 3.14 or later:

```powershell
python -m graci "Return PASS with a short confirmation that this task completed."
```

The controller uses only `http://127.0.0.1:8080/v1` and model
`qwen3.8-27b-q4_k_m`. It prints the complete run record and exits zero only for a
strictly validated model `PASS`. Every execution writes `runs/<run-id>.json`.

Run the offline test suite with:

```powershell
python -m unittest discover -s tests -v
```

Phase 1A deliberately has no retries, reviewers, resource scheduling, 4090 access,
cloud escalation, authentication, or service/API wrapper.

Phase 1B adds a deterministic, workspace-contained `graci.ToolLayer` for safe text
file operations, a narrow approved command policy, unittest execution, and read-only
Git observation. It is a programmatic interface only; models do not autonomously
invoke tools in this phase. See `phase1b/README.md` for its security boundary and
verification record.

Phase 1C integrates the local provider and controlled tool layer for one bounded
text-file action. The workspace must already exist and the only permitted target is
configured by the caller:

```powershell
python -m graci --workspace .\isolated-sandbox --target result.txt "Create result.txt containing exactly: example"
```

The model may propose only the strict `write_text` action contract. GRACI validates
the schema and exact target, executes through `ToolLayer`, reads the file back, and
reports `PASS` only when the observed content exactly equals the proposed content.
See `phase1c/README.md` for the accepted live evidence and limitations.
