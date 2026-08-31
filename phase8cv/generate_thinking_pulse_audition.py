from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import wave
from array import array
from pathlib import Path
from typing import Any, Iterable


PHASE_ROOT = Path(__file__).absolute().parent
DEFAULT_OUTPUT = PHASE_ROOT / "artifacts" / "audition" / "thinking-pulse" / "set-01"
DEFAULT_PROFILES = DEFAULT_OUTPUT / "thinking-pulse-profiles.json"
MANIFEST_NAME = "thinking-pulse-audition-manifest.json"
SIMPLE_INTERVALS = (1.25, 4 / 3, 1.5, 5 / 3, 2.0)


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    marker = rng.random() * sum(weights.values())
    running = 0.0
    for value, weight in weights.items():
        running += weight
        if marker <= running:
            return value
    return next(reversed(weights))


def biased_between(rng: random.Random, bounds: list[float], power: float = 1.6) -> float:
    low, high = bounds
    return low + (high - low) * rng.random() ** power


def log_uniform(rng: random.Random, low: float, high: float) -> float:
    return math.exp(rng.uniform(math.log(low), math.log(high)))


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def rounded(value: float, digits: int = 5) -> float:
    return round(float(value), digits)


def reject_pitch_pattern(rng: random.Random, profile: dict[str, Any], recent: list[float]) -> float:
    low, high = profile["base_frequency_hz"]
    candidate = log_uniform(rng, low, high)
    for _ in range(24):
        near_recent = sum(abs(candidate / old - 1.0) < 0.05 for old in recent[-3:]) >= 2
        aba_pattern = len(recent) >= 2 and abs(candidate / recent[-2] - 1.0) < 0.05
        if not near_recent and not aba_pattern:
            break
        candidate = log_uniform(rng, low, high)
    recent.append(candidate)
    del recent[:-4]
    return candidate


def draw_dual_ratio(rng: random.Random, bounds: list[float]) -> float:
    low, high = bounds
    ratio = rng.uniform(low, high)
    for _ in range(30):
        if all(abs(ratio - musical) > 0.022 for musical in SIMPLE_INTERVALS):
            break
        ratio = rng.uniform(low, high)
    return ratio if rng.random() < 0.62 else 1.0 / ratio


def draw_sweep_ratio(
    rng: random.Random,
    profile: dict[str, Any],
    sweep_directions: list[str],
) -> tuple[float, str]:
    behavior = profile["sweep_ratio"]
    direction = "up" if rng.random() < behavior["up_probability"] else "down"
    if len(sweep_directions) >= 2 and sweep_directions[-1] == sweep_directions[-2] == direction:
        direction = "down" if direction == "up" else "up"
    sweep_directions.append(direction)
    del sweep_directions[:-3]
    return rng.uniform(*behavior[direction]), direction


def periodic_spacing(
    rng: random.Random,
    bounds_ms: list[float],
    recent_spacings_ms: list[float],
) -> float:
    spacing = rng.uniform(*bounds_ms)
    for _ in range(16):
        repeated = any(abs(spacing - previous) <= max(3.0, previous * 0.08) for previous in recent_spacings_ms[-2:])
        if not repeated:
            break
        spacing = rng.uniform(*bounds_ms)
    recent_spacings_ms.append(spacing)
    del recent_spacings_ms[:-3]
    return spacing


