# Phase 8B — Observer-Only Resident Turn Continuity & Architecture Reconciliation

Phase 8B makes the latest completed governed browser turn resident presentation
state rather than state owned by the initiating browser DOM.

## Contract and flow

Snapshot schema v2 adds frozen `LatestTurnView`. It contains only bounded run ID,
trusted browser-PTT source, governed start/end timestamps and PASS/FAIL, optional
failure category/reason, presence and at most 4,000 characters of a validated
`AuthoritativeFinalResponse`, and independent speech outcome. Multiline response
format is retained and browser rendering uses `textContent`.

The one-way path is:

`completed submitted TurnResult -> VisualizerRuntimeObserver.publish_completed_turn -> LatestTurnView -> snapshot/latest_turn_updated SSE -> browser`

`BrowserPTTOperator` calls the optional publisher only after the existing coordinator
returns. Publisher exceptions are caught. Blank/failed STT, cancellation, invalid
audio, rejected input, and other zero-submission paths never publish a turn. A failed
governed record cannot carry response text, including rejected raw model attempts.

## Lifetime and restart

The resident process owns one latest value. Refresh, polling, SSE reconnect, and
additional tabs read the same snapshot. A new active task does not overwrite or
relabel the prior completed value. Restart GRACI clears transient task, capture, STT,
presentation lifecycle, model-display, and execution projection while retaining the
latest completed result. Resident exit discards it; startup does not inspect `runs/`.

## Authority and privacy

The browser route allowlist is unchanged: PTT begin/chunk/finish/cancel and Restart
GRACI. Phase 8B adds no route and no control, tool, memory, model, routing, compute,
approval, retry, cancellation, history, session, remote, CORS, cloud, or inference
capability. The 3090 remains authoritative and independently sufficient. The 4090
remains optional and fail-closed under unchanged MO2 and health policy.

Prompts, transcripts, partial STT, raw/rejected model output, hidden reasoning,
memory content, credentials, stdout/stderr, and arbitrary run-file data are excluded.

## Acceptance

Focused deterministic tests cover contract bounds, success/failure projection,
rejected-content exclusion, zero-run paths, exactly-once release, observer isolation,
resident refresh/multi-client continuity, latest-turn SSE notification, active/latest
separation, restart retention, empty reconstruction, safe rendering, accessibility,
and the unchanged control allowlist. Closure evidence is
`evidence/phase8b-closure.json`.

Physical browser refresh, reconnect, multi-tab, and Restart GRACI acceptance on the
resident workstation remains a product-owner/manual acceptance item. Phase 8C and
all later roadmap work remain unauthorized.
