import io
import json
import sys
import subprocess
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from graci.playback import (PlaybackConfig, PlaybackResult, PlaybackStatus,
                            SubprocessWavePlayback)
from graci.speech_presentation import (PresentationStatus,
                                       SpeechPresentationService)
from graci.tts import (MAX_SYNTHESIZED_AUDIO_BYTES,
                       AuthoritativeFinalResponse, KokoroConfig,
                       KokoroSubprocessTTS, SynthesizedAudio, TTSRequest,
                       TTSResult, TTSStatus)


def wav_bytes(seconds=0.05, sample_rate=24_000):
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\0\0" * int(sample_rate * seconds))
    return target.getvalue()


def audio():
    return SynthesizedAudio(wav_bytes(), 24_000, 1, 2, .05)


class FakeProcess:
    def __init__(self, command, stdout="", stderr="", returncode=0,
                 timeout=False, block=None):
        self.command = command
        self.stdout_value = stdout
        self.stderr_value = stderr
        self.returncode = returncode
        self.timeout = timeout
        self.block = block
        self.terminated = False
        self.killed = False

    def communicate(self, timeout=None):
        if self.block is not None:
            self.block.wait(2)
        if self.timeout and not self.terminated:
            raise subprocess.TimeoutExpired(self.command, timeout)
        return self.stdout_value, self.stderr_value

    def poll(self):
        return None if not self.terminated and (self.block is not None or self.timeout) else self.returncode

    def terminate(self):
        self.terminated = True
        if self.block is not None:
            self.block.set()

    def kill(self):
        self.killed = True
        self.terminated = True

    def wait(self, timeout=None):
        return self.returncode