def make_event(
    rng: random.Random,
    profile: dict[str, Any],
    start_seconds: float,
    episode: int,
    position: int,
    cluster_pan: float,
    recent_frequencies: list[float],
    sweep_directions: list[str],
    forced_type: str | None = None,
) -> dict[str, Any]:
    event_type = forced_type or weighted_choice(rng, profile["event_type_weights"])
    duration_ms = biased_between(rng, profile["duration_ms_by_type"][event_type])
    frequency = reject_pitch_pattern(rng, profile, recent_frequencies)
    oscillator = weighted_choice(rng, profile["oscillator_weights"])
    gain = biased_between(rng, profile["event_gain"], power=1.45)
    pan_low, pan_high = profile["stereo_pan"]
    pan = clamp(cluster_pan + rng.uniform(-0.035, 0.035), pan_low, pan_high)
    maximum = profile["maximum_rendered_frequency_hz"]
    frequency_end = frequency
    direction: str | None = None
    secondary: dict[str, Any] | None = None
    steps: list[dict[str, float]] | None = None

    if event_type == "click":
        frequency_end = frequency * rng.uniform(0.78, 1.22)
        attack_ms = rng.uniform(0.4, 1.4)
    elif event_type == "pip":
        frequency_end = frequency * rng.uniform(0.97, 1.035)
        attack_ms = rng.uniform(1.5, 4.5)
    elif event_type == "sweep":
        sweep_ratio, direction = draw_sweep_ratio(rng, profile, sweep_directions)
        frequency_end = frequency * sweep_ratio
        attack_ms = rng.uniform(2.0, 6.0)
    elif event_type == "dual":
        if rng.random() < 0.46:
            sweep_ratio, direction = draw_sweep_ratio(rng, profile, sweep_directions)
            frequency_end = frequency * math.sqrt(sweep_ratio)
        else:
            frequency_end = frequency * rng.uniform(0.96, 1.05)
        attack_ms = rng.uniform(2.0, 6.0)
        secondary_ratio = draw_dual_ratio(rng, profile["dual_tone_ratio"])
        secondary_start = clamp(frequency * secondary_ratio, 90.0, maximum)
        secondary_end = clamp(frequency_end * secondary_ratio, 90.0, maximum)
        secondary = {
            "oscillator": "sine" if rng.random() < 0.72 else "triangle",
            "start_frequency_hz": rounded(secondary_start, 2),
            "end_frequency_hz": rounded(secondary_end, 2),
            "gain_ratio": rounded(rng.uniform(*profile["dual_secondary_gain"]), 4),
        }
    elif event_type == "stepped":
        attack_ms = rng.uniform(1.0, 4.0)
        step_count = rng.randint(*profile["step_count"])
        boundaries = sorted(rng.uniform(0.20, 0.82) for _ in range(step_count - 1))
        ratios = [1.0]
        for _ in range(step_count - 1):
            ratio = rng.uniform(*profile["stepped_ratio"])
            for _ in range(16):
                if all(abs(ratio - old) > 0.08 for old in ratios[-2:]):
                    break
                ratio = rng.uniform(*profile["stepped_ratio"])
            ratios.append(ratio)
        steps = [
            {
                "at_fraction": rounded(boundary, 5),
                "frequency_hz": rounded(clamp(frequency * ratio, 90.0, maximum), 2),
            }
            for boundary, ratio in zip([0.0, *boundaries], ratios)
        ]
        frequency_end = steps[-1]["frequency_hz"]
    else:
        raise ValueError(f"unsupported event type: {event_type}")

    frequency_end = clamp(frequency_end, 90.0, maximum)
    event = {
        "episode": episode,
        "position_in_episode": position,
        "start_ms": rounded(start_seconds * 1000.0, 3),
        "duration_ms": rounded(duration_ms, 3),
        "type": event_type,
        "oscillator": oscillator,
        "start_frequency_hz": rounded(frequency, 2),
        "end_frequency_hz": rounded(frequency_end, 2),
        "gain": rounded(gain, 5),
        "pan": rounded(pan, 4),
        "attack_ms": rounded(min(attack_ms, duration_ms * 0.22), 3),
    }
    if direction is not None:
        event["sweep_direction"] = direction
    if secondary is not None:
        event["secondary"] = secondary
    if steps is not None:
        event["frequency_steps"] = steps
    return event


