"""Offline unit tests for workspace.py. Standard library only.

Every test builds its own workspace in a temporary folder and points HOME there,
so nothing outside that folder is ever read or written.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "skills" / "agent-workspace-setup"
SCRIPT = SKILL_DIR / "scripts" / "workspace.py"

spec = importlib.util.spec_from_file_location("workspace", SCRIPT)
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)


def run(*argv):
    """Run one command in-process. Returns (exit code, output)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        try:
            code = ws.main([str(arg) for arg in argv])
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else 2
    return code, buffer.getvalue()


def manifest(root):
    """Every file's hash and every folder's name under root."""
    found = {}
    for current, folders, files in os.walk(str(root)):
        for name in folders:
            found[os.path.relpath(os.path.join(current, name), str(root)) + "/"] = "dir"
        for name in files:
            path = os.path.join(current, name)
            with open(path, "rb") as handle:
                found[os.path.relpath(path, str(root))] = hashlib.sha256(handle.read()).hexdigest()
    return found


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aws-test-")).resolve()
        self.drive = self.tmp / "Drive"
        self.fake_home = self.tmp / "userhome"
        self.drive.mkdir()
        self.fake_home.mkdir()
        names = ("HOME", "USERPROFILE", "AGENT_WORKSPACE_HOST", "CLAUDE_CONFIG_DIR", "CODEX_HOME")
        self.saved = {name: os.environ.get(name) for name in names}
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        os.environ.pop("CODEX_HOME", None)
        os.environ["HOME"] = str(self.fake_home)
        os.environ["USERPROFILE"] = str(self.fake_home)
        os.environ["AGENT_WORKSPACE_HOST"] = "testbox"
        self.cwd = os.getcwd()
        os.chdir(str(self.tmp))
        self.home = self.drive / "90_AI-Agents"

    def tearDown(self):
        os.chdir(self.cwd)
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def answers(self, **extra):
        data = {
            "location": str(self.drive),
            "owner": "Ana Lopez",
            "work": [
                {"title": "Duplex renovation", "kind": "project", "purpose": "Renovate the duplex on Elm St."},
                {"title": "Bookkeeping", "kind": "area"},
            ],
        }
        data.update(extra)
        path = self.tmp / "answers.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def build(self, **extra):
        code, output = run("setup", "--answers", self.answers(**extra))
        self.assertEqual(code, 0, output)
        return output

    def check(self, home=None):
        code, output = run("check", "--json", "--home", home or self.home)
        data = json.loads(output)
        return code, data

    def rules(self, home=None):
        return sorted({finding["rule"] for finding in self.check(home)[1]["findings"]})

    def ledger(self, home=None):
        path = (home or self.home) / "_workspace" / "ledger.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def key_of(self, folder):
        text = (folder / "HANDOFF.md").read_text(encoding="utf-8")
        return re.search(r"\*\*Key:\*\* ([0-9a-f]{6})", text).group(1)

    def project(self):
        return self.home / "91_Projects" / "91.01_Duplex-renovation"


class SetupTests(Base):
    def test_dry_run_writes_nothing(self):
        answers = self.answers()
        before = manifest(self.tmp)
        code, output = run("setup", "--answers", answers, "--dry-run")
        after = manifest(self.tmp)
        self.assertEqual(code, 0, output)
        self.assertEqual(before, after)
        self.assertIn("nothing was written", output)
        self.assertIn("91.01_Duplex-renovation/", output)
        self.assertIn("92.01_Bookkeeping/", output)

    def test_setup_builds_a_clean_workspace(self):
        self.build()
        for rel in ("AGENTS.md", "CLAUDE.md", "README.md", "_workspace/settings.json", "_workspace/ledger.jsonl",
                    "90_Inbox", "91_Projects/AGENTS.md", "92_Areas/AGENTS.md", "95_Data/AGENTS.md",
                    "91_Projects/91.01_Duplex-renovation/AGENTS.md", "91_Projects/91.01_Duplex-renovation/HANDOFF.md",
                    "92_Areas/92.01_Bookkeeping/HANDOFF.md"):
            self.assertTrue((self.home / rel).exists(), rel)
        self.assertFalse((self.home / "99_Archive").exists())  # each group keeps its own archive, made on first use
        self.assertEqual([path for path in self.home.rglob("_Archive")], [])
        code, data = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(data["summary"]["error"], 0, data["findings"])
        self.assertEqual(data["summary"]["warn"], 0, data["findings"])
        self.assertEqual(len(data["work"]), 2)
        for path in self.home.rglob("*.md"):
            self.assertNotIn("{{", path.read_text(encoding="utf-8"), str(path))

    def test_work_folder_starts_with_the_six_standard_files(self):
        self.build()
        project = self.project()
        self.assertEqual(sorted(p.name for p in project.iterdir()),
                         ["AGENTS.md", "AGENT_SYNC.md", "CLAUDE.md", "DECISIONS.md", "HANDOFF.md", "README.md"])
        self.assertTrue((project / "CLAUDE.md").read_text(encoding="utf-8").startswith("@AGENTS.md\n"))
        self.assertTrue((self.home / "91_Projects" / "CLAUDE.md").is_file())
        readme = (project / "README.md").read_text(encoding="utf-8")
        self.assertIn("**Number:** " + project.name.split("_")[0], readme)
        self.assertIn("](../../README.md)", readme)
        self.assertIn("](../../AGENTS.md)", readme)
        self.assertTrue((project / "DECISIONS.md").read_text(encoding="utf-8").startswith("# Decisions: "))
        self.assertTrue((project / "AGENT_SYNC.md").read_text(encoding="utf-8").startswith("# Agent sync: "))
        agents = (project / "AGENTS.md").read_text(encoding="utf-8")
        for name in ("../../AGENTS.md", "README.md", "HANDOFF.md", "DECISIONS.md", "AGENT_SYNC.md"):
            self.assertIn(name, agents)

    def test_the_preview_lists_the_six_standard_files(self):
        code, output = run("setup", "--answers", self.answers(), "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("the six standard files  · Active  (new)", output)
        self.assertIn("README.md, HANDOFF.md, DECISIONS.md, AGENT_SYNC.md, AGENTS.md, CLAUDE.md.", output)
        self.assertEqual(output.count("```"), 2)

    def test_check_says_when_the_map_is_out_of_date_and_map_fixes_it(self):
        self.build()
        handoff = self.project() / "HANDOFF.md"
        text = handoff.read_text(encoding="utf-8")
        handoff.write_text(re.sub(r"\*\*Purpose:\*\* [^·]*·", "**Purpose:** Finish with the permit closed. ·", text, count=1),
                           encoding="utf-8")
        readme = self.project() / "README.md"
        readme.write_text(re.sub(r"(?m)^\*\*Purpose:\*\* .*$", "**Purpose:** Finish with the permit closed.",
                                 readme.read_text(encoding="utf-8"), count=1), encoding="utf-8")
        code, data = self.check()
        hits = [finding for finding in data["findings"] if finding["rule"] == "MAP003"]
        self.assertEqual(len(hits), 1, data["findings"])
        self.assertEqual(hits[0]["severity"], "info")
        code, output = run("map", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("Finish with the permit closed.", (self.home / "README.md").read_text(encoding="utf-8"))
        code, data = self.check()
        self.assertEqual([finding["rule"] for finding in data["findings"]], [])

    def test_a_private_folder_given_as_a_full_path_is_recorded_the_portable_way(self):
        private = self.home.parent / "Private"
        private.mkdir()
        self.build(private=[str(private)])
        settings = json.loads((self.home / "_workspace" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["private"], ["../Private"])
        self.assertIn("`../Private`", (self.home / "AGENTS.md").read_text(encoding="utf-8"))

    def test_a_private_folder_given_as_a_session_path_is_refused(self):
        code, output = run("setup", "--answers", self.answers(private=["/sessions/abc/mnt/Drive/Private"]), "--dry-run")
        self.assertNotEqual(code, 0, output)
        self.assertIn("only inside this session", output)

    def test_check_names_a_missing_standard_file(self):
        self.build()
        (self.project() / "DECISIONS.md").unlink()
        (self.project() / "README.md").unlink()
        code, data = self.check()
        hits = [finding for finding in data["findings"] if finding["rule"] == "WRK005"]
        self.assertEqual(len(hits), 1, data["findings"])
        self.assertIn("README.md", hits[0]["message"])
        self.assertIn("DECISIONS.md", hits[0]["message"])
        self.assertEqual(hits[0]["severity"], "info")
        self.assertEqual(data["summary"]["error"], 0, data["findings"])

    def test_second_run_adds_nothing_and_keeps_edits(self):
        self.build()
        handoff = self.project() / "HANDOFF.md"
        handoff.write_text(handoff.read_text(encoding="utf-8") + "\nOwner's note.\n", encoding="utf-8")
        before = manifest(self.home)
        output = self.build()
        self.assertEqual(before, manifest(self.home))
        self.assertIn("Nothing new was needed", output)
        self.assertIn("Owner's note.", handoff.read_text(encoding="utf-8"))

    def test_a_place_with_a_workspace_is_reused_not_doubled(self):
        self.build()
        self.build()
        self.assertEqual([p.name for p in self.drive.iterdir() if p.is_dir()], ["90_AI-Agents"])
        code, output = run("init", "--path", self.drive)
        self.assertIn("already in", output)

    def test_second_run_adds_only_new_work(self):
        self.build()
        self.build(home=str(self.home), work=[{"title": "Duplex renovation"}, {"title": "Roof repair"}])
        self.assertTrue((self.home / "91_Projects" / "91.02_Roof-repair" / "HANDOFF.md").is_file())
        self.assertEqual(len(list((self.home / "91_Projects").glob("91.*"))), 2)

    def test_home_number_is_the_owners_choice(self):
        self.build(home_number=10, home_name="AI")
        home = self.drive / "10_AI"
        for name in ("10_Inbox", "11_Projects", "12_Areas", "15_Data"):
            self.assertTrue((home / name).is_dir(), name)
        self.assertFalse((home / "19_Archive").exists())
        self.assertTrue((home / "11_Projects" / "11.01_Duplex-renovation").is_dir())
        self.assertTrue((home / "12_Areas" / "12.01_Bookkeeping").is_dir())
        code, data = self.check(home)
        self.assertEqual((code, data["summary"]["error"], data["summary"]["warn"]), (0, 0, 0), data["findings"])

    def test_suggested_number_fits_the_folders_around(self):
        self.assertEqual(ws.suggest_number(self.drive)[0], 90)
        (self.drive / "10_Business").mkdir()
        self.assertEqual(ws.suggest_number(self.drive)[0], 90)
        (self.drive / "90_Old").mkdir()
        self.assertEqual(ws.suggest_number(self.drive)[0], 80)

    def test_invalid_answers_change_nothing_and_say_why(self):
        before = manifest(self.tmp)
        path = self.tmp / "bad.json"
        path.write_text(json.dumps({"location": str(self.drive), "home_number": 95,
                                    "work": [{"kind": "project"}]}), encoding="utf-8")
        code, output = run("setup", "--answers", path)
        self.assertEqual(code, 1)
        self.assertIn("home_number", output)
        self.assertIn("**Next:**", output)
        path.unlink()
        self.assertEqual(before, manifest(self.tmp))

    def test_documents_stay_untouched_and_are_recorded_by_path(self):
        papers = self.drive / "Duplex papers"
        papers.mkdir()
        (papers / "permit.pdf").write_bytes(b"%PDF canary")
        before = manifest(papers)
        self.build(work=[{"title": "Duplex renovation", "documents": [str(papers)]}])
        self.assertEqual(before, manifest(papers))
        settings = json.loads((self.home / "_workspace" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["documents"], ["../Duplex papers"])
        self.assertIn("../Duplex papers", (self.project() / "HANDOFF.md").read_text(encoding="utf-8"))


class SessionPathTests(Base):
    def test_a_session_only_path_is_never_recorded(self):
        home = ws.Home(self.drive / "90_AI-Agents", dict(ws.DEFAULT_SETTINGS, owner="Ana Lopez"))
        self.assertIsNone(ws.record_location(home, "/sessions/abc123/mnt/Other/Papers"))
        self.assertEqual(ws.record_location(home, str(self.drive / "Papers")), "../Papers")
        path = self.tmp / "session.json"
        path.write_text(json.dumps({"location": str(self.drive), "owner": "Ana Lopez", "work": [
            {"title": "Duplex renovation", "documents": ["/sessions/abc123/mnt/Other/Papers"]}]}), encoding="utf-8")
        code, output = run("setup", "--answers", path, "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("only inside this session", output)


class NumberingTests(Base):
    def setUp(self):
        super().setUp()
        self.build()

    def new(self, title, kind="project"):
        code, output = run("new", "--home", self.home, "--title", title, "--kind", kind)
        self.assertEqual(code, 0, output)
        return output

    def test_new_takes_the_next_number_and_a_fresh_key(self):
        self.new("Roof repair")
        folder = self.home / "91_Projects" / "91.02_Roof-repair"
        self.assertTrue(folder.is_dir())
        self.assertNotEqual(self.key_of(folder), self.key_of(self.project()))
        self.assertIn("91.02", (self.home / "README.md").read_text(encoding="utf-8"))

    def test_new_dry_run_writes_nothing(self):
        before = manifest(self.home)
        code, output = run("new", "--home", self.home, "--title", "Roof repair", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.home))

    def test_numbers_are_never_reused(self):
        self.new("Roof repair")
        shutil.rmtree(str(self.home / "91_Projects" / "91.02_Roof-repair"))  # the owner deletes it by hand
        self.new("Fence")
        self.assertTrue((self.home / "91_Projects" / "91.03_Fence").is_dir())
        run("archive", "--home", self.home, "91.03")
        self.new("Gate")
        self.assertTrue((self.home / "91_Projects" / "91.04_Gate").is_dir())

    def test_new_stops_when_a_folder_is_not_in_the_ledger(self):
        (self.home / "91_Projects" / "91.07_Made-by-hand").mkdir()
        before = manifest(self.home)
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        self.assertEqual(code, 1)
        self.assertIn("NUM002", output)
        self.assertEqual(before, manifest(self.home))

    def test_new_stops_when_the_ledger_is_missing(self):
        (self.home / "_workspace" / "ledger.jsonl").rename(self.home / "_workspace" / "gone.txt")
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        self.assertEqual(code, 1)
        self.assertIn("LED001", output)

    def test_reconcile_adopts_a_folder_and_rebuilds_a_lost_ledger(self):
        (self.home / "_workspace" / "ledger.jsonl").rename(self.home / "_workspace" / "gone.txt")
        before = manifest(self.home)
        code, output = run("reconcile", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("nothing was changed", output)
        self.assertEqual(before, manifest(self.home))
        code, output = run("reconcile", "--home", self.home, "--apply")
        self.assertEqual(code, 0, output)
        events = self.ledger()
        self.assertEqual(events[0]["event"], "rebuilt")
        self.assertEqual({e["number"] for e in events if e["event"] == "adopted"}, {"91.01", "92.01"})
        self.assertEqual(self.check()[1]["summary"]["error"], 0)
        self.new("Roof repair")
        self.assertTrue((self.home / "91_Projects" / "91.02_Roof-repair").is_dir())

    def test_floor_continues_above_a_number_the_owner_gives(self):
        code, output = run("reconcile", "--home", self.home, "--apply", "--floor", "91=7")
        self.assertEqual(code, 0, output)
        self.new("Roof repair")
        self.assertTrue((self.home / "91_Projects" / "91.08_Roof-repair").is_dir())

    def test_two_computers_gave_out_the_same_number(self):
        self.new("Roof repair")
        first = self.home / "91_Projects" / "91.02_Roof-repair"
        # A second computer, not yet synced, also gave out 91.02.
        second = self.home / "91_Projects" / "91.02_Fence"
        shutil.copytree(str(first), str(second))
        handoff = second / "HANDOFF.md"
        handoff.write_text(handoff.read_text(encoding="utf-8").replace(self.key_of(first), "abc123"), encoding="utf-8")
        ws.append_line(self.home / "_workspace" / "ledger.jsonl", {
            "event": "issued", "number": "91.02", "key": "abc123", "name": "Fence", "kind": "project", "group_now": 91})
        self.assertIn("NUM001", self.rules())
        code, output = run("new", "--home", self.home, "--title", "Gate")
        self.assertEqual(code, 1, output)
        code, output = run("reconcile", "--home", self.home)
        self.assertIn("The owner picks which keeps it", output)
        self.assertIn("abc123", output)
        keep = self.key_of(first)
        code, output = run("reconcile", "--home", self.home, "--apply", "--keep", "91.02=" + keep)
        self.assertEqual(code, 0, output)
        self.assertTrue(first.is_dir())
        moved = self.home / "91_Projects" / "91.03_Fence"
        self.assertTrue(moved.is_dir())
        self.assertEqual(self.key_of(moved), "abc123")
        self.assertEqual(self.check()[1]["summary"]["error"], 0, self.check()[1]["findings"])
        self.new("Gate")
        self.assertTrue((self.home / "91_Projects" / "91.04_Gate").is_dir())

    def test_a_second_copy_of_the_ledger_is_merged_and_kept(self):
        copy = self.home / "_workspace" / "ledger (1).jsonl"
        shutil.copy(str(self.home / "_workspace" / "ledger.jsonl"), str(copy))
        ws.append_line(copy, {"event": "issued", "number": "91.02", "key": "abc123", "name": "Fence",
                              "kind": "project", "group_now": 91})
        self.assertIn("LED003", self.rules())
        code, output = run("reconcile", "--home", self.home, "--apply")
        self.assertEqual(code, 0, output)
        self.assertFalse(copy.exists())
        self.assertTrue((self.home / "_workspace" / "merged-ledger (1).jsonl").is_file())
        self.assertIn("abc123", {event.get("key") for event in self.ledger()})
        self.new("Gate")
        self.assertTrue((self.home / "91_Projects" / "91.03_Gate").is_dir())

    def test_a_group_stops_at_99(self):
        run("reconcile", "--home", self.home, "--apply", "--floor", "91=99")
        code, output = run("new", "--home", self.home, "--title", "One too many")
        self.assertEqual(code, 1)
        self.assertIn("full", output)

    def test_a_fresh_lock_refuses_and_a_stale_one_is_taken_over(self):
        lock = self.home / "_workspace" / "lock-testbox"
        lock.write_text("123\n", encoding="utf-8")
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        self.assertEqual(code, 1)
        self.assertIn("Another session", output)
        old = time.time() - 3600
        os.utime(str(lock), (old, old))
        self.new("Roof repair")
        self.assertFalse(lock.exists())


class MoveTests(Base):
    def setUp(self):
        super().setUp()
        self.build()

    def test_rename_keeps_the_number_and_undo_puts_it_back(self):
        code, output = run("rename", "--home", self.home, "91.01", "Elm Street duplex")
        self.assertEqual(code, 0, output)
        renamed = self.home / "91_Projects" / "91.01_Elm-Street-duplex"
        self.assertTrue(renamed.is_dir())
        self.assertFalse(self.project().exists())
        self.assertEqual(self.check()[1]["summary"]["error"], 0)
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue(self.project().is_dir())
        self.assertEqual(ws.replay(self.ledger())[0][self.key_of(self.project())]["name"], "Duplex-renovation")

    def test_dry_runs_change_nothing(self):
        before = manifest(self.home)
        for argv in (["rename", "91.01", "Other"], ["move", "91.01", "--to", "area"], ["archive", "91.01"]):
            code, output = run(argv[0], "--home", self.home, *argv[1:], "--dry-run")
            self.assertEqual(code, 0, output)
            self.assertIn("nothing was changed", output)
        self.assertEqual(before, manifest(self.home))

    def test_a_project_that_becomes_ongoing_keeps_its_number(self):
        key = self.key_of(self.project())
        code, output = run("move", "--home", self.home, "91.01", "--to", "area")
        self.assertEqual(code, 0, output)
        moved = self.home / "92_Areas" / "91.01_Duplex-renovation"
        self.assertTrue(moved.is_dir())
        self.assertEqual(self.key_of(moved), key)
        code, data = self.check()
        self.assertEqual(data["summary"]["error"], 0, data["findings"])
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        self.assertTrue((self.home / "91_Projects" / "91.02_Roof-repair").is_dir(), output)

    def test_archive_and_restore_keep_number_and_key(self):
        key = self.key_of(self.project())
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        archived = self.home / "91_Projects" / "_Archive" / "91.01_Duplex-renovation"
        self.assertEqual(self.key_of(archived), key)
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "archived")
        code, output = run("restore", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.key_of(self.project()), key)
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "active")

    def test_restore_returns_to_the_group_it_was_in(self):
        run("move", "--home", self.home, "91.01", "--to", "area")
        run("archive", "--home", self.home, "91.01")
        self.assertTrue((self.home / "92_Areas" / "_Archive" / "91.01_Duplex-renovation").is_dir())
        code, output = run("restore", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "92_Areas" / "91.01_Duplex-renovation").is_dir())

    def test_undo_refuses_and_leaves_both_folders_when_the_old_place_is_taken(self):
        run("rename", "--home", self.home, "91.01", "Elm Street duplex")
        self.project().mkdir()  # something took the old place
        before = manifest(self.home)
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("left where they are", output)
        self.assertEqual(before, manifest(self.home))

    def test_undo_refuses_when_the_folder_is_not_the_one_that_moved(self):
        run("rename", "--home", self.home, "91.01", "Elm Street duplex")
        handoff = self.home / "91_Projects" / "91.01_Elm-Street-duplex" / "HANDOFF.md"
        text = handoff.read_text(encoding="utf-8")
        handoff.write_text(re.sub(r"\*\*Key:\*\* [0-9a-f]{6}", "**Key:** ffffff", text), encoding="utf-8")
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("key is different", output)

    def test_moves_refuse_existing_targets_and_unknown_numbers(self):
        (self.home / "91_Projects" / "91.01_Taken").mkdir()
        code, output = run("rename", "--home", self.home, "91.01", "Taken")
        self.assertEqual(code, 1)  # two folders now carry 91.01, so the script stops
        shutil.rmtree(str(self.home / "91_Projects" / "91.01_Taken"))
        (self.home / "91_Projects" / "_Archive" / "91.01_Duplex-renovation").mkdir(parents=True)
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 1)
        code, output = run("archive", "--home", self.home, "91.55")
        self.assertEqual(code, 1)
        self.assertIn("**Next:**", output)

    def test_an_interrupted_move_is_settled_from_what_is_on_disk(self):
        key = self.key_of(self.project())
        target = self.home / "91_Projects" / "_Archive" / "91.01_Duplex-renovation"
        target.parent.mkdir()
        ws.append_line(self.home / "_workspace" / "moves.jsonl", {
            "id": 1, "op": "archive", "number": "91.01", "key": key, "state": "pending",
            "from": "91_Projects/91.01_Duplex-renovation", "to": "91_Projects/_Archive/91.01_Duplex-renovation",
            "ledger": {"event": "archived", "key": key, "number": "91.01"}})
        os.rename(str(self.project()), str(target))  # the move happened, then the session died
        self.assertIn("MOV001", self.rules())
        before = manifest(self.home)
        run("check", "--home", self.home)
        self.assertEqual(before, manifest(self.home))  # a read-only run settles nothing
        code, output = run("rename", "--home", self.home, "92.01", "Books")
        self.assertEqual(code, 0, output)
        self.assertNotIn("MOV001", self.rules())
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "archived")

    def test_private_folders_cannot_be_moved(self):
        settings_path = self.home / "_workspace" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["private"] = ["91_Projects/_Archive"]
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 1)
        self.assertTrue(self.project().is_dir())


