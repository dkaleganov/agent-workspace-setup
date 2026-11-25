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
│   ├── 91.01_Website-relaunch/
│   └── _Archive/                closed projects, each kept with its number
│       └── 91.02_Old-brochure/
├── 92_Areas/                    ongoing work
│   └── 92.01_Bookkeeping/
└── 95_Data/                     libraries and archives that agents read
```

The names in this picture are made up.

**How the numbers work**

- **The home's number is your choice:** any ten from 10 to 90. Setup looks at the names of the folders around the place you picked and suggests one that fits. 90 is the suggestion when it's free, because it leaves 10 to 80 for your own folders.
- **Group folders** take numbers inside the home's ten. With a home at 90: 90 Inbox, 91 Projects, 92 Areas, 95 Data. With a home at 10: 10, 11, 12, 15.
- **The groups fit your work.** Setup asks what you work on. With one thing, you get ours. With several kinds of work, the agent proposes groups in your own words and says which pattern they follow: by status, by line of work, one folder for each client, course or other thing you have several of, or a mix. No field is built in: the names come from you. Ours stay on offer. Groups are numbered in the order listed, up to eight besides the Inbox. Each says what goes there, and can say what doesn't. Agents file new work by those lines, and the map shows them. You can add a group later, or change a line.
- **Work folders** get the group's number, a dot and a counter: `91.01`, `91.02`. The script gives the next one.
- **A folder keeps its number for good.** Rename it, archive it, bring it back, move it from Projects to Areas: the number stays. A project that became ongoing work is still `91.03`, now inside `92_Areas`.
- **A number is never used twice,** including after you delete a folder.
- **Names are yours.** Rename `91_Projects` to `91_Jobs` if you like. The script goes by the numbers.
- **99 work folders fit in a group.** When one gets close, the check suggests adding another group, such as `93_Clients`. Ask your agent to "add a group".

**What keeps the numbers honest**

- **The ledger** is a file in `_workspace/` that records every number ever given. Lines are only ever added.
- **The key** is six characters on one line of each hand-off. It ties the folder to its ledger entry, so a folder you renamed by hand is still recognized. Don't change it.
- **The script stops** when the ledger and the folders disagree: the same number on two folders, a numbered folder the ledger doesn't know, a key that doesn't match, or a ledger that is missing. It tells you, and "reconcile" proposes the fix for your OK.
- **Two computers.** If two computers that haven't synced each add a folder, both can get the same number. The check catches it and shows both folders. You pick which one keeps the number, and the other gets the next one.
- **After restoring a backup** of the whole home, tell your agent the highest number you remember using. It continues above that.

The numbering is inspired by [Johnny.Decimal](https://johnnydecimal.com/) by Johnny Noble. It is a looser scheme of its own and copies nothing from it. This skill is independent and isn't endorsed by Johnny.Decimal, which is a trademark of Coruscade Pty Ltd.

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
- **The six standard files are never copied.** An agent updates `HANDOFF.md` in place. A `HANDOFF_v2.md` would leave the next session reading a stale file, so the check flags it.
- **Names that sort.** A dated file starts with its date, such as `2026-01-31 Meeting notes.md`. A recurring series is one work folder, and older files move into a folder for each year once there are about 30.
- **One table, not many folders.** A list of similar things, such as contacts or suppliers, is one table in one file.
- If a task needs a file that isn't there, the agent stops and says so.

## What each file is for

| File | Where | What it's for |
|---|---|---|
| `AGENTS.md` | the AI home | The rules every agent follows. The one place rules live |
| `CLAUDE.md` | the AI home | One line that makes Claude load `AGENTS.md` |
| `README.md` | the AI home | The map. The skill keeps its tables current; your own notes go outside them |
| `_workspace/` | the AI home | The skill's records: settings, the number ledger, the moves log. Not for editing by hand |
| `_workspace/friction.md` | the AI home | One line from an agent each time a command of the skill tripped it. Yours to read, pass on and empty |
| `STATUS.md` | the AI home | Only with a routine: what needs you today. Rewritten by every run |
| `BRIEF.md` | the AI home | How to brief you, step by step, for an agent with or without the skill |
| `_workspace/snapshots/` | the AI home | A copy of a hand-off, kept each time before a tidy-up rewrites it |
| `_workspace/drafts/` | the AI home | The draft of a hand-off while a tidy-up rewrites it. Writing it moves it over the hand-off |
| `AGENTS.md` | each group | Three lines that send an agent to the rules and the map |
| `CLAUDE.md` | each group and work folder | One line that makes Claude load the `AGENTS.md` beside it |
| `README.md` | each work folder | What the work is and how the folder is organized. It changes only when the goal changes |
| `HANDOFF.md` | each work folder | Where the work stands and what's next. The memory |
| `DECISIONS.md` | each work folder | Your decisions, with the date and the reason, so nobody reopens them |
| `AGENT_SYNC.md` | each work folder | Notes between agents and sessions |
| `FACTS.md` | a work folder, when needed | Optional. Facts that outlive a task, each with its source and date |
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

`- **D-001 · YYYY-MM-DD · <title>.** <Decision>. *Why:* <reason>. *Source:* <who and where>.`

Only your decisions go here. When one changes, add a new entry and mark the old one `(Superseded YYYY-MM-DD)`.

**Agent notes** (`AGENT_SYNC.md`): starts `# Agent sync: <name>`. Notes are added at the bottom as `### <timestamp> · <from> → <to> · open | FYI`. Nobody edits another agent's note. A reply is a new note that starts `Re: <timestamp>`.

## Facts and where they came from

