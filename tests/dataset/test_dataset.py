from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError

import evalsurfer.constants as constants
from evalsurfer.dataset import CHANGE_CHANGED, Dataset, DatasetCase
from evalsurfer.dataset import contamination


def _content_digest(
    input: str,
    gold_answer=None,
    gold_label=None,
    gold_score=None,
) -> str:
    """Re-derive the canonical content digest the way the module does."""
    canonical = json.dumps(
        {
            "input": input,
            "gold_answer": gold_answer,
            "gold_label": gold_label,
            "gold_score": gold_score,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dataset_of(n: int) -> Dataset:
    """A dataset of ``n`` distinct, untagged cases."""
    cases = tuple(DatasetCase.create(f"case input number {i}") for i in range(n))
    return Dataset(name="probe", version="1", cases=cases)


class ContentHashAndIdTest(unittest.TestCase):
    def test_hash_matches_hand_computed_canonical_form(self) -> None:
        case = DatasetCase.create("hello")
        expected = _content_digest("hello")
        self.assertEqual(len(expected), 64)
        self.assertEqual(case.content_hash, expected)

    def test_id_is_prefix_plus_hash_head(self) -> None:
        case = DatasetCase.create("hello")
        expected = _content_digest("hello")
        self.assertEqual(
            case.id,
            constants.DATASET_CASE_ID_PREFIX
            + expected[: constants.DATASET_ID_HASH_LENGTH],
        )

    def test_same_content_yields_same_hash_and_id(self) -> None:
        first = DatasetCase.create("repeatable input")
        second = DatasetCase.create("repeatable input")
        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.id, second.id)

    def test_contamination_hash_is_the_single_implementation(self) -> None:
        case = DatasetCase.create("hello")
        self.assertEqual(
            case.content_hash,
            contamination.content_hash("hello", None, None, None),
        )

    def test_hash_excludes_tags_and_held_out(self) -> None:
        plain = DatasetCase.create("x", tags=(constants.TAG_NORMAL,))
        decorated = DatasetCase.create(
            "x", tags=(constants.TAG_EDGE,), held_out=True
        )
        self.assertEqual(plain.content_hash, decorated.content_hash)
        self.assertEqual(plain.id, decorated.id)

    def test_hash_depends_on_gold_fields(self) -> None:
        base = DatasetCase.create("x")
        with_answer = DatasetCase.create("x", gold_answer="a")
        with_label = DatasetCase.create("x", gold_label="l")
        with_score = DatasetCase.create("x", gold_score=4)
        digests = {
            base.content_hash,
            with_answer.content_hash,
            with_label.content_hash,
            with_score.content_hash,
        }
        self.assertEqual(len(digests), 4)

    def test_int_and_float_gold_score_hash_identically(self) -> None:
        as_int = DatasetCase.create("x", gold_score=3)
        as_float = DatasetCase.create("x", gold_score=3.0)
        self.assertEqual(as_int.content_hash, as_float.content_hash)
        self.assertEqual(as_int.gold_score, 3.0)
        self.assertIsInstance(as_int.gold_score, float)


class CaseValidationTest(unittest.TestCase):
    def test_empty_input_rejected(self) -> None:
        for bad in ("", "   ", None, 5):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, TypeError)):
                    DatasetCase.create(bad)  # type: ignore[arg-type]

    def test_unknown_tag_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DatasetCase.create("x", tags=("bogus",))

    def test_known_tags_accepted(self) -> None:
        case = DatasetCase.create("x", tags=(constants.TAG_NORMAL, constants.TAG_EDGE))
        self.assertEqual(
            case.tags, frozenset({constants.TAG_NORMAL, constants.TAG_EDGE})
        )

    def test_string_tags_argument_rejected(self) -> None:
        # A bare string is a common mistake: iterating it would tag by character.
        with self.assertRaises(TypeError):
            DatasetCase.create("x", tags="normal")

    def test_gold_score_bool_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DatasetCase.create("x", gold_score=True)

    def test_gold_score_non_finite_rejected(self) -> None:
        for bad in (float("inf"), float("nan"), float("-inf")):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    DatasetCase.create("x", gold_score=bad)

    def test_gold_score_out_of_range_rejected(self) -> None:
        for bad in (0, 0.5, 6, 100):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    DatasetCase.create("x", gold_score=bad)

    def test_gold_score_boundaries_accepted(self) -> None:
        low = DatasetCase.create("x", gold_score=constants.CRITERION_MIN_SCORE)
        high = DatasetCase.create("y", gold_score=constants.CRITERION_MAX_SCORE)
        self.assertEqual(low.gold_score, float(constants.CRITERION_MIN_SCORE))
        self.assertEqual(high.gold_score, float(constants.CRITERION_MAX_SCORE))

    def test_gold_score_string_type_rejected(self) -> None:
        with self.assertRaises(TypeError):
            DatasetCase.create("x", gold_score="3")

    def test_blank_explicit_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DatasetCase.create("x", id="   ")

    def test_explicit_id_used_verbatim(self) -> None:
        case = DatasetCase.create("x", id="case-custom")
        self.assertEqual(case.id, "case-custom")

    def test_case_is_frozen(self) -> None:
        case = DatasetCase.create("x")
        with self.assertRaises(FrozenInstanceError):
            case.held_out = True  # type: ignore[misc]


