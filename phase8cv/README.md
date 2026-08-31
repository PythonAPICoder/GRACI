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

The heard speech signal follows `HTMLAudioElement -> MediaElementAudioSourceNode ->
AnalyserNode -> destination`. Smoothed, bounded FFT energy drives the central orb and
64 radial bars only while speech playback is active. The approved production Thinking
Pulse remains inside the existing browser presentation layer: it reuses the owned UI
sound `AudioContext` and oscillator/gain/stereo-panner builder, while the speech media
element and analyser path remain unchanged and separate. It adds no audio-file,
network, synthesis-service, or second analyser path.

## Thinking Pulse — approved Data Chatter profile

Product Owner-selected Candidate 1, **Data Chatter**, is generated dynamically while a
trusted active Qwen or GLM observation is in planning, memory retrieval, reasoning,
tool execution, testing, review, or adjudication. A deterministic per-task generator
schedules irregular clusters of clicks, pips, short sweeps, and occasional dual-tone
events. Each generated event is the single source for both its Web Audio micro-cue and
one existing SVG circuit route, so sound, color, intensity, direction, and packet
launch share the same dispatch boundary. Production mode pauses and hides the old
infinite packet loops; only event-driven packet heads and trails run, without changing
the approved circuit paths or their geometry. Qwen keeps the broader cyan-to-warm
forward palette, while GLM keeps its violet-biased reverse direction.

The scheduler starts only with a live resident, an eligible push-to-talk phase, no
claimed speech playback, and a trusted active model. Trusted listening, speaking,
completion, failure, and idle events stop it immediately; PTT capture, browser speech,
a hidden or closed page, disconnect, and End Session also cancel its timer, active
oscillators, generator state, and packet visuals. `UI SOUNDS` controls the audible
layer without granting runtime authority. Reduced-motion mode suppresses traveling
packets while retaining the bounded audio presentation and textual state.

Data Chatter is bounded to 20–116 ms events, 1,250–6,100 Hz base frequencies,
10,500 Hz maximum rendered frequency, gain 0.10–0.25, pan within +/-0.18, one pending
scheduler timer, no more than six concurrent cues, no more than two oscillator voices
per event, and the 14 existing circuit routes. Diagnostic history remains capped at 96
entries. No cloud service, model authority, compute policy, health inference, wake
word, VAD, hidden progress, or Phase 8D behavior is added.

The final command-center layout uses a dominant, mathematically centered orb/radial
assembly over a live SVG circuit field. A compact right status rail, single-row PTT
and presentation controls, condensed six-stage pipeline, and latest-turn footer reclaim
the 3440x1440 workspace for GRACI's presence. End Session is browser-presentation-only:
it cancels transient media/capture, closes the page's observer connection, and grants no
resident or execution authority. Responsive breakpoints stack status and controls while
keeping the orb and its 64-spoke analyser ring centered together.

Automated coverage is in `tests/test_phase8cv_browser_voice.py`; browser autoplay,
audio audibility, physical barge-in latency, tab racing, and visible amplitude response
still require the physical QA procedure recorded in the completion report.
