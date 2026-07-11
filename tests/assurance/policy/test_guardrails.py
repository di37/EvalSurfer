from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest

import evalsurfer.constants as constants
from evalsurfer.interface.cli.main import main as cli_main
from evalsurfer.assurance.policy.guardrails import GuardrailPolicy, Guardrails


def _report(*, decision="pass", safety=9.0, coverage=0.8, issues=()):
    """Build a minimal report the guardrails read."""
    return {
        "decision": decision,
        "overall": {"score": 8.5, "decision": decision},
        "assurance": {"safety": {"score": safety, "criteria": []}},
        "coverage": {"score": coverage},
        "top_issues": list(issues),
    }


_CRITICAL_ISSUE = {"severity": "critical", "criterion_id": "harmful_content", "description": "unsafe"}


class GuardrailPolicyValidationTest(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = GuardrailPolicy.from_mapping({})
        self.assertEqual(policy.min_decision, constants.DECISION_PASS_WITH_FIXES)
        self.assertIsNone(policy.min_safety)
        self.assertEqual(policy.sensitive_paths, ())
        self.assertFalse(policy.block_on_critical_issue)

    def test_full_policy_round_trips(self) -> None:
        policy = GuardrailPolicy.from_mapping(
            {
                "min_decision": "pass",
                "min_safety": 8.0,
                "coverage_floor": 0.6,
                "block_on_critical_issue": True,
                "max_fix_attempts": 3,
                "sensitive_paths": ["*auth/*"],
            }
        )
        self.assertEqual(policy.min_decision, "pass")
        self.assertEqual(policy.min_safety, 8.0)
        self.assertEqual(policy.coverage_floor, 0.6)
        self.assertTrue(policy.block_on_critical_issue)
        self.assertEqual(policy.max_fix_attempts, 3)
        self.assertEqual(policy.sensitive_paths, ("*auth/*",))

    def test_rejects_unknown_field(self) -> None:
        with self.assertRaises(ValueError):
            GuardrailPolicy.from_mapping({"nope": 1})

    def test_rejects_bad_decision(self) -> None:
        with self.assertRaises(ValueError):
            GuardrailPolicy.from_mapping({"min_decision": "ship_it"})

    def test_rejects_out_of_range_numbers(self) -> None:
        with self.assertRaises(ValueError):
            GuardrailPolicy.from_mapping({"min_safety": 11})
        with self.assertRaises(ValueError):
            GuardrailPolicy.from_mapping({"coverage_floor": 1.5})

    def test_rejects_boolean_safety(self) -> None:
        with self.assertRaises(TypeError):
            GuardrailPolicy.from_mapping({"min_safety": True})

    def test_rejects_non_positive_attempts(self) -> None:
        with self.assertRaises(ValueError):
            GuardrailPolicy.from_mapping({"max_fix_attempts": 0})
        with self.assertRaises(ValueError):
            GuardrailPolicy.from_mapping({"max_fix_attempts": True})

    def test_rejects_non_string_paths(self) -> None:
        with self.assertRaises(TypeError):
            GuardrailPolicy.from_mapping({"sensitive_paths": ["ok", 3]})


class GuardrailCheckTest(unittest.TestCase):
    FULL = GuardrailPolicy.from_mapping(
        {
            "min_decision": "pass",
            "min_safety": 8.0,
            "coverage_floor": 0.6,
            "block_on_critical_issue": True,
            "max_fix_attempts": 3,
            "sensitive_paths": ["*auth/*", "*.env*"],
        }
    )

    def test_clean_report_is_allowed(self) -> None:
        result = Guardrails.check(_report(), self.FULL, changed_files=["README.md"])
        self.assertTrue(result["allowed"])
        self.assertEqual(result["blocks"], [])
        self.assertFalse(result["human_review_required"])

    def test_decision_below_min_blocks(self) -> None:
        result = Guardrails.check(_report(decision="pass_with_fixes"), self.FULL)
        self.assertFalse(result["allowed"])
        self.assertTrue(any("below the minimum" in b for b in result["blocks"]))

    def test_safety_floor_blocks(self) -> None:
        result = Guardrails.check(_report(safety=6.0), self.FULL)
        self.assertFalse(result["allowed"])
        self.assertTrue(any("safety" in b for b in result["blocks"]))

    def test_coverage_floor_blocks(self) -> None:
        result = Guardrails.check(_report(coverage=0.3), self.FULL)
        self.assertFalse(result["allowed"])
        self.assertTrue(any("coverage" in b for b in result["blocks"]))

    def test_critical_issue_blocks_and_flags_review(self) -> None:
        result = Guardrails.check(_report(issues=[_CRITICAL_ISSUE]), self.FULL)
        self.assertFalse(result["allowed"])
        self.assertTrue(any("critical issue" in b for b in result["blocks"]))
        self.assertTrue(result["human_review_required"])  # ReviewGate also escalates

    def test_attempt_cap_blocks(self) -> None:
        result = Guardrails.check(_report(), self.FULL, attempt=4)
        self.assertFalse(result["allowed"])
        self.assertTrue(any("attempt 4" in b for b in result["blocks"]))
        # Within the cap is fine.
        self.assertTrue(Guardrails.check(_report(), self.FULL, attempt=3)["allowed"])

    def test_sensitive_path_forces_human_review(self) -> None:
        result = Guardrails.check(
            _report(), self.FULL, changed_files=["src/auth/login.py", "README.md"]
        )
        self.assertFalse(result["allowed"])
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["sensitive_paths_touched"], ["src/auth/login.py"])

    def test_path_match_is_case_insensitive(self) -> None:
        result = Guardrails.check(_report(), self.FULL, changed_files=["SRC/AUTH/x.py"])
        self.assertEqual(result["sensitive_paths_touched"], ["SRC/AUTH/x.py"])

    def test_does_not_mutate_report(self) -> None:
        report = _report()
        snapshot = json.loads(json.dumps(report))
        Guardrails.check(report, self.FULL, changed_files=["src/auth/x.py"])
        self.assertEqual(report, snapshot)

    def test_rejects_bad_types(self) -> None:
        with self.assertRaises(TypeError):
            Guardrails.check([], self.FULL)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            Guardrails.check(_report(), {"min_decision": "pass"})  # type: ignore[arg-type]


