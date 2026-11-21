# Tools

Where each tool finds the skill and the workspace rules, and what to watch for. Facts were checked against each vendor's documentation on 2026-11-21. Tools change: when something here doesn't match what you see, trust what you see and tell the owner.

## At a glance

| Tool | Runs the script | Gets the skill by | Finds the workspace rules by |
|---|---|---|---|
| Claude Code | Yes | a folder in `~/.claude/skills/` | `CLAUDE.md` in the home, which imports `AGENTS.md` |
| Cowork | Yes | uploading the skill's ZIP in the app | being told to read the home's `AGENTS.md` |
| Codex | Yes | a folder in `~/.agents/skills/` | `AGENTS.md` in the folder the session starts in |
| Claude chat | In its own sandbox only | uploading the skill's ZIP | being given the hand-off |
| Other agents | Varies | usually `~/.agents/skills/` | `AGENTS.md` in the working folder, for those that read it |

## Claude Code

- **Skill:** the whole `agent-workspace-setup` folder in `~/.claude/skills/`, or in a project's `.claude/skills/`. A symlinked folder works. `install --tool claude` copies it there and verifies the copy.
- **Personal instructions:** `~/.claude/CLAUDE.md`. `connect --tool claude` adds one marked section that points at the workspace.
- **Script path:** `${CLAUDE_SKILL_DIR}/scripts/workspace.py`.
- **Rules:** Claude Code loads `CLAUDE.md` from the working folder and every folder above it. Every work folder has a one-line `CLAUDE.md` that imports the `AGENTS.md` beside it, so that folder's rules load with no question asked.
- **The home's rules:** an import that points outside the working folder is asked about once in an interactive session and skipped in a headless one. So from a work folder, read `../../AGENTS.md` yourself at the start of every session. The work folder's `AGENTS.md` says the same. Tested on 2026-11-21 with Claude Code 2.1.322.
- **Start a session:** run `claude` in a work folder, or in the home for a brief.

## Cowork

- **Skill:** the owner uploads the ZIP in the Claude desktop app under Customize, then Skills. The ZIP has the skill folder at its top level. Cowork does not read `~/.claude`.
- **Script:** runs. In a hands-on check on 2026-11-21 (one Mac), Python 3.10 was present, and folders that a script created and renamed in the connected folder appeared on the real disk.
- **Paths look different:** the script sees the connected folder under a session path such as `/sessions/<id>/mnt/<FolderName>`. Don't show that path to the owner, and don't record it. Name folders by their own names. Pass `--documents` only for folders inside the connected folder.
- **The clock** in that environment may be in UTC. Timestamps carry their offset, so they stay correct.
- **Rules:** start by reading `AGENTS.md` in the home, then the work folder's `AGENTS.md` and `HANDOFF.md`.
- **Connect the right folder:** the owner connects the AI home, or the folder that holds it. Work on the folder the owner connected, never on an app's own folder.

## Codex

- **Skill:** the whole folder in `~/.agents/skills/`, or in a repository's `.agents/skills/`. A symlinked folder works. `install --tool codex` copies it there and verifies the copy.
- **Personal instructions:** `~/.codex/AGENTS.md`. `connect --tool codex` adds one marked section that points at the workspace.
- **Rules:** Codex reads `AGENTS.md` files from the project root down to the working folder, plus the personal file `~/.codex/AGENTS.md`. Outside a Git repository there is no project root, so it reads only the working folder's `AGENTS.md`. That is why every group and work folder has its own short `AGENTS.md` that points to the home's rules.
- **Size:** instruction files stop loading at 32 KiB combined by default. Keep `AGENTS.md` files short.
- **Sandbox:** in read-only mode the script can still run `check`, `scan` and every `--dry-run`. Changes need workspace write. In workspace write, folders named `.agents` and `.codex` stay read-only.
- **Start a session:** run `codex` in a work folder, or in the home for a brief.
- **Good to know:** a session started with `codex exec` doesn't appear in the app's list of threads.

## Claude chat

- **Skill:** uploaded as a ZIP under Customize, then Skills, with code execution and file creation turned on.
- **No access to the owner's folders.** The script runs only inside the chat's sandbox. Use "Without the script" in [modes.md](modes.md): a starter the owner downloads, and hand-off save-back for later sessions.
- **Never say** a folder was created on the owner's computer. Say what to download and where to put it.

## Other agents

| Tool | Reads `AGENTS.md` on its own | Personal skills folder |
|---|---|---|
| Cursor | Yes | `~/.agents/skills/` |
| GitHub Copilot (cloud agent and CLI) | Yes | `~/.agents/skills/` or `~/.copilot/skills/` |
| Devin Desktop (formerly Windsurf) | Yes | `~/.agents/skills/` |
| Amp | Yes | `~/.agents/skills/` |
| Gemini CLI | Only when `AGENTS.md` is listed in its `context.fileName` setting. Its default is `GEMINI.md` | `~/.agents/skills/` or `~/.gemini/skills/` |
| ChatGPT desktop app | In local projects with attached folders | plugins, or loose skill folders in the desktop app |

- For a tool that doesn't read `AGENTS.md` by itself, tell the owner to add this line to that tool's own instructions: "Before any work in a folder, read the AGENTS.md there and follow it."
- The whole `agent-workspace-setup` folder goes in the skills folder. Never a single file: the script and templates have to come along.
- If the tool can't run Python, use "Without the script" in [modes.md](modes.md).

## Rules for every tool

- Instruction changes apply to new sessions. Some tools read instructions only when they start, so tell the owner to restart the tool after connecting it.
- Change a tool's settings or instruction files only with the owner's OK for that exact file, after showing the exact text. `install` and `connect` are the only commands that write outside the AI home, and both have `--dry-run`.
- `install` never deletes. A different copy is replaced only with `--update`, and the old copy moves to a `skill-backups` folder beside the skills folder. A linked copy, or a folder that isn't this skill, is left alone.
- `connect` backs the file up first, writes between its own markers, and `--remove` takes out that section and nothing else.
- One workspace skill per tool. If a similar skill is installed, call this one by name.
