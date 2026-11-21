# Changelog

## 0.1.0

First public release.

- One script, `workspace.py` (Python 3.9 or later, standard library only), with these commands: `init`, `setup`, `new`, `scan`, `check`, `map`, `rename`, `move`, `archive`, `restore`, `undo`, `adopt`, `kit`, `install`, `connect`, `reconcile`.
- Every project and area folder starts with the same six files: `README.md`, `HANDOFF.md`, `DECISIONS.md`, `AGENT_SYNC.md`, `AGENTS.md` and a one-line `CLAUDE.md`.
- Numbers come from an append-only ledger. A folder keeps its number for good, and a number is never used twice.
- The home's number is the owner's choice: any ten from 10 to 90.
- Every command that writes has a dry run. Nothing is deleted, no file is overwritten, and every move is logged first so it can be undone.
- Tested with Claude Code on macOS, Linux and Windows, and hands-on with Codex and Cowork on macOS.
- License: MIT.
