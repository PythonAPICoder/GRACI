import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"


class Phase8EStage2BoundaryTests(unittest.TestCase):
    def test_fixture_helper_is_local_and_has_no_runtime_import(self):
        tree = ast.parse((ROOT / "phase8e" / "stage2_fixture.py").read_text("utf-8"))
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        self.assertTrue({"socket", "urllib", "requests", "http", "openai", "graci"}.isdisjoint(imports))

    @unittest.skipUnless(sys.platform == "win32", "PowerShell parsing is Windows-only")
    def test_stage2_powershell_files_parse(self):
        scripts = sorted(path for path in OPS.glob("*phase8e*.ps1")
                         if "obsidian" not in path.name)
        self.assertGreaterEqual(len(scripts), 7)
        for path in scripts:
            literal = str(path).replace("'", "''")
            command = (
                f"$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::"
                f"ParseFile('{literal}',[ref]$t,[ref]$e);"
                "if($e.Count){$e|ForEach-Object{Write-Error $_.Message};exit 1}"
            )
            subprocess.run(("powershell.exe", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", command), check=True)

    def test_rejected_application_control_source_is_quarantined_as_evidence(self):
        common = (OPS / "phase8e-review-boundary-common.ps1").read_text("utf-8")
        marker = "HOST-SYSTEM-CHANGE-QUARANTINE: PO-DEC-039"
        self.assertIn(marker, common)
        self.assertLess(common.index(marker), common.index("$script:Phase8EViewerName"))
        self.assertLess(common.index("throw", common.index(marker)),
                        common.index("New-Phase8EAppLockerXml"))
        self.assertIn('"GRACI_Review"', common)
        self.assertIn('"E:\\GRACI-Review-Staging"', common)
        self.assertIn('"E:\\GRACI-Review-Projection"', common)
        self.assertIn('"C:\\ProgramData\\GRACI\\Phase8E"', common)
        self.assertIn('"E:\\GRACI-Review-Evidence"', common)
        self.assertIn('UserOrGroupSid=`"S-1-1-0`" Action=`"Allow`"', common)
        self.assertEqual(common.count('Action=`"Deny`"'), 2)
        for collection in ("Exe", "Msi", "Script", "Dll"):
            self.assertIn(f'Type = "{collection}"', common)

    def test_launcher_requires_exact_stage3_qualification(self):
        launcher = (OPS / "open-phase8e-review.ps1").read_text("utf-8")
        marker = "HOST-SYSTEM-CHANGE-QUARANTINE: PO-DEC-039"
        self.assertIn(marker, launcher)
        self.assertLess(launcher.index("throw", launcher.index(marker)),
                        launcher.index("Get-AppLockerPolicy"))
        self.assertIn("Start-Process", launcher)
        self.assertIn('throw "APPLICATION_NOT_QUALIFIED"', launcher)
        self.assertIn('authority -ne "PO-DEC-033"', launcher)
        self.assertIn("VIEWER_IDENTITY_REQUIRED", launcher)
        self.assertIn("manifest_sha256", launcher)
        self.assertIn("UNMANIFESTED_OUTPUT", launcher)

    def test_no_stage2_script_changes_network_or_installs_obsidian(self):
        combined = "\n".join(
            path.read_text("utf-8") for path in OPS.glob("*phase8e*.ps1")
            if "obsidian" not in path.name and path.name != "open-phase8e-review.ps1"
        )
        forbidden = ("New-NetFirewallRule", "Set-NetFirewallRule", "Remove-NetFirewallRule",
                     "winget", "choco", "Install-Package", "obsidian.exe")
        for token in forbidden:
            self.assertNotIn(token.casefold(), combined.casefold())

    def test_finalizer_is_pointer_bounded_and_reparse_aware(self):
        finalizer = (OPS / "finalize-phase8e-projection.ps1").read_text("utf-8")
        self.assertIn("current.json", finalizer)
        self.assertIn("canonical lowercase UUID", finalizer)
        self.assertIn("Test-Phase8EReparse", finalizer)
        self.assertIn("/reset /T /C /Q", finalizer)


if __name__ == "__main__":
    unittest.main()
