"""Static stop gates for code that can administer the Windows host."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "governance" / "HOST_SYSTEM_CHANGE_SURFACES.json"
SOURCE_SUFFIXES = {".ps1", ".py", ".cmd", ".bat", ".js"}
SOURCE_ROOTS = ("ops", "graci", "phase8e", "phase8f")
QUARANTINE_MARKER = "HOST-SYSTEM-CHANGE-QUARANTINE: PO-DEC-039"
QUARANTINED_PHASE8E_ENTRYPOINTS = {
    "configure-phase8e-dedicated-obsidian.ps1",
    "configure-phase8e-obsidian-test.ps1",
    "finalize-phase8e-projection.ps1",
    "install-phase8e-review-boundary.ps1",
    "open-phase8e-review.ps1",
    "promote-phase8e-obsidian-launcher.ps1",
    "remove-phase8e-dedicated-obsidian.ps1",
    "remove-phase8e-obsidian-launcher-promotion.ps1",
    "remove-phase8e-obsidian-test.ps1",
    "remove-phase8e-review-boundary.ps1",
    "retest-phase8e-dedicated-obsidian.ps1",
    "test-phase8e-review-boundary.ps1",
    "test-phase8e-viewer-worker.ps1",
    "verify-phase8e-obsidian-test-rollback.ps1",
    "verify-phase8e-review-boundary.ps1",
}
RISK_PATTERNS = {
    "applocker": re.compile(
        r"\b(?:Get|Set)-AppLockerPolicy\b|<AppLockerPolicy\b|"
        r"\bAppIDSvc\b|\\SrpV2\b|\bAppCache\.dat\b", re.IGNORECASE),
    "code_integrity": re.compile(
        r"\bCiTool(?:\.exe)?\b|\b(?:New|Set|Merge|Remove)-CIPolicy\b|"
        r"\bConvertFrom-CIPolicy\b|\bVerifiedAndReputableDesktop\b", re.IGNORECASE),
    "defender_security": re.compile(
        r"\b(?:Add|Set|Remove)-MpPreference\b|\bSet-ProcessMitigation\b",
        re.IGNORECASE),
    "firewall": re.compile(
        r"\b(?:New|Set|Remove|Enable|Disable)-NetFirewallRule\b|"
        r"\bnetsh\s+advfirewall\b", re.IGNORECASE),
    "service_configuration": re.compile(
        r"\b(?:Set|New|Remove)-Service\b|"
        r"\bsc(?:\.exe)?\s+(?:config|create|delete)\b", re.IGNORECASE),
    "service_state": re.compile(
        r"\b(?:Start|Stop|Restart)-Service\b|"
        r"\bsc(?:\.exe)?\s+(?:start|stop)\b", re.IGNORECASE),
    "scheduled_tasks": re.compile(
        r"\b(?:Register|Unregister|Set|Disable|Enable)-ScheduledTask\b|"
        r"\bschtasks(?:\.exe)?\b", re.IGNORECASE),
    "accounts_groups": re.compile(
        r"\b(?:New|Set|Remove|Enable|Disable)-LocalUser\b|"
        r"\b(?:Add|Remove)-LocalGroupMember\b|"
        r"\bnet(?:\.exe)?\s+(?:user|localgroup)\b", re.IGNORECASE),
    "filesystem_acl": re.compile(r"\bSet-Acl\b|\bicacls(?:\.exe)?\b", re.IGNORECASE),
    "machine_registry_policy": re.compile(
        r"HKLM(?::|\\).*\\Policies\\|"
        r"\breg(?:\.exe)?\s+(?:add|delete)\s+[^\r\n]*HKLM|"
        r"\b(?:Set|New|Remove)-Item(?:Property)?\b[^\r\n]*"
        r"(?:HKLM|HKEY_LOCAL_MACHINE)", re.IGNORECASE),
    "group_security_policy": re.compile(
        r"\b(?:gpupdate|lgpo)(?:\.exe)?\b|"
        r"\b(?:Get|Set|New|Remove)-GP"
        r"(?:RegistryValue|Link|Inheritance|Permission)\b", re.IGNORECASE),
    "local_security_policy": re.compile(
        r"\b(?:secedit|auditpol)(?:\.exe)?\b", re.IGNORECASE),
    "user_rights_assignment": re.compile(
        r"\b(?:ntrights)(?:\.exe)?\b|\bLsaAddAccountRights\b", re.IGNORECASE),
    "boot_configuration": re.compile(r"\b(?:bcdedit|reagentc)(?:\.exe)?\b", re.IGNORECASE),
}


def source_files():
    paths = []
    for name in SOURCE_ROOTS:
        paths.extend((ROOT / name).rglob("*"))
    paths.extend(path for path in ROOT.iterdir() if path.is_file())
    return sorted({path for path in paths if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES})


def inventory():
    result = {}
    for path in source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        counts = {
            category: len(pattern.findall(text))
            for category, pattern in RISK_PATTERNS.items()
        }
        counts = {category: count for category, count in counts.items() if count}
        if counts:
            result[path.relative_to(ROOT).as_posix()] = counts
    return result


class HostSystemChangeGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_registry_is_review_inventory_not_authority(self):
        self.assertEqual(self.registry["schema_version"], 1)
        self.assertEqual(self.registry["authority"], "PO-DEC-039")
        self.assertIn("does not grant execution authority", self.registry["purpose"])
        self.assertTrue({
            "applocker", "code_integrity", "defender_security", "firewall",
            "service_configuration", "service_state", "scheduled_tasks",
            "accounts_groups", "filesystem_acl", "machine_registry_policy",
            "group_security_policy", "local_security_policy",
            "user_rights_assignment", "boot_configuration",
        }.issubset(RISK_PATTERNS))

    def test_every_host_change_surface_and_occurrence_is_registered(self):
        expected = {
            path: entry["counts"]
            for path, entry in self.registry["surfaces"].items()
        }
        self.assertEqual(inventory(), expected)

    def test_registry_entries_have_reviewable_state_and_recorded_authority(self):
        decisions = (ROOT / "docs" / "decisions" / "DECISION_INDEX.md").read_text("utf-8")
        acceptances = (ROOT / "docs" / "acceptance" / "ACCEPTANCE_INDEX.md").read_text("utf-8")
        for path, entry in self.registry["surfaces"].items():
            with self.subTest(path=path):
                self.assertIn(entry["status"], {"quarantined", "registered_existing"})
                self.assertTrue((ROOT / path).is_file())
                self.assertTrue(
                    entry["authority"] in decisions or entry["authority"] in acceptances)

    def test_quarantined_surfaces_fail_before_first_host_operation(self):
        for relative, entry in self.registry["surfaces"].items():
            if entry["status"] != "quarantined":
                continue
            text = (ROOT / relative).read_text(encoding="utf-8")
            if QUARANTINE_MARKER not in text:
                common_reference = 'phase8e-review-boundary-common.ps1'
                self.assertIn(common_reference, text, relative)
                self.assertLess(text.index(common_reference), self._first_risk(text), relative)
            else:
                marker = text.index(QUARANTINE_MARKER)
                throw = text.index("throw", marker)
                self.assertLess(throw, self._first_risk(text), relative)

    def test_all_dependent_phase8e_host_entrypoints_reach_the_stop_gate_first(self):
        common_reference = 'phase8e-review-boundary-common.ps1'
        for name in QUARANTINED_PHASE8E_ENTRYPOINTS:
            text = (ROOT / "ops" / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                direct = QUARANTINE_MARKER in text
                shared = common_reference in text
                self.assertTrue(direct or shared)
                if shared:
                    self.assertLess(text.index(common_reference), self._first_risk(text)
                                    if any(pattern.search(text) for pattern in RISK_PATTERNS.values())
                                    else len(text))

    def test_rejected_applocker_path_is_not_current_viewer_architecture(self):
        policy = (ROOT / "governance" / "CURRENT_POLICY.md").read_text("utf-8")
        design = (ROOT / "docs" / "PHASE_8E_REPLACEMENT_BOUNDARY_DESIGN.md").read_text("utf-8")
        self.assertIn("AppLocker architecture is unsafe, rejected", policy)
        self.assertIn("must not\nenable AppLocker", design)
        self.assertIn("strict inert-content validation", design)
        self.assertIn("Exact manifest and hashes", design)

    @staticmethod
    def _first_risk(text):
        positions = [
            match.start()
            for pattern in RISK_PATTERNS.values()
            for match in pattern.finditer(text)
        ]
        if not positions:
            raise AssertionError("registered quarantine has no detected host operation")
        return min(positions)


if __name__ == "__main__":
    unittest.main()
