import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CertificateRemotingArtifactTests(unittest.TestCase):
    def test_session_helper_is_certificate_only_and_fixed_to_4090(self):
        source = (ROOT / "ops" / "new-4090-certificate-session.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("[ValidateSet('VR-Gamer')]", source)
        self.assertIn("-UseSSL", source)
        self.assertIn("-CertificateThumbprint", source)
        self.assertIn("CN=GRACI-3090-4090-Deployment", source)
        self.assertIn("GRACI_Remote@VR-Gamer", source)
        self.assertNotIn("Get-Credential", source)
        self.assertNotIn("-Credential", source)

    def test_status_fails_closed_and_checks_remote_security_identity(self):
        source = (ROOT / "ops" / "status-4090-certificate-trust.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Expected exactly one usable GRACI 4090 client certificate", (
            ROOT / "ops" / "new-4090-certificate-session.ps1"
        ).read_text(encoding="utf-8"))
        self.assertIn("VR-Gamer\\GRACI_Remote", source)
        self.assertIn("GRACI WinRM HTTPS from 3090", source)
        self.assertIn("192.168.0.100", source)
        self.assertIn("CertificateAuth", source)
        self.assertIn("exit 1", source)
        self.assertNotIn("Get-Credential", source)

    def test_documented_boundary_is_one_way_and_not_authority(self):
        architecture = (ROOT / "CURRENT_ARCHITECTURE.md").read_text(encoding="utf-8")
        acceptance = (
            ROOT / "docs" / "acceptance" / "ACC-0005-4090-certificate-remoting.md"
        ).read_text(encoding="utf-8")
        self.assertIn("one-way certificate-authenticated WinRM", architecture)
        self.assertIn("technical access, not task authority", acceptance)
        self.assertIn("The 4090 receives no", acceptance)
        self.assertIn("administrative trust back into the 3090", acceptance)


if __name__ == "__main__":
    unittest.main()