def build_schedule(profile: dict[str, Any], duration_seconds: float) -> tuple[list[dict[str, Any]], list[int]]:
    rng = random.Random(profile["seed"])
    events: list[dict[str, Any]] = []
    episode_sizes: list[int] = []
    recent_frequencies: list[float] = []
    recent_spacings_ms: list[float] = []
    sweep_directions: list[str] = []
    cursor = rng.uniform(0.08, 0.15)
    episode = 0

    while cursor < duration_seconds - 0.12:
        requested_size = int(weighted_choice(rng, profile["cluster_size_weights"]))
        cluster_pan = rng.uniform(*profile["stereo_pan"])
        starts = [cursor]
        for _ in range(1, requested_size):
            spacing_ms = periodic_spacing(rng, profile["intra_cluster_start_spacing_ms"], recent_spacings_ms)
            starts.append(starts[-1] + spacing_ms / 1000.0)

        episode_events: list[dict[str, Any]] = []
        for position, start in enumerate(starts):
            if start >= duration_seconds - 0.025:
                break
            event = make_event(
                rng,
                profile,
                start,
                episode,
                position,
                cluster_pan,
                recent_frequencies,
                sweep_directions,
            )
            remaining_ms = (duration_seconds - start) * 1000.0
            event["duration_ms"] = rounded(min(event["duration_ms"], remaining_ms), 3)
            episode_events.append(event)
        if not episode_events:
            break
        events.extend(episode_events)
        episode_sizes.append(len(episode_events))
        last_end = max((event["start_ms"] + event["duration_ms"]) / 1000.0 for event in episode_events)
        cursor = last_end + rng.uniform(*profile["post_cluster_silence_ms"]) / 1000.0
        episode += 1

    if events[-1]["start_ms"] < 9600.0:
        tail_start = rng.uniform(9.64, 9.78)
        tail = make_event(
            rng,
            profile,
            tail_start,
            episode,
            0,
            rng.uniform(*profile["stereo_pan"]),
            recent_frequencies,
            sweep_directions,
        )
        tail["duration_ms"] = rounded(min(tail["duration_ms"], (duration_seconds - tail_start) * 1000.0), 3)
        events.append(tail)
        episode_sizes.append(1)

    events.sort(key=lambda event: event["start_ms"])
    missing_types = sorted(set(profile["event_type_weights"]) - {event["type"] for event in events})
    for missing_index, missing_type in enumerate(missing_types, 1):
        center = round(len(events) * missing_index / (len(missing_types) + 1))
        replacement_index = max(1, min(len(events) - 2, center + rng.randint(-2, 2)))
        original = events[replacement_index]
        events[replacement_index] = make_event(
            rng,
            profile,
            original["start_ms"] / 1000.0,
            original["episode"],
            original["position_in_episode"],
            original["pan"],
            recent_frequencies,
            sweep_directions,
            forced_type=missing_type,
        )
    for index, event in enumerate(events, 1):
        event["event_id"] = f"{profile['id']}-{index:03d}"
    return events, episode_sizes


