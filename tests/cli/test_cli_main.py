from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest

from evalsurfer.interface.cli.main import main


def run(argv: list[str]) -> int:
    """Run the CLI with its stdout suppressed, returning the exit code."""
    with contextlib.redirect_stdout(io.StringIO()):
        return main(argv)


def _write(tmp: str, name: str, data: object) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file)
    return path


class CliMainTest(unittest.TestCase):
    def test_evaluate_validate_gate_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = _write(tmp, "s.json", {"sample": {"answer": "hi"}, "scores": {"correctness_accuracy": 5}})
            report = os.path.join(tmp, "r.json")
            self.assertEqual(run(["evaluate", sample, "--out", report]), 0)
            self.assertEqual(run(["validate", report]), 0)
            # a report with a pass_with_fixes/pass decision clears the default bar
            self.assertEqual(run(["gate", report, "--min", "fail"]), 0)

    def test_validate_rejects_bad_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = _write(tmp, "bad.json", {"overall": {"score": 99, "decision": "great"}})
            self.assertEqual(run(["validate", bad]), 1)

    def test_gate_below_minimum_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _write(tmp, "r.json", {"overall": {"score": 6.0, "decision": "pass_with_fixes"}, "pillars": {}, "decision": "pass_with_fixes", "top_issues": []})
            self.assertEqual(run(["gate", report, "--min", "pass"]), 1)

    def test_redteam_template_and_check(self) -> None:
        self.assertEqual(run(["redteam-template", "--rag", "--pii"]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            outputs = _write(tmp, "o.json", {"pii_readback": "reach me at a@b.com"})
            self.assertEqual(run(["redteam-check", outputs]), 0)

    def test_trajectory_and_plan_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            traj = _write(tmp, "t.json", {"actual": {"tool_calls": [{"name": "search"}]}, "expected": {"required_tools": ["search"]}})
            self.assertEqual(run(["trajectory", traj]), 0)
            sample = _write(tmp, "s.json", {"sample": {"answer": "hi"}})
            self.assertEqual(run(["plan", sample]), 0)
            traces = _write(tmp, "tr.json", {"traces": [{"request_started_at": "2026-07-08T12:00:00Z", "response_completed_at": "2026-07-08T12:00:01Z"}]})
            self.assertEqual(run(["metrics", traces]), 0)

    def test_calibrate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = _write(tmp, "c.json", {
                "name": "rag-fail",
                "signals": {"answer": True, "retrieved_context": True},
                "expected_applicable_pillars": ["quality", "safety"],
                "expected_score_ranges": {"groundedness_faithfulness": [1, 2]},
                "expected_decision": "fail",
                "expected_top_issue_severity": "critical",
                "expected_safety_escalation": False,
                "judge_reports": [
                    {"decision": "fail", "overall": {"score": 4.0}, "pillars": {}, "top_issues": []},
                    {"decision": "pass_with_fixes", "overall": {"score": 6.5}, "pillars": {}, "top_issues": []},
                ],
            })
            self.assertEqual(run(["calibrate", case]), 0)

    def test_missing_file_exits_one(self) -> None:
        self.assertEqual(run(["evaluate", "does-not-exist.json"]), 1)


if __name__ == "__main__":
    unittest.main()
