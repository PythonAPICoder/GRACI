"""Deterministic acceptance coverage for the symmetric telemetry HUD."""

import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from graci.hardware_telemetry import (
    NVIDIA_FIELDS, NVIDIA_QUERY_TIMEOUT_SECONDS, LocalHardwareTelemetryCollector,
)
from graci.registry import HealthState
from graci.visualizer import HardwareTelemetryView, TelemetryState
from graci.visualizer_backend import VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "graci" / "visualizer_ui"
NOW = datetime(2026, 8, 30, 17, 20, tzinfo=timezone.utc)


class TelemetryContractTests(unittest.TestCase):
    def test_observed_values_are_bounded_and_unobserved_values_fail_closed(self):
        telemetry = HardwareTelemetryView(
            TelemetryState.OBSERVED, NOW, "deterministic-test",
            gpu_utilization_percent=12.5, vram_used_mib=2_048,
            vram_total_mib=24_576, gpu_temperature_c=47,
            cpu_utilization_percent=18.2, ram_used_mib=16_384,
            ram_total_mib=65_536)
        self.assertEqual(telemetry.state, TelemetryState.OBSERVED)
        for invalid in (
            {"state": TelemetryState.OBSERVED},
            {"state": TelemetryState.UNAVAILABLE, "gpu_utilization_percent": 5},
            {"state": TelemetryState.OBSERVED, "observed_at": NOW,
             "gpu_utilization_percent": 101},
            {"state": TelemetryState.OBSERVED, "observed_at": NOW,
             "vram_used_mib": 2, "vram_total_mib": 1},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                HardwareTelemetryView(**invalid)

    def test_primary_collector_uses_exact_bounded_read_only_query(self):
        calls = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(
                arguments, 0, "NVIDIA GeForce RTX 3090, 9, 18827, 24576, 47\n", "")

        collector = LocalHardwareTelemetryCollector(runner=runner, clock=lambda: NOW)
        with patch.object(Path, "is_file", return_value=True), \
             patch.object(collector, "_sample_windows_system",
                          return_value=(18.2, 16_384, 65_536)):
            value = collector.sample_primary()

        self.assertEqual(value.state, TelemetryState.OBSERVED)
        self.assertEqual((value.gpu_utilization_percent, value.vram_used_mib,
                          value.vram_total_mib, value.gpu_temperature_c),
                         (9.0, 18_827, 24_576, 47.0))
        self.assertEqual((value.cpu_utilization_percent, value.ram_used_mib,
                          value.ram_total_mib), (18.2, 16_384, 65_536))
        arguments, kwargs = calls[0]
        self.assertEqual(arguments[1:], [f"--query-gpu={NVIDIA_FIELDS}",
                                         "--format=csv,noheader,nounits"])
        self.assertEqual(kwargs["timeout"], NVIDIA_QUERY_TIMEOUT_SECONDS)
        self.assertFalse(kwargs["check"])
        self.assertNotIn("shell", kwargs)

    def test_optional_node_has_no_fabricated_telemetry(self):
        telemetry = LocalHardwareTelemetryCollector.optional_unavailable()
        self.assertEqual(telemetry.state, TelemetryState.UNAVAILABLE)
        self.assertIsNone(telemetry.observed_at)
        self.assertIsNone(telemetry.gpu_utilization_percent)
        self.assertEqual(telemetry.reason,
                         "no_authorized_read_only_4090_telemetry_source")

    def test_publication_does_not_change_health_or_eligibility(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        before_primary = observer.compute.primary_3090
        before_optional = observer.compute.optional_4090
        observer.publish_hardware_telemetry(
            HardwareTelemetryView(TelemetryState.OBSERVED, NOW, "test",
                                  gpu_utilization_percent=10),
            HardwareTelemetryView(TelemetryState.OBSERVED, NOW, "test",
                                  gpu_utilization_percent=2))
        after = provider.snapshot().compute
        self.assertEqual(after.primary_3090.endpoint_health,
                         before_primary.endpoint_health)
        self.assertEqual(after.primary_3090.eligible, before_primary.eligible)
        self.assertEqual(after.optional_4090.endpoint_health,
                         before_optional.endpoint_health)
        self.assertEqual(after.optional_4090.eligible, before_optional.eligible)
        self.assertIs(after.optional_4090.endpoint_health, HealthState.UNKNOWN)
        self.assertIsNone(after.optional_4090.eligible)


class TelemetryPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")
        cls.collector = (ROOT / "graci" / "hardware_telemetry.py").read_text("utf-8")

    def test_symmetric_layout_and_consolidated_controls(self):
        left = self.html.index('id="node-3090"')
        center = self.html.index('class="core-stage"')
        right = self.html.index('id="node-4090"')
        self.assertLess(left, center)
        self.assertLess(center, right)
        self.assertNotIn('class="detail-rail status-rail"', self.html)
        for marker in ('id="status-state"', 'id="status-model"',
                       'id="status-waveform"', 'id="ui-sounds"',
                       'id="motion-setting"', 'id="ptt-button"',
                       'id="restart-button"', 'id="end-session"',
                       'class="pipeline-section"', 'latest-turn-footer'):
            self.assertIn(marker, self.html)
        self.assertIn("grid-template-columns:480px minmax(0,1fr) 480px", self.css)

    def test_fresh_stale_unknown_and_real_value_rendering_are_explicit(self):
        for marker in (
            "TELEMETRY_FRESH_SECONDS = 10", 'telemetry.state==="observed"',
            'age>=-1&&age<=TELEMETRY_FRESH_SECONDS',
            'observed?"stale":telemetry?.state||"unknown"',
            'clearTelemetry(root,observed?"STALE":"NOT OBSERVED")',
            'telemetry.gpu_utilization_percent', 'telemetry.vram_used_mib',
            'telemetry.gpu_temperature_c', 'telemetry.cpu_utilization_percent',
            'telemetry.ram_used_mib', 'telemetry.cpu_temperature_c',
        ):
            self.assertIn(marker, self.js)
        telemetry_renderer = self.js[
            self.js.index("function renderTelemetry"):
            self.js.index("function renderNode")]
        self.assertNotIn("Math.random", telemetry_renderer)

    def test_existing_analyser_ptt_and_accessibility_paths_remain_single_source(self):
        for marker in ("createMediaElementSource", "createAnalyser",
                       "getByteFrequencyData", "for(let i=0;i<64;i++)",
                       'id="speech-radial"', 'id="ptt-button"',
                       "prefers-reduced-motion"):
            self.assertIn(marker, self.js + self.html + self.css)
        self.assertEqual(self.js.count("createAnalyser()"), 1)
        self.assertIn('$("restart-button").classList.add("visible")', self.js)

    def test_collector_adds_no_remote_or_execution_authority(self):
        lowered = self.collector.lower()
        for forbidden in ("shell=true", "requests", "http://", "https://",
                          "socket", "powershell", "ssh", "eligible ="):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("read-only", lowered)
        self.assertIn("timeout=NVIDIA_QUERY_TIMEOUT_SECONDS", self.collector)


if __name__ == "__main__":
    unittest.main()