class CaseSerializationTest(unittest.TestCase):
    def test_to_dict_shape(self) -> None:
        case = DatasetCase.create(
            "q",
            gold_answer="a",
            gold_label="l",
            gold_score=4,
            tags=(constants.TAG_EDGE, constants.TAG_NORMAL),
            held_out=True,
        )
        result = case.to_dict()
        self.assertEqual(
            set(result),
            {
                "id",
                "input",
                "gold_answer",
                "gold_label",
                "gold_score",
                "tags",
                "held_out",
                "content_hash",
            },
        )
        self.assertEqual(result["tags"], [constants.TAG_EDGE, constants.TAG_NORMAL])
        self.assertEqual(result["gold_score"], 4.0)
        self.assertTrue(result["held_out"])

    def test_from_mapping_roundtrip(self) -> None:
        case = DatasetCase.create(
            "q", gold_answer="a", gold_score=2, tags=(constants.TAG_DIFFICULT,)
        )
        self.assertEqual(DatasetCase.from_mapping(case.to_dict()), case)

    def test_from_mapping_requires_input(self) -> None:
        with self.assertRaises(ValueError):
            DatasetCase.from_mapping({"gold_answer": "a"})

    def test_from_mapping_recomputes_tampered_hash(self) -> None:
        case = DatasetCase.from_mapping({"input": "hello", "content_hash": "deadbeef"})
        self.assertEqual(case.content_hash, _content_digest("hello"))

    def test_from_mapping_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            DatasetCase.from_mapping(["input", "hello"])  # type: ignore[arg-type]


class DatasetValidationTest(unittest.TestCase):
    def test_blank_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Dataset(name="  ", version="1", cases=())

    def test_blank_version_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Dataset(name="d", version="", cases=())

    def test_none_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Dataset(name=None, version="1", cases=())  # type: ignore[arg-type]

    def test_duplicate_ids_rejected(self) -> None:
        dup = DatasetCase.create("same input")
        again = DatasetCase.create("same input")  # identical derived id
        with self.assertRaises(ValueError):
            Dataset(name="d", version="1", cases=(dup, again))

    def test_non_case_element_rejected(self) -> None:
        with self.assertRaises(TypeError):
            Dataset(name="d", version="1", cases=({"input": "x"},))  # type: ignore[arg-type]

    def test_dataset_is_frozen(self) -> None:
        ds = _dataset_of(1)
        with self.assertRaises(FrozenInstanceError):
            ds.name = "other"  # type: ignore[misc]

    def test_dataset_roundtrip(self) -> None:
        ds = Dataset(
            name="d",
            version="2",
            cases=(
                DatasetCase.create("one", tags=(constants.TAG_NORMAL,)),
                DatasetCase.create("two", gold_label="L", held_out=True),
            ),
        )
        self.assertEqual(Dataset.from_mapping(ds.to_dict()), ds)

    def test_from_mapping_rejects_non_list_cases(self) -> None:
        with self.assertRaises(TypeError):
            Dataset.from_mapping({"name": "d", "version": "1", "cases": "x"})