class MapAndCheckTests(Base):
    def setUp(self):
        super().setUp()
        self.build()

    def test_map_rewrites_only_its_own_tables(self):
        readme = self.home / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text + "\n## My notes\n\nKeep this line.\n", encoding="utf-8")
        run("new", "--home", self.home, "--title", "Roof repair")
        after = readme.read_text(encoding="utf-8")
        self.assertIn("Keep this line.", after)
        self.assertIn("91.02", after)
        outside = lambda body: re.sub(ws.MARK_RE, "", body)
        self.assertEqual(outside(text + "\n## My notes\n\nKeep this line.\n"), outside(after))

    def test_map_refuses_a_table_edited_by_hand(self):
        readme = self.home / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text.replace("| Active |", "| Active, edited by hand |"), encoding="utf-8")
        before = readme.read_text(encoding="utf-8")
        code, output = run("map", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("edited by hand", output)
        self.assertEqual(before, readme.read_text(encoding="utf-8"))
        self.assertIn("MAP002", self.rules())

    def test_check_finds_seeded_problems(self):
        project = self.project()
        area = self.home / "92_Areas" / "92.01_Bookkeeping"
        handoff = project / "HANDOFF.md"
        text = handoff.read_text(encoding="utf-8")
        text = text.replace("## Current state", "## TEMP").replace("## Next actions", "## Current state").replace("## TEMP", "## Next actions")
        text = re.sub(r"\*\*Status:\*\* \w+", "**Status:** Whenever", text)
        text = re.sub(r"\*\*Last updated:\*\* \S+", "**Last updated:** last week", text)
        handoff.write_text(text + "\n[gone](missing-file.md)\n" + ("x" * 21000), encoding="utf-8")
        (area / "HANDOFF.md").rename(area / "notes.txt")
        (self.home / "91_Projects" / "Loose folder").mkdir()
        (self.home / "90_Inbox" / "scan.pdf").write_bytes(b"x")
        (self.home / "AGENTS (conflicted copy).md").write_text("x", encoding="utf-8")
        rules = self.rules()
        for rule in ("HND001", "HND003", "HND004", "HND008", "LNK001", "WRK001", "NUM005", "INB001", "SYNC001"):
            self.assertIn(rule, rules)
        self.assertEqual(self.check()[0], 1)

    def test_check_flags_documents_and_stale_hand_offs(self):
        papers = self.drive / "Papers"
        papers.mkdir()
        (papers / "HANDOFF.md").write_text("stray", encoding="utf-8")
        settings_path = self.home / "_workspace" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["documents"] = ["../Papers", "../Not here"]
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        handoff = self.project() / "HANDOFF.md"
        text = re.sub(r"\*\*Last updated:\*\* \S+", "**Last updated:** 2020-01-01T09:00-08:00", handoff.read_text(encoding="utf-8"))
        handoff.write_text(text, encoding="utf-8")
        (self.project() / "draft_v1.md").write_text("new work", encoding="utf-8")
        rules = self.rules()
        for rule in ("DOC001", "DOC002", "HND005", "HND006"):
            self.assertIn(rule, rules)
        self.assertEqual((papers / "HANDOFF.md").read_text(encoding="utf-8"), "stray")

    def test_a_key_that_does_not_match_the_ledger_is_an_error(self):
        handoff = self.project() / "HANDOFF.md"
        text = handoff.read_text(encoding="utf-8")
        handoff.write_text(re.sub(r"\*\*Key:\*\* [0-9a-f]{6}", "**Key:** ffffff", text), encoding="utf-8")
        self.assertIn("NUM003", self.rules())

    def test_a_link_broken_by_a_move_gets_its_new_target(self):
        area_handoff = self.home / "92_Areas" / "92.01_Bookkeeping" / "HANDOFF.md"
        area_handoff.write_text(area_handoff.read_text(encoding="utf-8") +
                                "\nSee [the duplex](../../91_Projects/91.01_Duplex-renovation/HANDOFF.md).\n", encoding="utf-8")
        self.assertNotIn("LNK001", self.rules())
        run("rename", "--home", self.home, "91.01", "Elm Street duplex")
        findings = [f for f in self.check()[1]["findings"] if f["rule"] == "LNK001"]
        self.assertEqual(len(findings), 1)
        self.assertIn("91_Projects/91.01_Elm-Street-duplex/HANDOFF.md", findings[0]["fix"])
        self.assertIn("91.01_Duplex-renovation", area_handoff.read_text(encoding="utf-8"))  # never rewritten

    def test_a_suppress_entry_quiets_a_finding(self):
        (self.home / "90_Inbox" / "scan.pdf").write_bytes(b"x")
        self.assertIn("INB001", self.rules())
        settings_path = self.home / "_workspace" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["suppress"] = ["INB001:*"]
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        self.assertNotIn("INB001", self.rules())

    def test_brief_shows_each_next_action(self):
        code, output = run("check", "--brief", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("Ask Ana for the goal and the first task", output)
        self.assertIn("| 92.01 |", output)


class ReadOnlyAndPrivacyTests(Base):
    def setUp(self):
        super().setUp()
        self.build(private=["95_Data"])
        secret = self.home / "95_Data" / "95.01_Private-library"
        secret.mkdir()
        (secret / "canary-7f3a.md").write_text("CANARY-7F3A-PRIVATE", encoding="utf-8")

    def test_private_folders_are_never_listed_or_counted(self):
        for argv in (["scan"], ["check"], ["check", "--brief"], ["check", "--json"], ["reconcile"], ["map", "--dry-run"]):
            code, output = run(argv[0], "--home", self.home, *argv[1:])
            self.assertNotIn("canary", output.lower(), argv)
            self.assertNotIn("Private-library", output, argv)
        code, output = run("scan", "--home", self.home)
        self.assertIn("private, not opened", output)

    def test_scan_marks_a_folder_the_owner_calls_private(self):
        outside = self.drive / "Old stuff"
        (outside / "Personal").mkdir(parents=True)
        (outside / "Personal" / "canary-7f3a.md").write_text("CANARY", encoding="utf-8")
        (outside / "Taxes").mkdir()
        (outside / "Taxes" / "2025.pdf").write_bytes(b"12345")
        before = manifest(outside)
        code, output = run("scan", outside, "--private", "Personal")
        self.assertEqual(code, 0, output)
        self.assertIn("| `Personal/` | private, not opened | | | |", output)
        self.assertIn("`Taxes/` | folder | 1 |", output)
        self.assertNotIn("canary", output.lower())
        self.assertEqual(before, manifest(outside))

    def test_read_only_commands_write_nothing(self):
        before = manifest(self.tmp)
        commands = (["check"], ["check", "--brief"], ["check", "--json"], ["scan"], ["map", "--dry-run"],
                    ["reconcile"], ["undo", "--dry-run"], ["new", "--title", "X", "--dry-run"],
                    ["archive", "91.01", "--dry-run"], ["rename", "91.01", "Y", "--dry-run"])
        for argv in commands:
            run(argv[0], "--home", self.home, *argv[1:])
        run("init")
        run("init", "--path", self.drive)
        run("setup", "--answers", self.answers(), "--dry-run")
        after = manifest(self.tmp)
        after.pop("answers.json", None)
        before.pop("answers.json", None)
        self.assertEqual(before, after)


class ContractTests(Base):
    def test_every_command_ends_with_a_next_line(self):
        answers = self.answers()
        commands = [
            ["init"], ["init", "--path", self.drive], ["init", "--path", self.tmp / "nowhere"],
            ["setup", "--answers", answers, "--dry-run"], ["setup", "--answers", answers],
            ["setup", "--answers", self.tmp / "missing.json"],
            ["new", "--home", self.home, "--title", "Roof repair", "--dry-run"],
            ["new", "--home", self.home, "--title", "Roof repair"],
            ["new", "--home", self.home, "--title", "Roof repair"],
            ["scan", "--home", self.home], ["check", "--home", self.home], ["check", "--brief", "--home", self.home],
            ["map", "--home", self.home], ["map", "--home", self.home, "--dry-run"],
            ["rename", "--home", self.home, "91.01", "Elm duplex"], ["rename", "--home", self.home, "91.01", "Elm duplex"],
            ["move", "--home", self.home, "91.02", "--to", "area"], ["move", "--home", self.home, "91.02", "--to", "nowhere"],
            ["archive", "--home", self.home, "91.02"], ["archive", "--home", self.home, "91.02"],
            ["restore", "--home", self.home, "91.02"], ["restore", "--home", self.home, "91.02"],
            ["undo", "--home", self.home], ["undo", "--home", self.home, "--dry-run"],
            ["reconcile", "--home", self.home], ["reconcile", "--home", self.home, "--apply"],
            ["check", "--home", self.tmp / "not-a-workspace"], ["archive", "--home", self.home, "abc"],
            ["adopt", "--home", self.home, "nothing-here"], ["install"], ["install", "--tool", "claude", "--dry-run"],
            ["install", "--tool", "claude"], ["install", "--tool", "nope"],
            ["connect", "--home", self.home, "--tool", "claude", "--dry-run"], ["connect", "--home", self.home, "--tool", "claude"],
            ["connect", "--home", self.home, "--tool", "claude", "--remove"], ["connect", "--home", self.home, "--tool", "agents"],
            ["kit", "--answers", answers, "--out", self.tmp / "k.zip"], ["kit", "--answers", answers, "--out", self.tmp / "k.zip"],
        ]
        for argv in commands:
            code, output = run(*argv)
            self.assertIn(code, (0, 1), argv)
            last = [line for line in output.strip().splitlines() if line.strip()][-1]
            self.assertTrue(last.startswith("**Next:** "), "%s ended with: %s" % (argv, last))

    def test_json_output_parses_and_carries_next(self):
        self.build()
        code, output = run("check", "--json", "--home", self.home)
        data = json.loads(output)
        self.assertTrue(data["next"])
        self.assertEqual(set(data["summary"]), {"error", "warn", "info"})

    def test_the_home_is_found_from_a_work_folder(self):
        self.build()
        os.chdir(str(self.project()))
        code, output = run("check")
        self.assertEqual(code, 0, output)

    def test_the_script_parses_as_python_3_9(self):
        ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_every_rule_has_a_severity(self):
        for rule, (severity, text) in ws.RULES.items():
            self.assertIn(severity, ("error", "warn", "info"), rule)
            self.assertTrue(text, rule)

    def test_the_skill_holds_no_personal_data(self):
        real_home = self.saved["HOME"] or ""
        for path in SKILL_DIR.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if real_home:
                self.assertNotIn(real_home, text, str(path))
            for hit in re.findall(r"/Users/[A-Za-z0-9._-]+", text):
                self.assertEqual(hit, "/Users/ana", "%s names a real-looking user folder: %s" % (path, hit))
            self.assertNotIn("@gmail.com", text, str(path))

    def test_templates_have_no_em_dashes(self):
        for path in (SKILL_DIR / "assets" / "templates").glob("*.md"):
            self.assertNotIn("—", path.read_text(encoding="utf-8"), str(path))


class AdoptAndKitTests(Base):
    def setUp(self):
        super().setUp()
        self.build()
        self.old = self.home / "Kitchen remodel"
        (self.old / "quotes").mkdir(parents=True)
        (self.old / "quotes" / "bid.pdf").write_bytes(b"%PDF bid")
        (self.old / "notes.md").write_text("call the plumber", encoding="utf-8")

    def test_adopt_moves_a_folder_into_a_numbered_group_and_keeps_its_files(self):
        before = manifest(self.old)
        code, output = run("adopt", "--home", self.home, "Kitchen remodel", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertTrue(self.old.is_dir())
        code, output = run("adopt", "--home", self.home, "Kitchen remodel")
        self.assertEqual(code, 0, output)
        adopted = self.home / "91_Projects" / "91.02_Kitchen-remodel"
        self.assertFalse(self.old.exists())
        after = manifest(adopted)
        for path, digest in before.items():
            self.assertEqual(after[path], digest, path)
        for name in ("README.md", "HANDOFF.md", "DECISIONS.md", "AGENT_SYNC.md", "AGENTS.md", "CLAUDE.md"):
            self.assertTrue((adopted / name).is_file(), name)
        code, data = self.check()
        self.assertEqual(data["summary"]["error"], 0, data["findings"])
        self.assertEqual([f for f in data["findings"] if f["rule"] == "WRK005"], [])

    def test_adopt_keeps_a_readme_the_folder_already_had(self):
        (self.old / "README.md").write_text("# My kitchen notes\n", encoding="utf-8")
        code, output = run("adopt", "--home", self.home, "Kitchen remodel")
        self.assertEqual(code, 0, output)
        adopted = self.home / "91_Projects" / "91.02_Kitchen-remodel"
        self.assertEqual((adopted / "README.md").read_text(encoding="utf-8"), "# My kitchen notes\n")
        self.assertNotIn("README.md", output.split("New files in it:")[1].splitlines()[0])
        for name in ("DECISIONS.md", "AGENT_SYNC.md"):
            self.assertTrue((adopted / name).is_file(), name)

    def test_adopt_keeps_an_existing_hand_off_and_asks_for_the_key_line(self):
        (self.old / "HANDOFF.md").write_text("# Handoff: Kitchen\n\nMy own notes.\n", encoding="utf-8")
        code, output = run("adopt", "--home", self.home, "Kitchen remodel", "--kind", "area")
        self.assertEqual(code, 0, output)
        adopted = self.home / "92_Areas" / "92.02_Kitchen-remodel"
        self.assertEqual((adopted / "HANDOFF.md").read_text(encoding="utf-8"), "# Handoff: Kitchen\n\nMy own notes.\n")
        self.assertIn("**Key:**", output)

    def test_undoing_an_adoption_puts_the_folder_back_and_retires_the_number(self):
        run("adopt", "--home", self.home, "Kitchen remodel")
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.old / "quotes" / "bid.pdf").is_file())
        run("new", "--home", self.home, "--title", "Roof repair")
        self.assertTrue((self.home / "91_Projects" / "91.03_Roof-repair").is_dir())

    def test_adopt_refuses_folders_outside_the_home_and_the_homes_own_parts(self):
        outside = self.drive / "Elsewhere"
        outside.mkdir()
        for target in (outside, "91_Projects", "_workspace", "91_Projects/91.01_Duplex-renovation"):
            code, output = run("adopt", "--home", self.home, target)
            self.assertEqual(code, 1, target)
            self.assertIn("**Next:**", output)
        self.assertTrue(outside.is_dir())

    def test_kit_builds_a_starter_zip_and_nothing_else(self):
        import zipfile
        answers = self.tmp / "kit.json"
        answers.write_text(json.dumps({"owner": "Ana Lopez", "work": [
            {"title": "Duplex renovation", "documents": ["a folder called Duplex papers in my Drive"]}]}), encoding="utf-8")
        out = self.tmp / "starter.zip"
        before = manifest(self.tmp)
        code, output = run("kit", "--answers", answers, "--out", out)
        self.assertEqual(code, 0, output)
        after = manifest(self.tmp)
        self.assertEqual(set(after) - set(before), {"starter.zip"})
        with zipfile.ZipFile(str(out)) as archive:
            names = set(archive.namelist())
            handoff = archive.read("90_AI-Agents/91_Projects/91.01_Duplex-renovation/HANDOFF.md").decode("utf-8")
            settings = json.loads(archive.read("90_AI-Agents/_workspace/settings.json").decode("utf-8"))
        for name in ("90_AI-Agents/AGENTS.md", "90_AI-Agents/README.md", "90_AI-Agents/_workspace/ledger.jsonl",
                     "90_AI-Agents/90_Inbox/"):
            self.assertIn(name, names)
        self.assertNotIn("90_AI-Agents/99_Archive/", names)
        self.assertFalse([name for name in names if "lock-" in name])
        self.assertIn("Duplex papers in my Drive", handoff)
        self.assertEqual(settings["documents"], [])
        self.assertNotIn(str(self.tmp), handoff)
        code, output = run("kit", "--answers", answers, "--out", out)
        self.assertEqual(code, 1)


class ToolTests(Base):
    def setUp(self):
        super().setUp()
        self.build()
        self.claude = self.fake_home / ".claude" / "skills" / "agent-workspace-setup"
        self.agents = self.fake_home / ".agents" / "skills" / "agent-workspace-setup"

    def test_tool_folders_resolve_inside_the_test_home(self):
        for tool in ("claude", "codex", "agents"):
            info = ws.tool_info(tool)
            self.assertTrue(str(info["skills"]).startswith(str(self.fake_home)), info)
            if info["instructions"]:
                self.assertTrue(str(info["instructions"]).startswith(str(self.fake_home)), info)

    def test_install_status_and_dry_run_write_nothing(self):
        before = manifest(self.tmp)
        code, output = run("install")
        self.assertEqual(code, 0, output)
        self.assertIn("not installed", output)
        code, output = run("install", "--tool", "claude", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn(".claude/skills/agent-workspace-setup", output)
        self.assertEqual(before, manifest(self.tmp))

    def test_install_copies_and_verifies_and_then_has_nothing_to_do(self):
        code, output = run("install", "--tool", "claude", "--tool", "codex")
        self.assertEqual(code, 0, output)
        for folder in (self.claude, self.agents):
            self.assertEqual(ws.tree_digest(folder), ws.tree_digest(SKILL_DIR))
        self.assertFalse(list(self.claude.parent.glob(".new-*")))
        before = manifest(self.fake_home)
        code, output = run("install", "--tool", "claude")
        self.assertIn("already up to date", output)
        self.assertEqual(before, manifest(self.fake_home))

    def test_a_different_copy_is_left_alone_until_update_and_then_kept_as_a_backup(self):
        run("install", "--tool", "claude")
        (self.claude / "SKILL.md").write_text((self.claude / "SKILL.md").read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
        before = manifest(self.fake_home)
        code, output = run("install", "--tool", "claude")
        self.assertEqual(code, 1, output)
        self.assertIn("--update", output)
        self.assertEqual(before, manifest(self.fake_home))
        code, output = run("install", "--tool", "claude", "--update")
        self.assertEqual(code, 0, output)
        self.assertEqual(ws.tree_digest(self.claude), ws.tree_digest(SKILL_DIR))
        backups = list((self.fake_home / ".claude" / "skill-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertIn("local edit", (backups[0] / "SKILL.md").read_text(encoding="utf-8"))

    def test_a_linked_copy_and_a_foreign_folder_are_left_alone(self):
        real = self.tmp / "kept-elsewhere"
        real.mkdir()
        (real / "SKILL.md").write_text("---\nname: agent-workspace-setup\n---\nold\n", encoding="utf-8")
        self.claude.parent.mkdir(parents=True)
        try:
            os.symlink(str(real), str(self.claude))
        except (OSError, NotImplementedError):
            self.skipTest("links aren't available here")
        code, output = run("install", "--tool", "claude", "--update")
        self.assertEqual(code, 1, output)
        self.assertTrue(os.path.islink(str(self.claude)))
        self.assertEqual((real / "SKILL.md").read_text(encoding="utf-8"), "---\nname: agent-workspace-setup\n---\nold\n")
        self.agents.mkdir(parents=True)
        (self.agents / "SKILL.md").write_text("---\nname: something-else\n---\n", encoding="utf-8")
        code, output = run("install", "--tool", "codex", "--update")
        self.assertEqual(code, 1, output)
        self.assertIn("isn't this skill", output)

    def test_install_rejects_an_unknown_tool_and_supports_dest(self):
        code, output = run("install", "--tool", "notepad")
        self.assertEqual(code, 1)
        other = self.tmp / "other-skills"
        other.mkdir()
        code, output = run("install", "--dest", other)
        self.assertEqual(code, 0, output)
        self.assertTrue((other / "agent-workspace-setup" / "scripts" / "workspace.py").is_file())

    def test_connect_adds_one_section_once_and_keeps_everything_else(self):
        target = self.fake_home / ".claude" / "CLAUDE.md"
        target.parent.mkdir(parents=True)
        target.write_text("# My rules\n\n- Be brief.\n", encoding="utf-8")
        before = manifest(self.fake_home)
        code, output = run("connect", "--home", self.home, "--tool", "claude", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn(".claude/CLAUDE.md", output)
        self.assertIn("Backup first", output)
        self.assertEqual(before, manifest(self.fake_home))
        code, output = run("connect", "--home", self.home, "--tool", "claude")
        self.assertEqual(code, 0, output)
        text = target.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# My rules\n\n- Be brief.\n"))
        self.assertEqual(text.count(ws.SECTION_START), 1)
        self.assertIn("90_AI-Agents", text)
        backups = list(target.parent.glob("CLAUDE.md.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "# My rules\n\n- Be brief.\n")
        code, output = run("connect", "--home", self.home, "--tool", "claude")
        self.assertIn("already connected", output)
        self.assertEqual(target.read_text(encoding="utf-8"), text)

    def test_connect_remove_takes_out_only_its_own_section(self):
        target = self.fake_home / ".codex" / "AGENTS.md"
        code, output = run("connect", "--home", self.home, "--tool", "codex")
        self.assertEqual(code, 0, output)
        self.assertTrue(target.read_text(encoding="utf-8").startswith("# Personal instructions"))
        target.write_text(target.read_text(encoding="utf-8") + "\n## Later edit\n\n- Keep me.\n", encoding="utf-8")
        time.sleep(1.1)
        code, output = run("connect", "--home", self.home, "--tool", "codex", "--remove")
        self.assertEqual(code, 0, output)
        text = target.read_text(encoding="utf-8")
        self.assertNotIn(ws.SECTION_START, text)
        self.assertIn("- Keep me.", text)
        self.assertIn("# Personal instructions", text)

    def test_connect_for_a_tool_without_an_instructions_file_writes_nothing(self):
        before = manifest(self.tmp)
        code, output = run("connect", "--home", self.home, "--tool", "agents")
        self.assertEqual(code, 0, output)
        self.assertIn("paste", output)
        self.assertEqual(before, manifest(self.tmp))


class ArchiveTests(Base):
    def setUp(self):
        super().setUp()
        self.build()
        self.shelf = self.home / "91_Projects" / "_Archive"
        self.archived = self.shelf / "91.01_Duplex-renovation"

    def make_old_archive(self, number="91.01"):
        """Put the project where the first two versions archived it: one archive folder for the whole workspace."""
        key = self.key_of(self.project())
        old = self.home / "99_Archive"
        old.mkdir(exist_ok=True)
        os.rename(str(self.project()), str(old / "91.01_Duplex-renovation"))
        ws.append_line(self.home / "_workspace" / "ledger.jsonl",
                       {"event": "archived", "key": key, "number": number, "from_group": 91})
        run("map", "--home", self.home)  # the older versions refreshed the map after every move
        return old / "91.01_Duplex-renovation", key

    def test_archive_goes_into_the_group_and_the_archive_is_made_on_first_use(self):
        before = manifest(self.home)
        code, output = run("archive", "--home", self.home, "91.01", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.home))
        self.assertIn("`91_Projects/91.01_Duplex-renovation`  \u2192  `91_Projects/_Archive/91.01_Duplex-renovation`", output)
        self.assertIn("`91_Projects/_Archive/` is new", output)
        self.assertIn("would be made", output)
        self.assertIn("first set Status to Closed", output)
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertTrue(self.archived.is_dir())
        self.assertFalse(self.project().exists())
        self.assertFalse((self.home / "99_Archive").exists())
        code, data = self.check()
        self.assertEqual(data["summary"]["error"], 0, data["findings"])
        self.assertEqual(data["summary"]["warn"], 0, data["findings"])
        text = (self.home / "README.md").read_text(encoding="utf-8")
        self.assertIn("(91_Projects/_Archive/91.01_Duplex-renovation/HANDOFF.md)", text)
        self.assertIn("(archived)", text)
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        code, output = run("archive", "--home", self.home, "91.02")
        self.assertEqual(code, 0, output)
        self.assertNotIn("is new", output)
        self.assertTrue((self.shelf / "91.02_Roof-repair").is_dir())

    def test_archiving_twice_is_refused(self):
        run("archive", "--home", self.home, "91.01")
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 1)
        self.assertIn("already in its group's archive", output)

    def test_undo_of_an_archive_puts_the_folder_back_and_deletes_nothing(self):
        run("archive", "--home", self.home, "91.01")
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue(self.project().is_dir())
        self.assertTrue(self.shelf.is_dir())  # the empty archive folder stays: the skill deletes nothing
        self.assertEqual(self.check()[1]["summary"]["error"], 0)

    def test_an_archived_folder_keeps_its_number_out_of_reach(self):
        run("archive", "--home", self.home, "91.01")
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "91_Projects" / "91.02_Roof-repair").is_dir())
        (self.shelf / "91.02_Something-else").mkdir()
        self.assertIn("NUM001", self.rules())

    def test_archived_work_is_frozen_for_the_link_check(self):
        run("archive", "--home", self.home, "91.01")
        readme = self.archived / "README.md"
        self.assertIn("(../../README.md)", readme.read_text(encoding="utf-8"))
        self.assertFalse((self.archived / ".." / ".." / "README.md").exists())  # one level deeper now
        self.assertNotIn("LNK001", self.rules())
        run("restore", "--home", self.home, "91.01")
        self.assertNotIn("LNK001", self.rules())

    def test_a_private_archive_is_never_listed(self):
        run("archive", "--home", self.home, "91.01")
        settings_path = self.home / "_workspace" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["private"] = ["91_Projects/_Archive"]
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        for argv in (["check"], ["check", "--brief"], ["map", "--dry-run"]):
            code, output = run(argv[0], "--home", self.home, *argv[1:])
            self.assertNotIn("_Archive/91.01", output, argv)  # the folder is not scanned, listed or opened
        self.assertEqual(len(self.check()[1]["work"]), 1)

    def test_the_old_archive_still_works_and_the_check_points_at_it(self):
        old, key = self.make_old_archive()
        code, data = self.check()
        self.assertEqual(data["summary"]["error"], 0, data["findings"])
        found = [f for f in data["findings"] if f["rule"] == "ARC001"]
        self.assertEqual(len(found), 1)
        self.assertIn("91.01", found[0]["message"])
        self.assertEqual(found[0]["path"], "99_Archive")
        code, output = run("restore", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertTrue(self.project().is_dir())
        self.assertNotIn("ARC001", self.rules())

    def test_archive_refiles_a_folder_from_the_old_archive_into_its_group(self):
        old, key = self.make_old_archive()
        before = manifest(self.home)
        code, output = run("archive", "--home", self.home, "91.01", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.home))
        self.assertIn("`99_Archive/91.01_Duplex-renovation`  \u2192  `91_Projects/_Archive/91.01_Duplex-renovation`", output)
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertTrue(self.archived.is_dir())
        self.assertFalse(old.exists())
        self.assertTrue((self.home / "99_Archive").is_dir())  # left for the owner to remove
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "archived")
        self.assertNotIn("ARC001", self.rules())
        self.assertEqual(self.check()[1]["summary"]["error"], 0)
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue(old.is_dir())
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "archived")

    def test_refiling_follows_the_group_the_folder_last_lived_in(self):
        run("move", "--home", self.home, "91.01", "--to", "area")
        key = self.key_of(self.home / "92_Areas" / "91.01_Duplex-renovation")
        old = self.home / "99_Archive"
        old.mkdir()
        os.rename(str(self.home / "92_Areas" / "91.01_Duplex-renovation"), str(old / "91.01_Duplex-renovation"))
        ws.append_line(self.home / "_workspace" / "ledger.jsonl",
                       {"event": "archived", "key": key, "number": "91.01", "from_group": 92})
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "92_Areas" / "_Archive" / "91.01_Duplex-renovation").is_dir())

    def test_a_workspace_with_the_old_archive_keeps_it_when_work_is_added(self):
        self.make_old_archive()
        code, output = run("new", "--home", self.home, "--title", "Roof repair")
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "99_Archive" / "91.01_Duplex-renovation").is_dir())
        self.assertTrue((self.home / "91_Projects" / "91.02_Roof-repair").is_dir())

    def test_upgrade_from_the_last_version_adds_the_archive_rule(self):
        settings_path = self.home / "_workspace" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["skill_version"] = "0.2.0"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        rules_path = self.home / "AGENTS.md"
        lines = rules_path.read_text(encoding="utf-8").splitlines(keepends=True)
        swapped = ["- Closed work moves to `99_Archive/` and keeps its number, only when Ana says so.\n"
                   if "**Closed work goes into its own group's archive.**" in line else line for line in lines]
        self.assertNotEqual(lines, swapped)
        rules_path.write_text("".join(swapped), encoding="utf-8")
        old_rules = rules_path.read_text(encoding="utf-8")
        before = manifest(self.home)
        code, output = run("upgrade", "--home", self.home, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.home))
        self.assertIn("inside its own group", output)
        self.assertNotIn("rules-0.2.0", output)
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        new_rules = rules_path.read_text(encoding="utf-8")
        self.assertTrue(new_rules.startswith(old_rules))
        self.assertEqual(new_rules.count("<!-- agent-workspace-setup:rules-0.3.0 -->"), 1)
        self.assertIn("- **Closed work goes into its own group's archive.**", new_rules[len(old_rules):])
        self.assertIn("This replaces any older line", new_rules[len(old_rules):])
        self.assertNotIn("VER001", self.rules())