def waveform_value(kind: str, phase: float, harmonics: tuple[int, ...]) -> float:
    if kind == "sine":
        return math.sin(phase)
    if kind == "triangle":
        total = 0.0
        for harmonic in harmonics:
            sign = -1.0 if ((harmonic - 1) // 2) % 2 else 1.0
            total += sign * math.sin(harmonic * phase) / (harmonic * harmonic)
        return clamp((8.0 / (math.pi * math.pi)) * total, -1.0, 1.0)
    if kind == "square":
        total = sum(math.sin(harmonic * phase) / harmonic for harmonic in harmonics)
        return clamp((4.0 / math.pi) * total, -1.0, 1.0)
    if kind == "sawtooth":
        total = sum((1.0 if harmonic % 2 else -1.0) * math.sin(harmonic * phase) / harmonic for harmonic in harmonics)
        return clamp((2.0 / math.pi) * total, -1.0, 1.0)
    raise ValueError(f"unsupported oscillator: {kind}")


def harmonic_series(kind: str, maximum_frequency: float, sample_rate: int) -> tuple[int, ...]:
    highest = max(1, int((sample_rate * 0.45) / max(maximum_frequency, 1.0)))
    if kind == "sine":
        return (1,)
    if kind == "triangle":
        return tuple(value for value in (1, 3, 5, 7, 9) if value <= highest) or (1,)
    if kind == "square":
        return tuple(value for value in (1, 3, 5, 7) if value <= highest) or (1,)
    if kind == "sawtooth":
        return tuple(value for value in (1, 2, 3, 4, 5) if value <= highest) or (1,)
    raise ValueError(f"unsupported oscillator: {kind}")


def envelope(sample_index: int, sample_count: int, attack_samples: int, event_type: str) -> float:
    if sample_count <= 1:
        return 0.0
    if sample_index < attack_samples:
        position = sample_index / max(1, attack_samples)
        return math.sin(position * math.pi / 2.0) ** 2
    release = (sample_index - attack_samples) / max(1, sample_count - attack_samples - 1)
    if event_type == "click":
        return max(0.0, (1.0 - release) ** 1.8 * math.exp(-4.4 * release))
    return max(0.0, (1.0 - release) ** 1.35 * math.exp(-2.15 * release))


def render_voice(
    left: array,
    right: array,
    event: dict[str, Any],
    sample_rate: int,
    oscillator: str,
    start_frequency: float,
    end_frequency: float,
    gain_scale: float,
    frequency_steps: list[dict[str, float]] | None = None,
) -> None:
    start_frame = round(event["start_ms"] * sample_rate / 1000.0)
    sample_count = max(1, round(event["duration_ms"] * sample_rate / 1000.0))
    sample_count = min(sample_count, len(left) - start_frame)
    attack_samples = max(1, round(event["attack_ms"] * sample_rate / 1000.0))
    maximum_frequency = max(
        start_frequency,
        end_frequency,
        *(step["frequency_hz"] for step in frequency_steps or []),
    )
    harmonics = harmonic_series(oscillator, maximum_frequency, sample_rate)
    pan_angle = (event["pan"] + 1.0) * math.pi / 4.0
    left_gain = math.cos(pan_angle)
    right_gain = math.sin(pan_angle)
    amplitude = event["gain"] * gain_scale
    phase = 0.0
    frequency = start_frequency
    exponential_step = (end_frequency / max(start_frequency, 1.0)) ** (1.0 / max(1, sample_count - 1))
    step_index = 0

    for offset in range(sample_count):
        position = offset / max(1, sample_count - 1)
        if frequency_steps:
            while step_index + 1 < len(frequency_steps) and position >= frequency_steps[step_index + 1]["at_fraction"]:
                step_index += 1
            frequency = frequency_steps[step_index]["frequency_hz"]
        elif offset:
            frequency *= exponential_step
        phase += math.tau * frequency / sample_rate
        value = waveform_value(oscillator, phase, harmonics)
        value *= envelope(offset, sample_count, attack_samples, event["type"]) * amplitude
        frame = start_frame + offset
        left[frame] += value * left_gain
        right[frame] += value * right_gain


def render_schedule(
    events: list[dict[str, Any]],
    sample_rate: int,
    duration_seconds: float,
    target_peak_dbfs: float,
) -> tuple[array, array, dict[str, float]]:
    frame_count = round(sample_rate * duration_seconds)
    left = array("f", [0.0]) * frame_count
    right = array("f", [0.0]) * frame_count
    for event in events:
        render_voice(
            left,
            right,
            event,
            sample_rate,
            event["oscillator"],
            event["start_frequency_hz"],
            event["end_frequency_hz"],
            1.0,
            event.get("frequency_steps"),
        )
        if "secondary" in event:
            secondary = event["secondary"]
            render_voice(
                left,
                right,
                event,
                sample_rate,
                secondary["oscillator"],
                secondary["start_frequency_hz"],
                secondary["end_frequency_hz"],
                secondary["gain_ratio"],
            )

    source_peak = max(max(abs(value) for value in left), max(abs(value) for value in right))
    target_peak = 10.0 ** (target_peak_dbfs / 20.0)
    master_gain = target_peak / source_peak if source_peak else 1.0
    for index in range(frame_count):
        left[index] *= master_gain
        right[index] *= master_gain
    return left, right, {
        "source_peak_linear": rounded(source_peak, 7),
        "audition_master_gain": rounded(master_gain, 7),
        "rendered_peak_linear": rounded(target_peak, 7),
        "rendered_peak_dbfs": rounded(target_peak_dbfs, 3),
    }


def write_pcm16_wav(path: Path, left: array, right: array, sample_rate: int) -> None:
    pcm = array("h")
    for left_value, right_value in zip(left, right):
        pcm.append(round(clamp(left_value, -1.0, 1.0) * 32767.0))
        pcm.append(round(clamp(right_value, -1.0, 1.0) * 32767.0))
    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def validate_wav(path: Path, expected_frames: int, sample_rate: int) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        result = {
            "channels": wav.getnchannels(),
            "sample_width_bytes": wav.getsampwidth(),
            "sample_rate_hz": wav.getframerate(),
            "frames": wav.getnframes(),
            "duration_seconds": rounded(wav.getnframes() / wav.getframerate(), 6),
            "compression": wav.getcomptype(),
        }
    expected = {
        "channels": 2,
        "sample_width_bytes": 2,
        "sample_rate_hz": sample_rate,
        "frames": expected_frames,
        "compression": "NONE",
    }
    for field, value in expected.items():
        if result[field] != value:
            raise ValueError(f"invalid WAV {field} for {path}: {result[field]!r} != {value!r}")
    return result


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def encode_mp3(ffmpeg: str, wav_path: Path, mp3_path: Path) -> None:
    run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wav_path),
            "-map_metadata",
            "-1",
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "256k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(mp3_path),
        ]
    )


