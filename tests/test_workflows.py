"""워크플로 안전장치 점검: 멈춘 단계가 작업 전체 제한(340분)까지 끌고 가 저장 단계까지 날리는 일을 막는다."""
import os
import unittest

import yaml

WF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "workflows", "collect-gosigongo.yml")


def _collect_job():
    with open(WF, encoding="utf-8") as f:
        return yaml.safe_load(f)["jobs"]["collect"]


def _step(job, prefix):
    found = [s for s in job["steps"] if str(s.get("name", "")).startswith(prefix)]
    assert len(found) == 1, f"{prefix!r} 단계 {len(found)}개"
    return found[0]


class WorkflowSafetyTest(unittest.TestCase):
    def test_tesseract_install_is_time_boxed_and_optional(self):
        s = _step(_collect_job(), "Install tesseract")
        assert s["timeout-minutes"] <= 15
        assert s["continue-on-error"] is True
        assert "Acquire::Retries" in s["run"] and "Acquire::http::Timeout" in s["run"]


    def test_collect_step_ends_before_job_limit_so_commit_step_can_run(self):
        job = _collect_job()
        collect = _step(job, "Collect ")
        commit = _step(job, "Commit SQLite")
        assert collect["timeout-minutes"] + 10 <= job["timeout-minutes"]     # 저장 단계가 돌 여유
        assert str(commit["if"]).strip() == "always()"




if __name__ == "__main__":
    unittest.main()