class DatasetMutationImmutabilityTest(unittest.TestCase):
    def test_add_returns_new_object_and_leaves_original(self) -> None:
        original = _dataset_of(1)
        extra = DatasetCase.create("brand new input")
        grown = original.add(extra)
        self.assertIsNot(original, grown)
        self.assertEqual(len(original.cases), 1)
        self.assertEqual(len(grown.cases), 2)
        self.assertIn(extra, grown.cases)

    def test_add_duplicate_id_raises(self) -> None:
        ds = _dataset_of(1)
        clash = DatasetCase.create("case input number 0")  # same derived id
        with self.assertRaises(ValueError):
            ds.add(clash)

    def test_add_rejects_non_case(self) -> None:
        with self.assertRaises(TypeError):
            _dataset_of(1).add({"input": "x"})  # type: ignore[arg-type]

    def test_dedupe_drops_later_content_duplicate(self) -> None:
        first = DatasetCase.create("shared body", id="case-a")
        second = DatasetCase.create("shared body", id="case-c")  # same content
        distinct = DatasetCase.create("different body", id="case-b")
        ds = Dataset(name="d", version="1", cases=(first, second, distinct))
        deduped = ds.dedupe()
        self.assertEqual(len(ds.cases), 3)  # original untouched
        self.assertEqual([c.id for c in deduped.cases], ["case-a", "case-b"])