def probe_mp3(ffprobe: str, mp3_path: Path) -> dict[str, Any]:
    result = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,channel_layout,bit_rate:format=duration,size",
            "-of",
            "json",
            str(mp3_path),
        ]
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    format_data = data["format"]
    probe = {
        "codec": stream["codec_name"],
        "sample_rate_hz": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "channel_layout": stream.get("channel_layout"),
        "bit_rate_bps": int(stream["bit_rate"]),
        "duration_seconds": rounded(float(format_data["duration"]), 6),
        "file_size_bytes": int(format_data["size"]),
    }
    if probe["codec"] != "mp3" or probe["sample_rate_hz"] != 48000 or probe["channels"] != 2:
        raise ValueError(f"unexpected MP3 probe result for {mp3_path}: {probe}")
    return probe


def full_decode(ffmpeg: str, mp3_path: Path) -> None:
    run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(mp3_path),
            "-f",
            "null",
            "-",
        ]
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_values(items: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items()))


def maximum_silent_gap(events: list[dict[str, Any]], duration_seconds: float) -> float:
    intervals = sorted(
        (event["start_ms"] / 1000.0, (event["start_ms"] + event["duration_ms"]) / 1000.0)
        for event in events
    )
    current_end = 0.0
    maximum_gap = 0.0
    for start, end in intervals:
        maximum_gap = max(maximum_gap, start - current_end)
        current_end = max(current_end, end)
    maximum_gap = max(maximum_gap, duration_seconds - current_end)
    return maximum_gap