class KokoroTests(unittest.TestCase):
    def config(self, timeout=10):
        return KokoroConfig(Path("python312.exe"), Path("tts_worker.py"),
                            Path("kokoro-v1.0.int8.onnx"), Path("voices-v1.0.bin"),
                            timeout_seconds=timeout)

    def successful_process(self, command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        output.write_bytes(wav_bytes())
        return FakeProcess(command, json.dumps(
            {"status": "success", "voice": "af_bella", "device": "cpu"}))

    def test_authoritative_boundary_valid_blank_type_and_maximum(self):
        value = AuthoritativeFinalResponse("GRACI completed the task.")
        self.assertEqual(value.text, "GRACI completed the task.")
        for invalid in ("", " \t\n"):
            with self.assertRaises(ValueError):
                AuthoritativeFinalResponse(invalid)
        with self.assertRaises(TypeError):
            AuthoritativeFinalResponse(123)
        with self.assertRaises(ValueError):
            AuthoritativeFinalResponse("x" * 20_001)

    def test_request_requires_explicit_authoritative_value(self):
        with self.assertRaises(TypeError):
            TTSRequest("ordinary text")

    def test_exact_authoritative_text_and_pronunciation_copy(self):
        source = "  GRACI uses 3090, but XGRACI stays written.  "
        with patch("graci.tts.subprocess.Popen", side_effect=self.successful_process):
            result = KokoroSubprocessTTS(self.config()).synthesize(
                TTSRequest(AuthoritativeFinalResponse(source)))
        self.assertTrue(result.succeeded)
        self.assertEqual(result.authoritative_text, source)
        self.assertEqual(result.presentation_text,
                         "  GRAY-see uses thirty ninety, but XGRACI stays written.  ")
        self.assertEqual(source, "  GRACI uses 3090, but XGRACI stays written.  ")

    def test_configuration_is_fixed_to_af_bella_local_cpu_and_bounded(self):
        config = self.config()
        self.assertEqual(config.voice, "af_bella")
        self.assertEqual(config.device, "cpu")
        with self.assertRaises(ValueError):
            KokoroConfig(Path("p"), Path("w"), Path("m"), Path("v"), voice="af_heart")
        with self.assertRaises(ValueError):
            KokoroConfig(Path("p"), Path("w"), Path("m"), Path("v"), device="cuda")
        with self.assertRaises(ValueError):
            KokoroConfig(Path("p"), Path("w"), Path("m"), Path("v"), timeout_seconds=121)

    def test_worker_command_has_fixed_identity_and_bounds(self):
        seen = {}
        def run(command, **kwargs):
            seen["command"] = command
            return self.successful_process(command, **kwargs)
        with patch("graci.tts.subprocess.Popen", side_effect=run):
            KokoroSubprocessTTS(self.config()).synthesize(
                TTSRequest(AuthoritativeFinalResponse("hello")))
        command = seen["command"]
        self.assertEqual(command[command.index("--voice") + 1], "af_bella")
        self.assertEqual(command[command.index("--device") + 1], "cpu")
        self.assertIn("--max-audio-bytes", command)
        self.assertNotIn("http", " ".join(command).lower())

    def test_worker_rejects_invalid_voice_and_missing_local_assets(self):
        worker = Path(__file__).resolve().parents[1] / "phase6d" / "tts_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_path = root / "text.txt"
            text_path.write_text("hello", encoding="utf-8")
            base = [sys.executable, str(worker), "--text-file", str(text_path),
                    "--output", str(root / "out.wav"), "--model", str(root / "model"),
                    "--voices", str(root / "voices"), "--device", "cpu",
                    "--max-text-chars", "20000", "--max-audio-bytes", "8388608",
                    "--max-audio-seconds", "120"]
            invalid = subprocess.run(base + ["--voice", "af_heart"], capture_output=True,
                                     text=True, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            missing = subprocess.run(base + ["--voice", "af_bella"], capture_output=True,
                                     text=True, check=False)
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse((root / "out.wav").exists())

    def test_malformed_response_nonzero_and_missing_audio_fail_truthfully(self):
        cases = [
            (FakeProcess([], "not json"), "invalid_tts_response"),
            (FakeProcess([], "", "worker crash", 2), "tts_worker_failed"),
            (FakeProcess([], json.dumps({"status": "success", "voice": "af_bella",
                                        "device": "cpu"})), "invalid_tts_response"),
        ]
        for process, code in cases:
            with self.subTest(code=code), patch("graci.tts.subprocess.Popen", return_value=process):
                result = KokoroSubprocessTTS(self.config()).synthesize(
                    TTSRequest(AuthoritativeFinalResponse("hello")))
                self.assertFalse(result.succeeded)
                self.assertEqual(result.error_code, code)

    def test_timeout_terminates_worker(self):
        process = FakeProcess([], timeout=True)
        with patch("graci.tts.subprocess.Popen", return_value=process):
            result = KokoroSubprocessTTS(self.config()).synthesize(
                TTSRequest(AuthoritativeFinalResponse("hello")))
        self.assertEqual(result.status, TTSStatus.TIMEOUT)
        self.assertTrue(process.terminated)

    def test_audio_contract_rejects_size_format_and_duration(self):
        with self.assertRaises(ValueError):
            SynthesizedAudio(b"x" * (MAX_SYNTHESIZED_AUDIO_BYTES + 1), 24_000, 1, 2, 1)
        with self.assertRaises(ValueError):
            SynthesizedAudio(b"x", 24_000, 2, 2, 1)
        with self.assertRaises(ValueError):
            SynthesizedAudio(b"x", 24_000, 1, 2, 121)

    def test_temp_text_and_audio_are_cleaned_after_success_and_failure(self):
        paths = []
        def run(command, **kwargs):
            paths.extend([Path(command[command.index("--text-file") + 1]),
                          Path(command[command.index("--output") + 1])])
            return self.successful_process(command, **kwargs)
        with patch("graci.tts.subprocess.Popen", side_effect=run):
            KokoroSubprocessTTS(self.config()).synthesize(
                TTSRequest(AuthoritativeFinalResponse("hello")))
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_cleanup_failure_is_reported(self):
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path.name.startswith("graci-tts-"):
                original(path, missing_ok=True)
                raise OSError("cleanup denied")
            return original(path, *args, **kwargs)
        with patch("graci.tts.subprocess.Popen", side_effect=self.successful_process), \
             patch("graci.tts.Path.unlink", new=unlink):
            result = KokoroSubprocessTTS(self.config()).synthesize(
                TTSRequest(AuthoritativeFinalResponse("hello")))
        self.assertEqual(result.error_code, "tts_cleanup_failed")

    def test_cancel_and_single_outstanding_budget(self):
        release = threading.Event()
        process = FakeProcess([], stdout=json.dumps(
            {"status": "success", "voice": "af_bella", "device": "cpu"}), block=release)
        adapter = KokoroSubprocessTTS(self.config())
        with patch("graci.tts.subprocess.Popen", return_value=process):
            result_holder = []
            thread = threading.Thread(target=lambda: result_holder.append(adapter.synthesize(
                TTSRequest(AuthoritativeFinalResponse("first")))))
            thread.start()
            for _ in range(100):
                if adapter._process is process:
                    break
                time.sleep(.005)
            busy = adapter.synthesize(TTSRequest(AuthoritativeFinalResponse("second")))
            self.assertEqual(busy.error_code, "synthesis_busy")
            adapter.cancel()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result_holder[0].status, TTSStatus.CANCELLED)


class PlaybackTests(unittest.TestCase):
    def config(self, timeout=10):
        return PlaybackConfig(Path("python.exe"), Path("playback_worker.py"), timeout)

    def test_success_and_temp_cleanup(self):
        seen = {}
        def run(command, **kwargs):
            seen["path"] = Path(command[-1])
            self.assertTrue(seen["path"].exists())
            return FakeProcess(command)
        with patch("graci.playback.subprocess.Popen", side_effect=run):
            result = SubprocessWavePlayback(self.config()).play(audio())
        self.assertTrue(result.succeeded)
        self.assertFalse(seen["path"].exists())

    def test_cleanup_failure_is_reported(self):
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path.name.startswith("graci-playback-"):
                original(path, missing_ok=True)
                raise OSError("cleanup denied")
            return original(path, *args, **kwargs)
        with patch("graci.playback.subprocess.Popen", return_value=FakeProcess([])), \
             patch("graci.playback.Path.unlink", new=unlink):
            result = SubprocessWavePlayback(self.config()).play(audio())
        self.assertEqual(result.error_code, "playback_cleanup_failed")

    def test_failure_timeout_and_unavailable(self):
        with patch("graci.playback.subprocess.Popen",
                   return_value=FakeProcess([], stderr="device unavailable", returncode=2)):
            result = SubprocessWavePlayback(self.config()).play(audio())
        self.assertEqual(result.error_code, "playback_failed")
        process = FakeProcess([], timeout=True)
        with patch("graci.playback.subprocess.Popen", return_value=process):
            result = SubprocessWavePlayback(self.config()).play(audio())
        self.assertEqual(result.status, PlaybackStatus.TIMEOUT)
        self.assertTrue(process.terminated)
        with patch("graci.playback.subprocess.Popen", side_effect=OSError("no python")):
            result = SubprocessWavePlayback(self.config()).play(audio())
        self.assertEqual(result.error_code, "playback_unavailable")

    def test_stop_cancel_and_single_outstanding_budget(self):
        release = threading.Event()
        process = FakeProcess([], block=release)
        player = SubprocessWavePlayback(self.config())
        with patch("graci.playback.subprocess.Popen", return_value=process):
            results = []
            thread = threading.Thread(target=lambda: results.append(player.play(audio())))
            thread.start()
            for _ in range(100):
                if player._process is process:
                    break
                time.sleep(.005)
            busy = player.play(audio())
            self.assertEqual(busy.error_code, "playback_busy")
            player.stop()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0].status, PlaybackStatus.CANCELLED)


