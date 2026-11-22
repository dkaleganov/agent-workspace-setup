#!/usr/bin/env python3
"""workspace.py: set up and keep a numbered AI agent workspace.

One file, Python 3.9 or later, standard library only. Part of the
agent-workspace-setup skill.

What it promises:
- It previews before it changes anything (--dry-run on every command that writes).
- It creates new files and folders only; an existing file is never overwritten.
- It deletes nothing the owner made.
- Every rename and move is logged first and can be undone.
- It stops when its records and the folders on disk disagree.
- Every command ends with a "Next:" line that says what to do next.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import sys
import tempfile
import time
import traceback
import urllib.parse
import zipfile
from pathlib import Path

__version__ = "0.3.0"

SKILL = "agent-workspace-setup"
RECORDS = "_workspace"
SETTINGS_FILE = "settings.json"
LEDGER_FILE = "ledger.jsonl"
MOVES_FILE = "moves.jsonl"
FRICTION_FILE = "friction.md"
# Closed work goes here, inside the group it belongs to.
ARCHIVE_DIR = "_Archive"
# A workspace whose settings name no version was set up by the first release.
FIRST_VERSION = "0.1.0"

# What each version changed for a workspace that already exists, oldest first. "rules" are the bold titles
# of rules in the home-AGENTS.md template that a workspace set up before that version doesn't have yet.
UPGRADES = [
    {
        "version": "0.2.0",
        "news": [
            "A brief now ends with what it didn't cover: private folders, documents that aren't on this computer, "
            "hand-offs it didn't read, and everything outside the workspace.",
            "The check names work with no next action, and hand-off lines still marked Unconfirmed.",
            "A new request, \"tidy up my workspace\": it brings a hand-off up to date from its own log, "
            "one work folder at a time, and shows the change before making it.",
            "When a command trips an agent, it adds one line to `%s/%s`, so the owner can pass the notes on."
            % (RECORDS, FRICTION_FILE),
            "A new rule for agents: say where a fact came from.",
        ],
        "rules": ["Say where a fact came from."],
    },
    {
        "version": "0.3.0",
        "news": [
            "Closed work now goes into an `%s` folder inside its own group, so it stays beside the work it belonged to. "
            "There is no single archive for the whole workspace any more." % ARCHIVE_DIR,
            "A folder that is already in the old archive stays valid. The check lists those folders, and "
            "\"archive <number>\" moves one into the archive of the group it came from, after a preview.",
            "Agents don't work inside an archive. They restore the folder first.",
        ],
        "rules": ["Closed work goes into its own group's archive."],
        "note": "This replaces any older line in this file about one archive folder for the whole workspace.",
    },
]

# Group numbers are offsets from the home's ten: a home numbered 90 gets 90, 91, 92, 95, 99.
GROUPS = {
    0: ("Inbox", "Anything not filed yet."),
    1: ("Projects", "Work that finishes."),
    2: ("Areas", "Ongoing work."),
    5: ("Data", "Libraries and archives that agents read."),
    # Offset 9 is the old archive for the whole workspace. New workspaces don't get one: each group keeps its own.
    9: ("Archive", "Closed work from before each group had its own archive."),
}
KINDS = {"project": 1, "area": 2, "data": 5}
STATUSES = ("Active", "Paused", "Ongoing", "Closed")
HEADINGS = ["How to continue", "Current state", "Next actions", "Don't forget", "Session log"]
AGENT_FILES = ("AGENTS.md", "CLAUDE.md", "HANDOFF.md", "DECISIONS.md", "AGENT_SYNC.md")
DEFAULT_SETTINGS = {
    "version": 1,
    "owner": "",
    "home_number": 90,
    "separator": "_",
    "handoff_file": "HANDOFF.md",
    "private": [],
    "documents": [],
    "tools": [],
    "stale_after_days": 30,
    "suppress": [],
}
LIST_KEYS = ("private", "documents", "tools", "suppress")

GROUP_RE = re.compile(r"^(\d{2})[_ ](.+)$")
WORK_RE = re.compile(r"^(\d{2})\.(\d{2})[_ ](.+)$")
KEY_RE = re.compile(r"\*\*Key:\*\*\s*([0-9a-f]{6})\b")
MARK_RE = re.compile(
    r"<!-- agent-workspace-setup:(\w+)(?: sha=([0-9a-f]{12}))? -->\n(.*?)<!-- /agent-workspace-setup:\1 -->",
    re.S,
)
MAX_PATH = 250
# Paths that exist only inside one agent session. They mean nothing later, so they are never recorded.
SESSION_PATHS = ("/sessions/", "/mnt/user-data/", "/mnt/data/", "/home/claude/")
HANDOFF_LIMIT = 20000


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

class Refuse(Exception):
    """A refusal with a reason and the next step. Nothing was changed."""

    def __init__(self, message, next_step):
        super().__init__(message)
        self.message = message
        self.next_step = next_step


class Out:
    """Collects a command's output, then prints it with the Next line."""

    def __init__(self):
        self.lines = []

    def say(self, text=""):
        self.lines.append(text)

    def finish(self, next_step, code=0):
        print("\n".join(self.lines).rstrip("\n"))
        print()
        print("**Next:** " + next_step)
        return code


def now():
    return dt.datetime.now().astimezone().replace(microsecond=0)


def iso(moment=None):
    text = (moment or now()).strftime("%Y-%m-%dT%H:%M%z")
    if len(text) > 5 and text[-5] in "+-":
        text = text[:-2] + ":" + text[-2:]
    return text


def today():
    return now().strftime("%Y-%m-%d")


def host():
    name = os.environ.get("AGENT_WORKSPACE_HOST") or platform.node() or "unknown"
    return name.split(".")[0] or "unknown"


def new_key():
    return secrets.token_hex(3)


def read_text(path):
    return Path(path).read_text(encoding="utf-8-sig")


def write_new(path, text):
    """Create a file. Fails if it exists, so nothing is ever overwritten."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def append_line(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def slug(title):
    """A folder-safe name from a title. Keeps the owner's capitals and hyphens."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(title))
    text = text.strip().strip(".")
    text = re.sub(r"\s+", "-", text)
    text = text[:60].rstrip("-. _")
    return text or "Work"


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def link(target):
    return urllib.parse.quote(target, safe="/._-~")


def tilde(path):
    path = str(path)
    home_dir = str(Path.home())
    if path == home_dir or path.startswith(home_dir + os.sep):
        return "~" + path[len(home_dir):].replace(os.sep, "/")
    return path


def bullets(items):
    return "\n".join("- " + item for item in items)


def version_tuple(text):
    parts = re.findall(r"\d+", str(text or ""))[:3]
    return tuple(int(part) for part in parts) if len(parts) == 3 else (0, 1, 0)


# ----------------------------------------------------------------------------
# The home, its settings, and what is on disk
# ----------------------------------------------------------------------------

def load_settings(path):
    path = Path(path)
    try:
        data = json.loads(read_text(path))
    except OSError as error:
        raise Refuse(
            "Can't read the settings file `%s`: %s" % (tilde(path), error),
            "Check that this folder is a workspace, or pass --home with the workspace folder.",
        )
    except ValueError as error:
        raise Refuse(
            "The settings file `%s` isn't valid JSON: %s" % (tilde(path), error),
            "Fix the file with the owner, then run the command again.",
        )
    if not isinstance(data, dict):
        raise Refuse(
            "The settings file `%s` must hold one JSON object." % tilde(path),
            "Fix the file with the owner, then run the command again.",
        )
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    for key in LIST_KEYS:
        value = merged.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise Refuse(
                "`%s`: %s must be a list of strings." % (tilde(path), key),
                "Fix the file with the owner, then run the command again.",
            )
    return merged


def valid_ten(value):
    return isinstance(value, int) and not isinstance(value, bool) and value in range(10, 100, 10)


class Home:
    def __init__(self, root, settings=None):
        self.root = Path(root)
        self.records = self.root / RECORDS
        self.settings = settings if settings is not None else load_settings(self.records / SETTINGS_FILE)
        number = self.settings.get("home_number")
        if not valid_ten(number):
            raise Refuse(
                "The settings give the home the number `%s`. It has to be a ten from 10 to 90." % number,
                "Fix `home_number` in `%s/%s` with the owner." % (RECORDS, SETTINGS_FILE),
            )
        self.number = number
        self.sep = self.settings.get("separator") or "_"
        self.handoff = self.settings.get("handoff_file") or "HANDOFF.md"

    def group_no(self, offset):
        return self.number + offset

    def rel(self, path):
        return Path(path).relative_to(self.root).as_posix()

    def owner_first(self):
        owner = (self.settings.get("owner") or "").strip()
        return owner.split()[0] if owner else "the owner"

    def skill_version(self):
        """The version of the skill that set this workspace up, or last upgraded it."""
        return str(self.settings.get("skill_version") or FIRST_VERSION)

    def is_private(self, rel_path):
        rel_path = rel_path.strip("/").lower()
        for pattern in self.settings.get("private", []):
            pattern = pattern.replace("\\", "/").strip("/").lower()
            if not pattern:
                continue
            if rel_path == pattern or rel_path.startswith(pattern + "/") or fnmatch.fnmatch(rel_path, pattern):
                return True
        return False


def find_home(start):
    start = Path(start).expanduser().resolve()
    for folder in [start] + list(start.parents):
        if (folder / RECORDS / SETTINGS_FILE).is_file():
            return folder
    return None


def open_home(args):
    if getattr(args, "home", None):
        root = Path(args.home).expanduser().resolve()
        if not (root / RECORDS / SETTINGS_FILE).is_file():
            raise Refuse(
                "`%s` isn't a workspace: it has no `%s/%s`." % (tilde(root), RECORDS, SETTINGS_FILE),
                "Pass the workspace folder with --home, or run setup to create one.",
            )
    else:
        root = find_home(Path.cwd())
        if root is None:
            raise Refuse(
                "No workspace found in this folder or above it.",
                "Pass the workspace folder with --home, or run setup to create one.",
            )
    return Home(root)