class UpgradeAndBriefTests(Base):
    def setUp(self):
        super().setUp()
        self.build(private=["Private"])
        self.settings_path = self.home / "_workspace" / "settings.json"
        self.rules_path = self.home / "AGENTS.md"

    def settings(self):
        return json.loads(self.settings_path.read_text(encoding="utf-8"))

    def make_older(self):
        """Turn this workspace into one that the first release set up: no version, and no newer rule."""
        settings = self.settings()
        settings.pop("skill_version")
        settings["my_own_note"] = "keep me"
        self.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        lines = self.rules_path.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [line for line in lines if "**Say where a fact came from.**" not in line]
        self.assertEqual(len(lines) - len(kept), 1)
        self.rules_path.write_text("".join(kept), encoding="utf-8")

    def set_next_actions(self, body):
        path = self.project() / "HANDOFF.md"
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"(## Next actions\n\n).*?(\n\n## Don't forget)", lambda m: m.group(1) + body + m.group(2), text, flags=re.S)
        path.write_text(text, encoding="utf-8")

    def test_a_new_workspace_records_the_version_and_has_the_newest_rules(self):
        self.assertEqual(self.settings()["skill_version"], ws.__version__)
        rules = self.rules_path.read_text(encoding="utf-8")
        self.assertIn("**Say where a fact came from.**", rules)
        self.assertNotIn("agent-workspace-setup:rules-", rules)
        self.assertNotIn("VER001", self.rules())
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("already at version", output)

    def test_the_check_and_the_brief_name_an_older_workspace(self):
        self.make_older()
        self.assertIn("VER001", self.rules())
        code, output = run("check", "--brief", "--home", self.home)
        self.assertIn("set up with version 0.1.0", output)

    def test_upgrade_dry_run_writes_nothing_and_shows_the_exact_text(self):
        self.make_older()
        before = manifest(self.tmp)
        code, output = run("upgrade", "--home", self.home, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.tmp))
        self.assertIn("## What's new", output)
        self.assertIn("```markdown", output)
        self.assertIn("- **Say where a fact came from.**", output)
        self.assertIn("(Ana in chat,", output)
        self.assertNotIn("{{", output)

    def test_upgrade_adds_one_section_and_changes_nothing_else(self):
        self.make_older()
        old_rules = self.rules_path.read_text(encoding="utf-8")
        before = manifest(self.home)
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        new_rules = self.rules_path.read_text(encoding="utf-8")
        self.assertTrue(new_rules.startswith(old_rules))
        self.assertEqual(new_rules.count("<!-- agent-workspace-setup:rules-0.2.0 -->"), 1)
        self.assertEqual(new_rules.count("**Say where a fact came from.**"), 1)
        self.assertEqual(self.settings()["skill_version"], ws.__version__)
        self.assertEqual(self.settings()["my_own_note"], "keep me")
        after = manifest(self.home)
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        self.assertEqual(changed, ["AGENTS.md", os.path.join("_workspace", "settings.json")])
        self.assertNotIn("VER001", self.rules())
        code, output = run("upgrade", "--home", self.home)
        self.assertIn("already at version", output)
        self.assertEqual(self.rules_path.read_text(encoding="utf-8"), new_rules)

    def test_upgrade_adds_no_rule_the_home_already_has(self):
        settings = self.settings()
        settings.pop("skill_version")
        self.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        old_rules = self.rules_path.read_text(encoding="utf-8")
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("It needs no new rule", output)
        self.assertEqual(self.rules_path.read_text(encoding="utf-8"), old_rules)
        self.assertEqual(self.settings()["skill_version"], ws.__version__)

    def test_upgrade_refuses_when_the_rules_file_is_missing(self):
        self.make_older()
        self.rules_path.unlink()
        before = manifest(self.home)
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 1, output)
        self.assertIn("**Next:**", output)
        self.assertEqual(before, manifest(self.home))

    def test_a_workspace_newer_than_this_copy_of_the_skill_is_left_alone(self):
        settings = self.settings()
        settings["skill_version"] = "9.0.0"
        self.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        self.assertIn("VER002", self.rules())
        before = manifest(self.home)
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("older", output)
        self.assertEqual(before, manifest(self.home))

    def test_every_upgrade_rule_is_in_the_rules_template(self):
        template = (SKILL_DIR / "assets" / "templates" / "home-AGENTS.md").read_text(encoding="utf-8")
        versions = [step["version"] for step in ws.UPGRADES]
        self.assertEqual(versions, sorted(versions, key=ws.version_tuple))
        self.assertLessEqual(ws.version_tuple(versions[-1]), ws.version_tuple(ws.__version__))
        for step in ws.UPGRADES:
            self.assertTrue(step["news"], step["version"])
            for title in step["rules"]:
                self.assertRegex(template, r"(?m)^(?:\d+\.|-) \*\*%s\*\*" % re.escape(title))

    def test_brief_ends_with_what_it_did_not_cover(self):
        code, output = run("new", "--home", self.home, "--title", "Old fence", "--status", "Paused")
        self.assertEqual(code, 0, output)
        settings = self.settings()
        settings["documents"] = ["../Not here"]
        self.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        code, output = run("check", "--brief", "--home", self.home)
        self.assertEqual(code, 0, output)
        tail = output.split("## Not covered by this brief")[1]
        self.assertIn("Private, not opened: `Private`", tail)
        self.assertIn("aren't on this computer", tail)
        self.assertIn("Not here", tail)
        self.assertIn("1 paused or closed, 0 archived", tail)
        self.assertIn("mail, chat and calendars", tail)
        self.assertIn("End with the Not covered list", output)

    def test_brief_always_says_what_lies_outside_the_workspace(self):
        code, output = run("check", "--brief", "--home", self.home)
        self.assertIn("## Not covered by this brief", output)
        self.assertIn("Everything outside the workspace", output)

    def test_work_with_no_next_action_is_named(self):
        self.assertNotIn("HND009", self.rules())
        self.set_next_actions("1. None yet.")
        self.assertIn("HND009", self.rules())
        code, output = run("check", "--brief", "--home", self.home)
        self.assertIn("Next actions names nothing to do", output)
        self.set_next_actions("- Call the roofer about the leak.")
        self.assertNotIn("HND009", self.rules())
        code, output = run("check", "--brief", "--home", self.home)
        self.assertIn("Call the roofer about the leak.", output)
        self.set_next_actions("Nothing is planned.")
        self.assertIn("HND009", self.rules())

    def test_paused_work_needs_no_next_action(self):
        path = self.project() / "HANDOFF.md"
        path.write_text(path.read_text(encoding="utf-8").replace("**Status:** Active", "**Status:** Paused"), encoding="utf-8")
        self.set_next_actions("1. None yet.")
        self.assertNotIn("HND009", self.rules())

    def test_lines_marked_unconfirmed_are_counted(self):
        path = self.project() / "HANDOFF.md"
        text = path.read_text(encoding="utf-8").replace(
            "## Next actions",
            "- The permit expires in May. Unconfirmed (ask the owner).\n- Budget is 40,000 (unconfirmed).\n"
            "- Mark what you can't check `Unconfirmed`.\n\n## Next actions")
        path.write_text(text, encoding="utf-8")
        findings = [f for f in self.check()[1]["findings"] if f["rule"] == "HND010"]
        self.assertEqual(len(findings), 1)
        self.assertIn("2 lines marked Unconfirmed", findings[0]["message"])
        code, output = run("check", "--brief", "--home", self.home)
        self.assertIn("Not confirmed yet in", output.split("## Not covered by this brief")[1])

    def test_friction_notes_are_counted(self):
        self.assertNotIn("FRC001", self.rules())
        notes = self.home / "_workspace" / "friction.md"
        notes.write_text("# Friction notes\n\n", encoding="utf-8")
        self.assertNotIn("FRC001", self.rules())
        notes.write_text("# Friction notes\n\n- 2026-01-31 · a tool · new --kind client · the kind was refused\n"
                         "- 2026-02-01 · a tool · rename · no number given\n", encoding="utf-8")
        findings = [f for f in self.check()[1]["findings"] if f["rule"] == "FRC001"]
        self.assertEqual(len(findings), 1)
        self.assertIn("2 friction notes", findings[0]["message"])
        code, output = run("check", "--brief", "--home", self.home)
        self.assertIn("2 friction notes", output)

    def test_a_fault_in_the_script_ends_with_a_next_line(self):
        def boom(args):
            raise KeyError("oops")
        real = ws.cmd_map
        ws.cmd_map = boom
        try:
            code, output = run("map", "--home", self.home)
        finally:
            ws.cmd_map = real
        self.assertEqual(code, 2, output)
        self.assertIn("fault", output)
        self.assertIn("KeyError", output)
        self.assertIn("version %s" % ws.__version__, output)
        self.assertIn("**Next:**", output)
        self.assertNotIn("Traceback", output)


