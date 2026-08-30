# Phase 8C-V — Browser voice playback and reactive presence

Phase 8C-V moves only presentation playback from the Windows `winsound` worker to
the localhost browser. Response authority remains unchanged:

`AuthoritativeFinalResponse -> speech-only normalization/pronunciation -> Kokoro -> SynthesizedAudio -> BrowserPlaybackBroker -> claimed browser playback`

`BrowserPlaybackBroker` accepts only the existing bounded `SynthesizedAudio` value.
It creates one opaque, in-memory, expiring artifact and admits one atomic browser
claim. The audio route requires both the artifact identifier and its independent
claim token; it accepts no path, URL, text, synthesis request, historical run, or
filesystem input. Completed, cancelled, failed, abandoned, and restarted artifacts
are invalidated and cannot replay. The resident remains loopback-only with strict
Host/origin validation, `no-store`, `nosniff`, and a same-origin CSP.

The browser reports `started` only from the media element's actual `playing` event.
Only then does the resident publish trusted `SPEAKING`. Completion, media failure,
autoplay rejection, PTT barge-in, tab hiding/closure, claim timeout, and Restart
GRACI terminate the claim and return the lifecycle to idle. Multiple tabs may race,
but only one claim succeeds; refresh cannot reclaim an accepted or terminal artifact.
If no eligible browser claims an artifact, presentation fails explicitly by timeout.

The heard signal follows `HTMLAudioElement -> MediaElementAudioSourceNode ->
AnalyserNode -> destination`. Smoothed, bounded FFT energy drives the central orb and
64 radial bars only while playback is active. Idle/listening retain calmer static
identity; trusted Qwen processing uses stronger cyan phase activity; trusted GLM
review uses violet counter-oriented activity. A lightweight CSS circuit field remains
decorative and communicates only the trusted high-level state.

Sparse Web Audio chirps are scheduled only for trusted active Qwen/GLM observations.
They stop immediately for PTT capture, speech playback, hidden tabs, state exit, or a
disabled `UI SOUNDS` toggle. That presentation-only preference is stored locally.
Reduced-motion mode disables deformation and traveling activity while retaining text,
geometry, and state colors. No cloud service, model authority, compute policy, health
inference, wake word, VAD, hidden progress, or Phase 8D behavior is added.

Automated coverage is in `tests/test_phase8cv_browser_voice.py`; browser autoplay,
audio audibility, physical barge-in latency, tab racing, and visible amplitude response
still require the physical QA procedure recorded in the completion report.
