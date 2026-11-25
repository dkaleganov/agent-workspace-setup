# The skill's records

The agent-workspace-setup skill keeps its own records in this folder. Don't edit them by hand.

- `settings.json`: the owner's name, the home's number, private folders and document locations.
- `ledger.jsonl`: every number ever given to a work folder. Lines are added, never rewritten.
- `moves.jsonl`: every rename, move, archive, restore and filed Inbox item, so each can be undone.
- `layout.jsonl` and `layout-plan.json`: only if you asked for help with the folders beside the home. Every change made there, the way you chose to sort files, and the last plan you were shown.
- `snapshots/`: a copy of a hand-off, kept each time before a tidy-up rewrites it. It appears with the first copy. Yours to clear out.
- `drafts/`: the draft of a hand-off while a tidy-up rewrites it. It appears with the first tidy-up. A draft left there was never written: yours to remove.
- `friction.md`: one line from an agent each time a command of the skill tripped it. It appears with the first note. This one is yours to read, pass on to whoever maintains the skill, and empty.

If these files and the folders ever disagree, the skill stops and says so. Ask your agent to "reconcile the workspace".