- **A fact carries its source.** When an agent writes down a number, a date, a price, a name or a promise that didn't come from its own work in that session, it adds where it came from and when, in brackets: `(the supplier's quote, 2026-01-12)`.
- **Two sources that disagree are both written down,** and the conflict goes under Don't forget until you settle it.
- **What couldn't be checked is marked `Unconfirmed`.** The check counts those lines, and a brief lists them.
- **Facts that outlive a task get their own file.** A name, an address, an account or a term the work will need again goes into `FACTS.md` in the work folder: one line each, as `- <fact> (<source>, <date>)`. The file appears with the first fact. A changed fact gets a new line, and the old one is marked `(Replaced <date>)`. The check flags a line with no source and date. No passwords or keys go there.
- **A brief says what it didn't cover:** private folders, documents that aren't on this computer, hand-offs it didn't read, and everything outside the workspace, such as mail and chat.

## When files disagree

Two files will disagree sooner or later. The rules give every agent the same order:

1. What you tell it now.
2. `DECISIONS.md`: the newest entry that isn't marked Superseded.
3. `HANDOFF.md`: Current state and Next actions. Inside it, the line with the newer date.
4. `README.md`.
5. Notes, drafts and other files.

- **An original document outranks a summary of it.** If a contract says one number and a hand-off another, the contract is right about what it says.
- **An agent never settles a conflict quietly.** It works from the winner, writes a line that starts `Conflict:` with both values and where each came from, and asks you. Your answer becomes a decision.
- **Decisions carry numbers,** such as `D-004`, so a file can cite one and the check can tell when it was replaced.

## Routines are optional

- **A routine runs the check on a schedule.** It rewrites `STATUS.md` at the top of the home and speaks up only when something needs you.
- **You decide.** The skill offers it once. Nothing is scheduled without your yes, and a no is written down so no later session asks again.
- **A run only reads and reports.** It never moves, deletes or edits your files.
- **Its limits are real.** Every scheduler that can see your folder needs its app open and your computer awake. A check can't find a wrong fact that is written the same way everywhere, or anything that was never written down.

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

- **One writer per work folder.** Only the session you are working with edits that folder's hand-off and decisions. Other sessions leave a note in `AGENT_SYNC.md`. The session you are talking to is that writer. A scheduled or background agent is not.
- **Fresh sessions.** Start new work in a new session from the hand-off. A long chat drifts, and some tools replay an old chat's edits over newer files.
- **A brief session** reads across all work folders and reports. It edits no hand-off.

## Your other folders, if you want help

- **It is optional.** Setup asks whether you want only an AI home, or also help with the folders beside it. You can ask later too: "organize my folders".
- **The agent starts from names,** sizes and dates, and asks what each folder is for. Private folders and folders that belong to an app are named first and left alone.
- **You get one numbered list of changes:** create this folder, rename that one, move these files into that one. You approve by number.
- **The numbers are simple.** A folder takes two digits and a name. At the top, an inbox takes 00, an archive 99, and the tens between are yours. One level down, numbers stay inside the parent's ten.
- **No agent file is written there.** The map of your folders, the log of every change, the plan and the keep list all live in the AI home.
- **Nothing is deleted and no file is renamed.** A rename of a folder, a move or a batch of files can be undone.

### Sorting a messy folder: your choice

When files need sorting, the agent shows you two ways and you pick.

- **By name, with you.** The agent sees names, sizes and dates and opens nothing. Where a name doesn't say what a file is, it asks you. Best for private papers, or when the names are already clear.
- **Open and sort.** The agent opens the files in the folders you name and proposes a place for every file. It is cleaner and goes deeper. What it costs: the contents of those files go to your AI tool's service, a file kept only in the cloud is downloaded when it is opened, and it takes longer and uses more of your plan.
- **Before you pick the second way, check your AI tool's privacy settings.** If it has a setting that lets your chats train its models, turn it off first, unless you are fine with these files being used that way. Either way, the contents are sent to the service to be read.
- **What stays the same:** nothing moves before you approve it by number, and every move can be undone. Files whose names look like passwords, keys, identity papers or health records stay closed unless you name them. A private folder can't be picked.
- **The limit you should know:** the skill's script can't stop an agent from opening a file. The rules tell it which files, and your AI tool's own permission prompts are the backstop. A smaller model follows such rules less closely.
- **If you don't choose,** the agent sorts by name.

## Review, by number

- **"Review my workspace"** gives one numbered list of proposed changes: closed work to archive, Inbox items to file, hand-offs to tidy, questions only you can answer.
- **You approve by number.** "Do 1 and 3" does those two and nothing else.
- **Every move is logged** and can be undone, including an Inbox item filed into a work folder. The item is moved unopened.
- **Before a hand-off is rewritten,** a copy of it is kept in `_workspace/snapshots/`. The agent rewrites a draft, the script prints the before and after, and the hand-off changes only after your OK.
- **Structure changes go through the skill.** Agents never rename, move or archive a numbered folder by hand, because the number ledger and the move log would miss it.

## What the skill never does

- It deletes nothing. If something should go, it tells you and you delete it.
- It never overwrites a file. It creates new ones, keeps its own records, and refreshes the tables it owns in the map. After you update the skill and approve it, it adds new rules to the end of the home's `AGENTS.md`.
- It never writes a file outside the AI home. An agent opens a document of yours when your work needs it and you pointed to it, or when you chose "open and sort" for its folder.
- It never touches a folder outside the AI home, unless you ask it to help organize your folders. Then it creates, renames and moves only the folders and files you approve by number, logs each change in the AI home, and can undo a rename, a move or a batch of files.
- It never sends, posts, shares or pays.