def observed_frequency_range(events: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for event in events:
        values.extend((event["start_frequency_hz"], event["end_frequency_hz"]))
        values.extend(step["frequency_hz"] for step in event.get("frequency_steps", []))
        if "secondary" in event:
            values.extend(
                (
                    event["secondary"]["start_frequency_hz"],
                    event["secondary"]["end_frequency_hz"],
                )
            )
    return [rounded(min(values), 2), rounded(max(values), 2)]


def schedule_validation(
    profile: dict[str, Any],
    events: list[dict[str, Any]],
    episode_sizes: list[int],
    duration_seconds: float,
) -> dict[str, Any]:
    if len(events) < 30:
        raise ValueError(f"too few micro-events in {profile['id']}: {len(events)}")
    required_types = set(profile["event_type_weights"])
    observed_types = {event["type"] for event in events}
    if required_types - observed_types:
        raise ValueError(f"missing event types in {profile['id']}: {required_types - observed_types}")
    if not any(size == 1 for size in episode_sizes) or not any(size >= 2 for size in episode_sizes):
        raise ValueError(f"{profile['id']} needs both isolated events and clusters")
    if events[0]["start_ms"] > 170.0:
        raise ValueError(f"first activity is too late in {profile['id']}")
    if events[-1]["start_ms"] < 9600.0:
        raise ValueError(f"last activity is too early in {profile['id']}")
    duration_values = [event["duration_ms"] for event in events]
    if min(duration_values) < 19.5 or max(duration_values) > 250.0:
        raise ValueError(f"event duration outside the audition contract in {profile['id']}")

    events_per_second = [0] * math.ceil(duration_seconds)
    for event in events:
        bucket = min(len(events_per_second) - 1, int(event["start_ms"] // 1000))
        events_per_second[bucket] += 1
    if any(count == 0 for count in events_per_second):
        raise ValueError(f"activity is not distributed across every second in {profile['id']}: {events_per_second}")

    maximum_gap = maximum_silent_gap(events, duration_seconds)
    if maximum_gap > 0.75:
        raise ValueError(f"excessive silent gap in {profile['id']}: {maximum_gap:.3f}s")
    return {
        "event_count": len(events),
        "episode_count": len(episode_sizes),
        "isolated_episode_count": sum(size == 1 for size in episode_sizes),
        "cluster_episode_count": sum(size >= 2 for size in episode_sizes),
        "episode_size_counts": count_values(str(size) for size in episode_sizes),
        "event_type_counts": count_values(event["type"] for event in events),
        "oscillator_counts": count_values(event["oscillator"] for event in events),
        "observed_frequency_hz": observed_frequency_range(events),
        "observed_duration_ms": [rounded(min(duration_values), 3), rounded(max(duration_values), 3)],
        "observed_gain": [rounded(min(event["gain"] for event in events), 5), rounded(max(event["gain"] for event in events), 5)],
        "first_onset_ms": events[0]["start_ms"],
        "last_onset_ms": events[-1]["start_ms"],
        "last_event_end_ms": rounded(max(event["start_ms"] + event["duration_ms"] for event in events), 3),
        "maximum_silent_gap_ms": rounded(maximum_gap * 1000.0, 3),
        "onsets_per_one_second_bin": events_per_second,
    }


def validate_profile_document(document: dict[str, Any]) -> None:
    if document.get("schema_version") != 1 or len(document.get("profiles", [])) != 5:
        raise ValueError("the audition profile document must contain schema version 1 and five profiles")
    filenames: set[str] = set()
    for profile in document["profiles"]:
        for field in ("oscillator_weights", "event_type_weights", "cluster_size_weights"):
            total = sum(profile[field].values())
            if not math.isclose(total, 1.0, abs_tol=1e-8):
                raise ValueError(f"weights do not sum to one for {profile['id']} {field}: {total}")
        if profile["filename"] in filenames:
            raise ValueError(f"duplicate output filename: {profile['filename']}")
        filenames.add(profile["filename"])


def tool_path(name: str, sibling_of: str | None = None) -> str:
    located = shutil.which(name)
    if located:
        return located
    if sibling_of:
        sibling = Path(sibling_of).with_name(f"{name}.exe" if sys.platform == "win32" else name)
        if sibling.is_file():
            return str(sibling)
    raise RuntimeError(f"required existing tool is unavailable: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the five audio-only Thinking Pulse audition candidates.")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keep-wav", action="store_true", help="Also retain the PCM16 intermediates beside the MP3 files.")
    args = parser.parse_args()

    profile_path = args.profiles.absolute()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    document = json.loads(profile_path.read_text(encoding="utf-8"))
    validate_profile_document(document)
    common = document["common"]
    sample_rate = int(common["sample_rate_hz"])
    duration_seconds = float(common["duration_seconds"])
    expected_frames = round(sample_rate * duration_seconds)
    ffmpeg = tool_path("ffmpeg")
    ffprobe = tool_path("ffprobe", ffmpeg)
    ffmpeg_version = run_checked([ffmpeg, "-version"]).stdout.splitlines()[0]
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="graci-thinking-pulse-") as temporary:
        temporary_path = Path(temporary)
        for profile in document["profiles"]:
            events, episode_sizes = build_schedule(profile, duration_seconds)
            validation = schedule_validation(profile, events, episode_sizes, duration_seconds)
            left, right, render_levels = render_schedule(
                events,
                sample_rate,
                duration_seconds,
                float(common["master_peak_target_dbfs"]),
            )
            wav_path = temporary_path / f"{profile['id']}.wav"
            write_pcm16_wav(wav_path, left, right, sample_rate)
            wav_validation = validate_wav(wav_path, expected_frames, sample_rate)
            mp3_path = output / profile["filename"]
            encode_mp3(ffmpeg, wav_path, mp3_path)
            full_decode(ffmpeg, mp3_path)
            mp3_probe = probe_mp3(ffprobe, mp3_path)
            if not 9.9 <= mp3_probe["duration_seconds"] <= 10.2:
                raise ValueError(f"unexpected encoded duration for {mp3_path}: {mp3_probe['duration_seconds']}")
            if args.keep_wav:
                shutil.copy2(wav_path, output / f"{Path(profile['filename']).stem}.wav")
            results.append(
                {
                    "candidate": profile["candidate"],
                    "id": profile["id"],
                    "display_name": profile["display_name"],
                    "filename": profile["filename"],
                    "seed": profile["seed"],
                    "schedule_validation": validation,
                    "render_levels": render_levels,
                    "wav_intermediate_validation": wav_validation,
                    "mp3_validation": mp3_probe,
                    "sha256": sha256(mp3_path),
                    "events": events,
                }
            )

    manifest = {
        "schema_version": 1,
        "set_id": document["set_id"],
        "purpose": document["purpose"],
        "production_integration_performed": False,
        "circuitry_modified": False,
        "cloud_calls": False,
        "profile_document": profile_path.name,
        "generator": Path(__file__).name,
        "generator_runtime": f"Python {sys.version.split()[0]} standard library",
        "encoder": ffmpeg_version,
        "encoding": "libmp3lame, 256 kbit/s, 48 kHz, stereo, metadata stripped",
        "validation": "PCM structure checked, FFprobe metadata checked, and each complete MP3 decoded successfully",
        "candidates": results,
    }
    (output / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for item in results:
        details = item["schedule_validation"]
        print(
            f"{item['filename']}: {details['event_count']} events, "
            f"last onset {details['last_onset_ms']:.1f} ms, "
            f"max silence {details['maximum_silent_gap_ms']:.1f} ms, "
            f"sha256 {item['sha256'][:12]}..."
        )
    print(f"Manifest: {output / MANIFEST_NAME}")


if __name__ == "__main__":
    main()
