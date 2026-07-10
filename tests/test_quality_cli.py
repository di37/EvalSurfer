from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
import os
import tempfile
import unittest

from evalsurfer.cli.quality import build_report, main


class QualityBuildReportTest(unittest.TestCase):
    def test_retrieval_section(self) -> None:
        report = build_report(
            {
                "retrieval": {
                    "cases": [
                        {"retrieved": ["d1", "d2"], "relevant": ["d1"]},
                        {"retrieved": ["d3", "d1"], "relevant": ["d1"]},
                    ]
                }
            }
        )
        section = report["retrieval"]
        self.assertEqual(section["query_count"], 2)
        self.assertEqual(section["mean_recall_at_k"], 1.0)
        self.assertEqual(section["mrr"], 0.75)

    def test_retrieval_accepts_integer_ids(self) -> None:
        report = build_report(
            {"retrieval": {"cases": [{"retrieved": [1, 2, 3], "relevant": [2]}]}}
        )
        self.assertEqual(report["retrieval"]["mrr"], 0.5)

    def test_match_extraction(self) -> None:
        report = build_report(
            {
                "match": {
                    "predictions": ["The Cat.", "dog"],
                    "references": ["cat", "dog"],
                    "task": "extraction",
                }
            }
        )
        section = report["match"]
        self.assertEqual(section["task"], "extraction")
        self.assertEqual(section["exact_match_accuracy"], 1.0)
        self.assertEqual(section["count"], 2)

    def test_match_classification(self) -> None:
        report = build_report(
            {
                "match": {
                    "predictions": ["pos", "neg", "pos", "pos"],
                    "references": ["pos", "neg", "neg", "pos"],
                    "task": "classification",
                    "average": "macro",
                }
            }
        )
        section = report["match"]
        self.assertEqual(section["task"], "classification")
        self.assertEqual(section["accuracy"], 0.75)
        self.assertEqual(section["average"], "macro")

    def test_match_unknown_task_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_report(
                {"match": {"predictions": ["a"], "references": ["a"], "task": "weird"}}
            )

    def test_text_section_task_defaults(self) -> None:
        report = build_report(
            {
                "text": {
                    "task": "translation",
                    "items": [{"candidate": "the cat", "references": ["the cat"]}],
                }
            }
        )
        section = report["text"]
        self.assertEqual(section["metrics"], ["bleu"])  # translation -> BLEU
        self.assertEqual(section["items"][0]["bleu"], 1.0)
        self.assertEqual(section["corpus_bleu"], 1.0)

    def test_text_multi_reference_takes_best(self) -> None:
        report = build_report(
            {
                "text": {
                    "items": [
                        {"candidate": "the cat sat", "references": ["a dog", "the cat sat"]}
                    ],
                    "metrics": ["rouge_l"],
                }
            }
        )
        self.assertEqual(report["text"]["items"][0]["rouge_l"]["f1"], 1.0)

    def test_text_missing_reference_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_report({"text": {"items": [{"candidate": "x"}]}})

    def test_text_empty_metrics_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_report(
                {"text": {"items": [{"candidate": "a", "reference": "a"}], "metrics": []}}
            )

    def test_text_unknown_metric_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_report(
                {
                    "text": {
                        "items": [{"candidate": "a", "reference": "a"}],
                        "metrics": ["bertscore"],
                    }
                }
            )

    def test_requires_a_known_section(self) -> None:
        with self.assertRaises(ValueError):
            build_report({"unknown": {}})

    def test_rejects_non_object(self) -> None:
        with self.assertRaises(ValueError):
            build_report([1, 2, 3])


class QualityMainTest(unittest.TestCase):
    def test_main_reads_file_and_writes_output(self) -> None:
        payload = {"retrieval": {"cases": [{"retrieved": ["d1"], "relevant": ["d1"]}]}}
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "in.json")
            out_path = os.path.join(tmp, "out.json")
            with open(in_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            exit_code = main([in_path, "--output", out_path, "--pretty"])
            self.assertEqual(exit_code, 0)
            with open(out_path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(written["retrieval"]["mean_recall_at_k"], 1.0)

    def test_main_reports_error_on_missing_file(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["does-not-exist.json"])
        self.assertEqual(exit_code, 1)
        self.assertIn("error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