class GuardrailCliTest(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli_main(argv)
        return code, buf.getvalue()

    def _files(self, tmp, report, policy, changed=None):
        rpath = os.path.join(tmp, "report.json")
        ppath = os.path.join(tmp, "guardrails.json")
        with open(rpath, "w") as f:
            json.dump(report, f)
        with open(ppath, "w") as f:
            json.dump(policy, f)
        cpath = None
        if changed is not None:
            cpath = os.path.join(tmp, "changed.txt")
            with open(cpath, "w") as f:
                f.write("\n".join(changed))
        return rpath, ppath, cpath

    def test_gate_policy_allows_clean_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rpath, ppath, _ = self._files(tmp, _report(), {"min_decision": "pass"})
            code, out = self._run(["gate", rpath, "--policy", ppath])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(out)["allowed"])

    def test_gate_policy_blocks_on_sensitive_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rpath, ppath, cpath = self._files(
                tmp, _report(), {"sensitive_paths": ["*auth/*"]}, changed=["auth/x.py"]
            )
            code, out = self._run(
                ["gate", rpath, "--policy", ppath, "--changed-files", cpath]
            )
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(out)["allowed"])

    def test_gate_without_policy_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rpath, _, _ = self._files(tmp, _report(decision="fail"), {})
            code, out = self._run(["gate", rpath, "--min", "pass"])
            self.assertEqual(code, 1)
            self.assertIn("passed", json.loads(out))  # legacy Gate result shape


if __name__ == "__main__":
    unittest.main()
