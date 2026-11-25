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
  BRIEF.md                       how to brief you, for any agent
  _workspace/                    the skill's own records
  90_Inbox/                      things not sorted yet
  91_Projects/                   work that finishes
    91.01_Website-relaunch/
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

The names in the example are made up. The groups shown are ours. When you name several kinds of work, setup proposes groups in your own words.

## Install

**Cowork**

1. Download `agent-workspace-setup-0.6.0.zip` from the [Releases page](https://github.com/dkaleganov/agent-workspace-setup/releases).
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

The agent asks five questions in one message:

1. What should I set up: only an AI home, or an AI home and help organizing the folders beside it?
2. What's your name, and where should the AI home live?
3. Is there anything agents must never open?
4. What do you work on, and which of it finishes?
5. Where are its files now?

Then it shows a preview of every folder and file. Nothing is created until you say OK.

**The groups fit your work.** Name one thing, and you get ours: Inbox (anything not filed yet), Projects (work that finishes), Areas (ongoing work) and Data (libraries and archives that agents read). Name several kinds of work, and the agent proposes groups in your own words and says which pattern they follow: by status, by line of work, one folder for each client, course or other thing you have several of, or a mix. No field is built in: it works the same for a shop, a studio, a lab, a household or a set of rentals. Each group says what goes there and what doesn't. Ours stay one word away: say "ours". Every name is a suggestion.

The next day, open a session in a project folder and say "Continue this project." The agent reads the hand-off and carries on.

## What it promises

- **A preview before every change.** Each command that writes has a dry run.
- **No deleting, no overwriting.** The script creates new files and folders. It never deletes anything and never overwrites a file of yours. After you update the skill, it can add new rules to the end of your `AGENTS.md`, and only with your OK.
- **Every move can be undone.** A rename, a move or an archive is logged before it happens.
- **Your documents stay where they are.** The workspace records where they live, and agents read them by path.
- **Agent files live only in the AI home.** No hand-off, rules file or note is written into any other folder of yours.
- **Your other folders change only if you ask.** With "organize my folders" you get a numbered list of changes, and only the numbers you approve are done. Nothing is deleted, no file is renamed, and every move can be undone.
- **Private folders stay closed.** You name them once. The rules tell every agent to leave them shut, and the script never opens them.
- **The script works offline.** It reads and writes files on your computer and sends nothing anywhere. What your AI tool sends to its own service stays as it was.

## Sorting a messy folder

"Organize my folders" lists your loose files by name. When files need sorting, the agent shows you two ways, and you pick.

- **By name, with you.** The agent sees names, sizes and dates and opens nothing. Where a name doesn't say what a file is, it asks you. Best for private papers, or when the names are already clear.
- **Open and sort.** The agent opens the files in the folders you name and proposes a place for every file. It is cleaner and goes deeper. What it costs: the contents of those files go to your AI tool's service, a file kept only in the cloud is downloaded when it is opened, and it takes longer and uses more of your plan.

**Before you pick "open and sort", check your AI tool's privacy settings.** If it has a setting that lets your chats train its models, turn it off first, unless you are fine with these files being used that way. Either way, the contents are sent to the service to be read.

What stays the same in both:

- Nothing moves before you approve it by number, in batches, and one "undo that" puts a batch back.
- Files whose names look like passwords, keys, identity papers or health records stay closed unless you name them. A private folder can't be picked.
- The plan is kept, so a long tidy-up can stop and go on in a later session.
- If you don't choose, the agent sorts by name.

One limit to know: the skill's script can't stop an agent from opening a file. The rules tell it which files, and your AI tool's own permission prompts are the backstop. A smaller model follows such rules less closely.

## How the numbering works

- The AI home takes a ten of your choice, from 10 to 90. Pick one that fits the folders around it.
- Group folders count up from that ten: the Inbox first, then Projects, Areas and Data, or up to eight groups fitted to your work.
- Closed work moves into `_Archive` inside its own group, so you can always see where it came from.
- Each project or area gets a number such as `91.01`. The script gives it out and records it in a ledger.
- A folder keeps its number for good, through every rename, move and archive. A number is never used twice.

The numbering is inspired by [Johnny.Decimal](https://johnnydecimal.com/) by Johnny Noble. This skill uses a looser scheme of its own. It is independent and isn't endorsed by Johnny.Decimal, which is a trademark of Coruscade Pty Ltd.

## What else you can ask for

| Ask for | What happens |
|---|---|
| "Add a project" | A new numbered folder with the six files |
| "Check my workspace" | A read-only check, with a fix for each finding |
| "Brief me" | Where every piece of work stands, and what the brief didn't cover |
| "Set up a daily check" | Optional. A scheduled check that rewrites `STATUS.md` and speaks up only when something needs you |
| "Review my workspace" | One numbered list of proposed changes: closed work to archive, Inbox items to file, hand-offs to tidy. You approve by number, and nothing else changes |
| "Sort my Inbox" | Each item is moved into the work folder you name, unopened. The move is logged and can be undone |
| "Tidy up my workspace" | A hand-off is brought up to date from its own log. A copy of the old one is kept, and you see the before and after first |
| "Add a group" | A new group folder, with one line on what goes there and one on what doesn't |
| "Rethink my groups" | The agent asks what changed in your work and proposes new groups or new lines. Nothing changes before your OK |
| "Organize my folders" | Optional. A numbered layout for the folders beside the AI home, proposed in your words. You approve each change by number |
| "Sort this messy folder" | Optional. Two ways, and you pick: by name with you, or the agent opens the files in the folders you name. Files move in batches you approve by number |
| "Bring in this folder" | An existing folder gets a number and the files it lacks. Its own files stay as they are |
| "Rename this", "Archive this", "Undo that" | The move is previewed, logged and reversible. An archived folder goes into `_Archive` inside its own group |
| "Connect Codex" | The skill is copied into another tool's skills folder, after you see the exact folder |
| "Upgrade my workspace" | After you update the skill: what's new, and the new rules for your `AGENTS.md`, after a preview |

`SKILL.md` and the files in `references/` have the details.

## Keeping it tidy

A folder is memory only while someone keeps it current. Three things help:

- **A written order for what wins.** When two files disagree, the agent works from your latest word, then the newest decision, then the hand-off, then the README. It must flag the conflict and ask you.
- **A check that reads dates.** It finds an overdue next action, an open conflict, a hand-off that fell behind its own log, and a decision that was replaced and is still cited.
- **An optional daily check.** If you want one, the skill sets up a scheduled task that rewrites `STATUS.md` and speaks up only when something needs you. It is off until you say yes.

What no check will catch:

- A wrong fact written the same way everywhere.
- Anything that was never written down.
- Two files that state one fact differently in prose. A tidy-up looks for those, and can miss some.
- A computer that is off. Every scheduler that can see your folder needs its app open and the computer awake.

## Where it has been tested

| What | How | On |
|---|---|---|
| Claude Code | Automated runs of fifteen scenarios: setup, groups fitted to your work in three fields (rentals, a design studio and a bakery), your own groups, a next-day restart, a safety test, which plain requests start the skill, upgrade with tidy-up, a planted contradiction, the optional daily check, a review by number, organizing the folders beside the AI home, a messy folder sorted by name, and a messy folder the agent may open. Each ran once on Sonnet and three times on Haiku, a smaller model | macOS. Version 0.1.0 also ran on Linux and Windows |
| The daily check as a scheduled task | One scheduled run in the Claude desktop app, on version 0.4.0 | macOS |
| Codex | One hands-on run, on version 0.1.0 | macOS |
| Cowork | One hands-on run on Sonnet, on version 0.1.0 | macOS |
| The script alone | 183 unit tests | macOS, Linux and Windows, on Python 3.9 and later |

What the release runs showed, on the final code: 60 runs and 1,236 checks, of which ten failed.

- **Sonnet:** fourteen of the fifteen scenarios passed. In the fifteenth it drafted a note to the right agency, and the note's heading also named the agency that had been replaced. The check counts that as a miss.
- **Haiku:** twelve scenarios passed three times out of three. Two passed twice. One, the upgrade with tidy-up, passed once.
- **Haiku's four misses:**
  - a drafted note that named no one;
  - a second folder made for a house that already had one;
  - a tidy-up reported without the lines it took from the log;
  - an area it was asked to archive and said it couldn't find. It changed nothing.
- **Safety checks:** all passed but one. That check compares an archived folder's files before and after, and in that run the agent had archived nothing, so there was nothing to compare. No file was changed.
- **What earlier testing changed:** in runs before this release, Haiku listed folders with a plain command before using the skill, and once opened a file whose name looked sensitive. The rules now send every look at your folders through the skill. Only the script states the two ways to sort a messy folder, and it refuses to record a pick until it has printed what each way costs and the notice about model training.

A smaller model follows the rules less closely. The script's refusals and your tool's own permission prompts are the backstop.

Not tested yet: Claude chat, Cowork on a folder inside a cloud-synced drive, Cowork or Codex on Windows, and the folder help on a real drive with thousands of files. Everything added since 0.1.0 has been tested with Claude Code only.

This is version 0.6.0. Try it on a test folder first.

## Where the ideas come from

- **The numbering:** inspired by [Johnny.Decimal](https://johnnydecimal.com/), by Johnny Noble.
- **Work that finishes and work that goes on:** the split Tiago Forte's PARA method made popular.
- **Groups named for lasting work, with a line on what doesn't belong:** records management practice.
- **Inbox first, sort later:** research on how people file, by Thomas Malone and by Steve Whittaker.
- **One rules file that every tool reads:** the AGENTS.md convention.

Everything here is written in our own words and built our own way. None of these people or projects endorses this skill.

## Questions and problems

[Open an issue](https://github.com/dkaleganov/agent-workspace-setup/issues). Say which tool you use and what you saw.

## For developers

```
python3 -m unittest discover -s tests -v
```

The tests build workspaces in temporary folders with a stand-in home folder. They never touch a real one.

## License

MIT. See [LICENSE](LICENSE).
