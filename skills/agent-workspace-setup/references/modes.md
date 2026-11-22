# Modes in detail

For the agent. `SKILL.md` has the short checklists; this file has the detail behind them.

## Set up new

**The first run aims at tomorrow's restart:** one work folder whose hand-off holds a next action, so a fresh session the next day can continue.

**The answers file** is JSON that you write from the owner's answers.

| Field | Required | Meaning |
|---|---|---|
| `location` | Yes, unless `home` is given | The folder the AI home goes in. It must exist. If a workspace is already there, setup adds to it |
| `home` | No | The AI home itself, when adding to an existing workspace somewhere else |
| `owner` | Yes, for a new workspace | The owner's name |
| `home_name` | No | The home's name. Default `AI-Agents` |
| `home_number` | No | A ten from 10 to 90. Default: what `init --path` suggests |
| `work` | No | A list of `{"title", "kind", "purpose", "status", "documents"}` |
| `private` | No | Folders agents must never open: a folder's name, or its path. A full path is written down relative to the home or from `~/` |

For each item in `work`: `kind` is `project` (finishes), `area` (ongoing) or `data` (a library); the default is `project`. `status` starts with Active, Paused, Ongoing or Closed. `documents` lists folders the work reads; they stay where they are.

**What setup does:** creates the home if it's new, its records, the five group folders, the home's `AGENTS.md`, `CLAUDE.md` and `README.md`, and each work folder with its six standard files. Then it refreshes the map and runs the check.

**What setup never does:** overwrite a file, or touch a folder outside the home. Running it again adds only what is missing and keeps every edit the owner made.

**After setup:** ask the owner for the goal and the first task. Write the goal into the work folder's `README.md` and the first task under Next actions in its hand-off. That is the point of the whole exercise.

## New work folder

`new --title "<Title>" --kind project|area|data [--purpose "<one line>"] [--documents "<folder>"]`

The script takes the next number in that group from the ledger, makes the folder with its six standard files (`README.md`, `HANDOFF.md`, `DECISIONS.md`, `AGENT_SYNC.md`, `AGENTS.md`, `CLAUDE.md`), and refreshes the map. A title that already exists in that group is not added twice.

## Bring in existing

In this version, bringing in means pointing at folders. Nothing outside the home is copied, moved or renamed.

1. Ask which folders are private first.
2. `scan "<folder>" --private "<name>"` lists what is there: names, counts, sizes and dates. It opens no file.
3. For each folder the owner wants an agent to pick up, add a work folder with `--documents "<that folder>"`.
4. Write each hand-off from file names and dates. Mark every guess "Unconfirmed (ask the owner)". Record a decision only when the owner made it.

**A folder that already sits inside the home** (the owner turned an existing AI folder into the home, or dropped a folder into it): `adopt "<folder>" --kind project|area|data [--title "<Title>"]`. The folder moves into the right group under the next number, and every file in it stays as it is. It gets each of the six standard files only where that file is missing. If it already had a hand-off, the command names a `**Key:**` line to add to it; add that line yourself with the owner's OK. `undo` puts the folder back, and its number is retired.

## Upkeep: moves

| Command | What it does |
|---|---|
| `rename <number> "<New title>"` | Renames the folder. The number stays |
| `move <number> --to project\|area\|data` | Moves it to another group. The number stays, so `91.03` can live in `92_Areas` |
| `archive <number>` | Moves closed work to the archive. Only when the owner asked to close it |
| `restore <number>` | Brings it back to the group it was in |
| `undo` | Reverses the last of these |

Every one has `--dry-run`. Each move is written to the moves log before it happens. A move is refused when the target exists, when either side is private, when it would leave the home or cross to another drive, and when the records and the folders disagree.

`undo` works while the folder and its old place are as the move left them. If the old place is taken, or the folder's key changed, it refuses and leaves both folders where they are.

After a move, run `check`. A link that the move broke is listed with its new target. Edit the link yourself, after re-reading the file, with the owner's OK.

## Upkeep: check

`check` is read-only. Errors make it exit with code 1.