class TidyAndRoutineTests(Base):
    """The order for what wins, the checks that read dates, and the optional routines."""

    def setUp(self):
        super().setUp()
        self.saved_clock = os.environ.get("AGENT_WORKSPACE_NOW")
        self.clock("2026-03-01")
        self.build(private=["Private"])
        self.handoff = self.project() / "HANDOFF.md"
        self.settings_path = self.home / "_workspace" / "settings.json"
        self.status = self.home / "STATUS.md"

    def tearDown(self):
        if self.saved_clock is None:
            os.environ.pop("AGENT_WORKSPACE_NOW", None)
        else:
            os.environ["AGENT_WORKSPACE_NOW"] = self.saved_clock
        super().tearDown()

    def clock(self, day):
        os.environ["AGENT_WORKSPACE_NOW"] = day

    def section(self, name, body):
        """Replace one section of the project's hand-off."""
        text = self.handoff.read_text(encoding="utf-8")
        pattern = r"(## %s\n\n).*?(?=\n## |\Z)" % re.escape(name)
        self.assertTrue(re.search(pattern, text, re.S), name)
        self.handoff.write_text(re.sub(pattern, lambda m: m.group(1) + body + "\n", text, count=1, flags=re.S), encoding="utf-8")

    def found(self, rule):
        return [finding for finding in self.check()[1]["findings"] if finding["rule"] == rule]

    def routine(self, *argv):
        return run("routine", *argv, "--home", self.home)

    def runs(self):
        log = self.home / "_workspace" / "runs.jsonl"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []

    # --- the clock, the rules ---

    def test_the_test_clock_sets_today(self):
        self.assertEqual(ws.today(), "2026-03-01")
        self.assertIn("2026-03-01", self.handoff.read_text(encoding="utf-8"))

    def test_a_new_workspace_has_the_order_for_what_wins(self):
        rules = (self.home / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("**When files disagree, this order decides, and you say so.**", rules)
        for phrase in ("`Conflict:`", "`D-001`", "due 2026-01-31", "**Read the status first, if there is one.**"):
            self.assertIn(phrase, rules)
        self.assertIn("D-001", (self.project() / "DECISIONS.md").read_text(encoding="utf-8"))

    def test_upgrade_from_the_last_version_adds_the_four_new_rules(self):
        settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        settings["skill_version"] = "0.3.0"
        self.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        rules_path = self.home / "AGENTS.md"
        titles = [title for step in ws.UPGRADES if step["version"] == "0.4.0" for title in step["rules"]]
        self.assertEqual(len(titles), 4)
        kept = [line for line in rules_path.read_text(encoding="utf-8").splitlines(keepends=True)
                if not any("**%s**" % title in line for title in titles)]
        rules_path.write_text("".join(kept), encoding="utf-8")
        old = rules_path.read_text(encoding="utf-8")
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        added = rules_path.read_text(encoding="utf-8")[len(old):]
        self.assertEqual(added.count("<!-- agent-workspace-setup:rules-0.4.0 -->"), 1)
        for title in titles:
            self.assertIn("- **%s**" % title, added)
        self.assertIn("Optional routines", output)
        self.assertNotIn("VER001", self.rules())

    # --- checks that read dates and numbers ---

    def test_an_overdue_next_action_is_found_and_one_due_later_is_not(self):
        self.section("Next actions", "1. Book the window installer, due 2026-03-04.\n2. Call the roofer by phone.")
        self.assertEqual(self.found("HND013"), [])
        row = [row for row in self.check()[1]["work"] if row["number"] == "91.01"][0]
        self.assertEqual([(due["date"], due["days"]) for due in row["due"]], [("2026-03-04", 3)])
        self.clock("2026-03-10")
        hits = self.found("HND013")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warn")
        self.assertIn("was due 2026-03-04", hits[0]["message"])

    def test_open_conflicts_are_counted(self):
        self.section("Don't forget", "- Conflict: the permit date. The city's letter says May, the contractor says June.\n"
                                    "- **Conflict:** the budget. 40,000 in the quote, 45,000 in the email.\n"
                                    "- No conflict here, only a reminder.")
        hits = self.found("HND011")
        self.assertEqual(len(hits), 1)
        self.assertIn("2 open conflicts", hits[0]["message"])

    def test_a_hand_off_that_fell_behind_its_log_is_found(self):
        self.clock("2026-03-25")
        self.section("Session log", "- 2026-03-20 · a tool: ordered the windows. Delivery is expected on 2026-04-15.\n"
                                    "- 2026-03-01 · a tool: created this folder.")
        hits = self.found("HND012")
        self.assertEqual(len(hits), 1)
        self.assertIn("runs to 2026-03-20", hits[0]["message"])
        self.assertIn("stops at 2026-03-01", hits[0]["message"])
        self.section("Current state", "- 2026-03-20: windows ordered.")
        self.assertEqual(self.found("HND012"), [])

    def test_a_long_wait_is_found(self):
        self.section("Don't forget", "- Waiting on the bank since 2026-01-10 for the loan letter.")
        hits = self.found("HND014")
        self.assertEqual(len(hits), 1)
        self.assertIn("Waiting on the bank for 50 days", hits[0]["message"])

    def test_citations_of_replaced_and_missing_decisions_are_found(self):
        (self.project() / "DECISIONS.md").write_text(
            "# Decisions: Duplex renovation\n\n## Entries\n\n"
            "- **D-002 · 2026-02-20 · Switch contractor.** Use the second firm. *Why:* price. *Source:* Ana, chat.\n"
            "- **D-001 · 2026-01-10 · Contractor.** Use the first firm. *Why:* it was free.\n"
            "  (Superseded 2026-02-20)\n", encoding="utf-8")
        self.section("Current state", "- 2026-03-01: the first firm starts next week (D-001).\n- The loan follows (D-007).")
        self.assertEqual([finding["message"] for finding in self.found("DEC001")], ["It cites D-001, which is marked Superseded."])
        self.assertIn("D-007", self.found("DEC002")[0]["message"])
        self.section("Current state", "- 2026-03-01: the second firm starts next week (D-002).")
        self.assertEqual(self.found("DEC001") + self.found("DEC002"), [])
        with open(self.project() / "DECISIONS.md", "a", encoding="utf-8") as handle:
            handle.write("- **D-002 · 2026-03-01 · Windows.** Wood frames.\n")
        self.assertIn("used for two entries", self.found("DEC002")[0]["message"])

    def test_a_purpose_that_differs_between_readme_and_hand_off_is_found(self):
        self.assertEqual(self.found("FCT001"), [])
        text = self.handoff.read_text(encoding="utf-8")
        self.handoff.write_text(re.sub(r"\*\*Purpose:\*\* [^·]*·", "**Purpose:** Sell the duplex. ·", text, count=1), encoding="utf-8")
        self.assertEqual(len(self.found("FCT001")), 1)

    def test_an_old_open_note_is_found_until_it_is_answered(self):
        notes = self.project() / "AGENT_SYNC.md"
        base = notes.read_text(encoding="utf-8")
        notes.write_text(base + "\n### 2026-01-05T09:00-08:00 · Codex → Claude · open\n\nWhich quote is current?\n", encoding="utf-8")
        self.assertEqual(len(self.found("NOTE001")), 1)
        with open(notes, "a", encoding="utf-8") as handle:
            handle.write("\n### 2026-03-01T10:00-08:00 · Claude → Codex · FYI\n\nRe: 2026-01-05T09:00-08:00 The second one. done\n")
        self.assertEqual(self.found("NOTE001"), [])

    def test_closed_work_that_was_never_archived_and_old_inbox_items_are_found(self):
        text = self.handoff.read_text(encoding="utf-8")
        self.handoff.write_text(text.replace("**Status:** Active", "**Status:** Closed"), encoding="utf-8")
        (self.home / "90_Inbox" / "scan.pdf").write_bytes(b"x")
        self.assertEqual(self.found("STS001"), [])
        self.clock("2026-04-15")
        self.assertIn("Closed 45 days ago", self.found("STS001")[0]["message"])
        self.clock("2030-01-01")
        self.assertEqual(len(self.found("INB002")), 1)

    # --- routines are optional ---

    def test_nothing_about_routines_exists_until_the_owner_asks(self):
        self.assertFalse(self.status.exists())
        self.assertFalse((self.home / "_workspace" / "runs.jsonl").exists())
        self.assertNotIn("routines", json.loads(self.settings_path.read_text(encoding="utf-8")))
        self.assertEqual([rule for rule in self.rules() if rule.startswith("ROU")], [])

    def test_the_offer_is_made_once_and_a_no_is_remembered(self):
        code, output = run("check", "--home", self.home)
        self.assertIn("Routines are optional", output)
        self.assertIn("offer the daily check once", output)
        code, output = self.routine("offer", "--answer", "later")
        self.assertEqual(code, 0, output)
        self.assertNotIn("Routines are optional", run("check", "--home", self.home)[1])
        self.clock("2026-04-05")
        self.assertIn("Routines are optional", run("check", "--home", self.home)[1])
        self.routine("offer", "--answer", "no")
        self.clock("2027-04-05")
        self.assertNotIn("Routines are optional", run("check", "--home", self.home)[1])
        self.assertNotIn("Routines are optional", run("check", "--brief", "--home", self.home)[1])

    def test_plan_and_status_and_dry_runs_write_nothing(self):
        before = manifest(self.tmp)
        code, output = self.routine("plan", "--runner", "claude-desktop")
        self.assertEqual(code, 0, output)
        for phrase in ("Routines are optional", "until the owner says yes", "routine run --kind daily --runner claude-desktop",
                       "Never move, delete or edit", "## Weekly review"):
            self.assertIn(phrase, output)
        for argv in (["status"], ["status", "--short"], ["run", "--kind", "daily", "--dry-run"],
                     ["record", "--kind", "daily", "--runner", "os", "--dry-run"], ["offer", "--answer", "no", "--dry-run"]):
            code, output = self.routine(*argv)
            self.assertIn(code, (0, 10), (argv, output))
        self.assertEqual(before, manifest(self.tmp))

    def test_a_run_writes_only_the_status_file_and_its_own_records(self):
        self.section("Next actions", "1. Book the window installer, due 2026-02-20.")
        before = manifest(self.home)
        code, output = self.routine("run", "--kind", "daily")
        self.assertEqual(code, 10, output)
        self.assertIn("Tell the owner what is under Needs you", output)
        after = manifest(self.home)
        changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
        self.assertEqual(changed, ["STATUS.md", os.path.join("_workspace", "findings.json"), os.path.join("_workspace", "runs.jsonl")])
        text = self.status.read_text(encoding="utf-8")
        self.assertIn(ws.STATUS_MARK, text)
        self.assertIn("## Needs you (1)", text)
        self.assertIn("91.01 Duplex renovation", text)
        self.assertNotIn("Private", text)
        self.assertEqual(self.runs()[-1]["result"], "attention")

    def test_a_run_is_quiet_when_nothing_is_new_and_speaks_again_at_seven_days(self):
        self.section("Next actions", "1. Book the window installer, due 2026-02-20.")
        self.routine("record", "--kind", "daily", "--runner", "os")
        self.assertEqual(self.routine("run", "--kind", "daily", "--runner", "os")[0], 10)
        self.clock("2026-03-02")
        code, output = self.routine("run", "--kind", "daily", "--runner", "os")
        self.assertEqual(code, 0, output)
        self.assertIn("Nothing new needs the owner", output)
        self.assertIn("Open 1 day.", self.status.read_text(encoding="utf-8"))
        self.clock("2026-03-08")
        self.assertEqual(self.routine("run", "--kind", "daily", "--runner", "os")[0], 10)

    def test_a_second_run_in_the_same_day_and_a_standby_copy_both_exit(self):
        self.routine("record", "--kind", "daily", "--runner", "claude-desktop", "--standby", "codex")
        self.assertEqual(self.routine("run", "--kind", "daily", "--runner", "claude-desktop")[0], 0)
        first = self.status.read_bytes()
        code, output = self.routine("run", "--kind", "daily", "--runner", "claude-desktop")
        self.assertEqual(code, 0)
        self.assertIn("already ran", output)
        self.clock("2026-03-02")
        code, output = self.routine("run", "--kind", "daily", "--runner", "codex")
        self.assertEqual(code, 0)
        self.assertIn("standby", output)
        self.assertEqual(self.status.read_bytes(), first)
        self.assertEqual([entry.get("note") for entry in self.runs()], [None, "already ran", "standby"])
        code, output = self.routine("switch", "--kind", "daily", "--to", "codex")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.routine("run", "--kind", "daily", "--runner", "codex")[0], 0)
        entry = json.loads(self.settings_path.read_text(encoding="utf-8"))["routines"][0]
        self.assertEqual((entry["runner"], entry["standby"]), ("codex", ["claude-desktop"]))

    def test_the_same_inputs_give_the_same_status_file(self):
        self.section("Next actions", "1. Book the window installer, due 2026-03-02.")
        self.routine("run", "--kind", "weekly", "--runner", "os")
        first = self.status.read_text(encoding="utf-8")
        self.assertIn("## Worth a tidy-up", first)
        self.assertIn("## This month", first)
        self.assertIn("**Due in 1 day:**", first)
        self.routine("run", "--kind", "weekly", "--runner", "os", "--force")
        second = self.status.read_text(encoding="utf-8")
        self.assertEqual(first.replace("## This month (0)\n\n- Nothing to archive, and nothing unsettled for a month.\n\n", ""),
                         second)

    def test_an_owners_own_status_file_is_never_overwritten(self):
        self.status.write_text("# My own status notes\n", encoding="utf-8")
        code, output = self.routine("run", "--kind", "daily")
        self.assertEqual(code, 1)
        self.assertEqual(self.status.read_text(encoding="utf-8"), "# My own status notes\n")

    def test_a_routine_that_stopped_overlapped_or_failed_is_flagged(self):
        self.routine("record", "--kind", "daily", "--runner", "os")
        self.routine("run", "--kind", "daily", "--runner", "os")
        self.assertEqual([rule for rule in self.rules() if rule.startswith("ROU")], [])
        self.clock("2026-03-06")
        self.assertIn("last ran 5 days ago", self.found("ROU001")[0]["message"])
        self.assertIn("Alarm", self.routine("status")[1])
        self.routine("run", "--kind", "daily", "--runner", "os")
        self.clock("2026-03-07")
        self.assertEqual(self.found("ROU001"), [])
        log = self.home / "_workspace" / "runs.jsonl"
        ws.append_line(log, {"time": "2026-03-07T08:00-08:00", "kind": "daily", "runner": "os", "computer": "testbox",
                             "period": "2026-03-07", "result": "ok"})
        ws.append_line(log, {"time": "2026-03-07T08:05-08:00", "kind": "daily", "runner": "os", "computer": "laptop",
                             "period": "2026-03-07", "result": "ok"})
        self.assertEqual(len(self.found("ROU002")), 1)
        ws.append_line(log, {"time": "2026-03-07T09:00-08:00", "kind": "daily", "runner": "os", "computer": "testbox",
                             "period": "2026-03-07", "result": "error"})
        self.assertEqual(len(self.found("ROU003")), 1)

    def test_remove_takes_the_routine_out_and_keeps_the_files(self):
        self.routine("record", "--kind", "daily", "--runner", "os")
        self.routine("run", "--kind", "daily", "--runner", "os")
        code, output = self.routine("remove", "--kind", "daily")
        self.assertEqual(code, 0, output)
        self.assertTrue(self.status.is_file())
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8"))["routines"], [])
        self.clock("2026-06-01")
        self.assertEqual([rule for rule in self.rules() if rule.startswith("ROU")], [])

    def test_a_month_of_drift_and_missed_runs(self):
        """Thirty days: a deadline arrives and passes, the routine misses four days, a conflict appears and ages."""
        self.routine("record", "--kind", "daily", "--runner", "os")
        owners_files = lambda: {name: digest for name, digest in manifest(self.home).items()
                                if name != "STATUS.md" and not name.startswith("_workspace")}
        codes, missed = {}, {12, 13, 14, 15}
        kept = owners_files()
        for day in range(1, 31):
            self.clock("2026-03-%02d" % day)
            if day == 3:
                self.section("Next actions", "1. Book the window installer, due 2026-03-10.")
                kept = owners_files()
            if day == 20:
                self.section("Don't forget", "- Conflict: the permit date. The letter says May, the contractor says June.")
                kept = owners_files()
            if day in missed:
                continue
            code, output = self.routine("run", "--kind", "daily", "--runner", "os")
            codes[day] = code
            self.assertEqual(owners_files(), kept, "day %d changed one of the owner's files" % day)
            if day == 16:
                self.assertIn("last ran 5 days ago", self.status.read_text(encoding="utf-8"))
        self.assertEqual(codes[1], 0)            # nothing needs the owner yet
        self.assertEqual(codes[6], 0)            # the deadline is still more than three days away
        self.assertEqual(codes[7], 10)           # due in three days: said once
        self.assertEqual(codes[8], 0)
        self.assertEqual(codes[10], 10)          # due today
        self.assertEqual(codes[11], 10)          # overdue, new
        self.assertEqual(codes[16], 10)          # back after four missed days: the gap is news
        self.assertEqual(codes[17], 0)
        self.assertEqual(codes[18], 10)          # the overdue action has been open seven days
        self.assertEqual(codes[20], 10)          # a conflict appeared
        self.assertEqual(codes[21], 0)
        self.assertEqual(codes[27], 10)          # the conflict has been open seven days
        self.assertEqual(codes[30], 0)
        good = [entry for entry in self.runs() if entry.get("result") in ("ok", "attention")]
        self.assertEqual(len(good), 26)
        self.assertEqual(len({entry["period"] for entry in good}), 26)
        text = self.status.read_text(encoding="utf-8")
        self.assertIn("1 next action overdue", text)
        self.assertIn("1 open conflict between sources. Open 10 days.", text)