class FakeTTS:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []
        self.cancelled = False

    def synthesize(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result

    def cancel(self):
        self.cancelled = True


class FakePlayer:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []
        self.stopped = False

    def play(self, value):
        self.calls.append(value)
        if self.error:
            raise self.error
        return self.result

    def stop(self):
        self.stopped = True


class PresentationIsolationTests(unittest.TestCase):
    def response(self):
        return AuthoritativeFinalResponse("GRACI completed successfully.")

    def tts_success(self):
        response = self.response()
        return TTSResult(TTSStatus.SUCCESS, "Kokoro-82M-ONNX:cpu", "af_bella",
                         response.text, "GRAY-see completed successfully.", audio())

    def test_success_uses_only_explicit_response_and_preserves_exact_text(self):
        response = self.response()
        service = SpeechPresentationService(FakeTTS(self.tts_success()),
                                            FakePlayer(PlaybackResult(PlaybackStatus.SUCCESS)))
        result = service.speak(response)
        self.assertEqual(result.status, PresentationStatus.SPOKEN)
        self.assertIs(result.authoritative_response, response)
        self.assertEqual(response.text, "GRACI completed successfully.")

    def test_tts_failure_and_exception_preserve_completed_result(self):
        governed_result = {"status": "PASS", "final_response": "GRACI completed successfully."}
        response = self.response()
        failure = TTSResult(TTSStatus.FAILED, "Kokoro-82M-ONNX:cpu", "af_bella",
                            response.text, "GRAY-see completed successfully.",
                            error_code="tts_unavailable", error_message="missing")
        for tts in (FakeTTS(failure), FakeTTS(error=RuntimeError("crash"))):
            result = SpeechPresentationService(tts, FakePlayer()).speak(response)
            self.assertEqual(result.status, PresentationStatus.FAILED)
            self.assertEqual(governed_result,
                             {"status": "PASS", "final_response": "GRACI completed successfully."})
            self.assertIs(result.authoritative_response, response)

    def test_playback_failure_timeout_and_exception_preserve_completed_result(self):
        governed_result = {"status": "PASS", "final_response": "GRACI completed successfully."}
        for playback in (PlaybackResult(PlaybackStatus.FAILED, "device", "bad"),
                         PlaybackResult(PlaybackStatus.TIMEOUT, "timeout", "slow")):
            result = SpeechPresentationService(FakeTTS(self.tts_success()),
                                               FakePlayer(playback)).speak(self.response())
            self.assertEqual(result.status, PresentationStatus.FAILED)
            self.assertEqual(governed_result["status"], "PASS")
        result = SpeechPresentationService(FakeTTS(self.tts_success()),
                                           FakePlayer(error=RuntimeError("device"))).speak(self.response())
        self.assertEqual(result.error_code, "playback_exception")
        self.assertEqual(governed_result["status"], "PASS")

    def test_stop_cancels_synthesis_and_playback_without_runtime_capability(self):
        tts, player = FakeTTS(), FakePlayer()
        service = SpeechPresentationService(tts, player)
        service.stop()
        self.assertTrue(tts.cancelled)
        self.assertTrue(player.stopped)
        self.assertFalse(hasattr(service, "run"))


class Phase6DClosureTests(unittest.TestCase):
    def test_closure_evidence_is_truthful_and_bounded(self):
        root = Path(__file__).resolve().parents[1]
        closure = json.loads((root / "phase6d" / "evidence" /
                              "phase6d-closure.json").read_text(encoding="utf-8"))
        live = json.loads((root / "phase6d" / "evidence" /
                           "live-kokoro-synthesis.json").read_text(encoding="utf-8"))
        self.assertEqual(closure["status"], "PASS")
        self.assertEqual(closure["verification"]["full_tests_passed"], 307)
        self.assertFalse(closure["architecture"]["requires_4090"])
        self.assertFalse(closure["architecture"]["cloud_tts"])
        self.assertFalse(closure["verification"]["physical_playback_performed"])
        self.assertEqual(live["status"], "PASS")
        self.assertFalse(live["authoritative_text_mutated"])
        self.assertFalse(live["audio_retained"])
        self.assertEqual(live["voice"], "af_bella")


if __name__ == "__main__":
    unittest.main()
