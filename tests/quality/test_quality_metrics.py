from __future__ import annotations

import unittest

from evalsurfer.metrics.quality.matching import ClassificationReport, MatchMetrics
from evalsurfer.metrics.quality.retrieval import (
    RetrievalCase,
    RetrievalMetrics,
    RetrievalSummary,
)
from evalsurfer.metrics.quality.text import RougeScore, TextMetrics
from evalsurfer.metrics.quality.tokenize import (
    light_stem,
    ngrams,
    normalize_answer,
    normalized_tokens,
    tokenize,
)


class TokenizeTest(unittest.TestCase):
    def test_tokenize_lowercases_and_drops_punctuation(self) -> None:
        self.assertEqual(tokenize("Hello, World!"), ["hello", "world"])
        self.assertEqual(tokenize(""), [])

    def test_tokenize_rejects_non_string(self) -> None:
        with self.assertRaises(TypeError):
            tokenize(["not", "a", "string"])  # type: ignore[arg-type]

    def test_normalize_answer_squad_style(self) -> None:
        self.assertEqual(normalize_answer("The quick, brown fox."), "quick brown fox")
        self.assertEqual(normalize_answer("A an THE"), "")
        self.assertEqual(normalized_tokens("The Cat."), ["cat"])

    def test_ngrams(self) -> None:
        self.assertEqual(ngrams(["a", "b", "c"], 2), [("a", "b"), ("b", "c")])
        self.assertEqual(ngrams(["a"], 2), [])
        with self.assertRaises(ValueError):
            ngrams(["a", "b"], 0)

    def test_light_stem_strips_common_suffixes(self) -> None:
        self.assertEqual(light_stem("walked"), "walk")
        self.assertEqual(light_stem("cats"), "cat")
        self.assertEqual(light_stem("quickly"), "quick")
        self.assertEqual(light_stem("cat"), "cat")  # too short to strip further