class DatasetSplitTest(unittest.TestCase):
    def test_zero_fraction_holds_out_nothing(self) -> None:
        ds = _dataset_of(60).split(0.0, salt="s")
        self.assertEqual(len(ds.heldout_cases()), 0)
        self.assertEqual(len(ds.eval_cases()), 60)

    def test_full_fraction_holds_out_everything(self) -> None:
        ds = _dataset_of(60).split(1.0, salt="s")
        self.assertEqual(len(ds.heldout_cases()), 60)
        self.assertEqual(len(ds.eval_cases()), 0)

    def test_half_split_partitions_both_ways(self) -> None:
        held = len(_dataset_of(60).split(0.5, salt="s").heldout_cases())
        self.assertTrue(0 < held < 60)

    def test_same_salt_is_deterministic(self) -> None:
        base = _dataset_of(60)
        first = {c.id for c in base.split(0.5, salt="s").heldout_cases()}
        second = {c.id for c in base.split(0.5, salt="s").heldout_cases()}
        self.assertEqual(first, second)

    def test_held_out_count_is_monotonic_in_fraction(self) -> None:
        base = _dataset_of(60)
        counts = [
            len(base.split(f, salt="s").heldout_cases())
            for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(counts[0], 0)
        self.assertEqual(counts[-1], 60)

    def test_split_preserves_identity(self) -> None:
        base = _dataset_of(5)
        split = base.split(0.5, salt="s")
        for original, moved in zip(base.cases, split.cases):
            self.assertEqual(original.id, moved.id)
            self.assertEqual(original.content_hash, moved.content_hash)
            self.assertEqual(original.input, moved.input)

    def test_split_validates_fraction(self) -> None:
        base = _dataset_of(3)
        for bad in (-0.1, 1.1):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    base.split(bad)

    def test_split_rejects_bad_types(self) -> None:
        base = _dataset_of(3)
        with self.assertRaises(TypeError):
            base.split(True)  # bool is not a fraction
        with self.assertRaises(TypeError):
            base.split("0.5")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            base.split(0.5, salt=5)  # type: ignore[arg-type]


class DatasetDiffTest(unittest.TestCase):
    def _versions(self) -> tuple[Dataset, Dataset]:
        a_v1 = DatasetCase.create("A question", id="case-A")
        b_v1 = DatasetCase.create("B question v1", id="case-B")
        c_v1 = DatasetCase.create("C question", id="case-C")
        a_v2 = DatasetCase.create("A question", id="case-A")  # unchanged
        b_v2 = DatasetCase.create("B question v2", id="case-B")  # changed content
        d_v2 = DatasetCase.create("D question", id="case-D")  # added
        v1 = Dataset(name="d", version="1", cases=(a_v1, b_v1, c_v1))
        v2 = Dataset(name="d", version="2", cases=(a_v2, b_v2, d_v2))
        return v1, v2

    def test_diff_buckets(self) -> None:
        v1, v2 = self._versions()
        diff = v2.diff(v1)
        self.assertEqual(diff[constants.CHANGE_ADDED], ["case-D"])
        self.assertEqual(diff[constants.CHANGE_REMOVED], ["case-C"])
        self.assertEqual(diff[constants.CHANGE_UNCHANGED], ["case-A"])
        self.assertEqual(diff[CHANGE_CHANGED], ["case-B"])

    def test_diff_keys(self) -> None:
        v1, v2 = self._versions()
        self.assertEqual(
            set(v2.diff(v1)),
            {
                constants.CHANGE_ADDED,
                constants.CHANGE_REMOVED,
                constants.CHANGE_UNCHANGED,
                CHANGE_CHANGED,
            },
        )

    def test_diff_rejects_non_dataset(self) -> None:
        with self.assertRaises(TypeError):
            _dataset_of(1).diff({"cases": []})  # type: ignore[arg-type]


class FromTracesTest(unittest.TestCase):
    def test_extracts_from_various_keys(self) -> None:
        traces = [
            {"query": "q1"},
            {"input": "q2"},
            {"prompt": "q3"},
            {"question": "q4"},
            {"foo": "bar"},  # no usable key -> skipped
            {"query": ""},  # blank -> skipped
            {"query": "   ", "input": "q5"},  # falls through to input
        ]
        ds = Dataset.from_traces(traces, name="harvest", version="1")
        self.assertEqual(sorted(c.input for c in ds.cases), ["q1", "q2", "q3", "q4", "q5"])
        for case in ds.cases:
            self.assertEqual(case.tags, frozenset({constants.TAG_RANDOM}))

    def test_key_priority_prefers_query(self) -> None:
        ds = Dataset.from_traces([{"query": "Q", "input": "I"}], name="h", version="1")
        self.assertEqual(ds.cases[0].input, "Q")

    def test_skips_non_mapping_and_empty(self) -> None:
        ds = Dataset.from_traces(
            [{"query": "a"}, "not-a-dict", 42, None, {}], name="h", version="1"
        )
        self.assertEqual([c.input for c in ds.cases], ["a"])

    def test_dedupe_within_batch(self) -> None:
        ds = Dataset.from_traces(
            [{"query": "x"}, {"query": "x"}], name="h", version="1"
        )
        self.assertEqual(len(ds.cases), 1)

    def test_stable_ids_across_overlapping_batches(self) -> None:
        batch1 = [{"query": "a"}, {"query": "b"}]
        batch2 = [{"query": "b"}, {"query": "c"}]
        ds1 = Dataset.from_traces(batch1, name="h", version="1")
        ds_all = Dataset.from_traces(batch1 + batch2, name="h", version="2")
        self.assertEqual(len(ds_all.cases), 3)  # b deduped across batches
        id_b_1 = next(c.id for c in ds1.cases if c.input == "b")
        id_b_all = next(c.id for c in ds_all.cases if c.input == "b")
        self.assertEqual(id_b_1, id_b_all)

    def test_harvested_id_is_content_derived(self) -> None:
        ds = Dataset.from_traces([{"query": "a"}], name="h", version="1")
        self.assertEqual(ds.cases[0].id, DatasetCase.create("a").id)


class ContaminationTest(unittest.TestCase):
    def test_find_duplicates_groups_shared_content(self) -> None:
        a = DatasetCase.create("dup body", id="case-a")
        b = DatasetCase.create("unique body", id="case-b")
        c = DatasetCase.create("dup body", id="case-c")
        groups = contamination.find_duplicates((a, b, c))
        self.assertEqual(groups, [["case-a", "case-c"]])

    def test_blocklist_is_case_insensitive_across_fields(self) -> None:
        c1 = DatasetCase.create("This mentions SECRET stuff")
        c2 = DatasetCase.create("benign", gold_answer="the Password123 value")
        c3 = DatasetCase.create("clean", gold_label="TOPIC")
        cases = (c1, c2, c3)
        self.assertEqual(contamination.blocklist_hits(cases, ["secret"]), [c1.id])
        self.assertEqual(contamination.blocklist_hits(cases, ["password123"]), [c2.id])
        self.assertEqual(contamination.blocklist_hits(cases, ["topic"]), [c3.id])
        self.assertEqual(contamination.blocklist_hits(cases, ["absent"]), [])
        self.assertEqual(contamination.blocklist_hits(cases, []), [])

    def test_canary_requires_exact_case(self) -> None:
        case = DatasetCase.create("contains CANARY-XYZ marker")
        cases = (case,)
        self.assertEqual(contamination.canary_hits(cases, ["CANARY-XYZ"]), [case.id])
        self.assertEqual(contamination.canary_hits(cases, ["canary-xyz"]), [])
        self.assertEqual(contamination.canary_hits(cases, []), [])

    def test_report_shape_and_delegation(self) -> None:
        a = DatasetCase.create("dup body", id="case-a")
        c = DatasetCase.create("dup body", id="case-c")
        leak = DatasetCase.create("has CANARY9 and secret", id="case-x")
        ds = Dataset(name="d", version="1", cases=(a, c, leak))
        report = ds.contamination_report(blocklist=["secret"], canaries=["CANARY9"])
        self.assertEqual(
            set(report),
            {
                constants.CONTAMINATION_DUPLICATES,
                constants.CONTAMINATION_BLOCKLIST_HITS,
                constants.CONTAMINATION_CANARY_HITS,
            },
        )
        self.assertEqual(report[constants.CONTAMINATION_DUPLICATES], [["case-a", "case-c"]])
        self.assertEqual(report[constants.CONTAMINATION_BLOCKLIST_HITS], ["case-x"])
        self.assertEqual(report[constants.CONTAMINATION_CANARY_HITS], ["case-x"])


class CoverageSummaryTest(unittest.TestCase):
    def test_counts_tags_and_splits(self) -> None:
        cases = (
            DatasetCase.create("one", tags=(constants.TAG_NORMAL,)),
            DatasetCase.create("two", tags=(constants.TAG_NORMAL, constants.TAG_EDGE)),
            DatasetCase.create("three", tags=(constants.TAG_DIFFICULT,), held_out=True),
            DatasetCase.create("four", tags=(constants.TAG_RANDOM,), held_out=True),
            DatasetCase.create("five"),  # untagged
        )
        summary = Dataset(name="d", version="1", cases=cases).coverage_summary()
        self.assertEqual(summary[constants.TAG_NORMAL], 2)
        self.assertEqual(summary[constants.TAG_DIFFICULT], 1)
        self.assertEqual(summary[constants.TAG_EDGE], 1)
        self.assertEqual(summary[constants.TAG_RANDOM], 1)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["held_out"], 2)
        self.assertEqual(summary["eval"], 3)
        self.assertEqual(summary["unique_hashes"], 5)

    def test_unique_hashes_counts_distinct_content(self) -> None:
        cases = (
            DatasetCase.create("body", id="case-a"),
            DatasetCase.create("body", id="case-b"),  # duplicate content
            DatasetCase.create("other", id="case-c"),
        )
        summary = Dataset(name="d", version="1", cases=cases).coverage_summary()
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["unique_hashes"], 2)


if __name__ == "__main__":
    unittest.main()
