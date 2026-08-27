# GRACI Phase 1A evidence

Phase 1A was verified on 2026-08-27 (America/Chicago).

- Offline suite: 8 tests passed with Python warnings treated as errors.
- Live run: `d7e604aa-318d-47de-a735-966132894d6b`
- Endpoint: `http://127.0.0.1:8080/v1`
- Provider: `local-llama-cpp`
- Node: `3090-primary-localhost`
- Requested and server-reported model: `qwen3.8-27b-q4_k_m`
- HTTP status: 200
- Validated contract status: PASS

The live record is stored in `evidence/live-run-d7e604aa-318d-47de-a735-966132894d6b.json`.
Configuration rejects every endpoint except the Phase 1A loopback endpoint, so neither
the 4090 endpoint nor a cloud endpoint can receive work through this implementation.
