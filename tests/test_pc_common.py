"""PC 실행기 공통 부분(pc_common.py)과 통합 실행기(run_pc_all.py) 테스트. git·네트워크 없이 돈다.
실행: 저장소 최상위에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pc_common as C  # noqa: E402
import run_pc_all as A  # noqa: E402


def fake_git(answers):
    def git(args, cwd):
        for key, val in answers.items():
            if tuple(args[:len(key)]) == key:
                return val
        return 0, ""
    return git


class Preflight(unittest.TestCase):
    def run_pre(self, per_repo, push_ok=True):
        pushed = []

        def git(args, cwd):
            stuck, unp = per_repo[cwd]
            if args[:1] == ["diff"]:
                return 0, ",".join(stuck)
            if args[:1] == ["rev-list"]:
                return 0, str(unp)
            return 0, ""

        def push(cwd):
            pushed.append(cwd)
            return push_ok

        return C.preflight([("코드", "code"), ("DB", "db")], git=git, push=push), pushed

    def test_clean(self):
        self.assertEqual(self.run_pre({"code": ([], 0), "db": ([], 0)}), (True, []))

    def test_pushes_leftover_first(self):
        self.assertEqual(self.run_pre({"code": ([], 0), "db": ([], 2)}), (True, ["db"]))

    def test_stops_when_push_fails_or_conflict(self):
        self.assertFalse(self.run_pre({"code": ([], 0), "db": ([], 1)}, push_ok=False)[0])
        ok, pushed = self.run_pre({"code": (["a.sqlite"], 0), "db": ([], 0)})
        self.assertEqual((ok, pushed), (False, []))


class PcName(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.patches = [mock.patch.dict(os.environ, {"GOSI_PC_NAME": ""}), mock.patch.object(C, "local_dir", return_value=self.base)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_file_and_env(self):
        (self.base / "pc_name.txt").write_text("PCwj", encoding="utf-8")
        self.assertEqual(C.pc_name(), "PCwj")
        with mock.patch.dict(os.environ, {"GOSI_PC_NAME": "PCyw"}):
            self.assertEqual(C.pc_name(), "PCyw")

    def test_bad_names_rejected_and_asked_once(self):
        for bad in ("", "a", "PC wj", "x" * 30):
            self.assertFalse(C.save_pc_name(bad))
        self.assertEqual(C.ensure_pc_name(ask=lambda m: " PCyw ", interactive=True), "PCyw")
        self.assertEqual(C.ensure_pc_name(ask=lambda m: self.fail("다시 묻지 않아야 한다"), interactive=True), "PCyw")
        (self.base / "pc_name.txt").unlink()
        self.assertEqual(C.ensure_pc_name(interactive=False), "")


class RunLog(unittest.TestCase):
    def test_append_recent_summary(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x" / "pc_runs.jsonl"
            self.assertEqual(C.recent_records(f), [])
            rec = C.new_record("PCwj", "v1", "eiass")
            rec["stage"], rec["result"] = "push", "ok"
            C.append_record(f, rec)
            C.append_record(f, dict(rec, pc="PCyw"))
            got = C.recent_records(f, 5)
            self.assertEqual([r["pc"] for r in got], ["PCwj", "PCyw"])
            self.assertEqual(got[0]["job"], "eiass")
            self.assertIn("PCwj", C.summary(got[0]))


class RunAll(unittest.TestCase):
    def test_selected_and_job_args(self):
        self.assertEqual(A.selected([]), ["gosi", "eiass"])
        self.assertEqual(A.selected(["--only", "eiass"]), ["eiass"])
        with self.assertRaises(SystemExit):
            A.selected(["--only", "news"])
        argv = ["--no-git", "--reread"]
        self.assertEqual(A.job_args("gosi", argv), ["--no-git", "--reread"])
        self.assertEqual(A.job_args("eiass", argv), ["--no-git"])  # --reread 는 고시공고에만 의미가 있다

    def test_runs_both_even_if_first_fails(self):
        calls = []

        def fake_call(cmd, cwd=None, env=None):
            if "pip" in cmd:  # requirements 설치는 작업 호출이 아니다
                return 0
            calls.append((Path(cwd).name, cmd[-1] if cmd[-1].startswith("--") else cmd[2], env["GOSI_PC_NAME"]))
            return 3 if Path(cwd).name == "gosi" else 0

        with mock.patch.object(A.pc_common, "ensure_pc_name", return_value="PCwj"),              mock.patch.object(A.subprocess, "call", side_effect=fake_call):
            rc = A.main(["--no-git"])
        self.assertEqual(rc, 1)
        self.assertEqual([c[0] for c in calls], ["gosi", "eiass"])
        self.assertTrue(all(c[2] == "PCwj" for c in calls))

    def test_requirements_installed_before_each_job(self):
        calls = []
        with mock.patch.object(A.pc_common, "ensure_pc_name", return_value="PCwj"),              mock.patch.object(A.subprocess, "call", side_effect=lambda cmd, cwd=None, env=None: calls.append(cmd) or 0):
            A.main(["--no-git"])
        pips = [c for c in calls if "pip" in c]
        self.assertEqual(len(pips), 2)  # gosi, eiass 각각 requirements.txt
        self.assertTrue(all(c[-1].endswith("requirements.txt") for c in pips))

    def test_stops_without_pc_name(self):
        with mock.patch.object(A.pc_common, "ensure_pc_name", return_value=""):
            self.assertEqual(A.main(["--no-git"]), 2)


if __name__ == "__main__":
    unittest.main()
