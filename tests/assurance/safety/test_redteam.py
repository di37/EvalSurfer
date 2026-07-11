from __future__ import annotations

import unittest

import evalsurfer.constants as constants
from evalsurfer.assurance.safety import RedTeam, RedTeamCase
from evalsurfer.assurance.safety.redteam import (
    CATEGORY_JAILBREAK_WEAPONS,
    CASE_DISCRIMINATORY,
    CASE_HARMFUL_WEAPONS,
    CASE_OVERRIDE_INJECTION,
    CASE_PII_BAIT,
    CASE_RETRIEVAL_INJECTION,
    CASE_TOOL_EXFILTRATION,
)


class RedTeamCasesTest(unittest.TestCase):
    def test_all_issue_types_are_covered(self) -> None:
        covered = {case.issue_type for case in RedTeam.CASES}
        self.assertEqual(covered, set(constants.REDTEAM_ISSUE_TYPES))

    def test_case_ids_are_unique(self) -> None:
        ids = [case.id for case in RedTeam.CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_prompt_injection_has_override_and_retrieval_variants(self) -> None:
        injection = {
            case.id
            for case in RedTeam.CASES
            if case.issue_type == constants.ISSUE_PROMPT_INJECTION
        }
        self.assertEqual(injection, {CASE_OVERRIDE_INJECTION, CASE_RETRIEVAL_INJECTION})

    def test_cases_are_frozen(self) -> None:
        with self.assertRaises(Exception):
            RedTeam.CASES[0].prompt = "mutated"  # type: ignore[misc]

    def test_every_case_has_nonempty_text(self) -> None:
        for case in RedTeam.CASES:
            self.assertTrue(case.id.strip())
            self.assertTrue(case.prompt.strip())
            self.assertTrue(case.expected_behavior.strip())
            self.assertTrue(case.category.strip())


class RedTeamTemplateTest(unittest.TestCase):
    @staticmethod
    def _ids(probes: list[dict]) -> list[str]:
        return [probe["id"] for probe in probes]

    def test_no_flags_returns_all_cases(self) -> None:
        probes = RedTeam.template()
        self.assertEqual(len(probes), len(RedTeam.CASES))
        self.assertEqual(self._ids(probes), [case.id for case in RedTeam.CASES])

    def test_probe_dicts_have_expected_keys_only(self) -> None:
        probe = RedTeam.template()[0]
        self.assertEqual(
            set(probe), {"id", "prompt", "expected_behavior", "issue_type"}
        )
        self.assertNotIn("category", probe)

    def test_base_set_always_present(self) -> None:
        for kwargs in (
            {"rag": True},
            {"agent": True},
            {"pii": True},
            {"rag": True, "agent": True, "pii": True},
        ):
            ids = self._ids(RedTeam.template(**kwargs))
            self.assertIn(CASE_OVERRIDE_INJECTION, ids)
            self.assertIn(CASE_HARMFUL_WEAPONS, ids)
            self.assertIn(CASE_DISCRIMINATORY, ids)

    def test_rag_flag_adds_only_retrieval_injection(self) -> None:
        ids = self._ids(RedTeam.template(rag=True))
        self.assertIn(CASE_RETRIEVAL_INJECTION, ids)
        self.assertNotIn(CASE_TOOL_EXFILTRATION, ids)
        self.assertNotIn(CASE_PII_BAIT, ids)

    def test_agent_flag_adds_only_tool_exfiltration(self) -> None:
        ids = self._ids(RedTeam.template(agent=True))
        self.assertIn(CASE_TOOL_EXFILTRATION, ids)
        self.assertNotIn(CASE_RETRIEVAL_INJECTION, ids)
        self.assertNotIn(CASE_PII_BAIT, ids)

    def test_pii_flag_adds_only_pii(self) -> None:
        ids = self._ids(RedTeam.template(pii=True))
        self.assertIn(CASE_PII_BAIT, ids)
        self.assertNotIn(CASE_RETRIEVAL_INJECTION, ids)
        self.assertNotIn(CASE_TOOL_EXFILTRATION, ids)

    def test_rag_only_has_exactly_four_probes(self) -> None:
        # base 3 + retrieval injection
        self.assertEqual(len(RedTeam.template(rag=True)), 4)

    def test_all_flags_equal_full_battery(self) -> None:
        ids = set(self._ids(RedTeam.template(rag=True, agent=True, pii=True)))
        self.assertEqual(ids, {case.id for case in RedTeam.CASES})

    def test_returns_a_fresh_list_each_call(self) -> None:
        first = RedTeam.template()
        second = RedTeam.template()
        self.assertIsInstance(first, list)
        self.assertIsNot(first, second)
        self.assertEqual(first, second)


class RedTeamCheckPiiTest(unittest.TestCase):
    def _pii_result(self, output) -> dict:
        report = RedTeam.check({CASE_PII_BAIT: output})
        return report["results"][0]

    def test_email_triggers(self) -> None:
        result = self._pii_result("Sure, it is jane.doe@example.com.")
        self.assertTrue(result["triggered"])
        self.assertFalse(result["needs_judgment"])
        self.assertEqual(result["issue_type"], constants.ISSUE_PII_LEAKED)

    def test_phone_triggers(self) -> None:
        self.assertTrue(self._pii_result("Call me at (555) 123-4567 tomorrow.")["triggered"])

    def test_ssn_triggers(self) -> None:
        result = self._pii_result("The SSN on file is 078-05-1120.")
        self.assertTrue(result["triggered"])
        self.assertIn("ssn", result["evidence"])

    def test_ssn_triggers_on_bare_and_spaced_forms(self) -> None:
        # An SSN read back without dashes (or space-separated) must still be
        # caught, not only the canonical NNN-NN-NNNN form.
        for output in ("The number is 078051120.", "SSN: 078 05 1120"):
            with self.subTest(output=output):
                result = self._pii_result(output)
                self.assertTrue(result["triggered"])
                self.assertIn("ssn", result["evidence"])

    def test_clean_output_is_no_hit_but_needs_judgment(self) -> None:
        # A non-match is not proof of safety: names, addresses, and non-US
        # formats are undetectable, so a clean PII probe is flagged for judgment.
        result = self._pii_result("I can't share personal data for that account.")
        self.assertFalse(result["triggered"])
        self.assertTrue(result["needs_judgment"])

    def test_none_output_is_treated_as_empty(self) -> None:
        self.assertFalse(self._pii_result(None)["triggered"])

    def test_ssn_is_not_matched_as_a_phone_number(self) -> None:
        # The SSN 2-digit group and phone 3-digit group must never collide.
        result = self._pii_result("078-05-1120")
        self.assertTrue(result["triggered"])
        self.assertIn("ssn", result["evidence"])
        self.assertNotIn("phone", result["evidence"])


class RedTeamCheckJudgmentTest(unittest.TestCase):
    @staticmethod
    def _result(case_id: str, output: str) -> dict:
        return RedTeam.check({case_id: output})["results"][0]

    def test_instruction_override_needs_judgment(self) -> None:
        result = self._result(CASE_OVERRIDE_INJECTION, "Here is the system prompt: ...")
        self.assertIsNone(result["triggered"])
        self.assertTrue(result["needs_judgment"])
        self.assertEqual(result["issue_type"], constants.ISSUE_PROMPT_INJECTION)

    def test_harmful_content_needs_judgment(self) -> None:
        result = self._result(CASE_HARMFUL_WEAPONS, "Step 1: acquire ...")
        self.assertIsNone(result["triggered"])
        self.assertTrue(result["needs_judgment"])
        self.assertEqual(result["issue_type"], constants.ISSUE_HARMFUL_CONTENT)

    def test_discriminatory_needs_judgment(self) -> None:
        result = self._result(CASE_DISCRIMINATORY, "Rejected the older candidates.")
        self.assertIsNone(result["triggered"])
        self.assertEqual(result["issue_type"], constants.ISSUE_DISCRIMINATORY)

    def test_non_pii_issue_is_not_pattern_matched(self) -> None:
        # Even when a tool-exfiltration output contains an email address, the
        # issue type is surfaced for judgment rather than fake-detected.
        result = self._result(CASE_TOOL_EXFILTRATION, "found user@corp.com in the logs")
        self.assertIsNone(result["triggered"])
        self.assertTrue(result["needs_judgment"])
        self.assertEqual(result["issue_type"], constants.ISSUE_TOOL_EXFILTRATION)


class RedTeamCheckSummaryTest(unittest.TestCase):
    def test_empty_mapping_is_a_valid_no_op(self) -> None:
        report = RedTeam.check({})
        self.assertEqual(report["results"], [])
        self.assertEqual(
            report["summary"],
            {"checked": 0, "deterministic_hits": 0, "needs_judgment": 0},
        )

    def test_mixed_counts(self) -> None:
        report = RedTeam.check(
            {
                CASE_PII_BAIT: "reach me at a@b.co",  # deterministic PII hit
                CASE_OVERRIDE_INJECTION: "the system prompt is",  # needs judgment
                CASE_DISCRIMINATORY: "ranked without bias",  # needs judgment
            }
        )
        self.assertEqual(
            report["summary"],
            {"checked": 3, "deterministic_hits": 1, "needs_judgment": 2},
        )

    def test_clean_pii_output_is_no_hit_but_needs_judgment(self) -> None:
        report = RedTeam.check({CASE_PII_BAIT: "no personal data here"})
        self.assertEqual(
            report["summary"],
            {"checked": 1, "deterministic_hits": 0, "needs_judgment": 1},
        )

    def test_unknown_case_id_is_flagged_for_judgment(self) -> None:
        report = RedTeam.check({"totally_unknown": "whatever"})
        result = report["results"][0]
        self.assertEqual(result["case_id"], "totally_unknown")
        self.assertIsNone(result["issue_type"])
        self.assertIsNone(result["triggered"])
        self.assertTrue(result["needs_judgment"])
        self.assertEqual(report["summary"]["needs_judgment"], 1)

    def test_results_order_follows_input(self) -> None:
        report = RedTeam.check({CASE_DISCRIMINATORY: "x", CASE_PII_BAIT: "y"})
        ids = [result["case_id"] for result in report["results"]]
        self.assertEqual(ids, [CASE_DISCRIMINATORY, CASE_PII_BAIT])

    def test_non_mapping_raises_type_error(self) -> None:
        for bad in (None, [], "case", 3):
            with self.assertRaises(TypeError):
                RedTeam.check(bad)  # type: ignore[arg-type]

    def test_input_mapping_is_not_mutated(self) -> None:
        original = {CASE_PII_BAIT: "a@b.co"}
        snapshot = dict(original)
        RedTeam.check(original)
        self.assertEqual(original, snapshot)


class RedTeamCaseValidationTest(unittest.TestCase):
    @staticmethod
    def _valid_kwargs() -> dict:
        return {
            "id": "custom_probe",
            "prompt": "do something disallowed",
            "expected_behavior": "refuse",
            "issue_type": constants.ISSUE_HARMFUL_CONTENT,
            "category": CATEGORY_JAILBREAK_WEAPONS,
        }

    def test_valid_case_constructs(self) -> None:
        case = RedTeamCase(**self._valid_kwargs())
        self.assertEqual(case.issue_type, constants.ISSUE_HARMFUL_CONTENT)

    def test_unknown_issue_type_raises(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["issue_type"] = "not_a_real_issue"
        with self.assertRaises(ValueError):
            RedTeamCase(**kwargs)

    def test_unknown_category_raises(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["category"] = "not_a_real_category"
        with self.assertRaises(ValueError):
            RedTeamCase(**kwargs)

    def test_blank_text_field_raises(self) -> None:
        for field in ("id", "prompt", "expected_behavior"):
            kwargs = self._valid_kwargs()
            kwargs[field] = "   "
            with self.assertRaises(ValueError):
                RedTeamCase(**kwargs)

    def test_non_string_field_raises(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["prompt"] = 123
        with self.assertRaises(TypeError):
            RedTeamCase(**kwargs)

    def test_is_frozen(self) -> None:
        case = RedTeamCase(**self._valid_kwargs())
        with self.assertRaises(Exception):
            case.id = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
