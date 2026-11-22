# agent-workspace-setup

A skill that sets up a numbered workspace for your AI agents, in plain folders you own. Every project and area gets a short hand-off file, so any agent session in any tool picks up where the last one stopped.

It works with Claude Code, Cowork, Codex and other agents that read and write local files. You don't need to be technical to use it.

## The problem it solves

Agents forget. A chat ends, and tomorrow's session starts from zero. You explain the project again, or you scroll an old chat to find last week's decision.

This skill moves the memory out of the chat and into files. The agent reads them before it works and updates them when a task is done. Close the chat whenever you like.

## What you get

```
90_AI-Agents/                    the AI home. You pick its number and its name
  AGENTS.md                      the rules every agent follows
  README.md                      the map of all your work
  _workspace/                    the skill's own records
  90_Inbox/                      things not sorted yet
  91_Projects/                   work that finishes
    91.01_Duplex-renovation/
    _Archive/                    closed projects, kept with their numbers
  92_Areas/                      ongoing work
    92.01_Bookkeeping/
  95_Data/                       libraries and archives that agents read
```

Every project and area folder starts with the same six files:

| File | What it holds |
|---|---|
| `README.md` | What the work is. It changes only when the goal changes |
| `HANDOFF.md` | Where the work stands and what comes next |
| `DECISIONS.md` | What you decided, and why |
| `AGENT_SYNC.md` | Notes between agents and sessions |
| `AGENTS.md` | Instructions for agents |
| `CLAUDE.md` | One line that points Claude Code to `AGENTS.md` |

The names in the example are made up.

## Install

**Cowork**

1. Download `agent-workspace-setup-0.3.0.zip` from the [Releases page](https://github.com/dkaleganov/agent-workspace-setup/releases).
2. In the Claude desktop app, open Customize, then Skills, and upload the ZIP.

**Claude Code**

Copy the folder `skills/agent-workspace-setup` into `~/.claude/skills/`.

**Codex and other agents**

Copy the same folder into `~/.agents/skills/`. Codex loads skills from there, and so do Cursor, GitHub Copilot, Amp and Gemini CLI. Of that group, only Codex has been tested.

Cowork needs nothing installed on your computer. Claude Code and Codex need Python 3.9 or later, and nothing else.

New to this? [HOW-TO.md](HOW-TO.md) has the steps for each tool in plain words, a one-line install for Claude Code and Codex, and what to say day to day.

## First run

Start a session and say:

> Set up my AI workspace.

The agent asks four questions in one message:

1. What's your name, and where should the AI home live?
2. Is there anything agents must never open?
3. What's one thing you're working on?
4. Where are its files now?

Then it shows a preview of every folder and file. Nothing is created until you say OK.

The next day, open a session in a project folder and say "Continue this project." The agent reads the hand-off and carries on.

## What it promises

- **A preview before every change.** Each command that writes has a dry run.
- **No deleting, no overwriting.** The script creates new files and folders. It never deletes anything and never overwrites a file of yours. After you update the skill, it can add new rules to the end of your `AGENTS.md`, and only with your OK.
- **Every move can be undone.** A rename, a move or an archive is logged before it happens.
- **Your documents stay where they are.** The workspace records where they live, and agents read them by path.
- **Private folders stay closed.** You name them once. The rules tell every agent to leave them shut, and the script never opens them.
- **The script works offline.** It reads and writes files on your computer and sends nothing anywhere. What your AI tool sends to its own service stays as it was.

## How the numbering works

- The AI home takes a ten of your choice, from 10 to 90. Pick one that fits the folders around it.
- Group folders count up from that ten: Inbox, Projects, Areas, Data.
- Closed work moves into `_Archive` inside its own group, so you can always see where it came from.
- Each project or area gets a number such as `91.01`. The script gives it out and records it in a ledger.
- A folder keeps its number for good, through every rename, move and archive. A number is never used twice.

The numbering is inspired by [Johnny.Decimal](https://johnnydecimal.com/) by John Noble. It is a looser scheme of its own and copies nothing from it. This skill is independent and isn't endorsed by Johnny.Decimal.

## What else you can ask for

| Ask for | What happens |
|---|---|
| "Add a project" | A new numbered folder with the six files |
| "Check my workspace" | A read-only check, with a fix for each finding |
| "Brief me" | Where every piece of work stands, and what the brief didn't cover |
| "Tidy up my workspace" | A hand-off is brought up to date from its own log. You see the before and after first |
| "Bring in this folder" | An existing folder gets a number and the files it lacks. Its own files stay as they are |
| "Rename this", "Archive this", "Undo that" | The move is previewed, logged and reversible. An archived folder goes into `_Archive` inside its own group |
| "Connect Codex" | The skill is copied into another tool's skills folder, after you see the exact folder |
| "Upgrade my workspace" | After you update the skill: what's new, and the new rules for your `AGENTS.md`, after a preview |

`SKILL.md` and the files in `references/` have the details.

## Where it has been tested

| What | How | On |
|---|---|---|
| Claude Code | Automated runs of five scenarios on Sonnet: setup, a next-day restart, a safety test, which plain requests start the skill, and upgrade with tidy-up | macOS. Version 0.1.0 also ran on Linux and Windows |
| Codex | One hands-on run, on version 0.1.0 | macOS |
| Cowork | One hands-on run on Sonnet, on version 0.1.0 | macOS |
| The script alone | 108 unit tests | macOS, Linux and Windows, on Python 3.9 and later |

Not tested yet: Claude chat, Cowork on a folder inside a cloud-synced drive, and Cowork or Codex on Windows. The requests added since 0.1.0 (tidy up, upgrade, and the archive inside each group) have been tested with Claude Code only.

This is version 0.3.0. Try it on a test folder first.

## Questions and problems

[Open an issue](https://github.com/dkaleganov/agent-workspace-setup/issues). Say which tool you use and what you saw.

## For developers

```
python3 -m unittest discover -s tests -v
```

The tests build workspaces in temporary folders with a stand-in home folder. They never touch a real one.

## License

MIT. See [LICENSE](LICENSE).
