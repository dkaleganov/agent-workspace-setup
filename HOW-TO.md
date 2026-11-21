# How to use it

A short guide for people who don't write code. Pick your tool and do its three steps. The last three sections apply to every tool.

The idea is the same in every tool: install the skill once and ask for a workspace once. From then on, each session starts by reading the files and ends by updating them.

## What each tool needs

| Tool | Needs on your computer |
|---|---|
| Cowork | Nothing. The skill's script runs inside Cowork |
| Claude Code, Codex | Python 3.9 or later |

To check for Python, open Terminal and type `python3 --version`. On a Mac without it, that command offers to install Apple's developer tools, which include Python. On Windows, install Python from python.org or the Microsoft Store, and type `python` wherever this guide says `python3`.

## Cowork (Claude desktop app)

**1. Install**

1. Download `agent-workspace-setup-0.1.0.zip` from the [Releases page](https://github.com/dkaleganov/agent-workspace-setup/releases).
2. In the Claude desktop app, open Customize, then Skills, and upload the ZIP.

**2. Set up your workspace**

1. Start a new Cowork task and connect the folder that should hold your AI home, such as your Documents folder.
2. Say: "Set up my AI workspace."
3. Answer the four questions, read the preview, and say OK. Nothing is created before your OK.
4. Give it the goal and the first task when it asks. Then you can close the chat.

**3. Come back the next day**

Start a new task, connect the same folder, and say: "Continue the kitchen remodel. Do the next action." Use your own project's name.

Good to know: if Cowork asks to approve a command that runs `workspace.py`, approve it. That is the skill's script.

## Claude Code

**1. Install**

1. Download the ZIP from the [Releases page](https://github.com/dkaleganov/agent-workspace-setup/releases) and unzip it in your Downloads folder. You get a folder named `agent-workspace-setup`.
2. Open Terminal and paste this line. The skill copies itself into Claude Code's skills folder and tells you where it went:

   ```
   python3 ~/Downloads/agent-workspace-setup/scripts/workspace.py install --tool claude
   ```

   On Windows, "Extract All" puts the folder inside one named after the ZIP, so paste this into PowerShell:

   ```
   python "$HOME\Downloads\agent-workspace-setup-0.1.0\agent-workspace-setup\scripts\workspace.py" install --tool claude
   ```

3. Start a new Claude Code session.

Prefer to do it by hand? Move the folder into `~/.claude/skills/`. That folder is hidden on a Mac: in Finder, press Cmd+Shift+G and paste the path.

**2. Set up your workspace**

Open a terminal in the folder that should hold your AI home, start `claude`, and say: "Set up my AI workspace." Answer the questions, read the preview, say OK.

**3. Come back the next day**

Open a terminal in the project's folder, such as `90_AI-Agents/91_Projects/91.01_Kitchen-remodel`, start `claude`, and say: "Continue this project."

## Codex

**1. Install**

1. Download and unzip the same ZIP in your Downloads folder.
2. Open Terminal and paste this line. The skill copies itself into the skills folder Codex reads, and makes that folder if it isn't there:

   ```
   python3 ~/Downloads/agent-workspace-setup/scripts/workspace.py install --tool codex
   ```

   On Windows, "Extract All" puts the folder inside one named after the ZIP, so paste this into PowerShell:

   ```
   python "$HOME\Downloads\agent-workspace-setup-0.1.0\agent-workspace-setup\scripts\workspace.py" install --tool codex
   ```

3. Restart Codex.

Add `--dry-run` to the end of the line to see where the copy would go before anything is written.

**2. Set up your workspace**

Open the folder that should hold your AI home in the Codex app, or start `codex` in a terminal there. Say: "Set up my AI workspace with the agent-workspace-setup skill."

**3. Come back the next day**

Open the project's folder in Codex and say: "Continue this project."

Good to know: Codex asks whether you trust a folder the first time you open it there.

## Other agents

Cursor, GitHub Copilot, Amp and Gemini CLI also load skills from `~/.agents/skills/`, so the Codex steps apply. None of them has been tested with this version.

If your agent doesn't read `AGENTS.md` files by itself, add this line to its own instructions: "Before any work in a folder, read the AGENTS.md there and follow it."

## Claude chat, with no access to your folders

Not tested in this version. The skill is built to work like this:

1. Upload the ZIP as in the Cowork steps, and turn on code execution and file creation.
2. Say: "Build me a starter workspace I can download."
3. Unzip the download where you keep your files.
4. At the start of a chat, attach the project's `HANDOFF.md`. At the end, ask for the updated hand-off and save it over the old one. The work isn't saved until you do.

## What to say, day to day

| You say | What happens |
|---|---|
| "Brief me." | One line per piece of work: what is due, what is waiting on you, what is out of date |
| "Add a project: the garage sale." | A new numbered folder with the six standard files, after a preview |
| "Add an area: bookkeeping." | The same, for work that never finishes |
| "Record that decision." | Your decision goes into `DECISIONS.md`, with the date and the reason |
| "Update the hand-off." | The agent writes down where things stand and what comes next |
| "Rename this project to ..." | The folder is renamed and keeps its number |
| "Archive this project." | It moves to the archive and keeps its number |
| "Undo that." | The last rename, move or archive is reversed |
| "Check my workspace." | A read-only check, with a fix for each finding |
| "What is this file for?" | A plain answer |

The project names here are made up.

## Habits that make it work

- **One piece of work per chat.** Start a new chat for a new project. The files carry the memory.
- **Start from the hand-off.** Don't reopen an old, long chat to continue. Open a fresh one in the project's folder.
- **Say your decisions out loud.** "We're going with the second contractor. Record that."
- **Let the skill give out numbers.** Never number a folder by hand.
- **Keep documents where they are.** Contracts, statements and photos stay in your own folders. Tell the agent where they live, and it reads them from there.

## If something looks wrong

- **Ask for a check.** "Check my workspace" changes nothing and lists what it found.
- **Ask for an undo** right after a rename, a move or an archive.
- **Deleting is your job.** The skill never deletes anything. If a folder should go, you delete it yourself.
- **A folder you call private stays closed.** If an agent opens one anyway, tell it to stop, and name the folder as private again.
- **Report it.** [Open an issue](https://github.com/dkaleganov/agent-workspace-setup/issues) and say which tool you use and what you saw.
