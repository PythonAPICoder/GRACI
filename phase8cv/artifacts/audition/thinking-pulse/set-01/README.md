# Thinking Pulse audio-only audition — set 01

This directory is a Product Owner listening gate. It contains five standalone
10-second candidates and does not configure, call, or modify the production
Thinking Pulse, Qwen/GLM processing, or the approved circuit animation.

## Listening files

| # | File | Distinguishing character | Events |
|---|---|---|---:|
| 1 | `thinking-pulse-01-data-chatter.mp3` | Densest, driest rapid ticks and pips | 115 |
| 2 | `thinking-pulse-02-sci-fi-compute.mp3` | Most tonal, widest sweep motion, most layered events | 47 |
| 3 | `thinking-pulse-03-digital-bursts.mp3` | Strongest contrast between 2-5 event packets and silence | 60 |
| 4 | `thinking-pulse-04-retro-future.mp3` | Bright classic oscillator edge and stepped micro-events | 60 |
| 5 | `thinking-pulse-05-hybrid.mp3` | Balanced modern GRACI character; recommended for audition | 67 |

All five files are 10.000-second, 48 kHz stereo MP3s encoded at 256 kbit/s.
The source render is peak-matched to -6 dBFS before encoding. Every second of
every candidate contains one or more new event onsets. The longest scheduled
silence is 205 ms, 384 ms, 531 ms, 303 ms, and 310 ms respectively.

## Common synthesis design

- The generator uses only short oscillator events, gain envelopes, one-way
  frequency ramps, occasional two-oscillator layers, and bounded stereo pan.
- Pitch is drawn independently on a logarithmic continuum. It is not quantized
  to a musical scale and does not use a key, melody, repeating phrase, beat, or
  rhythmic LFO.
- Pattern guards reject A-B-A pitch returns, repeated near-equal pitches,
  near-equal adjacent onset spacings, a third same-direction sweep, and
  two-tone ratios close to common consonant intervals.
- Event durations are 20-198 ms in the rendered set. There are no sustained
  primary tones, background beds, continuous noise, reverb, or delay.
- Clicks use a 0.4-1.4 ms attack and steep decay. Other events use a 1.5-6 ms
  attack and compact smooth decay.
- Each deterministic seed, master gain, exact event schedule, event value,
  output hash, and validation result is recorded in
  `thinking-pulse-audition-manifest.json`.

## Candidate profiles

### 1 — Data Chatter

- Base frequency: 1,250-6,100 Hz; rendered layers and sweeps remain below
  10,500 Hz.
- Oscillators: sine 56%, triangle 30%, square 14%.
- Event weights: click 50%, pip 35%, sweep 10%, dual 5%.
- Duration ranges: click 20-44 ms, pip 32-78 ms, sweep 52-116 ms,
  dual 54-108 ms.
- Per-event gain: 0.10-0.25; pan: +/-0.18.
- Episode size weights: 1-6 events at 18/22/23/18/12/7%.
- Intra-cluster onset spacing: 22-64 ms; post-cluster silence: 65-210 ms.
- Sweep ratios: 0.62-0.84 down or 1.18-1.48 up.

### 2 — Sci-Fi Compute

- Base frequency: 650-4,700 Hz; rendered layers and sweeps remain below
  9,300 Hz.
- Oscillators: sine 70%, triangle 24%, sawtooth 6%.
- Event weights: click 8%, pip 27%, sweep 40%, dual 25%.
- Duration ranges: click 22-48 ms, pip 52-128 ms, sweep 74-198 ms,
  dual 68-188 ms.
- Per-event gain: 0.09-0.23; pan: +/-0.24.
- Episode size weights: 1-4 events at 40/32/18/10%.
- Intra-cluster onset spacing: 55-126 ms; post-cluster silence: 125-345 ms.
- Sweep ratios: 0.48-0.79 down or 1.25-1.88 up.

### 3 — Digital Bursts

- Base frequency: 900-5,600 Hz; rendered layers and sweeps remain below
  10,100 Hz.
- Oscillators: sine 48%, triangle 32%, square 14%, sawtooth 6%.
- Event weights: click 31%, pip 30%, sweep 25%, dual 14%.
- Duration ranges: click 20-42 ms, pip 32-84 ms, sweep 54-134 ms,
  dual 50-120 ms.
- Per-event gain: 0.09-0.26; pan: +/-0.22.
- Episode size weights: 1-5 events at 10/22/26/24/18%.
- Intra-burst onset spacing: 28-80 ms; inter-burst silence: 210-560 ms.
- Sweep ratios: 0.57-0.82 down or 1.20-1.62 up.

### 4 — Retro-Future

- Base frequency: 520-4,200 Hz; rendered layers and sweeps remain below
  8,400 Hz.
- Oscillators: sine 16%, triangle 36%, square 31%, sawtooth 17%.
- Event weights: click 24%, pip 25%, sweep 18%, dual 12%, stepped 21%.
- Duration ranges: click 22-50 ms, pip 38-100 ms, sweep 64-148 ms,
  dual 58-138 ms, stepped 56-142 ms.
- Per-event gain: 0.08-0.21; pan: +/-0.20.
- Episode size weights: 1-5 events at 27/29/23/14/7%.
- Intra-cluster onset spacing: 42-106 ms; post-cluster silence: 100-305 ms.
- Sweeps use ratios 0.63-0.84 down or 1.18-1.52 up. Stepped events use
  2-4 irregular plateaus across a 0.72-1.46 ratio range.

### 5 — GRACI Hybrid

- Base frequency: 850-5,400 Hz; rendered layers and sweeps remain below
  9,800 Hz.
- Oscillators: sine 64%, triangle 30%, square 4%, sawtooth 2%.
- Event weights: click 26%, pip 31%, sweep 26%, dual 17%.
- Duration ranges: click 20-45 ms, pip 35-94 ms, sweep 60-154 ms,
  dual 55-144 ms.
- Per-event gain: 0.08-0.22; pan: +/-0.21.
- Episode size weights: 1-5 events at 27/30/24/14/5%.
- Intra-cluster onset spacing: 30-88 ms; post-cluster silence: 95-310 ms.
- Sweep ratios: 0.55-0.82 down or 1.21-1.70 up.

The exact machine-readable source of truth is `thinking-pulse-profiles.json`.
It also records two-tone ratios, secondary gains, deterministic seeds, common
envelopes, and the Web Audio mapping.

## Browser reproducibility

The profiles deliberately map onto ordinary Web Audio primitives:

- `OscillatorNode.type` for sine, triangle, square, and sawtooth timbres;
- `frequency.setValueAtTime()` and `exponentialRampToValueAtTime()` for stable
  tones and sweeps;
- additional `setValueAtTime()` calls for Retro-Future stepped events;
- one `GainNode` envelope per oscillator;
- `StereoPannerNode` for bounded pan; and
- two oscillators feeding one event bus for dual-tone events.

That design can be translated into the existing Thinking Pulse event schema
after Product Owner approval. This set does not perform that translation.

## Reproduction and evidence

Run from the repository root:

```powershell
python -B phase8cv\generate_thinking_pulse_audition.py
```

The generator uses the Python standard library and the FFmpeg/libmp3lame encoder
already installed on the machine; it adds no dependency. It writes a temporary
PCM16 WAV for each candidate, validates the WAV, encodes the MP3, probes its
codec/rate/channels/duration, fully decodes it, and records the exact scheduled
events and SHA-256 digest in `thinking-pulse-audition-manifest.json`.

No winner is selected by these artifacts. Product Owner approval remains required
before any production integration or circuit synchronization.
