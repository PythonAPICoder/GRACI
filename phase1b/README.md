# GRACI Phase 1B controlled tool layer

Phase 1B was verified on 2026-08-27 (America/Chicago).

`graci.tools.ToolLayer` provides workspace-contained directory listing, UTF-8 text
read/create/replace, approved argument-array commands, warning-strict unittest
execution, and fixed read-only Git status/diff/log/HEAD operations. Results are
structured and report timestamps, resolved targets, truthful success, classified
errors, and process exit/output/timeout details where applicable.

The implementation resolves and checks paths, rejects traversal and absolute or
symlink escapes, blocks credential/secret paths and binary reads, writes atomically,
never invokes a shell, and permits only explicitly recognized commands. It provides
no deletion, arbitrary shell, package-manager, network, Git mutation, elevation,
system configuration, model-controlled tool loop, 4090 inference, or cloud AI path.

Verification evidence:

- `python -W error -m unittest discover -s tests -v`: 18 tests passed.
- A disposable repository-local validation sandbox successfully exercised file
  create/read/replace, `python --version`, one passing unittest, and safe Git status.
- An attempted read of `../PROJECT_STATE.md` from that sandbox failed with
  `PermissionError`; the disposable sandbox was then removed.
- No live LLM, 4090 workload, cloud AI, network operation, dependency installation,
  secret storage, or system configuration change occurred.