def groups_on_disk(home):
    """Group folders at the home's top level, by number. Returns (groups, extras)."""
    groups, extras = {}, []
    if not home.root.is_dir():
        return groups, extras
    for child in sorted(home.root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_symlink() or not child.is_dir():
            continue
        match = GROUP_RE.match(child.name)
        if not match:
            continue
        number = int(match.group(1))
        if number // 10 * 10 != home.number or number in groups:
            extras.append(child)
            continue
        groups[number] = child
    return groups, extras


def read_key(handoff_path):
    try:
        match = KEY_RE.search(read_text(handoff_path))
    except (OSError, UnicodeError):
        return None
    return match.group(1) if match else None


def work_on_disk(home, groups):
    """Folders directly inside the group folders, and inside each group's archive. Numbered ones carry number and key."""
    items = []
    archive_no = home.group_no(9)

    def folders(parent):
        try:
            children = sorted(parent.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return []
        return [child for child in children
                if not child.is_symlink() and child.is_dir() and not child.name.startswith((".", "_"))
                and not home.is_private(home.rel(child))]

    def add(child, group_no, archived, legacy):
        match = WORK_RE.match(child.name)
        handoff = child / home.handoff
        item = {
            "path": child,
            "rel": home.rel(child),
            "folder": child.name,
            "group_now": group_no,
            "archived": archived,
            "legacy": legacy,  # True for a folder in the old archive for the whole workspace
            "number": None,
            "name": child.name,
            "key": read_key(handoff) if handoff.is_file() else None,
            "has_handoff": handoff.is_file(),
        }
        if match:
            item["number"] = "%s.%s" % (match.group(1), match.group(2))
            item["name"] = match.group(3)
        items.append(item)

    for group_no, group_path in sorted(groups.items()):
        if home.is_private(home.rel(group_path)):
            continue
        old_archive = group_no == archive_no
        for child in folders(group_path):
            add(child, group_no, old_archive, old_archive)
        shelf = group_path / ARCHIVE_DIR
        if not old_archive and shelf.is_dir() and not shelf.is_symlink() and not home.is_private(home.rel(shelf)):
            for child in folders(shelf):
                add(child, group_no, True, False)
    return items


# ----------------------------------------------------------------------------
# The ledger: every number ever given. Lines are added, never rewritten.
# ----------------------------------------------------------------------------

def read_ledger(home):
    """Returns (events, problems). Problems are (rule, message) pairs."""
    events, problems = [], []
    path = home.records / LEDGER_FILE
    if home.records.is_dir():
        for other in sorted(home.records.iterdir()):
            name = other.name.lower()
            if other.name != LEDGER_FILE and name.startswith("ledger") and name.endswith(".jsonl"):
                problems.append(("LED003", "`%s/%s` looks like a second copy of the ledger." % (RECORDS, other.name)))
    if not path.is_file():
        problems.append(("LED001", "The number ledger `%s/%s` is missing." % (RECORDS, LEDGER_FILE)))
        return events, problems
    for index, line in enumerate(read_text(path).splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict) or "event" not in event:
                raise ValueError("not an event")
        except ValueError:
            problems.append(("LED002", "Line %d of the ledger can't be read." % index))
            continue
        events.append(event)
    return events, problems


def replay(events):
    """Current state from the ledger: entries by key, and the highest counter per group."""
    entries, highest = {}, {}

    def bump(number):
        group, counter = number.split(".")
        highest[int(group)] = max(highest.get(int(group), 0), int(counter))

    for event in events:
        kind, key = event.get("event"), event.get("key")
        if kind in ("issued", "adopted") and key and event.get("number"):
            number = event["number"]
            entries[key] = {
                "key": key,
                "number": number,
                "name": event.get("name", ""),
                "kind": event.get("kind", "project"),
                "state": event.get("state", "active"),
                "group_now": int(event.get("group_now", number[:2])),
                "time": event.get("time", ""),
            }
            bump(number)
        elif kind == "floor":
            group = int(event["group"])
            highest[group] = max(highest.get(group, 0), int(event["counter"]))
        elif key in entries:
            entry = entries[key]
            if kind == "renamed":
                entry["name"] = event.get("name", entry["name"])
            elif kind == "archived":
                entry["state"] = "archived"
            elif kind in ("restored", "unretired"):
                entry["state"] = "active"
                if event.get("to_group") is not None:
                    entry["group_now"] = int(event["to_group"])
            elif kind == "moved":
                entry["group_now"] = int(event["to_group"])
            elif kind == "retired":
                entry["state"] = "retired"
            elif kind == "renumbered":
                entry["number"] = event["to"]
                bump(event["to"])
    return entries, highest


class State:
    """Everything the commands need to know about a home, read once."""

    def __init__(self, home):
        self.home = home
        self.groups, self.extra_groups = groups_on_disk(home)
        self.disk = work_on_disk(home, self.groups)
        self.events, self.ledger_problems = read_ledger(home)
        self.entries, self.highest = replay(self.events)

    def numbered(self):
        return [item for item in self.disk if item["number"]]

    def blockers(self):
        """Disagreements that stop the script from giving out a number or moving a folder."""
        found = [(rule, "%s/%s" % (RECORDS, LEDGER_FILE), message) for rule, message in self.ledger_problems]
        by_number = {}
        for item in self.numbered():
            by_number.setdefault(item["number"], []).append(item)
        for number, items in sorted(by_number.items()):
            if len(items) > 1:
                names = ", ".join("`%s`" % item["rel"] for item in items)
                found.append(("NUM001", items[0]["rel"], "Number %s is on %d folders: %s." % (number, len(items), names)))
        ledger_numbers = {}
        for entry in self.entries.values():
            if entry["state"] != "retired":
                ledger_numbers.setdefault(entry["number"], []).append(entry)
        for number, entries in sorted(ledger_numbers.items()):
            if len(entries) > 1 and number not in by_number:
                found.append(("NUM001", "%s/%s" % (RECORDS, LEDGER_FILE), "The ledger has number %s twice." % number))
        for item in self.numbered():
            entry = self.entries.get(item["key"]) if item["key"] else None
            if entry is not None:
                if entry["number"] != item["number"]:
                    found.append((
                        "NUM003", item["rel"],
                        "The key in this folder's hand-off belongs to number %s in the ledger." % entry["number"],
                    ))
                continue
            same_number = [e for e in self.entries.values() if e["number"] == item["number"]]
            if not same_number:
                found.append(("NUM002", item["rel"], "Number %s isn't in the ledger." % item["number"]))
            elif item["key"]:
                found.append((
                    "NUM003", item["rel"],
                    "The key in this folder's hand-off isn't the one the ledger has for %s." % item["number"],
                ))
        return found

    def next_counter(self, group_no, already=0):
        top = self.highest.get(group_no, 0)
        for item in self.numbered():
            if int(item["number"][:2]) == group_no:
                top = max(top, int(item["number"][3:]))
        return top + 1 + already

    def find(self, number):
        """The one live folder with this number, and its ledger entry."""
        number = number.strip()
        if not re.match(r"^\d{2}\.\d{2}$", number):
            raise Refuse(
                "`%s` isn't a work folder number. Numbers look like `%d.01`." % (number, self.home.group_no(1)),
                "Run check to list the work folders and their numbers.",
            )
        items = [item for item in self.numbered() if item["number"] == number]
        if not items:
            raise Refuse("No folder has the number %s." % number, "Run check to list the work folders and their numbers.")
        if len(items) > 1:
            raise Refuse(
                "Number %s is on %d folders, so it's unclear which one you mean." % (number, len(items)),
                "Run reconcile and let the owner pick which folder keeps the number.",
            )
        item = items[0]
        entry = self.entries.get(item["key"]) if item["key"] else None
        if entry is None:
            matches = [e for e in self.entries.values() if e["number"] == number]
            entry = matches[0] if len(matches) == 1 else None
        if entry is None:
            raise Refuse("Number %s isn't in the ledger." % number, "Run reconcile to bring the records up to date.")
        return item, entry


def stop_on_blockers(state, doing):
    blockers = state.blockers()
    if blockers:
        lines = ["- `%s` (%s): %s" % (path, rule, message) for rule, path, message in blockers]
        raise Refuse(
            "The workspace's records and its folders disagree, so I can't %s. Nothing was changed:\n%s"
            % (doing, "\n".join(lines)),
            "Run reconcile, show the owner what it proposes, and apply it after their OK.",
        )


@contextlib.contextmanager
def lock(home):
    """One session at a time on this computer. Other computers are not locked out."""
    path = home.records / ("lock-" + host())
    home.records.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(handle, ("%s %s\n" % (os.getpid(), iso())).encode("utf-8"))
        os.close(handle)
    except FileExistsError:
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            age = 0
        if age < 600:
            raise Refuse(
                "Another session on this computer is changing the workspace right now.",
                "Wait a minute, then run the command again.",
            )
        os.utime(str(path), None)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


# ----------------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------------

def template_dir():
    return Path(__file__).resolve().parent.parent / "assets" / "templates"


def render(name, context):
    lines = []
    for line in read_text(template_dir() / name).splitlines():
        lone = re.fullmatch(r"\{\{([A-Z_]+)\}\}", line.strip())
        if lone and str(context.get(lone.group(1), "x")) == "":
            continue

        def fill(match):
            key = match.group(1)
            if key not in context:
                raise Refuse(
                    "The template `%s` asks for `%s`, which the script doesn't provide." % (name, key),
                    "This is a fault in the skill. Tell the owner and stop.",
                )
            return str(context[key])

        lines.append(re.sub(r"\{\{([A-Z_]+)\}\}", fill, line))
    return "\n".join(lines) + "\n"


def group_label(home, groups, offset):
    number = home.group_no(offset)
    if number in groups:
        return groups[number].name
    return "%d%s%s" % (number, home.sep, GROUPS[offset][0])


def home_context(home, groups):
    private = home.settings.get("private", [])
    documents = home.settings.get("documents", [])
    return {
        "HOME_NAME": home.root.name,
        "OWNER": home.settings.get("owner", ""),
        "OWNER_FIRST": home.owner_first(),
        "DATE": today(),
        "HANDOFF": home.handoff,
        "G_INBOX": group_label(home, groups, 0) + "/",
        "G_PROJECTS": group_label(home, groups, 1) + "/",
        "G_AREAS": group_label(home, groups, 2) + "/",
        "G_DATA": group_label(home, groups, 5) + "/",
        "G_ARCHIVE": group_label(home, groups, 9) + "/",
        "EXAMPLE_NUMBER": "%d.01" % home.group_no(1),
        "PRIVATE_NAMES": ", ".join("`%s`" % item for item in private) if private else "none yet",
        "DOCUMENTS_BULLETS": "\n".join("  - `%s`" % item for item in documents),
    }


def record_location(home, raw):
    """How a document location is written down: relative to the home if it sits nearby, else from ~/."""
    if str(raw).replace("\\", "/").startswith(SESSION_PATHS):
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return str(raw).replace("\\", "/")
    path = Path(os.path.realpath(str(path)))
    try:
        relative = os.path.relpath(str(path), str(home.root))
    except ValueError:
        relative = None
    if relative is not None and relative.count("..") <= 2:
        return relative.replace(os.sep, "/")
    shown = tilde(path)
    if shown.replace(os.sep, "/").startswith(SESSION_PATHS):
        return None
    return shown


def resolve_location(home, recorded):
    path = Path(recorded).expanduser()
    if not path.is_absolute():
        path = home.root / recorded
    return Path(os.path.normpath(str(path)))


# ----------------------------------------------------------------------------
# Hand-offs
# ----------------------------------------------------------------------------

def parse_handoff(text):
    info = {"title": None, "fields": {}, "headings": [], "next_action": None}
    for line in text.splitlines():
        match = re.match(r"#\s*Handoff:\s*(.+)", line)
        if match:
            info["title"] = match.group(1).strip()
        break
    for name in ("Purpose", "Status", "Main files", "Key", "Last updated"):
        match = re.search(
            r"\*\*" + re.escape(name) + r":\*\*[ \t]*(.*?)(?=[ \t]+·[ \t]+\*\*[A-Z][^*\n]*:\*\*|$)", text, re.M
        )
        if match:
            info["fields"][name] = match.group(1).strip()
    info["headings"] = [m.group(1).strip() for m in re.finditer(r"^##[ \t]+(.+?)[ \t]*$", text, re.M)]
    section = re.search(r"^##[ \t]+Next actions[ \t]*$(.*?)(?=^##[ \t]|\Z)", text, re.M | re.S)
    if section:
        first = (re.search(r"^[ \t]*1[.)][ \t]+(.+)$", section.group(1), re.M)
                 or re.search(r"^[ \t]*[-*][ \t]+(.+)$", section.group(1), re.M))
        if first:
            info["next_action"] = first.group(1).strip()
    return info


def no_next_action(text):
    """True when a hand-off's first next action is missing, or only says there is none."""
    return not re.sub(r"(?i)\b(none|nothing|n/?a|tbd|yet)\b|[\W_]", "", text or "")


def handoff_info(home, item):
    path = item["path"] / home.handoff
    if not path.is_file():
        return None
    try:
        return parse_handoff(read_text(path))
    except (OSError, UnicodeError):
        return None


# ----------------------------------------------------------------------------
# The map: tables between the script's own markers in the home's README
# ----------------------------------------------------------------------------

def fingerprint(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def map_tables(home, state):
    rows = ["| Group | What goes there |", "|---|---|"]
    for number, path in sorted(state.groups.items()):
        offset = number - home.number
        about = GROUPS[offset][1] if offset in GROUPS else "Your own group."
        if home.is_private(home.rel(path)):
            about = "Private."
        rows.append("| [%s](%s/) | %s |" % (cell(path.name), link(path.name), about))
    groups_table = "\n".join(rows) + "\n"

    rows = ["| Number | Work folder | Status | Purpose |", "|---|---|---|---|"]
    numbered = sorted(state.numbered(), key=lambda item: (item["number"], item["rel"]))
    for item in numbered:
        info = handoff_info(home, item)
        if info is None:
            title, status, purpose = item["name"].replace("-", " "), "Hand-off missing", ""
            target = item["rel"] + "/"
        else:
            title = info["title"] or item["name"].replace("-", " ")
            status = info["fields"].get("Status", "")
            purpose = info["fields"].get("Purpose", "")
            target = item["rel"] + "/" + home.handoff
        if item["archived"]:
            status = "Archived" if not status else status + " (archived)"
        rows.append("| %s | [%s](%s) | %s | %s |" % (item["number"], cell(title), link(target), cell(status), cell(purpose)))
    if not numbered:
        rows.append("| | None yet | | |")
    return {"groups": groups_table, "work": "\n".join(rows) + "\n"}


def refresh_map(home, state, write):
    """Returns (status, message). Only the text between the script's own markers is ever written."""
    path = home.root / "README.md"
    if not path.is_file():
        return "no-readme", "`README.md` is missing, so there is no map to refresh."
    text = read_text(path)
    tables = map_tables(home, state)
    new_text, changed = text, False
    for name, table in tables.items():
        opens = len(re.findall(r"<!-- agent-workspace-setup:%s(?: sha=[0-9a-f]{12})? -->" % name, text))
        closes = text.count("<!-- /agent-workspace-setup:%s -->" % name)
        if opens == 0 and closes == 0:
            continue
        if opens != 1 or closes != 1:
            return "unclear", "The `%s` markers in `README.md` are unclear, so the map was left alone." % name
        match = None
        for candidate in MARK_RE.finditer(new_text):
            if candidate.group(1) == name:
                match = candidate
        if match is None:
            return "unclear", "The `%s` markers in `README.md` are unclear, so the map was left alone." % name
        stamp, body = match.group(2), match.group(3)
        if stamp and fingerprint(body) != stamp:
            return "hand-edited", (
                "The `%s` table in `README.md` was edited by hand, so the map was left alone. "
                "Move your notes outside the markers, or put the table back." % name
            )
        if body == table and stamp == fingerprint(table):
            continue
        block = "<!-- agent-workspace-setup:%s sha=%s -->\n%s<!-- /agent-workspace-setup:%s -->" % (
            name, fingerprint(table), table, name,
        )
        new_text = new_text[:match.start()] + block + new_text[match.end():]
        changed = True
    if "<!-- agent-workspace-setup:" not in text:
        return "no-markers", "`README.md` has no map markers. It looks hand-written, so it was left alone."
    if not changed:
        return "current", "The map is current."
    if write:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(new_text)
        return "updated", "The map tables in `README.md` were refreshed."
    return "would-update", "The map tables in `README.md` would be refreshed."


# ----------------------------------------------------------------------------
# init
# ----------------------------------------------------------------------------

def suggest_number(location):
    """A ten that fits the folders around the chosen place: 90 when free, else the highest free ten."""
    used = set()
    try:
        names = [child.name for child in Path(location).iterdir() if child.is_dir()]
    except OSError:
        names = []
    for name in names:
        match = re.match(r"^(\d{2})(?:-\d{2})?[_ .-]", name)
        if match:
            used.add(int(match.group(1)) // 10 * 10)
    if 90 not in used:
        reason = "90 is free here" if used else "nothing here is numbered yet, so 90 leaves 10 to 80 for your own folders"
        return 90, reason, sorted(used)
    for ten in range(80, 0, -10):
        if ten not in used:
            return ten, "90 is taken here, and %d is the highest free ten" % ten, sorted(used)
    return 90, "every ten is taken here, so pick the one that fits", sorted(used)


def homes_in(location):
    """Workspaces that sit directly inside a folder."""
    found = []
    try:
        children = sorted(Path(location).resolve().iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return found
    for child in children:
        if child.is_dir() and not child.is_symlink() and (child / RECORDS / SETTINGS_FILE).is_file():
            found.append(child)
    return found


def candidate_places():
    """Likely places for the home. Quietly empty when a sandbox forbids looking at the home folder."""
    places = []
    home_dir = Path.home()
    try:
        cloud = home_dir / "Library" / "CloudStorage"
        if cloud.is_dir():
            for child in sorted(cloud.iterdir()):
                if child.is_dir():
                    inner = child / "My Drive"
                    places.append(inner if inner.is_dir() else child)
        children = sorted(home_dir.iterdir())
        for name in ("Dropbox", "Google Drive", "iCloud Drive", "OneDrive", "Nextcloud", "Box", "Sync"):
            for child in children:
                if child.is_dir() and child.name.startswith(name) and child not in places:
                    places.append(child)
        documents = home_dir / "Documents"
        if documents.is_dir():
            places.append(documents)
    except OSError:
        pass
    return places


def cmd_init(args):
    out = Out()
    if args.path:
        place = Path(args.path).expanduser().resolve()
        if not place.is_dir():
            raise Refuse("`%s` isn't a folder." % tilde(place), "Ask the owner where the AI home should live.")
        existing = find_home(place)
        if existing is not None:
            out.say("`%s` is already inside a workspace: `%s`." % (tilde(place), tilde(existing)))
            return out.finish("Run check there, or ask the owner whether they want a second workspace somewhere else.")
        inside = homes_in(place)
        if inside:
            out.say("A workspace is already in `%s`: %s." % (tilde(place), ", ".join("`%s`" % path.name for path in inside)))
            return out.finish("Run check on it, or run setup with the same `location`: it adds only what is missing.")
        number, reason, used = suggest_number(place)
        out.say("# A place for the AI home")
        out.say()
        out.say("Read-only: folder names only. Nothing was written.")
        out.say()
        out.say("- Place: `%s`" % tilde(place))
        out.say("- Tens already used by folders here: %s" % (", ".join(str(n) for n in used) if used else "none"))
        out.say("- Suggested number for the AI home: **%d** (%s)." % (number, reason))
        out.say("- The owner can pick any ten from 10 to 90, and any name.")
        return out.finish(
            "Tell the owner the suggested number and ask the setup questions in one message. "
            "Then write the answers file and run setup with --dry-run."
        )
    out.say("# Likely places for the AI home")
    out.say()
    out.say("Read-only. Nothing was written.")
    out.say()
    here = find_home(Path.cwd())
    if here is not None:
        out.say("- This folder is already inside a workspace: `%s`" % tilde(here))
    places = candidate_places()
    for index, place in enumerate(places, 1):
        out.say("%d. `%s`" % (index, tilde(place)))
    if not places:
        out.say("No synced folder or Documents folder could be seen from here. Ask the owner for the folder.")
    return out.finish(
        "Ask the owner which place they want. Never pick an app's own folder. "
        "Then run init --path \"<that folder>\" to get a suggested number."
    )


# ----------------------------------------------------------------------------
# setup and new
# ----------------------------------------------------------------------------

ANSWERS_EXAMPLE = """Example answers file:
{
  "location": "/Users/ana/Drive",
  "home_name": "AI-Agents",
  "home_number": 90,
  "owner": "Ana Lopez",
  "private": [],
  "work": [
    {"title": "Duplex renovation", "kind": "project", "purpose": "Renovate the duplex on Elm St.",
     "documents": ["/Users/ana/Drive/Duplex papers"]}
  ]
}"""


def load_answers(path):
    try:
        data = json.loads(read_text(path))
    except OSError as error:
        raise Refuse("Can't read the answers file `%s`: %s\n\n%s" % (path, error, ANSWERS_EXAMPLE),
                     "Write the answers file, then run setup again.")
    except ValueError as error:
        raise Refuse("The answers file `%s` isn't valid JSON: %s\n\n%s" % (path, error, ANSWERS_EXAMPLE),
                     "Fix the answers file, then run setup again.")
    if not isinstance(data, dict):
        raise Refuse("The answers file must hold one JSON object.\n\n" + ANSWERS_EXAMPLE,
                     "Fix the answers file, then run setup again.")
    return data


def plan_setup(answers):
    """Works out everything setup would do. Returns (plan, problems). Changes nothing."""
    problems = []
    root = None
    if answers.get("home"):
        root = Path(str(answers["home"])).expanduser()
        if not root.is_absolute():
            problems.append("`home` must be a full path.")
            root = None
    elif answers.get("location"):
        location = Path(str(answers["location"])).expanduser()
        if not location.is_absolute():
            problems.append("`location` must be a full path.")
        elif not location.is_dir():
            problems.append("`location` isn't an existing folder: `%s`." % tilde(location))
        else:
            number = answers.get("home_number")
            here = homes_in(location)
            if number is None and len(here) == 1:
                root = here[0]
            elif number is None and len(here) > 1:
                problems.append("`%s` holds more than one workspace. Give `home` with the one you mean: %s."
                                % (tilde(location), ", ".join("`%s`" % path.name for path in here)))
            else:
                if number is None:
                    number = suggest_number(location)[0]
                if not valid_ten(number):
                    problems.append("`home_number` must be a ten from 10 to 90, such as 90 or 10.")
                else:
                    root = location.resolve() / ("%d_%s" % (number, slug(answers.get("home_name") or "AI-Agents")))
    else:
        problems.append("Give `location` (the folder the AI home goes in) or `home` (the AI home itself).")
    if root is None:
        return None, problems
    root = Path(os.path.normpath(str(root)))
    if root.parent.is_dir():
        root = root.parent.resolve() / root.name
    if root.exists() and not root.is_dir():
        return None, problems + ["`%s` is a file, so it can't be the AI home." % tilde(root)]
    if not root.exists() and not root.parent.is_dir():
        return None, problems + ["The folder `%s` doesn't exist, so the AI home can't be created in it." % tilde(root.parent)]

    settings_path = root / RECORDS / SETTINGS_FILE
    existing = settings_path.is_file()
    if existing:
        home = Home(root.resolve())
    else:
        number = answers.get("home_number")
        if number is None:
            match = re.match(r"^(\d{2})[_ ]", root.name)
            number = int(match.group(1)) if match and int(match.group(1)) % 10 == 0 else None
        if number is None:
            number = suggest_number(root.parent)[0]
        if not valid_ten(number):
            problems.append("`home_number` must be a ten from 10 to 90, such as 90 or 10.")
            return None, problems
        owner = str(answers.get("owner") or "").strip()
        if not owner:
            problems.append("`owner` is missing: the owner's name.")
        settings = dict(DEFAULT_SETTINGS)
        settings.update({"owner": owner, "home_number": number, "skill_version": __version__})
        for key in ("private", "documents", "tools"):
            value = answers.get(key, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                problems.append("`%s` must be a list of text values." % key)
                value = []
            settings[key] = list(value)
        home = Home(root.resolve() if root.exists() else root, settings)
        # A private folder given as a full path is written down the way document folders are:
        # relative to the home or from ~/, so the record still reads right on another computer.
        named = []
        for item in settings["private"]:
            if Path(item).expanduser().is_absolute() or item.replace("\\", "/").startswith(SESSION_PATHS):
                shown = record_location(home, item)
                if shown is None:
                    problems.append("`private` holds `%s`, a path that exists only inside this session. "
                                    "Give the folder's own name." % item)
                    continue
                item = shown
            named.append(item)
        settings["private"] = named
        home.settings["private"] = named

    state = State(home)
    if existing:
        for rule, path, message in state.blockers():
            problems.append("`%s` (%s): %s Run reconcile first." % (path, rule, message))
    elif state.numbered():
        problems.append(
            "`%s` already has numbered work folders and isn't a workspace yet. Bringing those in comes in a later step: "
            "pick an empty place for the AI home for now." % tilde(root)
        )

    work_items = answers.get("work", [])
    if not isinstance(work_items, list):
        problems.append("`work` must be a list.")
        work_items = []
    documents = list(home.settings.get("documents", []))
    planned, skipped, per_group = [], [], {}
    for index, raw in enumerate(work_items, 1):
        if not isinstance(raw, dict) or not str(raw.get("title") or "").strip():
            problems.append("Work item %d has no `title`." % index)
            continue
        title = str(raw["title"]).strip()
        kind = str(raw.get("kind") or "project").strip().lower()
        if kind not in KINDS:
            problems.append("Work item %d (`%s`): `kind` must be project, area or data." % (index, title))
            continue
        status = str(raw.get("status") or ("Ongoing" if kind != "project" else "Active")).strip()
        if not status.lower().startswith(tuple(s.lower() for s in STATUSES)):
            problems.append("Work item %d (`%s`): `status` must start with %s." % (index, title, ", ".join(STATUSES)))
            continue
        item_documents = raw.get("documents", [])
        if not isinstance(item_documents, list) or not all(isinstance(d, str) for d in item_documents):
            problems.append("Work item %d (`%s`): `documents` must be a list of folder paths." % (index, title))
            continue
        name = slug(title)
        group_no = home.group_no(KINDS[kind])
        taken = [e for e in state.entries.values()
                 if e["state"] != "retired" and e["name"].lower() == name.lower() and int(e["number"][:2]) == group_no]
        taken += [p for p in planned if p["name"].lower() == name.lower() and p["group_no"] == group_no]
        if taken:
            skipped.append(title)
            continue
        counter = state.next_counter(group_no, per_group.get(group_no, 0))
        if counter > 99:
            problems.append(
                "Group %d is full: its numbers have reached .99. Add another group folder for `%s`." % (group_no, title)
            )
            continue
        per_group[group_no] = per_group.get(group_no, 0) + 1
        number = "%d.%02d" % (group_no, counter)
        recorded = [record_location(home, d) for d in item_documents]
        if None in recorded:
            problems.append(
                "Work item %d (`%s`): a `documents` path exists only inside this session. Give a folder inside the "
                "connected folder, or leave it out and describe the location in the hand-off." % (index, title)
            )
            continue
        for location in recorded:
            if location not in documents:
                documents.append(location)
        planned.append({
            "title": title, "name": name, "kind": kind, "status": status, "group_no": group_no,
            "number": number, "folder": "%s%s%s" % (number, home.sep, name), "key": new_key(),
            "purpose": str(raw.get("purpose") or "").strip() or "To confirm with %s." % home.owner_first(),
            "documents": recorded,
        })

    groups = []
    for offset in sorted(GROUPS):
        number = home.group_no(offset)
        path = state.groups.get(number)
        if offset == 9 and path is None:
            continue  # the old archive is kept only where it already exists
        groups.append({
            "no": number, "offset": offset, "new": path is None,
            "name": path.name if path else "%d%s%s" % (number, home.sep, GROUPS[offset][0]),
        })
    plan = {
        "home": home, "state": state, "existing": existing, "root_new": not root.exists(),
        "groups": groups, "work": planned, "skipped": skipped, "documents": documents,
    }
    return plan, problems


def home_files(plan):
    """(relative path, template, context) for every home-level file that should exist."""
    home, state = plan["home"], plan["state"]
    names = {group["no"]: group["name"] for group in plan["groups"]}
    fake_groups = {number: home.root / name for number, name in names.items()}
    fake_groups.update(state.groups)
    context = home_context(home, fake_groups)
    context["DOCUMENTS_BULLETS"] = "\n".join("  - `%s`" % item for item in plan["documents"])
    files = [
        ("AGENTS.md", "home-AGENTS.md", context),
        ("CLAUDE.md", "home-CLAUDE.md", context),
        ("README.md", "home-README.md", context),
        (RECORDS + "/README.md", "records-README.md", context),
    ]
    for group in plan["groups"]:
        if group["offset"] in (1, 2, 5):
            group_context = dict(context)
            group_context["TITLE"] = group["name"]
            files.append((group["name"] + "/AGENTS.md", "group-AGENTS.md", group_context))
            files.append((group["name"] + "/CLAUDE.md", "home-CLAUDE.md", group_context))
    return files


def work_templates(home):
    """(file name, template) for the standard files of every work folder, in the order people read them."""
    return (
        ("README.md", "work-README.md"),
        (home.handoff, "work-HANDOFF.md"),
        ("DECISIONS.md", "work-DECISIONS.md"),
        ("AGENT_SYNC.md", "work-AGENT_SYNC.md"),
        ("AGENTS.md", "work-AGENTS.md"),
        ("CLAUDE.md", "home-CLAUDE.md"),
    )


def readme_documents(locations):
    if not locations:
        return "- None recorded yet. Documents stay where they are: list their locations here."
    return "\n".join("- `%s` (read by path, left where it is)" % location for location in locations)


def work_files(plan, item, by):
    home = plan["home"]
    group_name = next(group["name"] for group in plan["groups"] if group["no"] == item["group_no"])
    base = "%s/%s" % (group_name, item["folder"])
    context = {
        "TITLE": item["title"], "PURPOSE": item["purpose"], "STATUS": item["status"], "KEY": item["key"],
        "TIMESTAMP": iso(), "DATE": today(), "BY": by, "HANDOFF": home.handoff,
        "OWNER_FIRST": home.owner_first(), "NUMBER": item["number"],
        "DOCUMENTS_BULLETS": "\n".join("- Documents for this work, read by path: `%s`" % d for d in item["documents"]),
        "README_DOCUMENTS": readme_documents(item["documents"]),
    }
    return base, [(base + "/" + name, template, context) for name, template in work_templates(home)]


def preview_setup(plan, out):
    home = plan["home"]
    mark = lambda new: "  (new)" if new else ""
    out.say("```")  # a fenced block, so the agent passes the tree on as it is
    out.say("%s/%s" % (home.root.name, mark(plan["root_new"])))
    top = [rel for rel, _, _ in home_files(plan) if "/" not in rel]
    new_top = [name for name in top if not (home.root / name).exists()]
    if new_top:
        out.say("  %s  (new)" % ", ".join(new_top))
    records_new = not (home.records / SETTINGS_FILE).exists()
    if records_new:
        out.say("  %s/  settings.json, ledger.jsonl, README.md  (new)" % RECORDS)
    for group in plan["groups"]:
        line = "  %s/" % group["name"]
        if group["offset"] in (1, 2, 5) and not (home.root / group["name"] / "AGENTS.md").exists():
            line += "  AGENTS.md, CLAUDE.md"
        out.say(line + mark(group["new"]))
        for item in plan["work"]:
            if item["group_no"] == group["no"]:
                out.say("    %s/  the six standard files  · %s  (new)" % (item["folder"], item["status"]))
                for location in item["documents"]:
                    out.say("      reads documents at `%s` (left where they are)" % location)
    out.say("```")
    existing = len(plan["state"].numbered())
    out.say()
    if plan["work"]:
        out.say("The six standard files of a work folder: %s." % ", ".join(name for name, _ in work_templates(home)))
    if existing:
        out.say("Already here: %d work folder%s, left as they are." % (existing, "" if existing == 1 else "s"))
    for title in plan["skipped"]:
        out.say("Already here, so not added again: %s." % title)
    out.say("Home number: %d. Existing files are never overwritten; existing folders are reused." % home.number)


def apply_setup(plan, out, by):
    home = plan["home"]
    created = []
    if plan["root_new"]:
        home.root.mkdir()
        created.append(home.root.name + "/")
        home.root = home.root.resolve()
        home.records = home.root / RECORDS
    home.records.mkdir(exist_ok=True)
    if not (home.records / SETTINGS_FILE).exists():
        settings = dict(home.settings)
        settings["documents"] = plan["documents"]
        write_new(home.records / SETTINGS_FILE, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        home.settings = settings
        created.append("%s/%s" % (RECORDS, SETTINGS_FILE))
    with lock(home):
        if not (home.records / LEDGER_FILE).exists():
            write_new(home.records / LEDGER_FILE, "")
            created.append("%s/%s" % (RECORDS, LEDGER_FILE))
        for group in plan["groups"]:
            path = home.root / group["name"]
            if not path.exists():
                path.mkdir()
                created.append(group["name"] + "/")
        for rel, template, context in home_files(plan):
            target = home.root / rel
            if not target.exists():
                write_new(target, render(template, context))
                created.append(rel)
        for item in plan["work"]:
            base, files = work_files(plan, item, by)
            folder = home.root / base
            if folder.exists():
                raise Refuse(
                    "`%s` already exists, so number %s was not given out." % (base, item["number"]),
                    "Run check, then run setup again.",
                )
            append_line(home.records / LEDGER_FILE, {
                "event": "issued", "number": item["number"], "key": item["key"], "name": item["name"],
                "kind": item["kind"], "group_now": item["group_no"], "time": iso(), "host": host(),
            })
            folder.mkdir()
            created.append(base + "/")
            for rel, template, context in files:
                write_new(home.root / rel, render(template, context))
                created.append(rel)
        state = State(home)
        status, message = refresh_map(home, state, write=True)
    return created, message


def cmd_setup(args):
    answers = load_answers(args.answers)
    plan, problems = plan_setup(answers)
    if problems:
        raise Refuse(
            "Fix the answers file, then run setup again. Nothing was changed:\n%s\n\n%s"
            % (bullets(problems), ANSWERS_EXAMPLE),
            "Fix exactly what is listed, then run setup again with --dry-run.",
        )
    out = Out()
    if args.dry_run:
        out.say("# Setup preview (dry run): nothing was written")
        out.say()
        preview_setup(plan, out)
        return out.finish(
            "Show this preview to the owner exactly as printed. When they approve, run the same command without --dry-run."
        )
    created, map_message = apply_setup(plan, out, args.by)
    home = plan["home"]
    out.say("# Setup done")
    out.say()
    out.say("Workspace: `%s`" % tilde(home.root))
    out.say()
    if created:
        out.say("Created:")
        for rel in created:
            out.say("- `%s`" % rel)
    else:
        out.say("Nothing new was needed.")
    for title in plan["skipped"]:
        out.say("- Already here, so not added again: %s." % title)
    out.say()
    out.say(map_message)
    findings = run_check(Home(home.root))[0]
    errors = sum(1 for finding in findings if finding["severity"] == "error")
    out.say("Check: %d error%s." % (errors, "" if errors == 1 else "s"))
    return out.finish(
        "Tell the owner what was created and where. Then open the first work folder's %s, "
        "ask for the goal and the first task, and write them into it." % home.handoff
    )


def cmd_new(args):
    home = open_home(args)
    item = {"title": args.title, "kind": args.kind, "purpose": args.purpose, "status": args.status,
            "documents": args.documents or []}
    item = {key: value for key, value in item.items() if value not in (None, "")}
    plan, problems = plan_setup({"home": str(home.root), "work": [item]})
    if problems:
        raise Refuse("Nothing was changed:\n" + bullets(problems), "Fix what is listed, then run the command again.")
    out = Out()
    if plan["skipped"]:
        out.say("A work folder named for `%s` is already here, so nothing was added." % args.title)
        return out.finish("Run check to see it, or pick a different title.")
    planned = plan["work"][0]
    group_name = next(group["name"] for group in plan["groups"] if group["no"] == planned["group_no"])
    if args.dry_run:
        out.say("# New work folder (dry run): nothing was written")
        out.say()
        out.say("`%s/%s/`  %s  · %s" % (
            group_name, planned["folder"], ", ".join(name for name, _ in work_templates(home)), planned["status"]))
        for location in planned["documents"]:
            out.say("- reads documents at `%s` (left where they are)" % location)
        return out.finish("Show this to the owner. When they approve, run the same command without --dry-run.")
    created, map_message = apply_setup(plan, out, args.by)
    out.say("# New work folder: %s" % planned["number"])
    out.say()
    for rel in created:
        out.say("- `%s`" % rel)
    out.say()
    out.say(map_message)
    return out.finish(
        "Open `%s/%s/%s`, ask the owner for the goal and the first task, and write them into it."
        % (group_name, planned["folder"], home.handoff)
    )


# ----------------------------------------------------------------------------
# scan: a read-only inventory. Names, counts, sizes and dates. No file is opened.
# ----------------------------------------------------------------------------

def folder_stats(path, cap=20000):
    count, size, newest = 0, 0, 0.0
    for current, folders, files in os.walk(str(path), followlinks=False):
        folders[:] = [name for name in folders if not os.path.islink(os.path.join(current, name))]
        for name in files:
            try:
                info = os.lstat(os.path.join(current, name))
            except OSError:
                continue
            count += 1
            size += info.st_size
            newest = max(newest, info.st_mtime)
            if count >= cap:
                return count, size, newest, True
    return count, size, newest, False


def human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%d %s" % (size, unit)) if unit == "B" else ("%.1f %s" % (size, unit))
        size /= 1024.0
    return "%d B" % size


def cmd_scan(args):
    home = None
    if args.path:
        target = Path(args.path).expanduser().resolve()
    else:
        home = open_home(args)
        target = home.root
    if not target.is_dir():
        raise Refuse("`%s` isn't a folder." % tilde(target), "Ask the owner which folder to look at.")
    if home is None:
        root = find_home(target)
        if root is not None:
            with contextlib.suppress(Refuse):
                home = Home(root)
    private = [name.strip("/").lower() for name in (args.private or [])]

    def is_private(child):
        if child.name.lower() in private:
            return True
        if home is not None:
            with contextlib.suppress(ValueError):
                return home.is_private(home.rel(child))
        return False

    out = Out()
    out.say("# What's in `%s`" % target.name)
    out.say()
    out.say("Read-only: names, counts, sizes and dates. No file was opened.")
    out.say()
    out.say("| # | Name | Kind | Files | Size | Newest |")
    out.say("|---|---|---|---|---|---|")
    children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    row = 0
    for child in children:
        if child.name.startswith(".") or child.name in ("desktop.ini", "thumbs.db"):
            continue
        row += 1
        if child.is_symlink():
            out.say("| %d | `%s` | link, not followed | | | |" % (row, cell(child.name)))
        elif is_private(child):
            out.say("| %d | `%s/` | private, not opened | | | |" % (row, cell(child.name)))
        elif child.is_dir():
            count, size, newest, capped = folder_stats(child)
            kind = "folder"
            if child.name == RECORDS:
                kind = "the skill's records"
            elif WORK_RE.match(child.name):
                kind = "work folder"
            elif GROUP_RE.match(child.name):
                kind = "numbered folder"
            elif count == 0:
                kind = "empty folder"
            stamp = dt.datetime.fromtimestamp(newest).strftime("%Y-%m-%d") if newest else ""
            out.say("| %d | `%s/` | %s | %s%s | %s | %s |" % (
                row, cell(child.name), kind, count, "+" if capped else "", human_size(size), stamp))
        else:
            info = child.lstat()
            stamp = dt.datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d")
            out.say("| %d | `%s` | file | 1 | %s | %s |" % (row, cell(child.name), human_size(info.st_size), stamp))
    if row == 0:
        out.say("| | Nothing here | | | | |")
    return out.finish(
        "Ask the owner which of these are work they want an agent to pick up. "
        "Folders outside the AI home stay where they are: a work folder points at them."
    )


# ----------------------------------------------------------------------------
# check
# ----------------------------------------------------------------------------

RULES = {
    "LED001": ("error", "The number ledger is missing"),
    "LED002": ("error", "A ledger line can't be read"),
    "LED003": ("error", "A second copy of the ledger"),
    "NUM001": ("error", "The same number on two folders"),
    "NUM002": ("error", "A numbered folder that isn't in the ledger"),
    "NUM003": ("error", "A hand-off key that doesn't match the ledger"),
    "NUM004": ("warn", "A number in the ledger with no folder here"),
    "NUM005": ("warn", "An unnumbered folder inside a group"),
    "NUM006": ("warn", "A numbered top-level folder outside the home's ten"),
    "NUM007": ("info", "A group is nearly full"),
    "HOME001": ("error", "The home's AGENTS.md is missing"),
    "HOME002": ("error", "The home's README.md is missing"),
    "HOME003": ("info", "The home's CLAUDE.md is missing"),
    "HOME004": ("info", "The home folder's name doesn't start with its number"),
    "WRK001": ("error", "A work folder has no hand-off"),
    "WRK002": ("warn", "A work folder has no AGENTS.md"),
    "WRK003": ("warn", "A work folder's AGENTS.md doesn't point to the workspace rules"),
    "WRK004": ("info", "A work folder has no CLAUDE.md"),
    "WRK005": ("info", "A work folder is missing a standard file"),
    "HND001": ("error", "Hand-off headings missing or out of order"),
    "HND002": ("warn", "A hand-off header field is missing"),
    "HND003": ("warn", "A hand-off status isn't one of the known ones"),
    "HND004": ("warn", "Last updated isn't a date"),
    "HND005": ("info", "Files changed after the hand-off"),
    "HND006": ("info", "An active hand-off that is old"),
    "HND008": ("info", "A hand-off longer than some tools read"),
    "HND009": ("info", "Active or ongoing work with no next action"),
    "HND010": ("info", "Hand-off lines still marked Unconfirmed"),
    "MAP001": ("warn", "A work folder is missing from the map"),
    "MAP002": ("warn", "The map table was edited by hand, or its markers are unclear"),
    "MAP003": ("info", "The map is out of date"),
    "LNK001": ("error", "A link that points nowhere"),
    "DOC001": ("warn", "An agent file inside a document folder"),
    "DOC002": ("info", "A document location that isn't on this computer"),
    "SYNC001": ("warn", "A sync conflict copy"),
    "INB001": ("info", "Items waiting in the Inbox"),
    "MOV001": ("warn", "A move that didn't finish"),
    "ARC001": ("info", "Folders in the old archive for the whole workspace"),
    "VER001": ("info", "The workspace was set up with an older version of the skill"),
    "VER002": ("info", "This copy of the skill is older than the workspace"),
    "FRC001": ("info", "Friction notes are waiting"),
}


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def managed_files(home, state, live_only=False):
    files = [home.root / name for name in ("AGENTS.md", "CLAUDE.md", "README.md")]
    for path in state.groups.values():
        files.append(path / "AGENTS.md")
    for item in state.disk:
        if live_only and item["archived"]:
            continue
        for name in ("README.md", "AGENTS.md", home.handoff, "DECISIONS.md", "AGENT_SYNC.md"):
            files.append(item["path"] / name)
    return [path for path in files if path.is_file()]


def suggest_target(home, state, moves, missing_rel):
    """A new target for a broken link, only when the moves log and the folder's key agree."""
    for move in reversed(moves):
        if move.get("state") != "done":
            continue
        old = move.get("from", "")
        if missing_rel == old or missing_rel.startswith(old + "/"):
            target = move.get("to", "") + missing_rel[len(old):]
            folder = home.root / move.get("to", "")
            if (home.root / target).exists() and move.get("key") and read_key(folder / home.handoff) == move.get("key"):
                return target
    return None


def run_check(home):
    state = State(home)
    moves, _ = read_moves(home)
    findings = []

    def add(rule, path, message, fix=""):
        findings.append({"rule": rule, "severity": RULES[rule][0], "path": path, "message": message, "fix": fix})

    reconcile = "Run reconcile and apply it after the owner's OK."
    for rule, path, message in state.blockers():
        add(rule, path, message, reconcile)
    live = {item["key"] for item in state.numbered() if item["key"]}
    live_numbers = {item["number"] for item in state.numbered()}
    for entry in state.entries.values():
        if entry["state"] != "retired" and entry["key"] not in live and entry["number"] not in live_numbers:
            add("NUM004", "%s/%s" % (RECORDS, LEDGER_FILE),
                "Number %s (%s) is in the ledger and its folder isn't here. It may have been deleted, "
                "or it hasn't synced yet." % (entry["number"], entry["name"]),
                "If it is gone for good, run reconcile --retire-missing after the owner's OK.")
    for item in state.disk:
        if item["number"] is None:
            add("NUM005", item["rel"], "This folder has no number.",
                "Ask the owner whether it is a piece of work. If so, run new for it and move its files in.")
    for path in state.extra_groups:
        add("NUM006", home.rel(path), "This numbered folder isn't one of the home's groups (%d to %d)."
            % (home.number, home.number + 9), "Rename it with the owner, or leave it.")
    for group_no in state.groups:
        if state.next_counter(group_no) > 90:
            add("NUM007", home.rel(state.groups[group_no]), "This group has used %d of its 99 numbers."
                % (state.next_counter(group_no) - 1), "Ask the owner to add another group folder before it fills up.")

    if not (home.root / "AGENTS.md").is_file():
        add("HOME001", "AGENTS.md", "The workspace rules are missing.", "Run setup again: it adds only what is missing.")
    if not (home.root / "README.md").is_file():
        add("HOME002", "README.md", "The map is missing.", "Run setup again: it adds only what is missing.")
    if not (home.root / "CLAUDE.md").is_file():
        add("HOME003", "CLAUDE.md", "Claude Code finds the rules through this file.", "Run setup again: it adds only what is missing.")
    if not home.root.name.startswith(str(home.number)):
        add("HOME004", ".", "The home is numbered %d in the settings, and its folder is named `%s`."
            % (home.number, home.root.name), "The owner can rename the folder by hand, or leave it.")

    stale_days = int(home.settings.get("stale_after_days", 30) or 30)
    rows = []
    for item in sorted(state.numbered(), key=lambda it: it["number"]):
        handoff_path = item["path"] / home.handoff
        row = {"number": item["number"], "path": item["rel"], "status": "", "last_updated": "",
               "next_action": "", "archived": item["archived"], "title": item["name"].replace("-", " ")}
        rows.append(row)
        if not handoff_path.is_file():
            add("WRK001", item["rel"], "There is no %s here." % home.handoff,
                "Write one in the format in the workspace rules, with the owner.")
            row["status"] = "Hand-off missing"
            continue
        agents = item["path"] / "AGENTS.md"
        if not agents.is_file():
            add("WRK002", item["rel"], "There is no AGENTS.md here.", "Add one that points to the workspace rules.")
        elif "../../AGENTS.md" not in read_text(agents):
            add("WRK003", item["rel"] + "/AGENTS.md", "It doesn't point to the workspace rules.",
                "Add a line that links to `../../AGENTS.md`.")
        if not (item["path"] / "CLAUDE.md").is_file():
            add("WRK004", item["rel"], "Without it, Claude Code doesn't load this folder's rules by itself.",
                "Add a CLAUDE.md whose first line is `@AGENTS.md`.")
        absent = [name for name in ("README.md", "DECISIONS.md", "AGENT_SYNC.md") if not (item["path"] / name).is_file()]
        if absent:
            add("WRK005", item["rel"], "There is no %s here." % " or ".join("`%s`" % name for name in absent),
                "With the owner's OK, write each one from its template in the skill's `assets/templates` folder.")
        text = read_text(handoff_path)
        info = parse_handoff(text)
        fields = info["fields"]
        row.update({"status": fields.get("Status", ""), "last_updated": fields.get("Last updated", "")[:10],
                    "next_action": info["next_action"] or "", "title": info["title"] or row["title"]})
        rel = item["rel"] + "/" + home.handoff
        if [h for h in info["headings"] if h in HEADINGS] != HEADINGS:
            add("HND001", rel, "The five headings must appear in this order: %s." % ", ".join(HEADINGS),
                "Re-read the file, then fix the headings with the owner's OK.")
        missing = [name for name in ("Purpose", "Status", "Key", "Last updated") if not fields.get(name)]
        if missing:
            add("HND002", rel, "Missing in the header: %s." % ", ".join(missing), "Add the missing fields.")
        status = fields.get("Status", "")
        if status and not status.lower().startswith(tuple(s.lower() for s in STATUSES)):
            add("HND003", rel, "Status is `%s`." % status, "Use one of: %s." % ", ".join(STATUSES))
        updated = fields.get("Last updated", "")
        stamp = None
        if updated:
            match = re.match(r"^(\d{4}-\d{2}-\d{2})", updated)
            if not match:
                add("HND004", rel, "Last updated is `%s`." % updated, "Use a date such as %s." % today())
            else:
                with contextlib.suppress(ValueError):
                    stamp = dt.datetime.strptime(match.group(1), "%Y-%m-%d")
        if stamp is not None and not item["archived"]:
            age = (dt.datetime.now() - stamp).days
            if status.lower().startswith("active") and age > stale_days:
                add("HND006", rel, "Active, and the hand-off is %d days old." % age,
                    "Ask the owner whether the status or the next action changed.")
            changed = 0
            cutoff = (stamp + dt.timedelta(days=1, hours=1)).timestamp()
            for current, folders, files in os.walk(str(item["path"]), followlinks=False):
                folders[:] = [name for name in folders if not name.startswith((".", "_"))]
                for name in files:
                    if name.startswith(".") or (current == str(item["path"]) and name == home.handoff):
                        continue
                    with contextlib.suppress(OSError):
                        if os.lstat(os.path.join(current, name)).st_mtime > cutoff:
                            changed += 1
            if changed:
                add("HND005", rel, "%d file%s here changed after the hand-off was last updated."
                    % (changed, "" if changed == 1 else "s"), "Read the hand-off and bring it up to date.")
        if len(text.encode("utf-8")) > HANDOFF_LIMIT:
            add("HND008", rel, "The hand-off is over %d KB. Some tools stop reading long files." % (HANDOFF_LIMIT // 1000),
                "Copy older Session log lines to a file beside it, link that file from How to continue, "
                "then shorten the log with the owner's OK.")
        if not item["archived"]:
            if status.lower().startswith(("active", "ongoing")) and no_next_action(info["next_action"]):
                add("HND009", rel, "%s, and Next actions names nothing to do." % status.split()[0],
                    "Ask the owner what comes next, or whether this work is now Paused or Closed.")
            unsure = len(re.findall(r"(?im)^.*\bunconfirmed\b.*$", strip_code(text)))
            if unsure:
                add("HND010", rel, "%d line%s marked Unconfirmed." % (unsure, "" if unsure == 1 else "s"),
                    "Ask the owner about each one, then replace the mark with the answer and where it came from.")

    readme = home.root / "README.md"
    if readme.is_file():
        status, message = refresh_map(home, state, write=False)
        if status in ("hand-edited", "unclear"):
            add("MAP002", "README.md", message, "Fix the table or the markers with the owner, then run map.")
        elif status == "would-update":
            readme_text = read_text(readme)
            absent = [item for item in state.numbered() if link(item["rel"]) not in readme_text]
            for item in absent:
                add("MAP001", item["rel"], "This work folder isn't in the map.", "Run map.")
            if not absent:
                add("MAP003", "README.md", "A name, status or purpose changed since the map was written.", "Run map.")

    # Archived work is frozen, and one level deeper than it was, so its links aren't checked until it is restored.
    for path in managed_files(home, state, live_only=True):
        rel = home.rel(path)
        with contextlib.suppress(OSError, UnicodeError):
            for match in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", strip_code(read_text(path))):
                target = match.group(1).strip("<>")
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                target = urllib.parse.unquote(target.split("#")[0])
                if not target:
                    continue
                resolved = Path(os.path.normpath(str(path.parent / target)))
                if resolved.exists():
                    continue
                fix = "Re-read the file, then fix or remove the link with the owner's OK."
                with contextlib.suppress(ValueError):
                    missing_rel = resolved.relative_to(home.root).as_posix()
                    if home.is_private(missing_rel):
                        continue
                    better = suggest_target(home, state, moves, missing_rel)
                    if better:
                        fix = "The folder was moved. The link should now point to `%s`." % better
                add("LNK001", rel, "The link to `%s` points nowhere." % target, fix)

    for recorded in home.settings.get("documents", []):
        location = resolve_location(home, recorded)
        if not location.exists():
            add("DOC002", recorded, "This document location isn't on this computer.",
                "Nothing to do if it lives on another computer. A task that needs it must stop and say so.")
            continue
        found, seen = [], 0
        for current, folders, files in os.walk(str(location), followlinks=False):
            folders[:] = [name for name in folders if not name.startswith(".")]
            seen += len(files)
            for name in files:
                if name in AGENT_FILES:
                    found.append(os.path.join(current, name))
            if seen > 5000 or current.count(os.sep) - str(location).count(os.sep) >= 4:
                folders[:] = []
        for hit in found[:25]:
            add("DOC001", recorded, "`%s` is an agent file inside a document folder." % tilde(hit),
                "Ask the owner before moving it. Agent files belong in the AI home.")

    for path in managed_files(home, state) + [home.records / LEDGER_FILE, home.records / MOVES_FILE]:
        folder = path.parent
        if not folder.is_dir():
            continue
        stem = path.stem.lower()
        for sibling in folder.iterdir():
            name = sibling.name.lower()
            if sibling == path or not name.startswith(stem) or name.startswith("ledger"):
                continue
            if "conflict" in name or re.search(r"\(\d+\)", name):
                add("SYNC001", home.rel(sibling), "This looks like a sync conflict copy of `%s`." % path.name,
                    "Compare both files with the owner and keep one. Don't pick by date alone.")

    inbox = state.groups.get(home.group_no(0))
    if inbox is not None:
        waiting = [child for child in inbox.iterdir() if not child.name.startswith(".")]
        if waiting:
            add("INB001", home.rel(inbox), "%d item%s waiting in the Inbox." % (len(waiting), "" if len(waiting) == 1 else "s"),
                "Go through them with the owner.")

    for move in moves:
        if move.get("state") == "pending":
            add("MOV001", "%s/%s" % (RECORDS, MOVES_FILE),
                "A %s of `%s` was started and not finished." % (move.get("op", "move"), move.get("from", "")),
                "Run any command that changes the workspace: it settles the record from what is on disk.")

    old_archive = [item for item in state.numbered() if item["legacy"]]
    if old_archive:
        add("ARC001", home.rel(state.groups[home.group_no(9)]),
            "%d folder%s in the old archive for the whole workspace: %s."
            % (len(old_archive), "" if len(old_archive) == 1 else "s", ", ".join(item["number"] for item in old_archive[:12])),
            "They stay valid. With the owner's OK, run archive <number> --dry-run for each: it moves the folder into "
            "the archive of the group it came from.")

    settings_rel = "%s/%s" % (RECORDS, SETTINGS_FILE)
    have, this = version_tuple(home.skill_version()), version_tuple(__version__)
    if have < this:
        add("VER001", settings_rel, "This workspace was set up with version %s of the skill. This copy is %s."
            % (home.skill_version(), __version__),
            "Run upgrade --dry-run, tell the owner what's new, and run it for real after their OK.")
    elif have > this:
        add("VER002", settings_rel, "This workspace was upgraded by version %s of the skill. This copy is %s."
            % (home.skill_version(), __version__),
            "Tell the owner to update this copy of the skill. Until then, leave the workspace's newer rules as they are.")

    friction = home.records / FRICTION_FILE
    if friction.is_file():
        with contextlib.suppress(OSError, UnicodeError):
            notes = [line for line in read_text(friction).splitlines() if line.lstrip().startswith("- ")]
            if notes:
                add("FRC001", "%s/%s" % (RECORDS, FRICTION_FILE),
                    "%d friction note%s from agents." % (len(notes), "" if len(notes) == 1 else "s"),
                    "Show them to the owner. They can pass them to whoever maintains the skill, then empty the file.")

    suppress = home.settings.get("suppress", [])
    kept = []
    for finding in findings:
        hidden = False
        for entry in suppress:
            rule, _, pattern = entry.partition(":")
            if rule in ("*", finding["rule"]) and fnmatch.fnmatch(finding["path"].lower(), (pattern or "*").lower()):
                hidden = True
        if not hidden:
            kept.append(finding)
    order = {"error": 0, "warn": 1, "info": 2}
    kept.sort(key=lambda finding: (order[finding["severity"]], finding["rule"], finding["path"]))
    return kept, rows


# Findings a brief puts under "Needs attention", besides every error.
BRIEF_RULES = ("HND005", "HND006", "HND009", "WRK001", "VER001", "FRC001")


def brief_gaps(home, findings, rows):
    """What a brief can't speak for. The last line is always there, so no brief reads as the whole picture."""
    gaps = []
    private = home.settings.get("private", [])
    if private:
        gaps.append("Private, not opened: %s." % ", ".join("`%s`" % name for name in private))
    away = [finding["path"] for finding in findings if finding["rule"] == "DOC002"]
    if away:
        gaps.append("Document folders that aren't on this computer: %s." % ", ".join("`%s`" % path for path in away))
    resting = sum(1 for row in rows if not row["archived"] and row["status"].lower().startswith(("paused", "closed")))
    archived = sum(1 for row in rows if row["archived"])
    if resting or archived:
        gaps.append("Hand-offs a brief doesn't read: %d paused or closed, %d archived." % (resting, archived))
    for finding in findings:
        if finding["rule"] == "HND010":
            gaps.append("Not confirmed yet in `%s`: %s" % (finding["path"], finding["message"]))
    gaps.append("Everything outside the workspace, such as mail, chat and calendars, and anything that was never "
                "written into a hand-off.")
    return gaps


def cmd_check(args):
    home = open_home(args)
    findings, rows = run_check(home)
    counts = {level: sum(1 for finding in findings if finding["severity"] == level) for level in ("error", "warn", "info")}
    code = 1 if counts["error"] else 0
    if counts["error"]:
        next_step = "Fix the errors first. Each finding says how."
    elif findings:
        next_step = "Tell the owner what you found, most serious first, and ask what to fix."
    else:
        next_step = "Nothing to fix. Work on the next actions."
    if args.brief:
        next_step = ("Read the hand-off of every Active or Ongoing work folder, and of any folder under Needs attention. "
                     "Then brief the owner: due or overdue, blocked or waiting on them, out of date, "
                     "then at most three things to focus on. End with the Not covered list, and add to it "
                     "anything else you couldn't read. Then wait.")
    if args.json:
        print(json.dumps({"summary": counts, "findings": findings, "work": rows, "next": next_step}, indent=2, ensure_ascii=False))
        return code
    out = Out()
    summary = "%d error%s · %d warning%s · %d info · %d work folder%s" % (
        counts["error"], "" if counts["error"] == 1 else "s", counts["warn"], "" if counts["warn"] == 1 else "s",
        counts["info"], len(rows), "" if len(rows) == 1 else "s")
    if args.brief:
        out.say("# Brief data · %s" % iso())
        out.say()
        out.say("**Check:** " + summary)
        out.say()
        out.say("| Number | Work folder | Status | Last updated | Next action |")
        out.say("|---|---|---|---|---|")
        for row in rows:
            if row["archived"]:
                continue
            out.say("| %s | %s | %s | %s | %s |" % (row["number"], cell(row["title"]), cell(row["status"]),
                                                   row["last_updated"], cell(row["next_action"])))
        attention = [finding for finding in findings
                     if finding["rule"] in BRIEF_RULES or finding["severity"] == "error"]
        if attention:
            out.say()
            out.say("## Needs attention")
            out.say()
            for finding in attention[:10]:
                out.say("- `%s`: %s" % (finding["path"], finding["message"]))
        out.say()
        out.say("## Not covered by this brief")
        out.say()
        for gap in brief_gaps(home, findings, rows):
            out.say("- " + gap)
        return out.finish(next_step, code)
    out.say("# Workspace check · %s" % iso())
    out.say()
    out.say("**Result:** " + summary)
    for level, title in (("error", "Errors"), ("warn", "Warnings"), ("info", "Info")):
        group = [finding for finding in findings if finding["severity"] == level]
        if not group:
            continue
        out.say()
        out.say("## %s" % title)
        out.say()
        out.say("| Rule | Where | Finding | Fix |")
        out.say("|---|---|---|---|")
        for finding in group[:25]:
            out.say("| %s | `%s` | %s | %s |" % (finding["rule"], cell(finding["path"]), cell(finding["message"]), cell(finding["fix"])))
        if len(group) > 25:
            out.say("| | | and %d more | Use --json for all of them |" % (len(group) - 25))
    return out.finish(next_step, code)


def cmd_map(args):
    home = open_home(args)
    state = State(home)
    out = Out()
    if args.dry_run:
        status, message = refresh_map(home, state, write=False)
        out.say(message)
        return out.finish("Run map without --dry-run to write it." if status == "would-update" else "Nothing to do.")
    with lock(home):
        status, message = refresh_map(home, state, write=True)
    out.say(message)
    if status in ("hand-edited", "unclear"):
        return out.finish("Show the owner the table in `README.md`, fix it together, then run map again.", 1)
    return out.finish("The map is current. Run check if you haven't.")


# ----------------------------------------------------------------------------
# Moves: rename, move to another group, archive, restore, and undo
# ----------------------------------------------------------------------------

def read_moves(home):
    """Returns (moves, problems). Each move's state comes from replaying the log."""
    path = home.records / MOVES_FILE
    moves, by_id, problems = [], {}, []
    if not path.is_file():
        return moves, problems
    for index, line in enumerate(read_text(path).splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or "id" not in record:
                raise ValueError("not a move record")
        except ValueError:
            problems.append("Line %d of the moves log can't be read." % index)
            continue
        if "op" in record:
            by_id[record["id"]] = record
            moves.append(record)
        elif record["id"] in by_id:
            by_id[record["id"]].update({key: value for key, value in record.items() if key != "id"})
    return moves, problems


def settle_moves(home):
    """Finish the bookkeeping of a move that was interrupted, from what is on disk."""
    moves, _ = read_moves(home)
    for move in moves:
        if move.get("state") != "pending":
            continue
        source, target = home.root / move["from"], home.root / move["to"]
        if target.exists() and not source.exists():
            append_line(home.records / MOVES_FILE, {"id": move["id"], "state": "done", "settled": iso()})
            append_line(home.records / LEDGER_FILE, dict(move["ledger"], time=iso()))
        elif source.exists() and not target.exists():
            append_line(home.records / MOVES_FILE, {"id": move["id"], "state": "abandoned", "settled": iso()})


def check_move(home, source, target, make_parent=False):
    """Reasons a move is refused. An empty list means it is safe. make_parent allows a target folder that is new."""
    reasons = []
    for label, path in (("from", source), ("to", target)):
        try:
            rel = Path(os.path.normpath(str(path))).relative_to(home.root).as_posix()
        except ValueError:
            reasons.append("`%s` is outside the workspace." % tilde(path))
            continue
        if home.is_private(rel):
            reasons.append("`%s` is private." % rel)
        if rel.split("/")[0] == RECORDS:
            reasons.append("`%s` holds the skill's records and can't be moved." % rel)
    if reasons:
        return reasons
    if os.path.islink(str(source)):
        reasons.append("`%s` is a link. Links are never moved." % home.rel(source))
    elif not source.is_dir():
        reasons.append("`%s` isn't here." % home.rel(source))
    if target.exists() or os.path.islink(str(target)):
        reasons.append("`%s` already exists." % home.rel(target))
    parent = target.parent
    if make_parent and not parent.exists() and not os.path.islink(str(parent)):
        parent = parent.parent
    if not parent.is_dir():
        reasons.append("`%s` isn't here." % home.rel(target.parent))
    elif source.exists() and os.stat(str(source)).st_dev != os.stat(str(parent)).st_dev:
        reasons.append("The move would cross to another drive. Moves stay on one drive.")
    if len(str(target)) > MAX_PATH:
        reasons.append("The new path would be longer than %d characters." % MAX_PATH)
    return reasons


def do_move(home, op, entry, source, target, ledger_event, dry_run, out, make_parent=False):
    reasons = check_move(home, source, target, make_parent)
    if reasons:
        raise Refuse("Nothing was moved:\n" + bullets(reasons), "Tell the owner why, and ask what they want instead.")
    src_rel, dst_rel = home.rel(source), home.rel(target)
    if dry_run:
        out.say("# %s (dry run): nothing was changed" % op.capitalize())
        out.say()
        out.say("`%s`  →  `%s`" % (src_rel, dst_rel))
        out.say("The folder keeps its number, %s." % entry["number"])
        return False
    with lock(home):
        settle_moves(home)
        moves, _ = read_moves(home)
        move_id = max([move["id"] for move in moves] + [0]) + 1
        ledger_event = dict(ledger_event, key=entry["key"], number=entry["number"])
        if make_parent:
            target.parent.mkdir(exist_ok=True)
        append_line(home.records / MOVES_FILE, {
            "id": move_id, "op": op, "number": entry["number"], "key": entry["key"], "from": src_rel, "to": dst_rel,
            "state": "pending", "time": iso(), "host": host(), "ledger": ledger_event,
        })
        os.rename(str(source), str(target))
        append_line(home.records / MOVES_FILE, {"id": move_id, "state": "done"})
        append_line(home.records / LEDGER_FILE, dict(ledger_event, time=iso()))
        state = State(home)
        _, map_message = refresh_map(home, state, write=True)
    out.say("# %s done" % op.capitalize())
    out.say()
    out.say("`%s`  →  `%s`" % (src_rel, dst_rel))
    out.say("The folder keeps its number, %s." % entry["number"])
    out.say(map_message)
    return True


def prepare_move(args, doing):
    home = open_home(args)
    state = State(home)
    stop_on_blockers(state, doing)
    item, entry = state.find(args.number)
    return home, state, item, entry


def cmd_rename(args):
    home, state, item, entry = prepare_move(args, "rename a folder")
    name = slug(args.title)
    target = item["path"].parent / ("%s%s%s" % (item["number"], home.sep, name))
    out = Out()
    if target == item["path"]:
        out.say("`%s` already has that name." % item["rel"])
        return out.finish("Nothing to do.")
    done = do_move(home, "rename", entry, item["path"], target, {"event": "renamed", "name": name, "was": entry["name"]},
                   args.dry_run, out)
    return out.finish(
        "Tell the owner. undo reverses it. Then run check: links to the old name are listed with their new target."
        if done else "Show this to the owner. When they approve, run the same command without --dry-run.")


def cmd_move(args):
    home, state, item, entry = prepare_move(args, "move a folder")
    wanted = args.to.strip().lower()
    if wanted in KINDS:
        group_no = home.group_no(KINDS[wanted])
    elif wanted.isdigit():
        group_no = int(wanted)
    else:
        raise Refuse("`%s` isn't a group. Use project, area, data, or a group number." % args.to,
                     "Run the command again with one of those.")
    if item["archived"]:
        raise Refuse("%s is in the archive." % item["number"], "Run restore first, then move it.")
    if group_no == home.group_no(9):
        raise Refuse("To close work, use archive.", "Run archive %s --dry-run." % item["number"])
    if group_no not in state.groups:
        raise Refuse("There is no group folder numbered %d." % group_no, "Run check to see the groups.")
    out = Out()
    if group_no == item["group_now"]:
        out.say("`%s` is already in that group." % item["rel"])
        return out.finish("Nothing to do.")
    target = state.groups[group_no] / item["folder"]
    done = do_move(home, "move", entry, item["path"], target,
                   {"event": "moved", "to_group": group_no, "from_group": item["group_now"]}, args.dry_run, out)
    return out.finish(
        "Tell the owner. undo reverses it. Then run check: links to the old place are listed with their new target."
        if done else "Show this to the owner. When they approve, run the same command without --dry-run.")


def origin_group(home, state, entry, item):
    """The group a folder in the old archive belongs to: where the ledger last saw it, else the group in its number."""
    for number in (entry["group_now"], int(item["number"][:2])):
        if number != home.group_no(9) and number in state.groups:
            return number
    return None


def cmd_archive(args):
    home, state, item, entry = prepare_move(args, "archive a folder")
    if item["archived"] and not item["legacy"]:
        raise Refuse("%s is already in its group's archive." % item["number"], "Nothing to do.")
    if item["legacy"]:
        # Out of the old archive for the whole workspace, into the archive of the group it came from.
        group_no = origin_group(home, state, entry, item)
        if group_no is None:
            raise Refuse("The group this folder came from isn't here, so it stays in the old archive.",
                         "Run check to see the groups, and ask the owner where it belongs.")
        op, event = "refile", {"event": "refiled", "to_group": group_no}
    else:
        group_no = item["group_now"]
        op, event = "archive", {"event": "archived", "from_group": group_no, "layout": "group"}
    shelf = state.groups[group_no] / ARCHIVE_DIR
    if os.path.islink(str(shelf)) or (shelf.exists() and not shelf.is_dir()):
        raise Refuse("`%s` isn't a plain folder, so nothing can be archived into it." % home.rel(shelf),
                     "Tell the owner. They can rename it, then run the command again.")
    made = not shelf.exists()
    out = Out()
    done = do_move(home, op, entry, item["path"], shelf / item["folder"], event, args.dry_run, out, make_parent=True)
    if made:
        out.say("`%s/` is new: this group's archive. It %s made for this move." % (home.rel(shelf), "was" if done else "would be"))
    if op == "refile":
        return out.finish(
            "Tell the owner. The folder is still archived, now inside its own group. undo puts it back in the old archive."
            if done else "Show this to the owner. When they approve this folder, run it without --dry-run.")
    return out.finish(
        "Tell the owner. restore %s or undo brings it back." % item["number"]
        if done else "Archive only when the owner asked to close this work. When they approve: first set Status to Closed "
        "in its hand-off and add a Session log line, then run this without --dry-run.")


def cmd_restore(args):
    home, state, item, entry = prepare_move(args, "restore a folder")
    if not item["archived"]:
        raise Refuse("%s isn't in an archive." % item["number"], "Nothing to do.")
    group_no = origin_group(home, state, entry, item) if item["legacy"] else item["group_now"]
    if group_no is None:
        raise Refuse("The group this folder came from isn't here.", "Run check to see the groups, then use move.")
    out = Out()
    done = do_move(home, "restore", entry, item["path"], state.groups[group_no] / item["folder"],
                   {"event": "restored", "to_group": group_no}, args.dry_run, out)
    return out.finish("Tell the owner. undo reverses it." if done
                      else "Show this to the owner. When they approve, run the same command without --dry-run.")


def cmd_undo(args):
    home = open_home(args)
    moves, _ = read_moves(home)
    done = [move for move in moves if move.get("state") == "done"]
    out = Out()
    if not done:
        out.say("There is no move to undo.")
        return out.finish("Nothing to do.")
    move = done[-1]
    current, original = home.root / move["to"], home.root / move["from"]
    reasons = check_move(home, current, original)
    if not reasons and move.get("key") and (current / home.handoff).is_file():
        found = read_key(current / home.handoff)
        if found is not None and found != move["key"]:
            reasons.append("`%s` isn't the folder that was moved: its key is different." % move["to"])
    if reasons:
        raise Refuse(
            "The last move can't be undone, so both folders were left where they are:\n" + bullets(reasons),
            "Tell the owner why, and ask what they want instead.",
        )
    if args.dry_run:
        out.say("# Undo (dry run): nothing was changed")
        out.say()
        out.say("`%s`  →  `%s`" % (move["to"], move["from"]))
        return out.finish("Show this to the owner. When they approve, run undo without --dry-run.")
    reverse = {"archive": {"event": "restored"}, "restore": {"event": "archived"}}.get(move["op"])
    logged = move.get("ledger", {})
    if move["op"] == "rename":
        reverse = {"event": "renamed", "name": logged.get("was", ""), "was": logged.get("name", "")}
    elif move["op"] == "move":
        reverse = {"event": "moved", "to_group": logged.get("from_group"), "from_group": logged.get("to_group")}
    elif move["op"] == "adopt":
        reverse = {"event": "retired", "reason": "the adoption was undone"}
    with lock(home):
        os.rename(str(current), str(original))
        append_line(home.records / MOVES_FILE, {"id": move["id"], "state": "undone", "undone": iso()})
        if reverse:
            append_line(home.records / LEDGER_FILE, dict(reverse, key=move["key"], number=move["number"], time=iso()))
        _, map_message = refresh_map(home, State(home), write=True)
    out.say("# Undo done")
    out.say()
    out.say("`%s`  →  `%s`" % (move["to"], move["from"]))
    out.say(map_message)
    return out.finish("Tell the owner the %s was undone." % move["op"])


# ----------------------------------------------------------------------------
# reconcile: bring the records back in line with the folders, with the owner's OK
# ----------------------------------------------------------------------------

def cmd_reconcile(args):
    home = open_home(args)
    state = State(home)
    path = home.records / LEDGER_FILE
    proposals, renames, manual = [], [], []

    keep = {}
    for raw in args.keep or []:
        number, _, who = raw.partition("=")
        if not who:
            raise Refuse("--keep takes NUMBER=KEY, such as --keep 91.05=a3f9c2.", "Run reconcile again.")
        keep[number.strip()] = who.strip()

    rebuilt = not path.is_file()
    if rebuilt:
        proposals.append(({"event": "rebuilt", "note": "A new ledger was started from the folders on disk. "
                           "Numbers retired before this are unknown."}, "Start a new ledger, marked as rebuilt."))
    for name, text in ((p.name, None) for p in sorted(home.records.iterdir())
                       if p.name != LEDGER_FILE and p.name.lower().startswith("ledger") and p.name.lower().endswith(".jsonl")):
        known = {json.dumps(event, sort_keys=True) for event in state.events}
        added = 0
        for line in read_text(home.records / name).splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and "event" in event and json.dumps(event, sort_keys=True) not in known:
                proposals.append((event, "Add a line from `%s`: %s %s." % (name, event.get("event"), event.get("number", ""))))
                known.add(json.dumps(event, sort_keys=True))
                added += 1
        renames.append((home.records / name, home.records / ("merged-" + name),
                        "Rename `%s` to `merged-%s` after taking its %d new line%s." % (name, name, added, "" if added == 1 else "s")))

    by_number = {}
    for item in state.numbered():
        by_number.setdefault(item["number"], []).append(item)
    counters = {}
    for number, items in sorted(by_number.items()):
        if len(items) > 1:
            who = keep.get(number)
            if who is None:
                lines = ["  - `%s`, key %s" % (item["rel"], item["key"] or "none") for item in items]
                manual.append("Number %s is on %d folders. The owner picks which keeps it:\n%s\n  Then run reconcile "
                              "--keep %s=<key of the folder that keeps it>." % (number, len(items), "\n".join(lines), number))
                continue
            keepers = [item for item in items if who in (item["key"], item["folder"])]
            if len(keepers) != 1:
                manual.append("--keep %s=%s doesn't match exactly one of the folders with that number." % (number, who))
                continue
            group_no = int(number[:2])
            for item in items:
                if item is keepers[0]:
                    continue
                counters[group_no] = counters.get(group_no, 0) + 1
                counter = state.next_counter(group_no, counters[group_no] - 1)
                if counter > 99:
                    manual.append("Group %d is full, so `%s` can't get a new number." % (group_no, item["rel"]))
                    continue
                new_number = "%d.%02d" % (group_no, counter)
                new_folder = "%s%s%s" % (new_number, home.sep, item["name"])
                key = item["key"] or new_key()
                event = ({"event": "renumbered", "key": key, "from": number, "to": new_number, "reason": "collision"}
                         if key in state.entries else
                         {"event": "adopted", "key": key, "number": new_number, "name": item["name"],
                          "group_now": item["group_now"] if not item["legacy"] else int(number[:2]),
                          "state": "archived" if item["archived"] else "active"})
                proposals.append((event, "`%s` becomes %s." % (item["rel"], new_number)))
                renames.append((item["path"], item["path"].parent / new_folder,
                                "Rename `%s` to `%s`." % (item["rel"], new_folder)))
                if not item["key"]:
                    manual.append("Add this line to `%s/%s` with the owner's OK: `**Key:** %s`"
                                  % (item["path"].parent.name + "/" + new_folder, home.handoff, key))
            continue
        item = items[0]
        if item["key"] and item["key"] in state.entries:
            if state.entries[item["key"]]["number"] != number:
                manual.append("`%s` carries the key of number %s. Compare the two with the owner."
                              % (item["rel"], state.entries[item["key"]]["number"]))
            continue
        same_number = [entry for entry in state.entries.values() if entry["number"] == number]
        if same_number and not item["key"]:
            continue
        if same_number:
            manual.append("`%s` has a key the ledger doesn't know for %s. Compare its hand-off with the ledger, with the owner."
                          % (item["rel"], number))
            continue
        key = item["key"] or new_key()
        proposals.append(({"event": "adopted", "key": key, "number": number, "name": item["name"],
                           "group_now": item["group_now"] if not item["legacy"] else int(number[:2]),
                           "state": "archived" if item["archived"] else "active"},
                          "Add number %s (`%s`) to the ledger." % (number, item["rel"])))
        if not item["key"]:
            manual.append("Add this line to `%s/%s` with the owner's OK: `**Key:** %s`" % (item["rel"], home.handoff, key))

    if args.retire_missing:
        live = {item["key"] for item in state.numbered() if item["key"]}
        live_numbers = {item["number"] for item in state.numbered()}
        for entry in state.entries.values():
            if entry["state"] != "retired" and entry["key"] not in live and entry["number"] not in live_numbers:
                proposals.append(({"event": "retired", "key": entry["key"], "number": entry["number"],
                                   "reason": "folder not found"}, "Retire number %s (%s): its folder isn't here."
                                  % (entry["number"], entry["name"])))
    for raw in args.floor or []:
        group, _, counter = raw.partition("=")
        if not (group.strip().isdigit() and counter.strip().isdigit() and 1 <= int(counter) <= 99):
            raise Refuse("--floor takes GROUP=COUNTER, such as --floor 91=7.", "Run reconcile again.")
        proposals.append(({"event": "floor", "group": int(group), "counter": int(counter)},
                          "Continue group %s above .%02d." % (group.strip(), int(counter))))
    for _, message in state.ledger_problems:
        if "can't be read" in message:
            manual.append(message + " Look at the file with the owner. Lines are never removed by the script.")

    out = Out()
    if not proposals and not renames and not manual:
        out.say("The records and the folders agree. Nothing to reconcile.")
        return out.finish("Nothing to do.")
    out.say("# Reconcile%s" % ("" if args.apply else " (proposal): nothing was changed"))
    out.say()
    if proposals or renames:
        out.say("Ledger lines and renames:" if args.apply else "This would be done:")
        for _, message in proposals:
            out.say("- " + message)
        for _, _, message in renames:
            out.say("- " + message)
    if manual:
        out.say()
        out.say("Needs the owner:")
        for message in manual:
            out.say("- " + message)
    if not args.apply:
        return out.finish(
            "Show this to the owner. After their OK, run reconcile again with --apply and the same options. "
            "If a home was restored from a backup, ask for the highest number they know was used and add --floor GROUP=COUNTER."
        )
    with lock(home):
        if rebuilt:
            write_new(path, "")
        for source, target, _ in renames:
            reasons = [] if source.parent == home.records else check_move(home, source, target)
            if source.parent == home.records and target.exists():
                reasons = ["`%s` already exists." % home.rel(target)]
            if reasons:
                raise Refuse("Reconcile stopped before changing anything else:\n" + bullets(reasons),
                             "Tell the owner why, and ask what they want instead.")
        for event, _ in proposals:
            append_line(path, dict(event, time=iso(), host=host()))
        for source, target, _ in renames:
            os.rename(str(source), str(target))
        _, map_message = refresh_map(home, State(home), write=True)
    out.say()
    out.say(map_message)
    left = State(home).blockers()
    return out.finish(
        "Run check. Then make the hand-off edits listed under Needs the owner, with their OK."
        if not left else "Some disagreements remain. Run reconcile again and show the owner.", 0)


# ----------------------------------------------------------------------------
# adopt: bring a folder that already sits inside the home into a numbered group
# ----------------------------------------------------------------------------

def cmd_adopt(args):
    home = open_home(args)
    state = State(home)
    stop_on_blockers(state, "give out a number")
    raw = Path(args.path).expanduser()
    source = raw if raw.is_absolute() else home.root / raw
    source = Path(os.path.normpath(str(source)))
    try:
        src_rel = source.resolve().relative_to(home.root).as_posix()
    except ValueError:
        raise Refuse(
            "`%s` is outside the workspace. Folders outside it stay where they are." % tilde(source),
            "Add a work folder that points at it: new --title \"<Title>\" --documents \"<that folder>\".",
        )
    source = home.root / src_rel
    if not source.is_dir() or os.path.islink(str(source)):
        raise Refuse("`%s` isn't a folder here." % src_rel, "Run scan to see what is in the workspace.")
    if WORK_RE.match(source.name):
        raise Refuse("`%s` already has a number." % src_rel, "Use move to change its group, or rename to change its name.")
    if source in state.groups.values() or src_rel.split("/")[0] == RECORDS or source == home.root:
        raise Refuse("`%s` is part of the workspace's own structure." % src_rel, "Pick a folder that holds a piece of work.")
    group_no = home.group_no(KINDS[args.kind])
    group = state.groups.get(group_no)
    if group is None:
        raise Refuse("There is no group folder numbered %d." % group_no, "Run setup again: it adds only what is missing.")
    counter = state.next_counter(group_no)
    if counter > 99:
        raise Refuse("Group %d is full: its numbers have reached .99." % group_no, "Ask the owner to add another group folder.")
    title = (args.title or source.name.replace("_", " ").replace("-", " ")).strip()
    name = slug(args.title) if args.title else slug(source.name)
    number = "%d.%02d" % (group_no, counter)
    target = group / ("%s%s%s" % (number, home.sep, name))
    reasons = check_move(home, source, target)
    if reasons:
        raise Refuse("Nothing was moved:\n" + bullets(reasons), "Tell the owner why, and ask what they want instead.")
    dst_rel = home.rel(target)
    existing_handoff = source / home.handoff
    key = read_key(existing_handoff) if existing_handoff.is_file() else None
    if key is None or key in state.entries:
        key, needs_key_line = new_key(), existing_handoff.is_file()
    else:
        needs_key_line = False
    status = "Ongoing" if args.kind != "project" else "Active"
    will_create = [name_ for name_, _ in work_templates(home) if not (source / name_).exists()]
    out = Out()
    if args.dry_run:
        out.say("# Adopt (dry run): nothing was changed")
        out.say()
        out.say("`%s`  →  `%s`" % (src_rel, dst_rel))
        out.say("It gets the number %s. Every file in it stays as it is." % number)
        if will_create:
            out.say("New files in it: %s." % ", ".join(will_create))
        return out.finish("Show this to the owner. When they approve, run the same command without --dry-run.")
    with lock(home):
        settle_moves(home)
        moves, _ = read_moves(home)
        move_id = max([move["id"] for move in moves] + [0]) + 1
        event = {"event": "issued", "number": number, "key": key, "name": name, "kind": args.kind,
                 "group_now": group_no, "host": host(), "adopted_from": src_rel}
        append_line(home.records / MOVES_FILE, {
            "id": move_id, "op": "adopt", "number": number, "key": key, "from": src_rel, "to": dst_rel,
            "state": "pending", "time": iso(), "host": host(), "ledger": event,
        })
        os.rename(str(source), str(target))
        append_line(home.records / MOVES_FILE, {"id": move_id, "state": "done"})
        append_line(home.records / LEDGER_FILE, dict(event, time=iso()))
        context = {
            "TITLE": title, "PURPOSE": args.purpose or "To confirm with %s." % home.owner_first(), "STATUS": status,
            "KEY": key, "TIMESTAMP": iso(), "DATE": today(), "BY": args.by, "HANDOFF": home.handoff,
            "OWNER_FIRST": home.owner_first(), "DOCUMENTS_BULLETS": "", "NUMBER": number,
            "README_DOCUMENTS": readme_documents([]),
        }
        for file_name, template in work_templates(home):
            if not (target / file_name).exists():
                write_new(target / file_name, render(template, context))
        _, map_message = refresh_map(home, State(home), write=True)
    out.say("# Adopt done: %s" % number)
    out.say()
    out.say("`%s`  →  `%s`" % (src_rel, dst_rel))
    if will_create:
        out.say("New files in it: %s." % ", ".join(will_create))
    out.say(map_message)
    if needs_key_line:
        return out.finish(
            "This folder already had a %s. With the owner's OK, add this line to its header: `**Key:** %s`. "
            "Then run check. undo puts the folder back." % (home.handoff, key)
        )
    return out.finish("Open its %s with the owner and fill in the goal and the next action. undo puts the folder back." % home.handoff)


# ----------------------------------------------------------------------------
# kit: a starter workspace as one ZIP, for a chat app that can't reach the owner's folders
# ----------------------------------------------------------------------------

def cmd_kit(args):
    answers = load_answers(args.answers)
    target = Path(args.out).expanduser()
    if target.exists():
        raise Refuse("`%s` already exists." % tilde(target), "Pick another name for the ZIP.")
    if not target.parent.is_dir():
        raise Refuse("The folder `%s` doesn't exist." % tilde(target.parent), "Pick a folder that exists for the ZIP.")
    notes = {}
    work = []
    for raw in answers.get("work", []) if isinstance(answers.get("work"), list) else []:
        if isinstance(raw, dict):
            item = dict(raw)
            described = item.pop("documents", None)
            if described and item.get("title"):
                notes[str(item["title"]).strip()] = described if isinstance(described, list) else [str(described)]
            work.append(item)
        else:
            work.append(raw)
    with tempfile.TemporaryDirectory(prefix="aws-kit-") as folder:
        kit_answers = dict(answers, location=str(Path(folder).resolve()), work=work, documents=[])
        kit_answers.pop("home", None)
        if kit_answers.get("home_number") is None:
            kit_answers["home_number"] = 90
        plan, problems = plan_setup(kit_answers)
        if problems:
            raise Refuse(
                "Fix the answers file, then run kit again. Nothing was created:\n%s" % bullets(problems),
                "Fix exactly what is listed, then run kit again.",
            )
        for item in plan["work"]:
            if item["title"] in notes:
                item["purpose"] = item["purpose"].rstrip(".") + ". Documents, as the owner described: " + "; ".join(
                    str(note) for note in notes[item["title"]]) + "."
        out = Out()
        apply_setup(plan, out, args.by)
        home_root = plan["home"].root
        files = sorted(path for path in home_root.rglob("*") if path.is_file() and not path.name.startswith("lock-"))
        folders = sorted(path for path in home_root.rglob("*") if path.is_dir())
        with zipfile.ZipFile(str(target), "w", zipfile.ZIP_DEFLATED) as archive:
            for path in folders:
                archive.writestr(home_root.name + "/" + path.relative_to(home_root).as_posix() + "/", "")
            for path in files:
                archive.write(str(path), home_root.name + "/" + path.relative_to(home_root).as_posix())
        name, count = home_root.name, len(files)
    out = Out()
    out.say("# Starter kit built")
    out.say()
    out.say("ZIP: `%s` (%d files). It holds one folder, `%s/`." % (tilde(target), count, name))
    out.say("Nothing was created on the owner's computer.")
    return out.finish(
        "Give the owner the ZIP. Tell them plainly: unzip it where the AI home should live, and nothing exists on "
        "their computer until they do. For later sessions they upload a work folder's %s and save the updated one back."
        % plan["home"].handoff
    )


# ----------------------------------------------------------------------------
# install and connect: the only commands that write outside the home
# ----------------------------------------------------------------------------

TOOLS = {
    "claude": {"label": "Claude Code", "aliases": ("claude-code",), "home_env": "CLAUDE_CONFIG_DIR", "home": ".claude",
               "skills": None, "instructions": "CLAUDE.md"},
    "codex": {"label": "Codex", "aliases": ("openai-codex",), "home_env": "CODEX_HOME", "home": ".codex",
              "skills": ".agents/skills", "instructions": "AGENTS.md"},
    "agents": {"label": "Other agents that read ~/.agents/skills", "aliases": ("cursor", "copilot", "amp", "gemini", "devin"),
               "home_env": None, "home": ".agents", "skills": ".agents/skills", "instructions": None},
}
SECTION_START = "<!-- agent-workspace-setup:start -->"
SECTION_END = "<!-- agent-workspace-setup:end -->"
SKIP_FILES = {".DS_Store", "thumbs.db", "desktop.ini"}


def tool_info(name):
    wanted = str(name).strip().lower()
    for key, spec in TOOLS.items():
        if wanted == key or wanted in spec["aliases"]:
            override = os.environ.get(spec["home_env"]) if spec["home_env"] else None
            base = Path(override).expanduser() if override else Path.home() / spec["home"]
            skills = Path.home() / spec["skills"] if spec["skills"] else base / "skills"
            return {
                "key": key, "label": spec["label"], "skills": skills,
                "instructions": base / spec["instructions"] if spec["instructions"] else None,
            }
    raise Refuse("`%s` isn't a tool this skill knows. Known: %s." % (name, ", ".join(sorted(TOOLS))),
                 "Use one of those, or --dest with the tool's skills folder.")


def skill_source():
    return Path(__file__).resolve().parent.parent


def tree_digest(folder):
    found = {}
    folder = Path(folder)
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if not path.is_file() or path.name in SKIP_FILES or path.suffix == ".pyc" or "__pycache__" in relative.parts:
            continue
        found[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def copy_state(destination):
    if os.path.islink(str(destination)):
        return "link"
    if not destination.exists():
        return "missing"
    skill_md = destination / "SKILL.md"
    if not skill_md.is_file() or not re.search(r"^name:\s*%s\s*$" % re.escape(SKILL), read_text(skill_md), re.M):
        return "foreign"
    return "current" if tree_digest(destination) == tree_digest(skill_source()) else "different"


STATE_WORDS = {
    "missing": "not installed",
    "current": "installed and up to date",
    "different": "installed, and different from this copy",
    "link": "a link to a copy kept somewhere else; left alone",
    "foreign": "a folder with this name that isn't this skill; left alone",
}


def copy_skill(destination):
    source = skill_source()
    wanted = tree_digest(source)
    staging = destination.parent / (".new-%s-%s" % (SKILL, secrets.token_hex(3)))
    for relative in wanted:
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source / relative), str(target))
    if tree_digest(staging) != wanted:
        raise Refuse(
            "The copy in `%s` doesn't match the skill, so it was not put in place." % tilde(staging),
            "Tell the owner. Nothing that was there before has changed.",
        )
    os.rename(str(staging), str(destination))


def cmd_install(args):
    targets = []
    for name in args.tool or []:
        info = tool_info(name)
        targets.append((info["label"], info["skills"] / SKILL))
    for raw in args.dest or []:
        targets.append((raw, Path(raw).expanduser() / SKILL))
    out = Out()
    if not targets:
        out.say("# Where this skill is installed")
        out.say()
        out.say("Read-only. Nothing was written.")
        out.say()
        out.say("| Tool | Folder | State |")
        out.say("|---|---|---|")
        seen = set()
        for key in TOOLS:
            info = tool_info(key)
            destination = info["skills"] / SKILL
            if destination in seen:
                continue
            seen.add(destination)
            label = info["label"] if key != "codex" else "Codex and other agents"
            out.say("| %s | `%s` | %s |" % (label, tilde(destination), STATE_WORDS[copy_state(destination)]))
        return out.finish("Ask the owner which tool they want it in. Then run install --tool <claude or codex> --dry-run.")
    unique, plans = [], []
    for label, destination in targets:
        if destination not in [d for _, d in unique]:
            unique.append((label, destination))
    stamp = now().strftime("%Y%m%d-%H%M%S")
    for label, destination in unique:
        state = copy_state(destination)
        backup = destination.parent.parent / "skill-backups" / ("%s-%s" % (SKILL, stamp))
        plans.append({"label": label, "destination": destination, "state": state, "backup": backup})
    out.say("# Install%s" % (" (dry run): nothing was written" if args.dry_run else ""))
    out.say()
    blocked = False
    for plan in plans:
        where = "`%s`" % tilde(plan["destination"])
        if plan["state"] == "missing":
            out.say("- %s: a fresh copy goes to %s." % (plan["label"], where))
        elif plan["state"] == "current":
            out.say("- %s: %s is already up to date. Nothing to do." % (plan["label"], where))
        elif plan["state"] == "different" and args.update:
            out.say("- %s: the copy in %s is replaced. The old copy is kept: it moves to `%s`."
                    % (plan["label"], where, tilde(plan["backup"])))
        elif plan["state"] == "different":
            out.say("- %s: %s holds a different copy. It was left alone. Run again with --update to replace it; "
                    "the old copy would move to `%s`." % (plan["label"], where, tilde(plan["backup"])))
            blocked = True
        else:
            out.say("- %s: %s is %s." % (plan["label"], where, STATE_WORDS[plan["state"]]))
            blocked = True
    if args.dry_run:
        return out.finish("Show this to the owner. When they approve these exact folders, run it without --dry-run.")
    for plan in plans:
        destination = plan["destination"]
        if plan["state"] == "missing":
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy_skill(destination)
        elif plan["state"] == "different" and args.update:
            plan["backup"].parent.mkdir(parents=True, exist_ok=True)
            os.rename(str(destination), str(plan["backup"]))
            copy_skill(destination)
    done = [plan for plan in plans if plan["state"] == "missing" or (plan["state"] == "different" and args.update)]
    out.say()
    out.say("Copied and verified: %d. Left as they were: %d." % (len(done), len(plans) - len(done)))
    return out.finish(
        "Tell the owner to start a new session in that tool and check that %s is listed." % SKILL
        if done else "Nothing was installed. Tell the owner why.", 1 if blocked and not done else 0)


def connect_section(home):
    shown = tilde(home.root)
    return "\n".join([
        SECTION_START,
        "## AI workspace",
        "",
        "- My AI workspace is `%s`. Before working on anything there, read `%s/AGENTS.md` and follow it, "
        "wherever the session started." % (shown, shown),
        "- The memory of each piece of work is its `%s`, not the chat. Read it first, and update it when a task is done."
        % home.handoff,
        SECTION_END,
    ]) + "\n"


def cmd_connect(args):
    home = open_home(args)
    info = tool_info(args.tool)
    section = connect_section(home)
    out = Out()
    if tilde(home.root).replace(os.sep, "/").startswith(SESSION_PATHS):
        raise Refuse(
            "From here the workspace has a path that exists only inside this session, so it can't be written into a "
            "tool's instructions.",
            "Run connect on the owner's own computer, in a tool that sees the workspace at its real path.",
        )
    if info["instructions"] is None:
        out.say("%s has no personal instructions file that this skill can write." % info["label"])
        out.say()
        out.say("The owner can paste this into that tool's own instructions:")
        out.say()
        out.say("Before any work in my AI workspace `%s`, read the AGENTS.md there and follow it." % tilde(home.root))
        return out.finish("Give the owner that line. Nothing was written.")
    path = info["instructions"]
    text = read_text(path) if path.is_file() else ""
    has_section = SECTION_START in text and SECTION_END in text
    backup = path.parent / ("%s.backup-%s" % (path.name, now().strftime("%Y%m%d-%H%M%S")))
    if args.remove:
        if not has_section:
            out.say("`%s` has no section from this skill. Nothing to remove." % tilde(path))
            return out.finish("Nothing to do.")
        start = text.index(SECTION_START)
        end = text.index(SECTION_END) + len(SECTION_END)
        new_text = (text[:start].rstrip("\n") + "\n" + text[end:].lstrip("\n")).lstrip("\n")
        action = "The section between this skill's markers is removed. Everything else in the file stays."
    elif has_section:
        if tilde(home.root) in text[text.index(SECTION_START):text.index(SECTION_END)]:
            out.say("%s is already connected: `%s` points at this workspace." % (info["label"], tilde(path)))
            return out.finish("Nothing to do.")
        raise Refuse(
            "`%s` already has a section from this skill that points at another workspace." % tilde(path),
            "Ask the owner which workspace they want. To switch, run connect --tool %s --remove first." % info["key"],
        )
    else:
        new_text = (text.rstrip("\n") + "\n\n" if text.strip() else "# Personal instructions\n\n") + section
        action = "This section is added at the end. Nothing else in the file changes."
    out.say("# Connect %s%s" % (info["label"], " (dry run): nothing was written" if args.dry_run else ""))
    out.say()
    out.say("File: `%s`%s" % (tilde(path), "" if path.is_file() else " (new)"))
    if path.is_file():
        out.say("Backup first: `%s`" % tilde(backup))
    out.say(action)
    if not args.remove:
        out.say()
        out.say("```markdown")
        out.say(section.rstrip("\n"))
        out.say("```")
    if args.dry_run:
        return out.finish("Show the owner this exact file and text. When they approve, run it without --dry-run.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        with open(backup, "xb") as handle:
            handle.write(path.read_bytes())
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(new_text)
    return out.finish(
        "Tell the owner to restart %s: it reads this file when it starts. connect --tool %s --remove takes the section out again."
        % (info["label"], info["key"]) if not args.remove else "Tell the owner the section was removed.")


# ----------------------------------------------------------------------------
# upgrade: bring a workspace that already exists up to this version of the skill
# ----------------------------------------------------------------------------

def rules_section(home, state, version, titles, note=""):
    """Rules a workspace set up before `version` lacks, in the template's own words, between this skill's markers."""
    rendered = render("home-AGENTS.md", home_context(home, state.groups))
    lines = []
    for title in titles:
        match = re.search(r"^(?:\d+\.|-)[ \t]+(\*\*%s\*\*.*)$" % re.escape(title), rendered, re.M)
        if match is None:
            raise Refuse(
                "The rule `%s` isn't in the rules template." % title,
                "This is a fault in the skill. Tell the owner and stop.",
            )
        lines.append("- " + match.group(1))
    if note:
        lines.append("- " + note)
    return "\n".join(
        ["<!-- agent-workspace-setup:rules-%s -->" % version, "## Added with version %s" % version, ""]
        + lines + ["<!-- /agent-workspace-setup:rules-%s -->" % version]
    ) + "\n"


def cmd_upgrade(args):
    home = open_home(args)
    have, this = home.skill_version(), __version__
    out = Out()
    if version_tuple(have) > version_tuple(this):
        out.say("This workspace was upgraded by version %s of the skill. This copy of the skill is %s, which is older."
                % (have, this))
        return out.finish("Nothing was changed. Tell the owner to update this copy of the skill.")
    if version_tuple(have) == version_tuple(this):
        out.say("This workspace is already at version %s." % this)
        return out.finish("Nothing to do.")
    pending = [step for step in UPGRADES if version_tuple(have) < version_tuple(step["version"]) <= version_tuple(this)]
    rules_path = home.root / "AGENTS.md"
    if not rules_path.is_file():
        raise Refuse(
            "The workspace rules, `AGENTS.md`, are missing, so the new rules have nowhere to go. Nothing was changed.",
            "Run setup again: it adds only what is missing. Then run upgrade again.",
        )
    text = read_text(rules_path)
    state = State(home)
    sections = []
    for step in pending:
        missing = [title for title in step["rules"] if "**%s**" % title not in text]
        if missing and "agent-workspace-setup:rules-%s " % step["version"] not in text:
            sections.append(rules_section(home, state, step["version"], missing, step.get("note", "")))
    settings_rel = "%s/%s" % (RECORDS, SETTINGS_FILE)
    out.say("# Upgrade to version %s%s" % (this, " (dry run): nothing was written" if args.dry_run else ""))
    out.say()
    out.say("This workspace was set up with version %s of the skill." % have)
    out.say()
    out.say("## What's new")
    out.say()
    news = [line for step in pending for line in step["news"]]
    for line in news or ["Nothing that changes how a workspace is used."]:
        out.say("- " + line)
    out.say()
    out.say("## What %s" % ("would change" if args.dry_run else "changed"))
    out.say()
    if sections:
        out.say("- `AGENTS.md`: the section below is added at the end. Nothing else in the file changes.")
    else:
        out.say("- `AGENTS.md`: nothing. It needs no new rule.")
    out.say("- `%s`: the recorded version becomes %s." % (settings_rel, this))
    out.say("- Nothing else. No hand-off, no work folder and no number is touched.")
    if sections:
        out.say()
        out.say("```markdown")
        out.say("\n".join(sections).rstrip("\n"))
        out.say("```")
    if args.dry_run:
        return out.finish("Tell the owner what's new in plain words, and show them the exact text for `AGENTS.md`. "
                          "When they approve, run upgrade without --dry-run.")
    with lock(home):
        if sections:
            gap = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") or not text else "\n\n")
            with open(rules_path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(gap + "\n".join(sections))
        settings_path = home.records / SETTINGS_FILE
        recorded = json.loads(read_text(settings_path))
        recorded["skill_version"] = this
        draft = settings_path.with_name(SETTINGS_FILE + ".new")
        with open(draft, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(recorded, indent=2, ensure_ascii=False) + "\n")
        os.replace(str(draft), str(settings_path))
    return out.finish("Tell the owner what changed. Some tools read the rules only when they start, "
                      "so they should restart those tools.")


# ----------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="workspace.py",
        description="Set up and keep a numbered AI agent workspace. Every command ends with a Next line.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name, func, text, home=True, dry_run=False):
        sub = commands.add_parser(name, help=text, description=text)
        sub.set_defaults(func=func)
        if home:
            sub.add_argument("--home", help="the workspace folder (default: found from the current folder)")
        if dry_run:
            sub.add_argument("--dry-run", action="store_true", help="show what would happen and change nothing")
        return sub

    sub = add("init", cmd_init, "List likely places for the AI home, or suggest a number for one place. Writes nothing.", home=False)
    sub.add_argument("--path", help="a folder the AI home could go in")

    sub = add("setup", cmd_setup, "Build a workspace, or add to one, from an answers file.", home=False, dry_run=True)
    sub.add_argument("--answers", required=True, help="the JSON answers file")
    sub.add_argument("--by", default=SKILL + " skill", help="the tool doing the work, for the hand-off")

    sub = add("new", cmd_new, "Add one numbered work folder.", dry_run=True)
    sub.add_argument("--title", required=True)
    sub.add_argument("--kind", default="project", choices=sorted(KINDS))
    sub.add_argument("--purpose")
    sub.add_argument("--status")
    sub.add_argument("--documents", action="append", help="a document folder this work reads; it stays where it is")
    sub.add_argument("--by", default=SKILL + " skill")

    sub = add("scan", cmd_scan, "Read-only inventory of a folder: names, counts, sizes, dates.")
    sub.add_argument("path", nargs="?", help="the folder to look at (default: the workspace)")
    sub.add_argument("--private", action="append", help="a folder name the owner calls private; it is not opened")

    sub = add("check", cmd_check, "Read-only check of the workspace.")
    sub.add_argument("--brief", action="store_true", help="the short view for briefing the owner")
    sub.add_argument("--json", action="store_true", help="everything as JSON")

    add("map", cmd_map, "Refresh the map tables in the home's README.", dry_run=True)

    sub = add("rename", cmd_rename, "Rename a work folder. It keeps its number.", dry_run=True)
    sub.add_argument("number")
    sub.add_argument("title")

    sub = add("move", cmd_move, "Move a work folder to another group. It keeps its number.", dry_run=True)
    sub.add_argument("number")
    sub.add_argument("--to", required=True, help="project, area, data, or a group number")

    sub = add("archive", cmd_archive, "Move closed work into its group's archive. It keeps its number.", dry_run=True)
    sub.add_argument("number")

    sub = add("restore", cmd_restore, "Bring a work folder back out of an archive.", dry_run=True)
    sub.add_argument("number")

    add("undo", cmd_undo, "Reverse the last rename, move, archive or restore.", dry_run=True)

    sub = add("adopt", cmd_adopt, "Bring a folder that is already inside the home into a numbered group.", dry_run=True)
    sub.add_argument("path", help="the folder, relative to the home")
    sub.add_argument("--kind", default="project", choices=sorted(KINDS))
    sub.add_argument("--title")
    sub.add_argument("--purpose")
    sub.add_argument("--by", default=SKILL + " skill")

    sub = add("kit", cmd_kit, "Build a starter workspace as one ZIP, for a chat app that can't reach the owner's folders.", home=False)
    sub.add_argument("--answers", required=True, help="the JSON answers file; `location` is ignored")
    sub.add_argument("--out", required=True, help="where to write the ZIP")
    sub.add_argument("--by", default=SKILL + " skill")

    sub = add("install", cmd_install, "Copy this skill into a tool's skills folder. With no options, show where it is installed.",
              home=False, dry_run=True)
    sub.add_argument("--tool", action="append", help="claude, codex or agents")
    sub.add_argument("--dest", action="append", help="any other skills folder")
    sub.add_argument("--update", action="store_true", help="replace a different copy; the old one is moved to a backup folder")

    sub = add("connect", cmd_connect, "Point a tool's personal instructions at this workspace.", dry_run=True)
    sub.add_argument("--tool", required=True, help="claude or codex")
    sub.add_argument("--remove", action="store_true", help="take the section out again")

    sub = add("reconcile", cmd_reconcile, "Propose how to bring the records back in line with the folders.")
    sub.add_argument("--apply", action="store_true", help="do what was proposed, after the owner's OK")
    sub.add_argument("--keep", action="append", metavar="NUMBER=KEY", help="which folder keeps a number that is on two")
    sub.add_argument("--floor", action="append", metavar="GROUP=COUNTER", help="the highest number known to be used")
    sub.add_argument("--retire-missing", action="store_true", help="retire numbers whose folders are gone")

    add("upgrade", cmd_upgrade, "After the skill was updated: say what's new, and add new rules to this workspace.",
        dry_run=True)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except Refuse as refusal:
        print(refusal.message)
        print()
        print("**Next:** " + refusal.next_step)
        return 1
    except Exception as fault:  # a fault in this script, not in the workspace
        frames = [frame for frame in traceback.extract_tb(fault.__traceback__) if frame.filename == __file__]
        line = frames[-1].lineno if frames else 0
        print("The script hit a fault and stopped: %s: %s (`%s`, workspace.py line %d, version %s)."
              % (type(fault).__name__, fault, args.command, line, __version__))
        print()
        print("**Next:** This is a fault in the skill. Tell the owner, and add the line above to `%s/%s` "
              "if there is a workspace. Run check before any other command, and don't repeat this one."
              % (RECORDS, FRICTION_FILE))
        return 2


if __name__ == "__main__":
    sys.exit(main())
