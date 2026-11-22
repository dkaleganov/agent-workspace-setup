# Principles and formats

Written for people. An agent follows the same rules from the `AGENTS.md` file in the AI home.

## The idea

A chat forgets. A folder doesn't. Keep the memory of your work in plain folders you own, and any AI session in any tool can pick up where the last one stopped. Close the chat. Keep the folder.

## Six principles

1. **Files are the memory.** Every piece of work has a hand-off file that says where it stands and what's next. The agent reads it first and updates it when a task is done.
2. **One AI home, numbered.** All AI work lives in one folder. Numbers keep the order fixed, so you learn where things are.
3. **The script gives every number.** You never pick one, and a number is never used twice.
4. **Documents stay where they are.** Your contracts, statements and photos are read where they live. The skill writes only inside the AI home.
5. **Agents draft, you decide.** Nothing is sent, shared, moved or deleted without your OK for that action.
6. **Keep it light.** Six small files per piece of work, the same in every folder. Start with one project and add the rest when you need them.

## The numbered home

```
90_AI-Agents/                    the AI home; you pick the name and the number
├── AGENTS.md                    the rules every agent follows
├── CLAUDE.md                    one line that points Claude at AGENTS.md
├── README.md                    the map: every folder below and its status
├── _workspace/                  the skill's own records
├── 90_Inbox/                    anything not filed yet
├── 91_Projects/                 work that finishes
│   ├── 91.01_Duplex-renovation/
│   └── _Archive/                closed projects, each kept with its number
│       └── 91.02_Old-fence/
├── 92_Areas/                    ongoing work
│   └── 92.01_Bookkeeping/
└── 95_Data/                     libraries and archives that agents read
```

The names in this picture are made up.

**How the numbers work**

- **The home's number is your choice:** any ten from 10 to 90. Setup looks at the names of the folders around the place you picked and suggests one that fits. 90 is the suggestion when it's free, because it leaves 10 to 80 for your own folders.
- **Group folders** take numbers inside the home's ten. With a home at 90: 90 Inbox, 91 Projects, 92 Areas, 95 Data. With a home at 10: 10, 11, 12, 15.
- **Work folders** get the group's number, a dot and a counter: `91.01`, `91.02`. The script gives the next one.
- **A folder keeps its number for good.** Rename it, archive it, bring it back, move it from Projects to Areas: the number stays. A project that became ongoing work is still `91.03`, now inside `92_Areas`.
- **A number is never used twice,** including after you delete a folder.
- **Names are yours.** Rename `91_Projects` to `91_Jobs` if you like. The script goes by the numbers.
- **99 work folders fit in a group.** When one gets close, the check suggests adding another group, such as `93_Clients`.

**What keeps the numbers honest**

- **The ledger** is a file in `_workspace/` that records every number ever given. Lines are only ever added.
- **The key** is six characters on one line of each hand-off. It ties the folder to its ledger entry, so a folder you renamed by hand is still recognized. Don't change it.
- **The script stops** when the ledger and the folders disagree: the same number on two folders, a numbered folder the ledger doesn't know, a key that doesn't match, or a ledger that is missing. It tells you, and "reconcile" proposes the fix for your OK.
- **Two computers.** If two computers that haven't synced each add a folder, both can get the same number. The check catches it and shows both folders. You pick which one keeps the number, and the other gets the next one.
- **After restoring a backup** of the whole home, tell your agent the highest number you remember using. It continues above that.