class SmallBorrowTests(Base):
    """Standard files stay single, and the log and the decisions keep their shape."""

    def setUp(self):
        super().setUp()
        self.build()
        self.handoff = self.project() / "HANDOFF.md"

    def found(self, rule):
        return [finding for finding in self.check()[1]["findings"] if finding["rule"] == rule]

    def log(self, body):
        text = self.handoff.read_text(encoding="utf-8")
        self.handoff.write_text(text.split("## Session log")[0] + "## Session log\n\n" + body + "\n", encoding="utf-8")

    def test_the_rules_say_standard_files_are_updated_in_place(self):
        rules = (self.home / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("**Update the standard files in place.**", rules)
        self.assertIn("`HANDOFF_v2.md`", rules)
        self.assertIn("a new version of a deliverable as `_v2`", rules)
        self.assertIn("**Names that sort, and lists that stay small.**", rules)

    def test_a_second_copy_of_the_hand_off_is_an_error_the_brief_shows(self):
        self.assertEqual(self.found("HND015") + self.found("WRK006"), [])
        (self.project() / "HANDOFF-log.md").write_text("# Older log lines\n", encoding="utf-8")
        (self.project() / "README-notes.md").write_text("# Notes\n", encoding="utf-8")
        self.assertEqual(self.found("HND015") + self.found("WRK006"), [])
        (self.project() / "HANDOFF_v2.md").write_text("# Handoff: Duplex renovation\n", encoding="utf-8")
        (self.project() / "handoff copy.md").write_text("x\n", encoding="utf-8")
        (self.project() / "DECISIONS_v2.md").write_text("x\n", encoding="utf-8")
        hits = self.found("HND015")
        self.assertEqual(sorted(finding["path"].rsplit("/", 1)[1] for finding in hits), ["HANDOFF_v2.md", "handoff copy.md"])
        self.assertEqual(hits[0]["severity"], "error")
        self.assertEqual([finding["path"].rsplit("/", 1)[1] for finding in self.found("WRK006")], ["DECISIONS_v2.md"])
        code, output = run("check", "--brief", "--home", self.home)
        self.assertEqual(code, 1)
        self.assertIn("second copy of `HANDOFF.md`", output)

    def test_session_log_lines_need_a_date_and_newest_first(self):
        self.assertEqual(self.found("HND016"), [])
        self.log("- 2026-03-02 · a tool: ordered the windows.\n- 2026-03-01 · a tool: created this folder.")
        self.assertEqual(self.found("HND016"), [])
        self.log("- ordered the windows.\n- 2026-03-01 · a tool: created this folder.")
        self.assertIn("1 Session log line with no date", self.found("HND016")[0]["message"])
        self.log("- 2026-03-01 · a tool: created this folder.\n- 2026-03-02 · a tool: ordered the windows.")
        self.assertIn("isn't newest first", self.found("HND016")[0]["message"])

    def test_decision_entries_need_a_number_or_a_date(self):
        path = self.project() / "DECISIONS.md"
        self.assertEqual(self.found("DEC003"), [])
        base = path.read_text(encoding="utf-8").replace("- None yet.\n", "")
        path.write_text(base + "- **D-002 · 2026-03-02 · Windows.** Wood frames. *Why:* looks. *Source:* Ana, chat.\n"
                               "- **2026-01-10 · Contractor.** The first firm.\n", encoding="utf-8")
        self.assertEqual(self.found("DEC003"), [])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("- We should probably repaint the fence.\n")
        hits = self.found("DEC003")
        self.assertEqual(len(hits), 1)
        self.assertIn("1 entry not in the decision format", hits[0]["message"])

    def test_upgrade_from_the_last_version_adds_the_two_new_rules(self):
        settings_path = self.home / "_workspace" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["skill_version"] = "0.4.0"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        rules_path = self.home / "AGENTS.md"
        titles = [title for step in ws.UPGRADES if step["version"] == "0.5.0" for title in step["rules"]]
        kept = [line for line in rules_path.read_text(encoding="utf-8").splitlines(keepends=True)
                if not any("**%s**" % title in line for title in titles)]
        rules_path.write_text("".join(kept), encoding="utf-8")
        old = rules_path.read_text(encoding="utf-8")
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        added = rules_path.read_text(encoding="utf-8")[len(old):]
        self.assertEqual(added.count("<!-- agent-workspace-setup:rules-0.5.0 -->"), 1)
        for title in titles:
            self.assertIn("- **%s**" % title, added)
        self.assertNotIn("rules-0.4.0", added)

    def test_the_skill_text_has_the_two_new_rules_for_agents(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("never a guessed or placeholder path", text)
        self.assertIn('"import skill"', text)


class LayoutTests(Base):
    """Optional help with the folders beside the home: folders only, by approved number, and nothing written there."""

    CHANGES = [
        {"create": "00_Inbox", "about": "Anything not sorted yet."},
        {"rename": "Taxes 2025", "to": "30_Finance-Taxes", "about": "Returns, statements and receipts."},
        {"create": "99_Archive", "about": "Things that are finished."},
        {"move": "Old stuff", "into": "99_Archive"},
        {"rename": "Client work/Acme", "to": "41_Acme"},
        {"move": "loose.txt", "into": "00_Inbox"},
    ]

    def setUp(self):
        super().setUp()
        for folder in ("Taxes 2025/2024", "Old stuff", "Client work/Acme", "Private", "Photos Library", "Shared drives", "Documents"):
            (self.drive / folder).mkdir(parents=True)
        for name, body in (("Taxes 2025/return.pdf", "return"), ("Taxes 2025/2024/w2.pdf", "w2"), ("Old stuff/x.txt", "x"),
                           ("Client work/Acme/notes.txt", "notes"), ("Private/secret.txt", "SECRET-CANARY"),
                           ("Photos Library/p.jpg", "jpg"), ("loose.txt", "loose")):
            (self.drive / name).write_text(body, encoding="utf-8")
        self.build(private=["Private"], work=[{"title": "Taxes", "kind": "area", "documents": [str(self.drive / "Taxes 2025")]}])
        self.settings_path = self.home / "_workspace" / "settings.json"

    def outside(self):
        """Every file and folder outside the AI home."""
        files, folders = {}, set()
        for current, names, found in os.walk(str(self.drive)):
            names[:] = [name for name in names if os.path.join(current, name) != str(self.home)]
            for name in names:
                folders.add(os.path.relpath(os.path.join(current, name), str(self.drive)))
            for name in found:
                path = os.path.join(current, name)
                with open(path, "rb") as handle:
                    files[os.path.relpath(path, str(self.drive))] = hashlib.sha256(handle.read()).hexdigest()
        return files, folders

    def changes(self, changes=None, **extra):
        path = self.tmp / "changes.json"
        path.write_text(json.dumps(dict({"changes": self.CHANGES if changes is None else changes, "keep": ["Photos Library"]}, **extra)),
                        encoding="utf-8")
        return path

    def settings(self):
        return json.loads(self.settings_path.read_text(encoding="utf-8"))

    def layout(self, *argv):
        return run("layout", *argv, "--home", self.home)

    def test_look_and_plan_change_nothing_and_never_list_private(self):
        before = manifest(self.tmp)
        code, look = self.layout("look", "--keep", "Photos Library")
        self.assertEqual(code, 0, look)
        self.assertIn("| `Private/` | private, not opened | | | |", look)
        self.assertIn("| `Photos Library/` | kept as it is | | | |", look)
        self.assertIn("| `90_AI-Agents/` | the AI home | | | |", look)
        self.assertIn("| `Taxes 2025/` | not numbered | 2 |", look)
        self.assertIn("## How the numbers work", look)
        code, inside = self.layout("look", "--inside", "Client work")
        self.assertEqual(code, 0, inside)
        self.assertIn("| `Acme/` | not numbered | 1 |", inside)
        code, plan = self.layout("plan", "--changes", self.changes())
        self.assertEqual(code, 0, plan)
        for index, line in enumerate(("Create `00_Inbox/`.", "Rename `Taxes 2025/`  →  `30_Finance-Taxes/`.", "Create `99_Archive/`.",
                                      "Move `Old stuff/`  →  `99_Archive/Old stuff/`.",
                                      "Rename `Client work/Acme/`  →  `Client work/41_Acme/`.",
                                      "Move `loose.txt`  →  `00_Inbox/loose.txt`."), 1):
            self.assertIn("%d. %s" % (index, line), plan)
        self.assertIn("ask which numbers to do. Then stop.", plan)
        for output in (look, inside, plan):
            self.assertNotIn("secret", output)
            self.assertNotIn("SECRET-CANARY", output)
        code, output = self.layout("look", "--inside", "Private")
        self.assertEqual(code, 1, output)
        self.assertIn("is private", output)
        os.remove(str(self.tmp / "changes.json"))
        self.assertEqual(before, manifest(self.tmp))

    def test_apply_does_only_the_approved_numbers_and_every_file_keeps_its_hash(self):
        files, folders = self.outside()
        home_before = manifest(self.home)
        code, preview = self.layout("apply", "--changes", self.changes(), "--only", "1,2", "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual((files, folders), self.outside())
        self.assertEqual(home_before, manifest(self.home))
        code, output = self.layout("apply", "--changes", self.changes(), "--only", "1,2")
        self.assertEqual(code, 0, output)
        self.assertIn("1. Done. Create `00_Inbox/`.", output)
        self.assertIn("The settings now give the document folder `../Taxes 2025` as `../30_Finance-Taxes`.", output)
        after, after_folders = self.outside()
        self.assertEqual(sorted(after.values()), sorted(files.values()))       # every file is still there, unchanged
        self.assertEqual(len(after), len(files))                               # and no file was added out there
        self.assertEqual(after["30_Finance-Taxes/2024/w2.pdf".replace("/", os.sep)], files["Taxes 2025/2024/w2.pdf".replace("/", os.sep)])
        self.assertEqual(after_folders - folders, {"00_Inbox", "30_Finance-Taxes", os.path.join("30_Finance-Taxes", "2024")})
        self.assertTrue((self.drive / "Old stuff").is_dir())                   # number 4 was not approved
        self.assertFalse((self.drive / "99_Archive").exists())                 # nor number 3
        self.assertEqual(list((self.drive / "00_Inbox").iterdir()), [])        # a created folder is empty: no agent file
        log = ws.read_layout(ws.Home(self.home))
        self.assertEqual([(entry["op"], entry["state"]) for entry in log], [("create", "done"), ("rename", "done")])
        recorded = self.settings()
        self.assertEqual(recorded["documents"], ["../30_Finance-Taxes"])
        self.assertEqual(recorded["layout"]["about"], {"00_Inbox": "Anything not sorted yet.",
                                                       "30_Finance-Taxes": "Returns, statements and receipts."})
        self.assertEqual(recorded["layout"]["keep"], ["Photos Library"])
        readme = (self.home / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Your folders", readme)
        self.assertIn("| `30_Finance-Taxes/` | Returns, statements and receipts. |", readme)
        self.assertIn("| `Private/` | Private. |", readme)
        self.assertIn("| `90_AI-Agents/` | This workspace. Agent files live only here. |", readme)
        stale = [finding for finding in self.check()[1]["findings"] if finding["rule"] == "LAY001"]
        self.assertEqual(sorted(finding["path"] for finding in stale),
                         ["92_Areas/92.01_Taxes/HANDOFF.md", "92_Areas/92.01_Taxes/README.md", "AGENTS.md"])
        self.assertIn("It is now `../30_Finance-Taxes`.", stale[0]["message"])
        self.assertNotIn("MAP003", self.rules())
        self.assertEqual(self.check()[1]["summary"]["error"], 0)

    def test_undo_puts_a_rename_and_a_move_back(self):
        files, folders = self.outside()
        code, output = self.layout("apply", "--changes", self.changes(), "--only", "all")
        self.assertEqual(code, 0, output)
        moved, _ = self.outside()
        self.assertEqual(sorted(moved.values()), sorted(files.values()))
        self.assertTrue((self.drive / "00_Inbox" / "loose.txt").is_file())
        self.assertTrue((self.drive / "Client work" / "41_Acme" / "notes.txt").is_file())
        for expected in ("`00_Inbox/loose.txt`  →  `loose.txt`", "`Client work/41_Acme/`  →  `Client work/Acme/`",
                         "`99_Archive/Old stuff/`  →  `Old stuff/`", "`30_Finance-Taxes/`  →  `Taxes 2025/`"):
            before = self.outside()
            code, preview = self.layout("undo", "--dry-run")
            self.assertEqual(code, 0, preview)
            self.assertIn(expected, preview)
            self.assertEqual(before, self.outside())
            code, output = self.layout("undo")
            self.assertEqual(code, 0, output)
        back, back_folders = self.outside()
        self.assertEqual(back, files)
        self.assertEqual(back_folders - folders, {"00_Inbox", "99_Archive"})    # created empty, and left for the owner
        self.assertEqual(self.settings()["documents"], ["../Taxes 2025"])
        self.assertNotIn("LAY001", self.rules())
        code, output = self.layout("undo")
        self.assertEqual(code, 0, output)
        self.assertIn("no rename or move to undo", output)
        # a place that is taken again is never overwritten
        self.layout("apply", "--changes", self.changes([{"rename": "Old stuff", "to": "80_Old"}]), "--only", "1")
        (self.drive / "Old stuff").mkdir()
        code, output = self.layout("undo")
        self.assertEqual(code, 1, output)
        self.assertIn("`Old stuff` exists again.", output)
        self.assertTrue((self.drive / "80_Old" / "x.txt").is_file())

    def test_what_layout_refuses(self):
        cases = [
            ({"rename": "Private", "to": "70_Private"}, "`Private` is private"),
            ({"move": "Old stuff", "into": "Private"}, "`Private` is private"),
            ({"create": "Private/New"}, "is private"),
            ({"rename": "Photos Library", "to": "50_Photos"}, "is on the keep list"),
            ({"rename": "90_AI-Agents", "to": "80_AI"}, "is the AI home, or inside it"),
            ({"move": "Old stuff", "into": "90_AI-Agents"}, "is the AI home, or inside it"),
            ({"create": "90_AI-Agents/91_Projects/New"}, "more than two levels down"),
            ({"rename": "Shared drives", "to": "20_Shared"}, "is part of how the synced drive is built"),
            ({"rename": "Old stuff", "to": "90_Old"}, "would share the number 90 with `90_AI-Agents`"),
            ({"rename": "Old stuff", "to": "Taxes 2025"}, "`Taxes 2025` already exists"),
            ({"create": "Old stuff"}, "`Old stuff` already exists"),
            ({"move": "Client work/Acme", "into": "Taxes 2025/2024"}, "more than two levels down"),
            ({"move": "Old stuff", "into": "Nowhere"}, "`Nowhere` isn't a folder here"),
            ({"rename": "Missing", "to": "10_Missing"}, "`Missing` isn't here"),
            ({"create": "../escape"}, "isn't a plain path inside the work folder"),
            ({"create": str(self.tmp / "elsewhere")}, "outside the work folder"),
            ({"create": ".hidden"}, "hidden folders are left alone"),
            ({"rename": "Old stuff", "to": "a/b"}, "`rename` needs `to`"),
            ({"rename": "Old stuff", "to": "bad:name"}, "isn't a name every computer accepts"),
            ({"move": "Old stuff", "into": "Old stuff"}, "can't move into itself"),
            ({"create": "X", "rename": "Y"}, "exactly one of"),
        ]
        files, folders = self.outside()
        home_before = manifest(self.home)
        code, plan = self.layout("plan", "--changes", self.changes([case for case, _ in cases]))
        self.assertEqual(code, 0, plan)
        lines = {int(number): text for number, text in re.findall(r"^(\d+)\. (.+)$", plan, re.M)}
        for index, (case, message) in enumerate(cases, 1):
            self.assertTrue(lines[index].startswith("Not possible:"), lines[index])
            self.assertIn(message, lines[index])
        for only, message in (("", "needs --only"), ("0", "names one outside that"), ("99", "names one outside that"), ("one", "isn't a list of numbers")):
            code, output = self.layout("apply", "--changes", self.changes(), *(["--only", only] if only else []))
            self.assertEqual(code, 1, output)
            self.assertIn(message, output)
        # a number that can't be done stops the run, and the numbers after it are left
        mixed = [{"create": "00_Inbox"}, {"rename": "Private", "to": "70_Private"}, {"rename": "Old stuff", "to": "80_Old"}]
        code, output = self.layout("apply", "--changes", self.changes(mixed), "--only", "all")
        self.assertEqual(code, 1, output)
        self.assertIn("1. Done. Create `00_Inbox/`.", output)
        self.assertIn("2. Not done: `Private` is private. The numbers after it were left too.", output)
        after, after_folders = self.outside()
        self.assertEqual(after, files)
        self.assertEqual(after_folders - folders, {"00_Inbox"})
        self.assertEqual((self.drive / "Private" / "secret.txt").read_text(encoding="utf-8"), "SECRET-CANARY")
        changed = {path for path, digest in manifest(self.home).items() if home_before.get(path) != digest}
        self.assertEqual(changed, {"README.md", os.path.join("_workspace", "settings.json"), os.path.join("_workspace", "layout.jsonl")})

    def test_a_refusal_by_the_system_stops_cleanly(self):
        # A sandbox that forbids changes outside the session's folder makes the rename fail. Nothing may be left half done.
        files, folders = self.outside()
        real_rename = os.rename

        def refuse(source, target, *args, **kwargs):
            if "Taxes 2025" in str(source) or "30_Finance-Taxes" in str(source):
                raise PermissionError(1, "Operation not permitted")
            return real_rename(source, target, *args, **kwargs)

        os.rename = refuse
        try:
            code, output = self.layout("apply", "--changes", self.changes(), "--only", "1,2,3")
        finally:
            os.rename = real_rename
        self.assertEqual(code, 1, output)
        self.assertIn("1. Done. Create `00_Inbox/`.", output)
        self.assertIn("2. Not done: the system refused it (Operation not permitted). The numbers after it were left too.", output)
        self.assertIn("Never switch a sandbox or a permission check off yourself.", output)
        self.assertNotIn("fault", output)
        after, after_folders = self.outside()
        self.assertEqual(after, files)
        self.assertEqual(after_folders - folders, {"00_Inbox"})
        self.assertEqual(self.settings()["documents"], ["../Taxes 2025"])
        self.assertEqual([(entry["op"], entry["state"]) for entry in ws.read_layout(ws.Home(self.home))],
                         [("create", "done"), ("rename", "abandoned")])
        self.assertNotIn("LAY001", self.rules())
        # the same change works once the system allows it, and an undo that is refused leaves both places alone
        code, output = self.layout("apply", "--changes", self.changes(), "--only", "2")
        self.assertEqual(code, 0, output)
        os.rename = refuse
        try:
            code, output = self.layout("undo")
        finally:
            os.rename = real_rename
        self.assertEqual(code, 1, output)
        self.assertIn("The system refused the undo", output)
        self.assertTrue((self.drive / "30_Finance-Taxes" / "return.pdf").is_file())

    def test_a_link_is_never_moved(self):
        try:
            os.symlink(str(self.drive / "Old stuff"), str(self.drive / "Shortcut"))
        except (OSError, NotImplementedError):
            self.skipTest("this system doesn't allow links here")
        code, plan = self.layout("plan", "--changes", self.changes([{"rename": "Shortcut", "to": "60_Shortcut"},
                                                                    {"rename": "Documents", "to": "20_Documents"}]))
        self.assertIn("`Shortcut` is a link. Links are never moved", plan)
        self.assertIn("2. Rename `Documents/`  →  `20_Documents/`.", plan)  # an ordinary folder in a drive, whatever its name

    def test_the_owners_home_folder_is_never_organized(self):
        (self.fake_home / "Desktop").mkdir()
        answers = self.tmp / "home.json"
        answers.write_text(json.dumps({"location": str(self.fake_home), "owner": "Ana Lopez"}), encoding="utf-8")
        code, output = run("setup", "--answers", answers)
        self.assertEqual(code, 0, output)
        before = manifest(self.fake_home)
        for action in (["look"], ["plan", "--changes", self.changes([{"rename": "Desktop", "to": "10_Desktop"}])],
                       ["apply", "--changes", self.tmp / "changes.json", "--only", "all"], ["undo"], ["keep", "Desktop"]):
            code, output = run("layout", *action, "--home", self.fake_home / "90_AI-Agents")
            self.assertEqual(code, 1, output)
            self.assertIn("belong to the system and to apps", output)
        self.assertEqual(before, manifest(self.fake_home))

    def test_agent_files_outside_the_home_are_flagged_once_the_owner_uses_the_layout_help(self):
        (self.drive / "Client work" / "AGENTS.md").write_text("rules\n", encoding="utf-8")
        (self.drive / "Client work" / "Acme" / "HANDOFF.md").write_text("handoff\n", encoding="utf-8")
        (self.drive / "Private" / "CLAUDE.md").write_text("x\n", encoding="utf-8")
        self.assertNotIn("OUT001", self.rules())            # the folders beside the home aren't looked at unasked
        code, look = self.layout("look")
        self.assertIn("`Client work/AGENTS.md`", look)
        self.assertNotIn("Private/CLAUDE.md", look)
        before, _ = self.outside()
        code, preview = self.layout("keep", "Photos Library", "--dry-run")
        self.assertNotIn("layout", self.settings())
        code, output = self.layout("keep", "Photos Library")
        self.assertEqual(code, 0, output)
        hits = sorted(finding["path"] for finding in self.check()[1]["findings"] if finding["rule"] == "OUT001")
        self.assertEqual(hits, ["../Client work/AGENTS.md", "../Client work/Acme/HANDOFF.md"])
        code, output = self.layout("keep", "Client work")
        self.assertEqual(code, 0, output)
        self.assertNotIn("OUT001", self.rules())
        code, plan = self.layout("plan", "--changes", self.changes([{"rename": "Client work", "to": "40_Clients"}], keep=[]))
        self.assertIn("is on the keep list", plan)
        self.assertEqual(before, self.outside()[0])


class RedirectedToolTests(Base):
    """A wrapper app, or a second profile, can point a tool's home somewhere else. The owner is told."""

    def test_install_and_connect_say_when_the_tools_home_was_moved(self):
        self.build()
        code, usual = run("install", "--tool", "claude", "--dry-run")
        self.assertEqual(code, 0, usual)
        self.assertNotIn("Note:", usual)
        wrapper = self.tmp / "wrapper-app" / "claude-home"
        wrapper.mkdir(parents=True)
        os.environ["CLAUDE_CONFIG_DIR"] = str(wrapper)
        os.environ["CODEX_HOME"] = str(self.tmp / "wrapper-app" / "codex-home")
        before = manifest(self.tmp)
        code, output = run("install", "--tool", "claude", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("claude-home/skills/agent-workspace-setup", output.replace(os.sep, "/"))
        self.assertIn("Note: `CLAUDE_CONFIG_DIR` points Claude Code at", output)
        self.assertIn("not the usual `~/.claude`", output)
        self.assertIn("pass --dest with its skills folder", output)
        self.assertIn("the note included", output)
        code, output = run("connect", "--tool", "claude", "--dry-run", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("Note: `CLAUDE_CONFIG_DIR` points Claude Code at", output)
        code, output = run("install", "--tool", "codex", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertNotIn("Note:", output)  # Codex skills sit in ~/.agents/skills wherever CODEX_HOME points
        code, output = run("connect", "--tool", "codex", "--dry-run", "--home", self.home)
        self.assertIn("Note: `CODEX_HOME` points Codex at", output)
        self.assertEqual(before, manifest(self.tmp))


class GroupTests(Base):
    """Groups the owner names, each with one line on what goes there."""

    OWN = [
        {"name": "Clients", "about": "One folder for each client.", "work": "ongoing"},
        {"name": "Campaigns", "about": "Launches and pushes that end.", "work": "finishes"},
        {"name": "Library", "about": "Reference material agents read."},
    ]
    WORK = [{"title": "Acme", "group": "Clients"}, {"title": "Spring launch", "group": "92"}]

    def settings(self):
        return json.loads((self.home / "_workspace" / "settings.json").read_text(encoding="utf-8"))

    def test_ours_stay_the_default(self):
        self.build()
        self.assertNotIn("groups", self.settings())
        for name in ("90_Inbox", "91_Projects", "92_Areas", "95_Data"):
            self.assertTrue((self.home / name).is_dir(), name)
        readme = (self.home / "README.md").read_text(encoding="utf-8")
        self.assertIn("Work that finishes.", readme)
        rules = (self.home / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("The map in [README.md](README.md) lists the groups", rules)
        self.assertNotIn("is for work that finishes", rules)

    def test_the_owners_own_groups_are_built_with_their_lines(self):
        answers = self.answers(groups=self.OWN, work=self.WORK)
        before = manifest(self.tmp)
        code, preview = run("setup", "--answers", answers, "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(before, manifest(self.tmp))
        self.assertIn("91_Clients/  AGENTS.md, CLAUDE.md  (new)", preview)
        self.assertIn("- `92_Campaigns/`: Launches and pushes that end.", preview)
        self.assertIn("Every name above is a suggestion", preview)
        self.build(groups=self.OWN, work=self.WORK)
        self.assertEqual(sorted(p.name for p in self.home.iterdir() if p.is_dir() and p.name[0].isdigit()),
                         ["90_Inbox", "91_Clients", "92_Campaigns", "93_Library"])
        client, launch = self.home / "91_Clients" / "91.01_Acme", self.home / "92_Campaigns" / "92.01_Spring-launch"
        self.assertIn("**Status:** Ongoing", (client / "HANDOFF.md").read_text(encoding="utf-8"))
        self.assertIn("**Status:** Active", (launch / "HANDOFF.md").read_text(encoding="utf-8"))
        for name in ("91_Clients", "92_Campaigns", "93_Library"):
            self.assertTrue((self.home / name / "AGENTS.md").is_file(), name)
        recorded = self.settings()["groups"]
        self.assertEqual([(entry["number"], entry["name"]) for entry in recorded],
                         [(90, "Inbox"), (91, "Clients"), (92, "Campaigns"), (93, "Library")])
        self.assertEqual(recorded[3]["work"], "ongoing")
        readme = (self.home / "README.md").read_text(encoding="utf-8")
        self.assertIn("| [91_Clients](91_Clients/) | One folder for each client. |", readme)
        self.assertIn("Anything not filed yet.", readme)
        code, data = self.check()
        self.assertEqual(data["summary"]["error"], 0, data)
        # running setup again adds nothing and changes nothing
        after = manifest(self.home)
        self.build(groups=self.OWN, work=self.WORK)
        self.assertEqual(after, manifest(self.home))

    def test_the_folder_the_owner_named_is_not_taken_for_the_homes_name(self):
        # A cheaper model once wrote the parent as `location` and the named folder as `home_name`.
        answers = self.tmp / "wrong.json"
        answers.write_text(json.dumps({"location": str(self.tmp), "home_name": "Drive", "owner": "Ana Lopez"}), encoding="utf-8")
        before = manifest(self.tmp)
        code, output = run("setup", "--answers", answers, "--dry-run")
        self.assertEqual(code, 1, output)
        self.assertIn("`location` already holds a folder called `Drive`", output)
        self.assertIn("leave `home_name` out", output)
        self.assertEqual(before, manifest(self.tmp))
        code, preview = run("setup", "--answers", self.answers(), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertIn("Where: inside `", preview)
        self.assertIn("Drive`", preview.split("```")[0])

    def test_bad_groups_are_refused_with_plain_reasons(self):
        cases = [
            ([{"name": "Clients"}], "Group `Clients` needs `about`"),
            ([{"name": "A", "about": "x"}, {"name": "a", "about": "y"}], "listed twice"),
            ([{"name": "G%d" % n, "about": "x"} for n in range(9)], "up to 8 groups besides the Inbox"),
            ([{"name": "Clients", "about": "x", "work": "sometimes"}], "`work` must be finishes or ongoing"),
            ([{"name": "Inbox", "about": "Drop things here."}], "no group besides the Inbox"),
        ]
        for groups, message in cases:
            code, output = run("setup", "--answers", self.answers(groups=groups, work=[]), "--dry-run")
            self.assertEqual(code, 1, output)
            self.assertIn(message, output)
            self.assertFalse(self.home.exists())
        code, output = run("setup", "--answers", self.answers(groups=self.OWN, work=[{"title": "Acme"}]), "--dry-run")
        self.assertEqual(code, 1, output)
        self.assertIn("has no group for `project` work", output)
        self.assertIn("`91_Clients`", output)

    def test_a_group_named_like_ours_keeps_our_line_and_its_kind(self):
        self.build(groups=[{"name": "Clients", "about": "One folder for each client."}, {"name": "Projects"}],
                   work=[{"title": "Fence", "kind": "project"}])
        self.assertTrue((self.home / "92_Projects" / "92.01_Fence").is_dir())
        self.assertIn("| [92_Projects](92_Projects/) | Work that finishes. |", (self.home / "README.md").read_text(encoding="utf-8"))

    def test_new_takes_a_group_by_name_or_number(self):
        self.build(groups=self.OWN, work=self.WORK)
        code, output = run("new", "--title", "Autumn sale", "--group", "campaigns", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "92_Campaigns" / "92.02_Autumn-sale").is_dir())
        code, output = run("new", "--title", "Style guide", "--group", "93", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "93_Library" / "93.01_Style-guide").is_dir())
        before = manifest(self.home)
        for extra, message in ((["--kind", "project"], "has no group for `project` work"), (["--group", "Nope"], "`Nope` isn't a group here"),
                               ([], "has no group for `project` work"), (["--group", "90"], "isn't a group here")):
            code, output = run("new", "--title", "Other", "--home", self.home, *extra)
            self.assertEqual(code, 1, output)
            self.assertIn(message, output)
            self.assertIn("`92_Campaigns`", output)
        self.assertEqual(before, manifest(self.home))

    def test_group_list_add_and_describe_on_an_older_workspace(self):
        self.build()
        before = manifest(self.home)
        code, listing = run("group", "list", "--home", self.home)
        self.assertEqual(code, 0, listing)
        self.assertIn("| 91 | `91_Projects/` | Work that finishes. | finishes |", listing)
        code, preview = run("group", "add", "--name", "Clients", "--about", "One folder for each client.", "--dry-run", "--home", self.home)
        self.assertEqual(code, 0, preview)
        self.assertIn("`93_Clients/`  AGENTS.md, CLAUDE.md  (new)", preview)
        self.assertEqual(before, manifest(self.home))
        code, output = run("group", "add", "--name", "Clients", "--about", "One folder for each client.", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "93_Clients" / "AGENTS.md").is_file())
        recorded = self.settings()["groups"]
        self.assertEqual([entry["number"] for entry in recorded], [90, 91, 92, 93, 95])
        self.assertEqual([entry.get("kind", "") for entry in recorded], ["", "project", "area", "", "data"])
        self.assertIn("| [93_Clients](93_Clients/) | One folder for each client. |", (self.home / "README.md").read_text(encoding="utf-8"))
        # nothing that was there changed, apart from the settings and the map
        after = manifest(self.home)
        changed = sorted(path for path in before if before[path] != after.get(path))
        self.assertEqual(changed, ["README.md", os.path.join("_workspace", "settings.json")])
        code, output = run("new", "--title", "Acme", "--group", "clients", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("**Status:** Ongoing", (self.home / "93_Clients" / "93.01_Acme" / "HANDOFF.md").read_text(encoding="utf-8"))
        code, output = run("new", "--title", "Taxes", "--kind", "area", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "92_Areas" / "92.02_Taxes").is_dir())
        code, output = run("move", "93.01", "--to", "Projects", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "91_Projects" / "93.01_Acme").is_dir())
        code, output = run("group", "describe", "93", "--about", "Client work, one folder each.", "--work", "finishes", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("| [93_Clients](93_Clients/) | Client work, one folder each. |", (self.home / "README.md").read_text(encoding="utf-8"))
        for argv, message in (
            (["group", "add", "--name", "clients", "--about", "x"], "already a group named"),
            (["group", "add", "--name", "Vendors"], "needs --name and --about"),
            (["group", "describe", "Inbox", "--work", "finishes"], "doesn't apply"),
            (["group", "describe", "97", "--about", "x"], "isn't a group here"),
            (["group", "describe", "93"], "Nothing to change"),
        ):
            code, output = run(*argv, "--home", self.home)
            self.assertEqual(code, 1, output)
            self.assertIn(message, output)
        self.assertEqual(self.check()[1]["summary"]["error"], 0)

    def test_a_home_holds_eight_groups_besides_the_inbox(self):
        self.build()
        for index in range(5):
            code, output = run("group", "add", "--name", "Extra %d" % index, "--about", "More work.", "--home", self.home)
            self.assertEqual(code, 0, output)
        numbers = sorted(int(p.name[:2]) for p in self.home.iterdir() if p.is_dir() and p.name[:2].isdigit())
        self.assertEqual(numbers, [90, 91, 92, 93, 94, 95, 96, 97, 98])
        code, output = run("group", "add", "--name", "One more", "--about", "x", "--home", self.home)
        self.assertEqual(code, 1, output)
        self.assertIn("already has 8 groups besides the Inbox", output)

    def test_adopt_goes_into_a_named_group(self):
        self.build(groups=self.OWN, work=self.WORK)
        loose = self.home / "Loose notes"
        loose.mkdir()
        (loose / "notes.txt").write_text("x", encoding="utf-8")
        code, output = run("adopt", "Loose notes", "--group", "Library", "--home", self.home)
        self.assertEqual(code, 0, output)
        target = self.home / "93_Library" / "93.01_Loose-notes"
        self.assertTrue((target / "notes.txt").is_file())
        self.assertIn("**Status:** Ongoing", (target / "HANDOFF.md").read_text(encoding="utf-8"))
        self.assertEqual(self.ledger()[-1]["kind"], "own")


class ReviewTests(Base):
    """Review by number, filing from the Inbox, snapshots, facts, versions and the brief file."""

    def setUp(self):
        super().setUp()
        self.saved_clock = os.environ.get("AGENT_WORKSPACE_NOW")
        os.environ["AGENT_WORKSPACE_NOW"] = "2026-03-01"
        self.build()
        self.handoff = self.project() / "HANDOFF.md"
        self.inbox = self.home / "90_Inbox"

    def tearDown(self):
        if self.saved_clock is None:
            os.environ.pop("AGENT_WORKSPACE_NOW", None)
        else:
            os.environ["AGENT_WORKSPACE_NOW"] = self.saved_clock
        super().tearDown()

    def found(self, rule):
        return [finding for finding in self.check()[1]["findings"] if finding["rule"] == rule]

    def moves(self):
        return ws.read_moves(ws.Home(self.home))[0]

    def test_review_numbers_the_proposals_and_writes_nothing(self):
        code, output = run("review", "--home", self.home)
        self.assertEqual(code, 0, output)
        (self.inbox / "scan.pdf").write_bytes(b"x")
        (self.inbox / "Receipts").mkdir()
        text = self.handoff.read_text(encoding="utf-8")
        self.handoff.write_text(text.replace("**Status:** Active", "**Status:** Closed"), encoding="utf-8")
        os.environ["AGENT_WORKSPACE_NOW"] = "2026-04-15"
        before = manifest(self.home)
        code, output = run("review", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.home))
        numbered = re.findall(r"^(\d+)\. (.+)$", output, re.M)
        self.assertEqual([int(number) for number, _ in numbered], list(range(1, len(numbered) + 1)))
        lines = [line for _, line in numbered]
        self.assertTrue(any(line.startswith("Archive 91.01") and "`archive 91.01 --dry-run`" in line for line in lines), output)
        self.assertTrue(any("File `scan.pdf` from the Inbox." in line and 'file "scan.pdf" --to <number> --dry-run' in line for line in lines), output)
        self.assertTrue(any("File `Receipts` from the Inbox." in line for line in lines), output)
        self.assertTrue(all("**How:**" in line for line in lines), output)
        self.assertIn("The owner approves by number.", output)
        self.assertIn("ask which numbers to do. Then stop.", output)
        self.assertNotIn("INB002", output)

    def test_file_moves_an_inbox_item_and_undo_puts_it_back(self):
        scan = self.inbox / "scan 1.pdf"
        scan.write_bytes(b"pdf bytes")
        digest = hashlib.sha256(b"pdf bytes").hexdigest()
        ledger = self.ledger()
        before = manifest(self.home)
        code, output = run("file", "scan 1.pdf", "--to", "91.01", "--dry-run", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("`90_Inbox/scan 1.pdf`  →  `91_Projects/91.01_Duplex-renovation/scan 1.pdf`", output)
        self.assertEqual(before, manifest(self.home))
        code, output = run("file", "90_Inbox/scan 1.pdf", "--to", "91.01", "--home", self.home)
        self.assertEqual(code, 0, output)
        moved = self.project() / "scan 1.pdf"
        self.assertFalse(scan.exists())
        self.assertEqual(hashlib.sha256(moved.read_bytes()).hexdigest(), digest)
        self.assertEqual(self.moves()[-1]["state"], "done")
        self.assertEqual(self.moves()[-1]["op"], "file")
        self.assertEqual(self.ledger(), ledger)
        code, output = run("undo", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue(scan.is_file())
        self.assertFalse(moved.exists())
        self.assertEqual(self.ledger(), ledger)
        # a folder is filed whole, a work folder can be named in words, and an Inbox folder needs no number
        (self.inbox / "Receipts").mkdir()
        (self.inbox / "Receipts" / "a.txt").write_text("a", encoding="utf-8")
        self.assertEqual(self.found("NUM005"), [])
        self.assertIn("Work folders an Inbox item can go to: 91.01 Duplex renovation · 92.01 Bookkeeping.", run("review", "--home", self.home)[1])
        code, output = run("file", "Receipts", "--to", "the bookkeeping area", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / "92_Areas" / "92.01_Bookkeeping" / "Receipts" / "a.txt").is_file())
        self.assertEqual(self.check()[1]["summary"]["error"], 0)

    def test_file_refuses_what_it_should(self):
        (self.inbox / "scan.pdf").write_bytes(b"new")
        (self.project() / "scan.pdf").write_bytes(b"old")
        (self.home / "outside.txt").write_text("x", encoding="utf-8")
        before = manifest(self.home)
        for argv, message in (
            (["file", "scan.pdf", "--to", "91.01"], "already exists"),
            (["file", "missing.pdf", "--to", "91.01"], "isn't an item directly in `90_Inbox/`"),
            (["file", "../outside.txt", "--to", "91.01"], "isn't an item directly in `90_Inbox/`"),
            (["file", "scan.pdf", "--to", "91.77"], "No folder has the number"),
            (["file", "scan.pdf", "--to", "the garden shed"], "isn't a work folder number, or a name here"),
        ):
            code, output = run(*argv, "--home", self.home)
            self.assertEqual(code, 1, output)
            self.assertIn(message, output)
        self.assertIn("Work folders here: 91.01 Duplex renovation, 92.01 Bookkeeping.", output)
        self.assertEqual(before, manifest(self.home))
        code, output = run("archive", "92.01", "--home", self.home)
        self.assertEqual(code, 0, output)
        code, output = run("file", "scan.pdf", "--to", "92.01", "--home", self.home)
        self.assertEqual(code, 1, output)
        self.assertIn("is in the archive", output)
        self.assertEqual((self.project() / "scan.pdf").read_bytes(), b"old")

    def test_snapshot_keeps_the_hand_off_as_it_is(self):
        rules = self.rules()
        before = manifest(self.home)
        code, output = run("snapshot", "91.01", "--dry-run", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertEqual(before, manifest(self.home))
        code, output = run("snapshot", "91.01", "--home", self.home)
        self.assertEqual(code, 0, output)
        code, output = run("snapshot", "91.01", "--home", self.home)
        self.assertEqual(code, 0, output)
        copies = sorted((self.home / "_workspace" / "snapshots" / "91.01").iterdir())
        self.assertEqual([path.name for path in copies], ["20260301-000000-2-HANDOFF.md", "20260301-000000-HANDOFF.md"])
        for path in copies:
            self.assertEqual(path.read_bytes(), self.handoff.read_bytes())
        after = manifest(self.home)
        self.assertEqual({path for path in after if after[path] != before.get(path) and not path.startswith(os.path.join("_workspace", "snapshots"))}, set())
        self.assertEqual(self.rules(), rules)
        code, output = run("snapshot", "91.77", "--home", self.home)
        self.assertEqual(code, 1, output)

    def test_facts_need_a_source_and_a_date(self):
        self.assertEqual(self.found("FCT002"), [])
        (self.project() / "FACTS.md").write_text(
            "# Facts: Duplex renovation\n\n- The lot is 5,000 square feet (county record, 2026-01-05)\n"
            "- The roof's age isn't known. Unconfirmed\n- None yet.\n", encoding="utf-8")
        self.assertEqual(self.found("FCT002"), [])
        with open(self.project() / "FACTS.md", "a", encoding="utf-8") as handle:
            handle.write("- The contractor's office is on Pine Street\n- Budget is 40,000 (Ana)\n")
        hits = self.found("FCT002")
        self.assertEqual(len(hits), 1)
        self.assertIn("2 facts with no source and date", hits[0]["message"])
        self.assertTrue(hits[0]["path"].endswith("91.01_Duplex-renovation/FACTS.md"))

    def test_three_versions_of_one_file_are_listed(self):
        for name in ("Plan_v1.docx", "Plan_v2.docx", "Budget v1.xlsx"):
            (self.project() / name).write_bytes(b"x")
        self.assertEqual(self.found("FIL001"), [])
        (self.project() / "Plan_v3.docx").write_bytes(b"x")
        hits = self.found("FIL001")
        self.assertEqual(len(hits), 1)
        self.assertIn("`Plan.docx` has 3 versions here, v1 to v3.", hits[0]["message"])
        self.assertIn("Delete nothing", hits[0]["fix"])

    def test_setup_writes_the_brief_file_and_the_new_rules(self):
        brief = (self.home / "BRIEF.md").read_text(encoding="utf-8")
        self.assertIn("# How to brief Ana", brief)
        self.assertIn("`HANDOFF.md`", brief)
        self.assertNotIn("{{", brief)
        rules = (self.home / "AGENTS.md").read_text(encoding="utf-8")
        for title in ("Change the structure with the skill.", "Facts that outlive a task go in `FACTS.md`.", "Brief from `BRIEF.md`."):
            self.assertIn("- **%s**" % title, rules)
        self.assertIn("When Ana is talking to you in this session, you are that session", rules)
        self.assertEqual(self.found("LNK001"), [])

    def test_upgrade_adds_the_brief_file_and_never_replaces_one(self):
        settings_path = self.home / "_workspace" / "settings.json"
        rules_path = self.home / "AGENTS.md"
        titles = [title for step in ws.UPGRADES if step["version"] == "0.5.0" for title in step["rules"]]

        def make_old():
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings["skill_version"] = "0.4.0"
            settings_path.write_text(json.dumps(settings), encoding="utf-8")
            kept = [line for line in rules_path.read_text(encoding="utf-8").splitlines(keepends=True)
                    if not any("**%s**" % title in line for title in titles) and "agent-workspace-setup:rules-0.5.0" not in line
                    and "Added with version 0.5.0" not in line and "On rule 8" not in line]
            rules_path.write_text("".join(kept), encoding="utf-8")

        make_old()
        (self.home / "BRIEF.md").unlink()
        before = manifest(self.home)
        code, output = run("upgrade", "--dry-run", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("`BRIEF.md`: a new file at the top of the workspace", output)
        self.assertIn("On rule 8, one writer per work folder", output)
        self.assertEqual(before, manifest(self.home))
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("# How to brief Ana", (self.home / "BRIEF.md").read_text(encoding="utf-8"))
        added = rules_path.read_text(encoding="utf-8")
        for title in titles:
            self.assertEqual(added.count("**%s**" % title), 1, title)
        self.assertEqual(self.found("LNK001"), [])
        make_old()
        (self.home / "BRIEF.md").write_text("my own notes\n", encoding="utf-8")
        code, output = run("upgrade", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertNotIn("`BRIEF.md`: a new file", output)
        self.assertEqual((self.home / "BRIEF.md").read_text(encoding="utf-8"), "my own notes\n")

    def test_the_weekly_status_counts_the_proposals(self):
        def proposed():
            run("routine", "run", "--kind", "weekly", "--runner", "manual", "--home", self.home)
            found = re.search(r"\*\*Proposed changes:\*\* (\d+)\. Say \"review my workspace\"", (self.home / "STATUS.md").read_text(encoding="utf-8"))
            return int(found.group(1)) if found else 0

        first = proposed()
        self.assertEqual(first, len(re.findall(r"^\d+\. ", run("review", "--home", self.home)[1], re.M)))
        (self.inbox / "scan.pdf").write_bytes(b"x")
        self.assertEqual(proposed(), first + 1)

    def test_the_routine_plan_says_stop_before_anything_is_scheduled(self):
        code, output = run("routine", "plan", "--runner", "cowork", "--home", self.home)
        self.assertEqual(code, 0, output)
        self.assertIn("**Next:** Stop here and show this to the owner. Asking for a check is not yet a yes to this job", output)


class PackageTests(unittest.TestCase):
    """The skill's own text: what a host loads and what a person reads."""

    def markdown(self):
        return [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))

    def frontmatter(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        block = text.split("---\n", 2)[1]
        fields, current = {}, None
        for line in block.splitlines():
            match = re.match(r"^([a-z-]+):\s*(.*)$", line)
            if match:
                current = match.group(1)
                fields[current] = "" if match.group(2) in (">-", ">", "|") else match.group(2)
            elif current:
                fields[current] = (fields[current] + " " + line.strip()).strip()
        return fields

    def test_frontmatter_fits_every_host(self):
        fields = self.frontmatter()
        self.assertEqual(fields["name"], SKILL_DIR.name)
        self.assertRegex(fields["name"], r"^[a-z0-9-]{1,64}$")
        self.assertLessEqual(len(fields["description"]), 1024)
        self.assertLessEqual(len(fields["compatibility"]), 500)
        allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        self.assertLessEqual(set(fields), allowed)
        first = fields["description"][:200]
        self.assertIn("picks up where the last one stopped", first)

    def test_the_license_is_mit_and_travels_with_the_skill(self):
        repo_copy = (REPO / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(repo_copy.startswith("MIT License\n"))
        self.assertEqual((SKILL_DIR / "LICENSE.txt").read_text(encoding="utf-8"), repo_copy)
        self.assertTrue(self.frontmatter()["license"].startswith("MIT"))

    def test_the_script_stays_offline(self):
        """The public README promises this: no network code, and no other program is started."""
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        banned = {"socket", "ssl", "http", "http.client", "urllib.request", "ftplib", "smtplib", "telnetlib",
                  "xmlrpc", "xmlrpc.client", "requests", "subprocess", "multiprocessing", "webbrowser"}
        self.assertEqual(sorted(imported & banned), [])
        self.assertNotIn("os.system(", SCRIPT.read_text(encoding="utf-8"))

    def test_skill_md_stays_short(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(text.encode("utf-8")), 19500)
        self.assertLess(len(text.splitlines()), 192)

    def test_the_docs_name_the_current_version(self):
        modes = (SKILL_DIR / "references" / "modes.md").read_text(encoding="utf-8")
        self.assertIn('"skill_version": "%s"' % ws.__version__, modes)
        path = REPO / "public" / "CHANGELOG.md"  # in the public repo the same file sits at the top
        changelog = (path if path.is_file() else REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## %s" % ws.__version__, changelog)

    def test_no_file_still_says_a_work_folder_has_three_files(self):
        for path in self.markdown():
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?i)three small files", str(path))
            self.assertNotIn("`AGENTS.md`, `CLAUDE.md` and `HANDOFF.md`", text, str(path))
            self.assertNotIn("`HANDOFF.md`, `AGENTS.md` and a one-line `CLAUDE.md`", text, str(path))

    def test_every_local_link_resolves(self):
        for path in self.markdown():
            text = ws.strip_code(path.read_text(encoding="utf-8"))
            for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", text):
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                self.assertTrue((path.parent / target.split("#")[0]).exists(), "%s links to %s" % (path.name, target))

    def test_every_check_rule_is_explained(self):
        modes = (SKILL_DIR / "references" / "modes.md").read_text(encoding="utf-8")
        for rule in ws.RULES:
            self.assertIn("| %s |" % rule, modes)

    def test_every_command_is_in_skill_md(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        parser = ws.build_parser()
        commands = next(a for a in parser._actions if a.dest == "command").choices
        missing = [name for name in commands if ("`%s" % name) not in text]
        self.assertEqual(missing, [])

    def test_the_skill_folder_stays_small(self):
        files = [p for p in SKILL_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"]
        self.assertLessEqual(len(files), 20, [str(p.relative_to(SKILL_DIR)) for p in files])

    def test_no_em_dashes_in_the_skill_text(self):
        for path in self.markdown():
            self.assertNotIn("\u2014", path.read_text(encoding="utf-8"), str(path))

    def test_every_template_is_used_by_the_script(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for path in (SKILL_DIR / "assets" / "templates").glob("*.md"):
            self.assertIn('"%s"' % path.name, script, path.name)


if __name__ == "__main__":
    unittest.main()
