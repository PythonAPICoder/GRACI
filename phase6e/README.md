# Phase 6E — Voice Lifecycle Publication

Phase 6E publishes bounded voice activity as observer-only facts. It reuses the
canonical `graci.visualizer.SystemState` values `idle`, `listening`, and `speaking`;
it adds no state system, execution path, authority, runtime dependency, or loop.

`VoiceLifecycle` owns one guarded in-process state and accepts an optional replaceable
`VoiceLifecycleObserver`. `enter()` returns an idempotent generation lease. Only
`idle -> listening|speaking -> idle` is accepted. Overlap is rejected without a
second claim, and a late or repeated lease close cannot restore a newer activity.
Observer exceptions are logged and retained in `publication_failures`; state changes
and restoration continue, and speech/governed results are not changed.

`LISTENING` begins immediately before the explicit Phase 6B capture start and remains
active through bounded capture stop and local recognition. It restores in `finally`
after transcription success, rejection, timeout, worker/device failure, or exception;
explicit cancel restores even if capture cleanup raises. Capture startup failure also
restores. Merely constructing or enabling voice components publishes nothing.

`SPEAKING` begins only after successful TTS has produced validated audio and
immediately before the Phase 6D player call. It restores in `finally` after success,
failure, timeout, stop/cancel result, or exception. Synthesis alone never publishes
`speaking`. Publication and playback failures cannot alter the immutable authoritative
response or the separate speech-presentation result.

Run deterministic acceptance without devices, models, network, or GPUs:

```powershell
python -W error -m unittest tests.test_phase6e_voice_lifecycle -v
python -W error -m unittest discover -s tests -v
```

No physical microphone or speaker validation was performed for Phase 6E. Wake word,
VAD, continuous listening, automatic reopening, speech loops, duplex, barge-in, UI,
animation, and network lifecycle broadcasting remain deferred.
