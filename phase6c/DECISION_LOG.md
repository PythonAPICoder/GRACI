# Phase 6C Decision Log

- Reused the runtime `run(task)` method because it is the ordinary typed user-input
  boundary; a separate voice runtime would duplicate or bypass governance.
- Preserved the complete transcript string. Whitespace is inspected only to reject an
  empty utterance and is never stripped before submission.
- Used explicit adapter validation errors and otherwise preserved the runtime's own
  return/exception behavior.
- Did not add source metadata because the current runtime contract has no suitable
  facility and changing its persisted schema solely for provenance was not justified.
- Added no automatic TTS or follow-on execution.
