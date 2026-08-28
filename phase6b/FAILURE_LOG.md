# Phase 6B Failure Log

The first Phase 6A regression run caught a stale status assertion that required
`Phase 6A — CURRENT`; it was updated to require Phase 6A complete and Phase 6B
complete. No production defect or data loss occurred.

Expected operational failures are
explicit result/error paths: unavailable device, capture start/runtime failure,
insufficient audio, worker unavailable/nonzero/timeout/malformed/empty output. Raw
audio cleanup is attempted for every STT outcome unless debug retention is explicit.
