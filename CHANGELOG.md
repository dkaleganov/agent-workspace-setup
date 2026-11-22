# Changelog

## 0.2.0

- **A brief says what it didn't cover.** "Brief me" now ends with a short list: private folders, documents that aren't on this computer, hand-offs it didn't read, and everything outside the workspace, such as mail and chat.
- **Facts carry their source.** A new rule for agents: a number, date, price, name or promise is written down with where it came from and when. Two sources that disagree are both kept. What couldn't be checked is marked `Unconfirmed`.
- **"Tidy up my workspace."** A new request that brings a hand-off up to date from its own log, one work folder at a time. You see the before and after, and nothing is written before your OK.
- **Friction notes.** When a command trips an agent, it adds one line to `_workspace/friction.md`. You can pass the notes on in an issue.
- **`upgrade`, and a note on what's new.** A workspace now records which version set it up. After you update the skill, the check says so, tells you what's new, and offers to add the new rule to the end of your `AGENTS.md`. Nothing is added before your OK, and no other file is touched.
- **Five new check findings:** work with no next action (HND009), lines still marked Unconfirmed (HND010), a workspace older than the skill (VER001) or newer (VER002), and friction notes waiting (FRC001).
- If the script itself fails, it now says so in one line with a next step, with no traceback.
- Fixed: five lines in the skill's text still said a work folder starts with three files. It is six.
- 97 unit tests.

## After 0.1.0

- Added `HOW-TO.md`: the steps for each tool in plain words, and what to say day to day. The skill itself is unchanged.
- The how-to now installs the skill for Claude Code and Codex with one pasted line, and says which tools need Python.
- The README says the script works offline, and where to report a problem. A test keeps the script free of network code.

## 0.1.0

First public release.

- One script, `workspace.py` (Python 3.9 or later, standard library only), with these commands: `init`, `setup`, `new`, `scan`, `check`, `map`, `rename`, `move`, `archive`, `restore`, `undo`, `adopt`, `kit`, `install`, `connect`, `reconcile`.
- Every project and area folder starts with the same six files: `README.md`, `HANDOFF.md`, `DECISIONS.md`, `AGENT_SYNC.md`, `AGENTS.md` and a one-line `CLAUDE.md`.
- Numbers come from an append-only ledger. A folder keeps its number for good, and a number is never used twice.
- The home's number is the owner's choice: any ten from 10 to 90.
- Every command that writes has a dry run. Nothing is deleted, no file is overwritten, and every move is logged first so it can be undone.
- Tested with Claude Code on macOS, Linux and Windows, and hands-on with Codex and Cowork on macOS.
- License: MIT.
