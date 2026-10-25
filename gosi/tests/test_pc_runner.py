"""PC 수집 실행기(run_blocked_local.py)의 시작 전 점검과 PC 이름 처리 테스트. git·네트워크 없이 가짜 git 으로 돈다.
전제: PC 두 대(PCwj, PCyw)가 서로 다른 시간에 돈다 - 위험은 push 실패로 DB 가 한 PC 에만 남는 경우와 pull 충돌 상태뿐이다."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import run_blocked_local as R  # noqa: E402
from core import local_dir  # noqa: E402


def fake_git(answers):
    """answers: {명령 앞부분 튜플: (rc, out)}. 모르는 명령은 (0, '')."""
    def git(args, cwd):
        for key, val in answers.items():
            if tuple(args[:len(key)]) == key:
                return val
        return 0, ""
    return git


class GitProblems(unittest.TestCase):
    def test_clean_repo(self):
        stuck, unpushed = R.git_problems("x", git=fake_git({("rev-list",): (0, "0")}), exists=lambda p: False)
        self.assertEqual((stuck, unpushed), ([], 0))

    def test_unpushed_commits_are_counted(self):
        """한 PC 에서 push 가 실패해 남은 커밋."""
        stuck, unpushed = R.git_problems("x", git=fake_git({("rev-list",): (0, "2")}), exists=lambda p: False)
        self.assertEqual((stuck, unpushed), ([], 2))

    def test_no_upstream_is_not_a_problem(self):
        stuck, unpushed = R.git_problems("x", git=fake_git({("rev-list",): (128, "")}), exists=lambda p: False)
        self.assertEqual((stuck, unpushed), ([], 0))

    def test_rebase_in_progress_and_conflicts_block(self):
        git = fake_git({("rev-parse", "--git-path", "rebase-merge"): (0, ".git/rebase-merge"),
                        ("diff",): (0, "gosi/국내IP_전남.sqlite")})
        stuck, _ = R.git_problems("x", git=git, exists=lambda p: p.endswith("rebase-merge"))
        self.assertEqual(len(stuck), 2)
        self.assertIn("rebase-merge", stuck[0])
        self.assertIn("국내IP_전남.sqlite", stuck[1])


class Preflight(unittest.TestCase):
    def run_pre(self, per_repo, push_ok=True):
        pushed = []

        def git(args, cwd):
            st, unp = per_repo[cwd]
            if args[:1] == ["diff"]:
                return 0, "\n".join(st)
            if args[:1] == ["rev-list"]:
                return 0, str(unp)
            return 0, ""

        def push(cwd):
            pushed.append(cwd)
            return push_ok

        with mock.patch.object(R, "HERE", "code"), mock.patch.object(R, "DATA", "db"):
            ok = R.preflight(True, git=git, push=push)
        return ok, pushed

    def test_ok_when_clean(self):
        ok, pushed = self.run_pre({"code": ([], 0), "db": ([], 0)})
        self.assertEqual((ok, pushed), (True, []))

    def test_pushes_leftover_commits_first(self):
        ok, pushed = self.run_pre({"code": ([], 0), "db": ([], 1)})
        self.assertEqual((ok, pushed), (True, ["db"]))

    def test_stops_when_code_repo_push_fails(self):
        ok, pushed = self.run_pre({"code": ([], 1), "db": ([], 0)}, push_ok=False)
        self.assertFalse(ok)  # 코드 저장소는 자동으로 버리지 않는다

    def test_db_repo_push_failure_is_recovered(self):
        ok, pushed = self.run_pre({"code": ([], 0), "db": ([], 1)}, push_ok=False)
        self.assertTrue(ok)  # DB 저장소의 이 PC 결과는 버리고 원격 최신으로 맞춘 뒤 계속한다(pc_common.recover_db_repo)

    def test_stops_on_conflict(self):
        ok, pushed = self.run_pre({"code": (["a.sqlite"], 0), "db": ([], 0)})
        self.assertFalse(ok)
        self.assertEqual(pushed, [])

    def test_no_git_mode_skips(self):
        self.assertTrue(R.preflight(False))


class PcName(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"GOSI_PC_NAME": ""})
        self.env.start()
        self.patch_dir = mock.patch.object(local_dir, "local_dir", return_value=self.base)
        self.patch_dir.start()

    def tearDown(self):
        self.patch_dir.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_reads_file_and_env(self):
        (self.base / "pc_name.txt").write_text("PCwj\n", encoding="utf-8")
        self.assertEqual(local_dir.pc_name(), "PCwj")
        with mock.patch.dict(os.environ, {"GOSI_PC_NAME": "PCyw"}):
            self.assertEqual(local_dir.pc_name(), "PCyw")  # 환경변수가 우선

    def test_rejects_bad_names(self):
        for bad in ("", "a", "PC wj", "PC/wj", "x" * 30):
            (self.base / "pc_name.txt").write_text(bad, encoding="utf-8")
            self.assertEqual(local_dir.pc_name(), "", bad)
            self.assertFalse(local_dir.save_pc_name(bad))

    def test_asks_once_and_saves(self):
        self.assertEqual(R.ensure_pc_name(ask=lambda msg: " PCyw ", interactive=True), "PCyw")
        self.assertEqual((self.base / "pc_name.txt").read_text(encoding="utf-8").strip(), "PCyw")
        self.assertEqual(R.ensure_pc_name(ask=lambda msg: self.fail("다시 묻지 않아야 한다"), interactive=True), "PCyw")

    def test_non_interactive_without_name_stops(self):
        self.assertEqual(R.ensure_pc_name(interactive=False), "")


class RunLog(unittest.TestCase):
    def test_append_recent_and_summary(self):
        from core import pc_runlog
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "sub" / "pc_runs.jsonl"
            self.assertEqual(pc_runlog.recent(f), [])
            rec = pc_runlog.new_record("PCwj", "v1")
            rec["regions"] = {"경남": {"status": "ok", "minutes": 3.0}, "전남": {"status": "timeout", "minutes": 30.0}}
            rec["stage"], rec["result"] = "push", "ok"
            pc_runlog.append(f, rec)
            pc_runlog.append(f, dict(rec, pc="PCyw"))
            got = pc_runlog.recent(f, 5)
            self.assertEqual([r["pc"] for r in got], ["PCwj", "PCyw"])
            self.assertIn("ended", got[0])
            self.assertIn("문제 지역: 전남", pc_runlog.summary(got[0]))

    def test_main_leaves_local_record_when_stopped(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(local_dir, "local_dir", return_value=Path(d)),                  mock.patch.object(local_dir, "pc_name", return_value="PCwj"),                  mock.patch.object(R, "preflight", return_value=False),                  mock.patch("core.pnu.load_key", return_value="k"),                  mock.patch.object(R.pc_runlog, "recent", return_value=[]),                  mock.patch.object(R.os.path, "isdir", return_value=True):
                self.assertEqual(R.main(use_git=True), 1)
            lines = (Path(d) / "pc_runs_local.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("preflight", lines[0])


if __name__ == "__main__":
    unittest.main()
