# How to brief {{OWNER_FIRST}}

For any agent. A brief changes no file.

**If the agent-workspace-setup skill is installed in this tool, use it for the brief.** Its `check --brief` gathers steps 1 to 3 in one table and adds what the check found. Without the skill, follow these steps.

1. If `STATUS.md` is in this folder, read it first and say how old it is.
2. Open [README.md](README.md). Find every work folder whose status is Active or Ongoing. Skip `_Archive/` folders and anything private.
3. Read each one's `{{HANDOFF}}`: Current state, Next actions and Don't forget. Open nothing else.
4. Brief in this order, one line per item, each with its work folder's number:
   1. Due or overdue: next actions with `due <date>`.
   2. Waiting on {{OWNER_FIRST}}, or blocked.
   3. Open questions: lines that start `Conflict:` and lines marked `Unconfirmed`.
   4. Out of date: a hand-off not updated in 30 days.
   5. At most three things to focus on next.
5. End with what you couldn't read, and what a brief never covers: private folders and everything outside this workspace. Then wait.
