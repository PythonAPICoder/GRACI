"""Static acceptance contracts for bounded Windows login startup scripts."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"


def source(name):
    return (OPS / name).read_text(encoding="utf-8").lower()


class WindowsLoginStartupTests(unittest.TestCase):
    def test_llama_task_is_current_user_limited_logon_hidden_and_ignore_new(self):
        install = source("install-3090-llama-router-task.ps1")
        for marker in ("new-scheduledtasktrigger -atlogon", "-logontype interactive",
                       "-runlevel limited", "-multipleinstances ignorenew",
                       "-windowstyle hidden", "-noninteractive"):
            self.assertIn(marker, install)
        self.assertIn("graci 3090 llama.cpp router", source("llama-router-common.ps1"))

    def test_resident_task_and_child_are_hidden_and_remain_independent(self):
        install = source("install-graci-resident-task.ps1")
        start = source("start-graci-resident.ps1")
        self.assertIn("-windowstyle hidden", install)
        self.assertIn("-windowstyle hidden", start)
        self.assertNotIn("llama", install + start)

    def test_router_args_preserve_loopback_native_autoload_without_preload(self):
        start = source("start-3090-llama-router.ps1")
        for marker in ("'--models-dir'", "'--models-max', '1'", "'--models-autoload'",
                       "'--host', '127.0.0.1'", "'--no-webui'"):
            self.assertIn(marker, start)
        self.assertNotIn("'--model',", start)
        self.assertNotIn("models/load", start)

    def test_duplicate_port_stale_and_health_paths_fail_safely(self):
        start = source("start-3090-llama-router.ps1")
        common = source("llama-router-common.ps1")
        self.assertIn("threading.mutex", start)
        self.assertIn("another graci 3090 router start is already in progress", start)
        self.assertIn("test-netconnection -computername 127.0.0.1", start)
        self.assertIn("refusing to stop or replace an unrelated server", start)
        self.assertIn("remove-item -literalpath $script:routerstate", start)
        self.assertIn("invoke-restmethod", common)
        self.assertIn("$record.schema_version -eq 1", common)
        self.assertIn("$existing.schema_version -eq 1", start)

    def test_stop_validates_owned_pid_and_never_uses_broad_termination(self):
        common = source("llama-router-common.ps1")
        stop = source("stop-3090-llama-router.ps1")
        self.assertIn("get-validatedgracirouterprocess", stop)
        self.assertIn("recorded router pid belongs to another executable", common)
        self.assertIn("recorded router pid identity and start time do not match", common)
        self.assertIn("stop-process -id $process.id", stop)
        for forbidden in ("stop-process -name", "get-process llama", "taskkill", "wmic process"):
            self.assertNotIn(forbidden, common + stop)

    def test_status_reports_task_installation_and_runtime_health_separately(self):
        status = source("status-graci-login-tasks.ps1")
        self.assertIn("get-scheduledtask -taskname", status)
        self.assertIn("status-graci-resident.ps1", status)
        self.assertIn("status-3090-llama-router.ps1", status)

    def test_startup_scripts_have_no_governed_run_or_microphone_authority(self):
        names = ("start-3090-llama-router.ps1", "install-3090-llama-router-task.ps1",
                 "install-graci-resident-task.ps1")
        combined = "\n".join(source(name) for name in names)
        for forbidden in ("run_typed", "run_speech", "windowswaveincapture",
                          "microphone", "push-to-talk", "models/load"):
            self.assertNotIn(forbidden, combined)

    def test_existing_model_lease_switch_contract_remains_present(self):
        lifecycle = (ROOT / "graci" / "model_lifecycle.py").read_text(encoding="utf-8")
        self.assertIn("APPROVED_PRIMARY_MODELS", lifecycle)
        self.assertIn('self._request("/models/load"', lifecycle)
        self.assertIn("with self._process_lock()", lifecycle)


if __name__ == "__main__":
    unittest.main()