| Rule | Level | Meaning | Fix |
|---|---|---|---|
| LED001 | error | The number ledger is missing | `reconcile` |
| LED002 | error | A ledger line can't be read | Look at the file with the owner. Lines are never removed by the script |
| LED003 | error | A second copy of the ledger, usually from two computers | `reconcile` merges its lines and renames the copy |
| NUM001 | error | The same number on two folders | `reconcile`; the owner picks which keeps it |
| NUM002 | error | A numbered folder the ledger doesn't know | `reconcile` adds it |
| NUM003 | error | A hand-off key that doesn't match the ledger | Compare the hand-off and the ledger with the owner |
| NUM004 | warn | A number in the ledger with no folder here | Nothing, if it hasn't synced yet. If it is gone for good: `reconcile --retire-missing` |
| NUM005 | warn | An unnumbered folder inside a group | If it is work, add a work folder for it and move its files in with the owner |
| NUM006 | warn | A numbered top-level folder outside the home's ten | Rename it with the owner, or leave it |
| NUM007 | info | A group has used 90 or more of its 99 numbers | Ask the owner to add another group folder |
| HOME001 | error | The home's `AGENTS.md` is missing | Run setup again |
| HOME002 | error | The home's `README.md` is missing | Run setup again |
| HOME003 | info | The home's `CLAUDE.md` is missing | Run setup again |
| HOME004 | info | The home folder's name doesn't start with its number | The owner can rename it by hand |
| WRK001 | error | A work folder has no hand-off | Write one with the owner, in the format in the workspace rules |
| WRK002 | warn | A work folder has no `AGENTS.md` | Add one that points to the workspace rules |
| WRK003 | warn | A work folder's `AGENTS.md` doesn't point to the workspace rules | Add a link to `../../AGENTS.md` |
| WRK004 | info | A work folder has no `CLAUDE.md` | Add one whose first line is `@AGENTS.md` |
| WRK005 | info | A work folder is missing `README.md`, `DECISIONS.md` or `AGENT_SYNC.md` | With the owner's OK, write it from its template in `assets/templates` |
| HND001 | error | Hand-off headings missing or out of order | Fix them after re-reading the file |
| HND002 | warn | A header field is missing: Purpose, Status, Key or Last updated | Add it |
| HND003 | warn | The status isn't one of the four known ones | Use Active, Paused, Ongoing or Closed |
| HND004 | warn | Last updated isn't a date | Use an ISO date |
| HND005 | info | Files changed after the hand-off was last updated | Read the hand-off and bring it up to date |
| HND006 | info | Active, and the hand-off is older than the limit (30 days) | Ask whether the status or next action changed |
| HND008 | info | The hand-off is over 20 KB | Copy older log lines to a file beside it, link it, then shorten the log with the owner's OK |
| HND009 | info | Active or ongoing work whose Next actions names nothing to do | Ask the owner what comes next, or whether the work is now Paused or Closed |
| HND010 | info | Hand-off lines still marked Unconfirmed | Ask the owner about each one, then replace the mark with the answer and its source |
| MAP001 | warn | A work folder is missing from the map | `map` |
| MAP002 | warn | A map table was edited by hand, or its markers are unclear | Fix it with the owner, then `map` |
| MAP003 | info | A name, status or purpose changed since the map was written | `map` |
| LNK001 | error | A link that points nowhere | The finding names the new target when a logged move explains it |
| DOC001 | warn | An agent file inside a document folder | Ask the owner before moving it |
| DOC002 | info | A document location that isn't on this computer | Nothing. A task that needs it must stop and say so |
| SYNC001 | warn | A sync conflict copy of a managed file | Compare both with the owner. Don't pick by date alone |
| INB001 | info | Items waiting in the Inbox | Go through them with the owner |
| MOV001 | warn | A move that didn't finish | The next command that changes the workspace settles it |
| VER001 | info | The workspace was set up with an older version of the skill | `upgrade --dry-run`, then for real after the OK |
| VER002 | info | This copy of the skill is older than the one that last upgraded the workspace | The owner updates this copy. Leave the workspace's newer rules alone |
| FRC001 | info | Friction notes from agents are waiting in `_workspace/friction.md` | Show them to the owner. They can pass them on, then empty the file |

**Quieting a finding:** with the owner's OK, add `"RULE:path-pattern"` to `suppress` in `_workspace/settings.json`, such as `"HND005:91_Projects/91.02_*"`.

## Upkeep: tidy up

For when hand-offs have drifted. The owner says "tidy up my workspace", or a check lists HND005, HND006, HND008, HND009 or HND010. The script edits no hand-off, so this is done by hand, one work folder at a time.

1. Run `check`. Tell the owner which work folders it names, and ask which to tidy. Finish one before starting the next.
2. Read that folder's `README.md`, hand-off and `DECISIONS.md`. Open other files only when the log points to them.
3. Draft the new hand-off and show the before and after. Write nothing yet.
   - **Current state:** rewritten from the Session log and the files' dates. What is done, in progress and blocked, each with its date. Keep everything that is still true.
   - **Next actions:** finished ones removed, the rest renumbered. If nothing comes next, ask whether the status is now Paused or Closed.
   - **Don't forget:** keep every item that isn't resolved.
   - **Session log:** past about 30 lines, the older ones move to `HANDOFF-log.md` beside the hand-off, in the same order, and How to continue links that file. Copy them first, check the copy, then shorten the log.
   - Mark anything you can't confirm from the files `Unconfirmed`. Don't guess.
