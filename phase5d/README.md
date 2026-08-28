# Phase 5D — Live Runtime Integration

Phase 5D connects authoritative GRACI lifecycle boundaries to the accepted Phase
5 visualizer without giving the visualizer authority.

## Architecture

`graci.observation` is the only core-facing API. Controllers optionally publish
small immutable `RuntimeObservation` values through `observe()`. That function is
a no-op when no observer is supplied and catches every observer exception. Core
execution does not import the visualizer contract, backend, HTTP server, or UI.

`graci.visualizer_runtime.VisualizerRuntimeObserver` is the adapter. It consumes
trusted observations, constructs immutable Phase 5A snapshots/events, and
publishes them directly in process to the Phase 5B `VisualizerStateProvider`.
There are no network calls, sleeps, polls, shared-drive files, or per-token events
on the runtime path.

## Authoritative mapping

| Runtime boundary | Visual state |
| --- | --- |
| task accepted / orchestration | `planning` |
| governed memory preparation | `retrieving_memory` |
| Qwen implementer invocation | `reasoning` |
| bounded file operation | `executing_tool` |
| governed deterministic suite | `testing` |
| GLM evidence review | `reviewing` |
| deterministic adjudication | `adjudicating` |
| accepted PASS | `completed` |
| recoverable runtime warning | `warning` |
| authoritative execution/review failure | `failed` |

LISTENING and SPEAKING remain unused and reserved for Phase 6. No timers or model
thought are interpreted as state.

## Display-safe facts

- Model projection includes only exact model ID, role, selected node, and activity.
- Task display uses a fixed runtime label rather than publishing the user/model prompt.
- Phase 3D routing projection displays the existing selection, optional request,
  fallback, endpoint health, MO2 state, and eligibility; it does not probe or route.
- Memory projection includes mode, relevance keys, selected/supplied IDs and counts,
  context character count, conflict count, corruption count, and status. It never
  receives record content or the memory envelope.
- Tool events include bounded category, action, safe relative target label, status,
  and bounded error classification/reason. Raw stdout/stderr are excluded.
- Reviewer verdict and deterministic adjudication remain separate fields and states.

## Failure and security boundaries

Observer absence and observer exceptions leave authoritative return status and
terminal reason unchanged. Backend/browser absence needs no special handling because
they are not runtime dependencies. HTTP remains the existing loopback GET/HEAD-only,
no-CORS Phase 5B surface; Phase 5D adds no route or browser control.

No prompts, chain-of-thought, raw memory, secret material, arbitrary output dumps,
task submission, approvals, tools, routing controls, memory mutation, MO2 controls,
or repository mutation are added. Shared-drive telemetry is not used.

## Acceptance scenarios

- A: deterministic real controller execution uses the configured exact Qwen identity
  on the authoritative 3090 binding and projects tool/test completion.
- B: governed Phase 4D memory lifecycle and metadata-only projection are tested.
- C: the real Phase 3B controller path projects exact GLM identity and distinct
  REVIEWING then ADJUDICATING states using deterministic provider fixtures.
- D: a genuine controller policy failure projects FAILED.
- E: the same controller completes with no observer/backend/browser.
- F: an observer that raises for every callback cannot change the GRACI result.
- G: Phase 3D routing facts preserve primary 3090 authority and optional-only 4090;
  MO2 RUNNING is represented as ineligible without probing from the visualizer.

The acceptance suite uses deterministic provider fixtures. Live workstation model
availability is environment-dependent and is reported separately rather than
fabricated. UI markup/styling is unchanged; existing Phase 5C orbital behavior reads
the live `system_state` values published by this adapter.
