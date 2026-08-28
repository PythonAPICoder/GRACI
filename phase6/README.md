# Phase 6 — Integrated Voice Acceptance and Closure

## Accepted Phase 6 capability

Phase 6 is complete at bounded push-to-talk voice interaction. Its accepted boundary
is explicit user-triggered local audio capture, local faster-whisper STT, one ordinary
governed runtime submission with typed-input-equivalent authority, and optional local
bounded Kokoro TTS/playback from an explicitly constructed authoritative final
response. Canonical `idle`, `listening`, and `speaking` publication is observer-only.

The integrated acceptance fixture composes the already accepted Phase 6B–6E public
interfaces. It is test-only: no production coordinator, alternate execution path,
automatic presentation, authority, persistence, scheduling, or network dependency was
added. The governed result exists before and independently of optional presentation.

The deterministic ordering is:

`explicit begin -> LISTENING -> capture/recognition -> IDLE -> exact transcript -> existing run(task) -> governed result -> explicit AuthoritativeFinalResponse -> synthesis while IDLE -> SPEAKING during playback -> IDLE`

Failures stop at their boundary. Rejected transcription submits zero tasks. Synthesis,
playback, cancellation, cleanup, and lifecycle publication failures cannot alter or
replace a completed governed result. Presentation and lifecycle callbacks submit zero
tasks. The speech-only pronunciation copy may render `GRACI` as `GRAY-see`; the
authoritative response remains unchanged.

Run closure verification without hardware, models, network, cloud, or GPUs:

```powershell
python -W error -m unittest tests.test_phase6_voice_closure -v
python -W error -m unittest discover -s tests -v
python -W error -m py_compile phase6a/pronunciation.py
python -W error -m compileall -q graci phase6b phase6c phase6d phase6e phase6 tests
```

Compilation acceptance is intentionally scoped to GRACI-owned source and tests. An
initial broader diagnostic traversal entered the ignored third-party Python runtime
under `phase6a/cache` and found a pre-existing Tcl/Tix `WmDefault.py` tab-indentation
error. That cached upstream file is not GRACI source, is not tracked, and is excluded
from the accepted command above; all GRACI-owned targets pass warning-strict compile.

Consolidated evidence is `phase6/evidence/phase6-closure.json`. It references rather
than rewrites accepted historical Phase 6 evidence.

## Deferred future enhancements

No Phase 6F is named or authorized. Wake word, VAD, continuous listening, automatic
microphone reopening, automatic speech loops/submission, turn-taking, duplex, barge-in
beyond explicit stop/cancel, hotkey/UI work, visualizer redesign/animation, device
selection, warm STT worker, Piper implementation, network/cloud/distributed speech,
GPU/4090 routing or scheduling, and new persistence remain deferred. Any future voice
enhancement requires separate roadmap authorization.