4. After the owner's OK for that folder, write it. Set Last updated, and add one Session log line that says the hand-off was tidied.
5. Leave `DECISIONS.md`, other agents' notes in `AGENT_SYNC.md` and the Key line alone. When all are done, run `map`, then `check`.

**On a schedule:** the skill runs nothing by itself. An owner whose tool has scheduled tasks can schedule the words "tidy up my workspace and show me what you'd change". It still waits for their OK.

## Upkeep: after the skill was updated

A workspace remembers which version of the skill set it up. When the copy of the skill is newer, `check` says so (VER001).

1. Run `upgrade --dry-run`. It lists what's new, and shows the exact section it would add to the end of the home's `AGENTS.md`: the rules that workspaces set up today already have.
2. Tell the owner what's new in plain words, and show them that text.
3. After the OK, run `upgrade`. It adds the section, records the new version, and changes nothing else. Then tell the owner to restart tools that read the rules only when they start.

A rule the home's `AGENTS.md` already has is not added twice. To take a rule out again, the owner deletes that section by hand.

## Upkeep: reconcile

`reconcile` proposes; `reconcile --apply` does it. Always show the proposal first.

| Situation | What it proposes |
|---|---|
| The ledger is missing | A new ledger, marked rebuilt, with a line for every numbered folder on disk |
| A second copy of the ledger | Add its new lines to the ledger, and rename the copy so it is kept and no longer in the way |
| A numbered folder the ledger doesn't know | Add it |
| The same number on two folders | Nothing until the owner picks. Then `--keep <number>=<key>`: the other folder gets the next number in its group |
| A home restored from a backup | `--floor <group>=<counter>` with the highest number the owner knows was used |
| Folders deleted for good | `--retire-missing` |

When a folder has no key in its hand-off, the proposal names a key. Add that `**Key:**` line to the hand-off yourself, with the owner's OK.

## Brief me

1. `check --brief` gives every work folder's status, last update and next action, a "Needs attention" list, and a "Not covered by this brief" list.
2. Read the hand-off of every Active or Ongoing work folder, and of each folder under Needs attention: Current state, Next actions, Don't forget.
3. Brief in this order, one line each: due today or tomorrow, or overdue; blocked, or waiting on the owner; hand-offs that look out of date; then at most three things to focus on.
4. End with what the brief didn't cover. Pass on the script's "Not covered" list in your own words: private folders, document folders that aren't on this computer, hand-offs you didn't read, lines still marked Unconfirmed, and everything outside the workspace. Add anything else you couldn't open. A brief that leaves this out reads as the whole picture, and it isn't.
5. Then wait. Don't edit any hand-off, and don't start work the owner hasn't picked.

## Without the script

**The agent can write files and has no Python.** Build a starter by hand, one approved step at a time, and never overwrite a file.

1. Create the home folder, `_workspace/`, and the five group folders, numbered from the home's ten: +0 Inbox, +1 Projects, +2 Areas, +5 Data, +9 Archive.
2. Write `_workspace/settings.json`:
   ```json
   {"version": 1, "skill_version": "0.2.0", "owner": "<name>", "home_number": 90, "separator": "_",
    "handoff_file": "HANDOFF.md", "private": [], "documents": [], "tools": [], "stale_after_days": 30, "suppress": []}
   ```
3. For each file, copy the matching template from `assets/templates`, replace every `{{PLACEHOLDER}}`, and show it before writing it.
4. Number the work folders from `.01` in the order the owner listed them. For each one, make up a key of six characters from `0-9a-f`, put it on the hand-off's Key line, and add one line to `_workspace/ledger.jsonl`:
   ```json
   {"event": "issued", "number": "91.01", "key": "<the key>", "name": "<folder name after the number>", "kind": "project", "group_now": 91, "time": "<ISO timestamp>"}
   ```
5. Stop there. Adding a numbered folder later, and any move, needs the script. Day-to-day work in the folders that exist is fine.

**A chat with a code sandbox and no access to the owner's folders.** Run `kit --answers <file> --out <name>.zip` inside the sandbox. It builds the starter in a temporary folder and writes one ZIP that holds the home folder. In the answers file, leave `location` out, and write each `documents` entry as plain words, such as "a folder called Duplex papers in my Drive": sandbox paths mean nothing on the owner's computer. Hand the ZIP to the owner. Tell them to unzip it where they want the home, and say plainly that nothing was created on their computer yet.

**A chat with neither.** Give the starter as paste-ready files, each with the exact path to save it under.

**Hand-off save-back,** for any chat: the owner uploads or pastes the work folder's hand-off. Work from it. At the end, give back the complete updated hand-off and say "save this over the old `HANDOFF.md`". The work isn't saved until they do.
