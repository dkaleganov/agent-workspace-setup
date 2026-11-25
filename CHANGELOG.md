# Changelog

## 0.6.1

A fix release. No new command, rule or question, and no workspace needs an upgrade.

- **Every work folder is in plain sight.** The check and the list of groups now name each work folder, so an agent sees them without searching.
- **A similar name gets a question.** When you add a work folder and one with a similar name exists, the agent is told to ask you whether it is the same work.
- **A clearer line before a tidy-up.** After the copy of a hand-off is kept, the script now tells the agent to show you the before and after and wait for your OK. A smaller model may still skip that step. The copy is kept either way.

## 0.6.0

- **Groups that fit your work.** Setup now asks what you work on. Name several kinds of work, and it proposes groups in your own words and says which pattern they follow: by status, by line of work, one folder for each client, course or other thing you have several of, or a mix. No field is built in. Ours stay one word away. A group can also say what doesn't belong in it.
- **"Rethink my groups."** The same consult for a workspace that exists. It proposes new groups or new lines, and never renames or removes a group folder.
- **A messy folder, two ways.** "Organize my folders" now lists loose files by name. When files need sorting, you pick: by name with you, or the agent opens the files in the folders you name. The choice says what the second way costs, and tells you to check your AI tool's setting for model training first.
- **Files move in batches.** One approved number moves a listed batch of files, and one undo puts it back. A file that would overwrite another is left and listed.
- **A plan that waits for you.** The plan for your folders is kept, so a long tidy-up can stop and go on in a later session. The check says when one was left half done.
- **Warnings on names,** with nothing renamed: odd characters, names that differ only by capitals, "final" and "copy", a number with no leading zero.
- **A check on the size of the rules,** because long rules are followed less closely and one tool stops reading past 32 KB.
- **Keywords.** A work folder can be found by a word written on a Keywords line in its README.
- **Five new rules for agents:** one home for work that fits two groups, done means checked, write down what surprised you, help the next search, and open a file outside the workspace only by choice.
- **What changed in the promises:** the README no longer says that no file is opened. A file of yours is opened in a tidy-up only when you chose "open and sort" for its folder.
- "Upgrade my workspace" adds the new rules to the end of your `AGENTS.md`, after a preview. Your groups stay as they are.

## 0.5.0

- **The hand-off is never copied.** The rules now say the six standard files are updated in place, and the check flags a second copy such as `HANDOFF_v2.md`. A cheaper model can read "save a new version as `_v2`" too broadly, and the next session would then read a stale hand-off.
- **Checks for shape:** Session log lines dated and newest first, and decision entries that start with a number or a date.
- **Naming that sorts:** dated files start with the date, a recurring series is one work folder, and a list of similar things is one table.
- **Two rules for agents:** use only paths a command printed or you gave, and install with the skill's own installer, never an app's "import skill" feature.
- **Your own groups.** Setup now asks first whether you want our groups or your own, with one line on what goes in each. Agents file new work by those lines, and the map shows them. "Add a group" makes one later. A workspace that already exists keeps its groups.
- **Review by number.** "Review my workspace" gives one numbered list of proposed changes. You answer with numbers, and only those are done.
- **Sort the Inbox.** An Inbox item is moved into the work folder you name, unopened. The move is logged, and "undo" reverses it.
- **A copy before a tidy-up.** Before an agent rewrites a hand-off, a copy of the old one is kept in the workspace's records.
- **`BRIEF.md`.** A short file at the top of the workspace tells any agent how to brief you, with or without this skill. "Upgrade my workspace" adds it.
- **`FACTS.md`, when you need it.** Facts that outlive a task go in one file in the work folder, each with its source and date. The check flags a line that has neither.
- **A check for piles of versions:** three or more versions of one file in a work folder.
- **Help with your other folders, if you want it.** Setup now asks whether you want only an AI home, or also help organizing the folders beside it. "Organize my folders" looks at names, proposes a numbered layout in your words, and makes only the changes you approve by number. It opens no file, writes no file there, deletes nothing, and can undo a rename or a move.
- **Clearer rules for cheaper models,** found by running every test on a mid-tier model: change the structure only through the skill, the session you are talking to is the one that writes the hand-off, and a request for a daily check is not yet a yes to a scheduled job.

## 0.4.0

- **A written order for what wins.** When two files disagree, the rules now say which one an agent works from: your word now, then the newest decision, then the hand-off, then the README. The agent must flag the conflict with a line that starts `Conflict:`, and ask you.
- **Decisions carry numbers,** such as `D-004`, so a file can cite one and the check can tell when it was replaced.
- **Ten new checks,** all run by the script with no AI: an overdue next action, an open conflict, a hand-off that is behind its own log, a long wait, a citation of a replaced or missing decision, a README and hand-off that give different purposes, an old open note, closed work that was never archived, and an old Inbox item.
- **Optional routines.** A daily check can rewrite `STATUS.md` at the top of your workspace and speak up only when something needs you. The skill offers it once. Nothing is scheduled unless you say yes, and a no is remembered.
- **A routine that stops is flagged.** Each run is logged, and the check says when one has gone quiet, overlapped with a second runner, or failed.
- **Honest limits,** in the README: what no check will catch.
- "Upgrade my workspace" adds the new rules to the end of your `AGENTS.md`, after a preview.

## 0.3.0

- **Each group keeps its own archive.** Closed work now moves into `_Archive` inside the group it is in, such as `91_Projects/_Archive/91.02_Old-brochure`. It stays beside the work it belonged to, and you can see where it came from. The folder is made the first time something in that group is archived.
- **No more single archive.** New workspaces don't get a `99_Archive` folder.
- **Nothing changes in a workspace you already have until you ask.** Its old archive keeps working. The check lists what is in it (ARC001), and "archive 91.02" moves one folder into its own group's archive, after a preview.
- **Archived work is frozen.** Agents restore a folder before working in it, and the check skips links inside archived folders.
- "Upgrade my workspace" adds the new archive rule to the end of your `AGENTS.md`, after a preview.
- 108 unit tests.

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
