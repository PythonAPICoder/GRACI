import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"


class Phase8EStage3ObsidianTests(unittest.TestCase):
    def test_exact_candidate_and_viewer_scoped_controls(self):
        setup = (OPS / "configure-phase8e-obsidian-test.ps1").read_text("utf-8")
        self.assertIn('"C:\\Users\\Steve\\AppData\\Local\\Programs\\Obsidian"', setup)
        self.assertIn('"c01bbd79583037639f5422396cddb457ef48e89e159ca50a8492bbd1f1f10775"', setup)
        self.assertIn('-Direction Outbound -Action Block', setup)
        self.assertIn('-LocalUser $localUserSddl', setup)
        self.assertIn('"ReadAndExecute, Synchronize"', setup)
        self.assertNotIn('S-1-5-32-545', setup)

    def test_synthetic_test_stays_read_only_and_offline(self):
        worker = (OPS / "test-phase8e-obsidian-worker.ps1").read_text("utf-8")
        self.assertIn("VIEWER_IDENTITY_REQUIRED", worker)
        self.assertIn("projection_write_denied", worker)
        self.assertIn("projection_unchanged", worker)
        self.assertIn("non_loopback_established_connections", worker)
        self.assertIn("--disable-background-networking", worker)

    def test_stage3_does_not_qualify_routine_launch_or_touch_bitlocker(self):
        combined = "\n".join(
            (OPS / name).read_text("utf-8")
            for name in (
                "configure-phase8e-obsidian-test.ps1",
                "test-phase8e-obsidian-worker.ps1",
                "remove-phase8e-obsidian-test.ps1",
            )
        )
        self.assertIn("qualified_for_routine_launch = $false", combined)
        self.assertNotIn("qualified-application.json", combined)
        self.assertNotIn("bitlocker", combined.casefold())

    def test_dedicated_install_is_viewer_specific_and_owner_readable(self):
        setup = (OPS / "configure-phase8e-dedicated-obsidian.ps1").read_text("utf-8")
        worker = (OPS / "test-phase8e-dedicated-obsidian-worker.ps1").read_text("utf-8")
        self.assertIn('"AppData\\Local\\Programs\\Obsidian"', setup)
        self.assertIn('"ReadAndExecute, Synchronize"', setup)
        self.assertIn('-Direction Outbound -Action Block', setup)
        self.assertIn('-LocalUser $localUserSddl', setup)
        self.assertIn("owner_can_read_synthetic_notes", setup)
        self.assertIn("product_owner_obsidian_changed = $false", setup)
        self.assertIn("projection_write_denied", worker)
        self.assertIn("protected_projection_unchanged", worker)
        self.assertIn("non_loopback_established_connections", worker)
        self.assertIn("configuration_parse_error", worker)
        self.assertIn("UTF8Encoding]::new($false)", setup)
        self.assertNotIn("bitlocker", (setup + worker).casefold())

    def test_dedicated_install_has_exact_rollback(self):
        rollback = (OPS / "remove-phase8e-dedicated-obsidian.ps1").read_text("utf-8")
        self.assertIn("created_paths_preexisted", rollback)
        self.assertIn("GetFullPath", rollback)
        self.assertIn("ReparsePoint", rollback)
        self.assertIn("GRACI-Phase8E-Stage3-Obsidian-Dedicated-Viewer-Block", rollback)
        self.assertIn("remove-phase8e-obsidian-launcher-promotion.ps1", rollback)

    def test_routine_launcher_promotion_is_exact_and_synthetic_only(self):
        promote = (OPS / "promote-phase8e-obsidian-launcher.ps1").read_text("utf-8")
        launcher = (OPS / "open-phase8e-review.ps1").read_text("utf-8")
        self.assertIn('"PO-DEC-033"', promote)
        self.assertIn('"qualified-application.json"', promote)
        self.assertIn("routine_viewer_launch_passed", promote)
        self.assertIn("$launcherResult.application_launched", promote)
        self.assertIn("real_data_used = $false", promote)
        self.assertIn("owner_obsidian_processes_stopped = $false", promote)
        self.assertIn("Restore-RoutineLaunch", promote)
        self.assertIn("QUALIFICATION_RECORD_INVALID", launcher)
        self.assertIn("QUALIFIED_APPLICATION_CHANGED", launcher)
        self.assertIn("QUALIFIED_FIREWALL_INVALID", launcher)
        self.assertIn("COMMUNITY_PLUGIN_LIST_INVALID", launcher)
        self.assertIn("COMMUNITY_PLUGIN_DIRECTORY_INVALID", launcher)
        self.assertIn("Start-Process -FilePath $applicationPath", launcher)
        self.assertNotIn("bitlocker", (promote + launcher).casefold())

    def test_routine_launcher_promotion_has_exact_rollback(self):
        rollback = (OPS / "remove-phase8e-obsidian-launcher-promotion.ps1").read_text("utf-8")
        self.assertIn('"PO-DEC-033"', rollback)
        self.assertIn('"qualified-application.json"', rollback)
        self.assertIn("qualification_preexisted", rollback)
        self.assertIn("GetFullPath", (OPS / "remove-phase8e-dedicated-obsidian.ps1").read_text("utf-8"))
        self.assertIn("product_owner_obsidian_changed = $false", rollback)
        self.assertNotIn("bitlocker", rollback.casefold())

    @unittest.skipUnless(sys.platform == "win32", "PowerShell parsing is Windows-only")
    def test_stage3_powershell_files_parse(self):
        for path in sorted(OPS.glob("*phase8e-obsidian*.ps1")):
            literal = str(path).replace("'", "''")
            command = (
                f"$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::"
                f"ParseFile('{literal}',[ref]$t,[ref]$e);"
                "if($e.Count){$e|ForEach-Object{Write-Error $_.Message};exit 1}"
            )
            subprocess.run(("powershell.exe", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", command), check=True)


if __name__ == "__main__":
    unittest.main()
