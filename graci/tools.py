"""Fail-closed, workspace-contained tools for deterministic GRACI workflows."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
_SENSITIVE_NAMES = {
    ".env", ".git", ".ssh", ".gnupg", "credentials", "credential", "secrets",
    "secret", "id_rsa", "id_ed25519",
}
_SENSITIVE_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ToolLayer:
    """Bounded programmatic tools; no model-controlled autonomous loop."""

    def __init__(self, workspace: Path | str, runner: ProcessRunner = subprocess.run):
        root = Path(workspace).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("workspace must be an existing directory")
        self.workspace = root
        self._runner = runner

    def _result(self, tool: str, requested: dict[str, Any], **values: Any) -> dict[str, Any]:
        result = {
            "tool": tool,
            "success": False,
            "requested": requested,
            "started_at": _timestamp(),
            "ended_at": None,
            "error_classification": None,
            "error": None,
        }
        result.update(values)
        return result

    @staticmethod
    def _finish(result: dict[str, Any], success: bool, classification: str | None = None,
                error: str | None = None) -> dict[str, Any]:
        result["success"] = success
        result["error_classification"] = classification
        result["error"] = error
        result["ended_at"] = _timestamp()
        return result

    def _resolve(self, requested_path: str | Path) -> Path:
        raw = Path(requested_path)
        candidate = raw if raw.is_absolute() else self.workspace / raw
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError("path resolves outside the configured workspace") from exc
        relative_parts = resolved.relative_to(self.workspace).parts
        for part in relative_parts:
            lowered = part.lower()
            if lowered in _SENSITIVE_NAMES or Path(lowered).suffix in _SENSITIVE_SUFFIXES:
                raise PermissionError("access to credential or secret paths is prohibited")
        return resolved

    def list_directory(self, path: str | Path = ".") -> dict[str, Any]:
        requested = {"path": str(path)}
        result = self._result("list_directory", requested, resolved_path=None, entries=[])
        try:
            target = self._resolve(path)
            result["resolved_path"] = str(target)
            if not target.exists():
                raise FileNotFoundError("directory does not exist")
            if not target.is_dir():
                raise NotADirectoryError("target is not a directory")
            result["entries"] = [
                {"name": item.name, "type": "directory" if item.is_dir() else "file"}
                for item in sorted(target.iterdir(), key=lambda item: item.name.casefold())
            ]
            return self._finish(result, True)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError) as exc:
            return self._finish(result, False, type(exc).__name__, str(exc))

    def read_text(self, path: str | Path) -> dict[str, Any]:
        requested = {"path": str(path), "encoding": "utf-8"}
        result = self._result("read_text", requested, resolved_path=None, content=None)
        try:
            target = self._resolve(path)
            result["resolved_path"] = str(target)
            if not target.exists():
                raise FileNotFoundError("file does not exist")
            if not target.is_file():
                raise IsADirectoryError("target is not a regular file")
            data = target.read_bytes()
            if b"\x00" in data:
                raise ValueError("binary content is unsupported")
            result["content"] = data.decode("utf-8")
            return self._finish(result, True)
        except (PermissionError, FileNotFoundError, IsADirectoryError, UnicodeDecodeError,
                ValueError, OSError) as exc:
            classification = "unsupported_content" if isinstance(exc, (UnicodeDecodeError, ValueError)) else type(exc).__name__
            return self._finish(result, False, classification, str(exc))

    def write_text(self, path: str | Path, content: str, *, replace: bool = False) -> dict[str, Any]:
        requested = {"path": str(path), "operation": "replace" if replace else "create", "encoding": "utf-8"}
        result = self._result("write_text", requested, resolved_path=None, bytes_written=0)
        temporary: Path | None = None
        try:
            if not isinstance(content, str):
                raise TypeError("content must be text")
            target = self._resolve(path)
            result["resolved_path"] = str(target)
            if target.exists() and not replace:
                raise FileExistsError("file exists; use replace=True to update it")
            if target.exists() and not target.is_file():
                raise IsADirectoryError("target is not a regular file")
            if not target.parent.is_dir():
                raise FileNotFoundError("parent directory does not exist")
            encoded = content.encode("utf-8")
            descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            result["bytes_written"] = len(encoded)
            return self._finish(result, True)
        except (PermissionError, FileExistsError, FileNotFoundError, IsADirectoryError,
                TypeError, UnicodeEncodeError, OSError) as exc:
            return self._finish(result, False, type(exc).__name__, str(exc))
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def run_command(self, executable: str, arguments: Sequence[str], *, cwd: str | Path = ".",
                    timeout_seconds: float = 30.0) -> dict[str, Any]:
        args = list(arguments)
        requested = {"executable": executable, "arguments": args, "cwd": str(cwd), "timeout_seconds": timeout_seconds}
        result = self._result("run_command", requested, resolved_cwd=None, command=None,
                              exit_code=None, stdout="", stderr="", timed_out=False)
        try:
            workdir = self._resolve(cwd)
            result["resolved_cwd"] = str(workdir)
            if not workdir.is_dir():
                raise NotADirectoryError("working directory does not exist")
            if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be positive")
            command = self._allowed_command(executable, args, workdir)
            result["command"] = command
            environment = os.environ.copy()
            if Path(executable).name.lower() in {Path(sys.executable).name.lower(), "python", "python.exe"}:
                environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
            if Path(executable).name.lower() in {"git", "git.exe"}:
                environment.update({
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_OPTIONAL_LOCKS": "0",
                    "GIT_PAGER": "cat",
                    "GIT_TERMINAL_PROMPT": "0",
                })
            completed = self._runner(command, cwd=workdir, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=timeout_seconds,
                                     shell=False, check=False, env=environment)
            result["exit_code"] = completed.returncode
            result["stdout"] = completed.stdout
            result["stderr"] = completed.stderr
            return self._finish(result, completed.returncode == 0,
                                None if completed.returncode == 0 else "nonzero_exit",
                                None if completed.returncode == 0 else f"command exited with {completed.returncode}")
        except subprocess.TimeoutExpired as exc:
            result["timed_out"] = True
            result["stdout"] = self._output_text(exc.stdout)
            result["stderr"] = self._output_text(exc.stderr)
            return self._finish(result, False, "timeout", f"command exceeded {timeout_seconds} seconds")
        except (PermissionError, NotADirectoryError, ValueError, OSError) as exc:
            return self._finish(result, False, type(exc).__name__, str(exc))

    @staticmethod
    def _output_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value

    def _allowed_command(self, executable: str, arguments: list[str], workdir: Path) -> list[str]:
        name = Path(executable).name.lower()
        python_names = {Path(sys.executable).name.lower(), "python", "python.exe"}
        if name in python_names:
            if arguments in (["--version"], ["-V"]):
                return [sys.executable, *arguments]
            normalized = arguments[2:] if arguments[:2] == ["-W", "error"] else arguments
            if len(normalized) == 6 and normalized[:3] == ["-m", "unittest", "discover"] and normalized[3] == "-s" and normalized[5] == "-v":
                start = Path(normalized[4])
                resolved_start = (workdir / start).resolve(strict=False) if not start.is_absolute() else start.resolve(strict=False)
                try:
                    resolved_start.relative_to(self.workspace)
                except ValueError as exc:
                    raise PermissionError("test discovery path resolves outside the configured workspace") from exc
                self._resolve(resolved_start)
                return [sys.executable, *arguments]
        if name in {"git", "git.exe"}:
            safe_exact = {
                ("status", "--short", "--branch"),
                ("diff", "--no-ext-diff", "--no-textconv"),
                ("log", "--oneline", "--decorate", "-n", "10"),
                ("rev-parse", "HEAD"),
            }
            if tuple(arguments) in safe_exact:
                return ["git", "-c", "core.fsmonitor=false", *arguments]
        raise PermissionError("command is not permitted by the Phase 1B allow policy")

    def run_tests(self, *, start_directory: str = "tests", timeout_seconds: float = 120.0) -> dict[str, Any]:
        command_result = self.run_command(
            Path(sys.executable).name,
            ["-W", "error", "-m", "unittest", "discover", "-s", start_directory, "-v"],
            timeout_seconds=timeout_seconds,
        )
        return {
            "tool": "run_tests",
            "success": command_result["success"],
            "requested": {"start_directory": start_directory, "timeout_seconds": timeout_seconds},
            "command_result": command_result,
            "status": "PASS" if command_result["success"] else "FAIL",
            "started_at": command_result["started_at"],
            "ended_at": command_result["ended_at"],
            "error_classification": command_result["error_classification"],
            "error": command_result["error"],
        }

    def git_status(self) -> dict[str, Any]:
        return self.run_command("git", ["status", "--short", "--branch"])

    def git_diff(self) -> dict[str, Any]:
        return self.run_command("git", ["diff", "--no-ext-diff", "--no-textconv"])

    def git_log(self) -> dict[str, Any]:
        return self.run_command("git", ["log", "--oneline", "--decorate", "-n", "10"])

    def git_head(self) -> dict[str, Any]:
        return self.run_command("git", ["rev-parse", "HEAD"])