The numbering is inspired by [Johnny.Decimal](https://johnnydecimal.com/) by John Noble. It is a looser scheme of its own and copies nothing from it. This skill is independent and isn't endorsed by Johnny.Decimal.

## Closed work

- **Each group keeps its own archive.** When you close a piece of work, its folder moves into `_Archive` inside the group it is in: a closed project stays under Projects, a closed area under Areas. Nothing is deleted.
- **The folder appears on first use.** A group has no `_Archive` until something in it is archived.
- **You can always see where it came from:** it sits in its own group, with its number, and the map still lists it as archived.
- **Archived work is frozen.** To pick it up again, ask to restore it. It goes back into the same group.
- **Workspaces from the first two versions** have one archive for the whole workspace, such as `99_Archive`. It keeps working. The check lists what is in it, and you can ask to move a folder into its own group's archive, one at a time.

## Documents stay apart

- Leave your existing folders exactly where they are. A work folder records where its documents live, and the agent opens them by path.
- No agent files go into document folders. Changing or adding a document there needs your OK for that action.
- **One master per deliverable.** Drafts live in the work folder as `_v1`, `_v2`. Once you approve one, the hand-off's "Main files" line says where the master lives.
- If a task needs a file that isn't there, the agent stops and says so.

## What each file is for

| File | Where | What it's for |
|---|---|---|
| `AGENTS.md` | the AI home | The rules every agent follows. The one place rules live |
| `CLAUDE.md` | the AI home | One line that makes Claude load `AGENTS.md` |
| `README.md` | the AI home | The map. The skill keeps its tables current; your own notes go outside them |
| `_workspace/` | the AI home | The skill's records: settings, the number ledger, the moves log. Not for editing by hand |
| `_workspace/friction.md` | the AI home | One line from an agent each time a command of the skill tripped it. Yours to read, pass on and empty |
| `AGENTS.md` | each group | Three lines that send an agent to the rules and the map |
| `CLAUDE.md` | each group and work folder | One line that makes Claude load the `AGENTS.md` beside it |
| `README.md` | each work folder | What the work is and how the folder is organized. It changes only when the goal changes |
| `HANDOFF.md` | each work folder | Where the work stands and what's next. The memory |
| `DECISIONS.md` | each work folder | Your decisions, with the date and the reason, so nobody reopens them |
| `AGENT_SYNC.md` | each work folder | Notes between agents and sessions |
| `AGENTS.md` | each work folder | A pointer to the home's rules and four starter rules, plus any rules for this work only |

Every work folder starts with the same six files, so any project or area reads the same way.

## Formats

**Hand-off** (`HANDOFF.md`): a title, three header lines, then five headings in this order.

```markdown
# Handoff: <name>

**Purpose:** <one line> · **Status:** Active | Paused | Ongoing | Closed
**Main files:** <current deliverables and where they live, or "none yet">
**Key:** <six characters; never change this> · **Last updated:** <ISO timestamp> by <tool>

## How to continue
## Current state
## Next actions
## Don't forget
## Session log
```

Keep it short. Past about 20 KB, some tools stop reading. Copy older Session log lines to a file beside it and link that file from How to continue.

**Decisions** (`DECISIONS.md`): starts `# Decisions: <name>`, then one entry per decision, newest first.

`- **YYYY-MM-DD · <title>.** <Decision>. *Why:* <reason>. *Source:* <who and where>.`

Only your decisions go here. When one changes, add a new entry and mark the old one `(Superseded YYYY-MM-DD)`.

**Agent notes** (`AGENT_SYNC.md`): starts `# Agent sync: <name>`. Notes are added at the bottom as `### <timestamp> · <from> → <to> · open | FYI`. Nobody edits another agent's note. A reply is a new note that starts `Re: <timestamp>`.

## Facts and where they came from

- **A fact carries its source.** When an agent writes down a number, a date, a price, a name or a promise that didn't come from its own work in that session, it adds where it came from and when, in brackets: `(the supplier's quote, 2026-01-12)`.
- **Two sources that disagree are both written down,** and the conflict goes under Don't forget until you settle it.
- **What couldn't be checked is marked `Unconfirmed`.** The check counts those lines, and a brief lists them.
- **A brief says what it didn't cover:** private folders, documents that aren't on this computer, hand-offs it didn't read, and everything outside the workspace, such as mail and chat.

## Private folders

Tell the skill which folders are private. The script never lists or opens them, and the rules tell every agent the same.

An honest limit: the skill can't block an agent from reading a file. For anything truly confidential, use your tool's own deny rules, or keep those files where no agent can reach.

## A piece of work, start to finish

1. **Start:** the skill creates the numbered folder with its six standard files.
2. **Work:** drafts as `_v1`, `_v2`. The hand-off is updated after each finished task.
3. **Confirm:** you approve a version. "Main files" says where the master lives.
4. **Share:** only with your OK for that action.
5. **Close:** the status becomes Closed. When you say so, the folder moves into its group's `_Archive` and keeps its number.

## Sessions and agents

- **One writer per work folder.** Only the session you are working with edits that folder's hand-off and decisions. Other sessions leave a note in `AGENT_SYNC.md`.
- **Fresh sessions.** Start new work in a new session from the hand-off. A long chat drifts, and some tools replay an old chat's edits over newer files.
- **A brief session** reads across all work folders and reports. It edits no hand-off.

## What the skill never does

- It deletes nothing. If something should go, it tells you and you delete it.
- It never overwrites a file. It creates new ones, keeps its own records, and refreshes the tables it owns in the map. After you update the skill and approve it, it adds new rules to the end of the home's `AGENTS.md`.
- It never touches a folder outside the AI home.
- It never sends, posts, shares or pays.
