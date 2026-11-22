# The skill's records

The agent-workspace-setup skill keeps its own records in this folder. Don't edit them by hand.

- `settings.json`: the owner's name, the home's number, private folders and document locations.
- `ledger.jsonl`: every number ever given to a work folder. Lines are added, never rewritten.
- `moves.jsonl`: every rename, move, archive and restore, so each can be undone.
- `friction.md`: one line from an agent each time a command of the skill tripped it. It appears with the first note. This one is yours to read, pass on to whoever maintains the skill, and empty.

If these files and the folders ever disagree, the skill stops and says so. Ask your agent to "reconcile the workspace".