class RetrievalMetricsTest(unittest.TestCase):
    def test_recall_at_k(self) -> None:
        self.assertEqual(
            RetrievalMetrics.recall_at_k(["d1", "d2", "d3"], {"d1", "d4"}, k=2), 0.5
        )
        self.assertEqual(RetrievalMetrics.recall_at_k(["d1"], {"d1"}), 1.0)

    def test_recall_none_when_no_relevant(self) -> None:
        self.assertIsNone(RetrievalMetrics.recall_at_k(["d1"], []))

    def test_precision_at_k(self) -> None:
        self.assertEqual(
            RetrievalMetrics.precision_at_k(["d1", "d2", "d3"], {"d1", "d4"}, k=2), 0.5
        )

    def test_precision_none_when_nothing_retrieved(self) -> None:
        self.assertIsNone(RetrievalMetrics.precision_at_k([], {"d1"}, k=3))

    def test_reciprocal_rank(self) -> None:
        self.assertEqual(
            RetrievalMetrics.reciprocal_rank(["d3", "d1", "d2"], {"d1"}), 0.5
        )
        self.assertEqual(RetrievalMetrics.reciprocal_rank(["d3"], {"d1"}), 0.0)

    def test_tool_selection_recall(self) -> None:
        recall = RetrievalMetrics.tool_selection_recall(
            ["search", "book"], {"search", "book", "confirm"}
        )
        self.assertAlmostEqual(recall, 2 / 3)

    def test_invalid_k_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalMetrics.recall_at_k(["d1"], {"d1"}, k=0)

    def test_non_sequence_retrieved_raises(self) -> None:
        with self.assertRaises(TypeError):
            RetrievalMetrics.recall_at_k("d1", {"d1"})  # type: ignore[arg-type]

    def test_case_from_mapping_coerces_ids_to_str(self) -> None:
        case = RetrievalCase.from_mapping({"retrieved": [1, 2], "relevant": [2], "k": 1})
        self.assertEqual(case.retrieved, ("1", "2"))
        self.assertEqual(case.relevant, frozenset({"2"}))
        self.assertEqual(case.k, 1)

    def test_summarize(self) -> None:
        cases = [
            RetrievalCase(retrieved=("d1", "d2"), relevant=frozenset({"d1"})),
            RetrievalCase(retrieved=("d3", "d2"), relevant=frozenset({"d2"})),
        ]
        summary = RetrievalMetrics.summarize(cases)
        self.assertIsInstance(summary, RetrievalSummary)
        self.assertEqual(summary.query_count, 2)
        self.assertEqual(summary.mean_recall_at_k, 1.0)
        self.assertEqual(summary.mean_precision_at_k, 0.5)
        self.assertEqual(summary.mrr, 0.75)

    def test_summarize_empty(self) -> None:
        summary = RetrievalMetrics.summarize([])
        self.assertEqual(summary.query_count, 0)
        self.assertIsNone(summary.mean_recall_at_k)
        self.assertIsNone(summary.mrr)

    def test_summarize_skips_queries_without_gold_for_mrr(self) -> None:
        # A query with no gold-relevant docs must not drag the MRR down: only
        # the query that has gold (and a rank-1 hit) counts.
        cases = [
            RetrievalCase(retrieved=("d5", "d6"), relevant=frozenset()),
            RetrievalCase(retrieved=("d1", "d2"), relevant=frozenset({"d1"})),
        ]
        summary = RetrievalMetrics.summarize(cases)
        self.assertEqual(summary.query_count, 2)
        self.assertEqual(summary.mean_recall_at_k, 1.0)
        self.assertEqual(summary.mrr, 1.0)

    def test_precision_counts_per_slot_with_duplicate_ids(self) -> None:
        self.assertAlmostEqual(
            RetrievalMetrics.precision_at_k(["d1", "d1", "d2"], {"d1"}, k=3), 2 / 3
        )

    def test_case_rejects_invalid_k_on_construction(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalCase(retrieved=("d1",), relevant=frozenset({"d1"}), k=-5)


class MatchMetricsTest(unittest.TestCase):
    def test_exact_match_normalized(self) -> None:
        self.assertEqual(MatchMetrics.exact_match("The Answer.", "answer"), 1.0)
        self.assertEqual(MatchMetrics.exact_match("cat", "dog"), 0.0)

    def test_token_f1(self) -> None:
        self.assertAlmostEqual(
            MatchMetrics.token_f1("the cat sat", "cat sat on the mat"), 2 / 3
        )
        self.assertEqual(MatchMetrics.token_f1("", ""), 1.0)
        self.assertEqual(MatchMetrics.token_f1("cat", ""), 0.0)

    def test_batch_helpers(self) -> None:
        self.assertEqual(
            MatchMetrics.exact_match_accuracy(["a", "b"], ["a", "c"]), 0.5
        )
        self.assertEqual(MatchMetrics.accuracy(["pos", "neg", "pos"], ["pos", "neg", "neg"]), 0.667)

    def test_paired_validation(self) -> None:
        with self.assertRaises(ValueError):
            MatchMetrics.accuracy(["a"], ["a", "b"])
        with self.assertRaises(ValueError):
            MatchMetrics.accuracy([], [])
        with self.assertRaises(TypeError):
            MatchMetrics.accuracy("a", "a")  # type: ignore[arg-type]

    def test_classification_report_macro(self) -> None:
        report = MatchMetrics.classification_report(
            ["pos", "pos", "neg", "neg"], ["pos", "neg", "neg", "neg"], average="macro"
        )
        self.assertIsInstance(report, ClassificationReport)
        self.assertEqual(report.accuracy, 0.75)
        self.assertEqual(report.average, "macro")
        self.assertEqual(report.per_label["pos"]["precision"], 0.5)
        self.assertEqual(report.per_label["pos"]["recall"], 1.0)
        self.assertEqual(report.per_label["neg"]["precision"], 1.0)
        self.assertEqual(report.precision, 0.75)
        self.assertAlmostEqual(report.recall, 0.833, places=3)
        self.assertAlmostEqual(report.f1, 0.733, places=3)

    def test_classification_report_micro_equals_accuracy(self) -> None:
        report = MatchMetrics.classification_report(
            ["pos", "pos", "neg", "neg"], ["pos", "neg", "neg", "neg"], average="micro"
        )
        self.assertEqual(report.precision, report.accuracy)
        self.assertEqual(report.recall, report.accuracy)
        self.assertEqual(report.f1, report.accuracy)

    def test_classification_report_binary(self) -> None:
        report = MatchMetrics.classification_report(
            ["pos", "pos", "neg", "neg"],
            ["pos", "neg", "neg", "neg"],
            positive_label="pos",
        )
        self.assertEqual(report.average, "binary")
        self.assertEqual(report.precision, 0.5)
        self.assertEqual(report.recall, 1.0)
        self.assertAlmostEqual(report.f1, 0.667, places=3)

    def test_classification_report_errors(self) -> None:
        with self.assertRaises(ValueError):
            MatchMetrics.classification_report(["a"], ["a"], average="weird")
        with self.assertRaises(ValueError):
            MatchMetrics.classification_report(["a"], ["a"], positive_label="z")


class TextMetricsTest(unittest.TestCase):
    def test_bleu_perfect(self) -> None:
        self.assertEqual(
            TextMetrics.bleu("the cat sat on the mat", "the cat sat on the mat"), 1.0
        )

    def test_bleu_short_both_equal(self) -> None:
        # Orders 3-4 have no n-grams and drop out; 1-2 gram precision is perfect.
        self.assertEqual(TextMetrics.bleu("hello world", "hello world"), 1.0)

    def test_bleu_brevity_penalty(self) -> None:
        self.assertAlmostEqual(
            TextMetrics.bleu("the cat", "the cat sat", max_n=2), 0.607, places=3
        )

    def test_bleu_smoothing(self) -> None:
        self.assertEqual(TextMetrics.bleu("dog", "cat", max_n=1, smooth=True), 0.5)
        self.assertEqual(TextMetrics.bleu("dog", "cat", max_n=1, smooth=False), 0.0)

    def test_bleu_multiple_references(self) -> None:
        score = TextMetrics.bleu("the cat", ["a dog", "the cat"], max_n=2)
        self.assertEqual(score, 1.0)

    def test_corpus_bleu_matches_sentence(self) -> None:
        sentence = TextMetrics.bleu("the cat", "the cat sat", max_n=2)
        corpus = TextMetrics.corpus_bleu(["the cat"], [["the cat sat"]], max_n=2)
        self.assertEqual(sentence, corpus)

    def test_rouge_n(self) -> None:
        perfect = TextMetrics.rouge_n("the cat sat", "the cat sat", n=1)
        self.assertEqual(perfect, RougeScore(precision=1.0, recall=1.0, f1=1.0))
        partial = TextMetrics.rouge_n("the cat", "the cat sat on the mat", n=1)
        self.assertEqual(partial.precision, 1.0)
        self.assertAlmostEqual(partial.recall, 0.333, places=3)
        self.assertEqual(partial.f1, 0.5)

    def test_rouge_l_is_order_sensitive(self) -> None:
        # ROUGE-1 would be 1.0 (same bag of words); ROUGE-L drops for reordering.
        score = TextMetrics.rouge_l("cat the sat", "the cat sat")
        self.assertAlmostEqual(score.f1, 2 / 3, places=3)

    def test_meteor_identical_has_small_fragmentation_penalty(self) -> None:
        score = TextMetrics.meteor("the cat sat", "the cat sat")
        self.assertAlmostEqual(score, 0.981, places=3)

    def test_meteor_empty(self) -> None:
        self.assertEqual(TextMetrics.meteor("", ""), 1.0)
        self.assertEqual(TextMetrics.meteor("cat", "dog"), 0.0)

    def test_meteor_stemming_helps(self) -> None:
        stemmed = TextMetrics.meteor("the cats", "the cat", stem=True)
        exact_only = TextMetrics.meteor("the cats", "the cat", stem=False)
        self.assertGreater(stemmed, exact_only)
        self.assertGreater(stemmed, 0.9)

    def test_text_metrics_type_errors(self) -> None:
        with self.assertRaises(TypeError):
            TextMetrics.bleu(123, "cat")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            TextMetrics.corpus_bleu(["a"], [["b"]], max_n=0)


if __name__ == "__main__":
    unittest.main()
