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
                    "90_Inbox", "91_Projects/AGENTS.md", "92_Areas/AGENTS.md", "95_Data/AGENTS.md", "99_Archive",
                    "91_Projects/91.01_Duplex-renovation/AGENTS.md", "91_Projects/91.01_Duplex-renovation/HANDOFF.md",
                    "92_Areas/92.01_Bookkeeping/HANDOFF.md"):
            self.assertTrue((self.home / rel).exists(), rel)
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
        for name in ("10_Inbox", "11_Projects", "12_Areas", "15_Data", "19_Archive"):
            self.assertTrue((home / name).is_dir(), name)
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
        archived = self.home / "99_Archive" / "91.01_Duplex-renovation"
        self.assertEqual(self.key_of(archived), key)
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "archived")
        code, output = run("restore", "--home", self.home, "91.01")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.key_of(self.project()), key)
        self.assertEqual(ws.replay(self.ledger())[0][key]["state"], "active")

    def test_restore_returns_to_the_group_it_was_in(self):
        run("move", "--home", self.home, "91.01", "--to", "area")
        run("archive", "--home", self.home, "91.01")
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
        (self.home / "99_Archive" / "91.01_Duplex-renovation").mkdir()
        code, output = run("archive", "--home", self.home, "91.01")
        self.assertEqual(code, 1)
        code, output = run("archive", "--home", self.home, "91.55")
        self.assertEqual(code, 1)
        self.assertIn("**Next:**", output)

    def test_an_interrupted_move_is_settled_from_what_is_on_disk(self):
        key = self.key_of(self.project())
        target = self.home / "99_Archive" / "91.01_Duplex-renovation"
        ws.append_line(self.home / "_workspace" / "moves.jsonl", {
            "id": 1, "op": "archive", "number": "91.01", "key": key, "state": "pending",
            "from": "91_Projects/91.01_Duplex-renovation", "to": "99_Archive/91.01_Duplex-renovation",
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
        settings["private"] = ["99_Archive"]
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
                     "90_AI-Agents/90_Inbox/", "90_AI-Agents/99_Archive/"):
            self.assertIn(name, names)
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
                self.assertRegex(template, r"(?m)^\d+\. \*\*%s\*\*" % re.escape(title))

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
        self.assertLess(len(text.encode("utf-8")), 13500)
        self.assertLess(len(text.splitlines()), 140)

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
