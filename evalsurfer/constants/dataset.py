"""Golden dataset artifact (versioned cases + contamination controls).

Coverage tags, dataset splits, content-derived case id parameters, and the
contamination report sections.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Golden dataset artifact (versioned cases + contamination controls)
# --------------------------------------------------------------------------- #
# Coverage tags describing how hard / representative a case is.
TAG_NORMAL: Final = "normal"
TAG_DIFFICULT: Final = "difficult"
TAG_EDGE: Final = "edge"
TAG_RANDOM: Final = "random"
COVERAGE_TAGS: Final = (TAG_NORMAL, TAG_DIFFICULT, TAG_EDGE, TAG_RANDOM)

# Dataset splits: the eval-visible set vs a held-out / fresh set.
SPLIT_EVAL: Final = "eval"
SPLIT_HELDOUT: Final = "heldout"
DATASET_SPLITS: Final = (SPLIT_EVAL, SPLIT_HELDOUT)

# Stable, content-derived case ids: "case-<first N hex chars of sha256>".
DATASET_CASE_ID_PREFIX: Final = "case-"
DATASET_ID_HASH_LENGTH: Final = 12

# Contamination report sections (duplicate content, blocklist / canary hits).
CONTAMINATION_DUPLICATES: Final = "duplicates"
CONTAMINATION_BLOCKLIST_HITS: Final = "blocklist_hits"
CONTAMINATION_CANARY_HITS: Final = "canary_hits"
CONTAMINATION_SECTIONS: Final = (
    CONTAMINATION_DUPLICATES,
    CONTAMINATION_BLOCKLIST_HITS,
    CONTAMINATION_CANARY_HITS,
)

__all__ = [
    "TAG_NORMAL",
    "TAG_DIFFICULT",
    "TAG_EDGE",
    "TAG_RANDOM",
    "COVERAGE_TAGS",
    "SPLIT_EVAL",
    "SPLIT_HELDOUT",
    "DATASET_SPLITS",
    "DATASET_CASE_ID_PREFIX",
    "DATASET_ID_HASH_LENGTH",
    "CONTAMINATION_DUPLICATES",
    "CONTAMINATION_BLOCKLIST_HITS",
    "CONTAMINATION_CANARY_HITS",
    "CONTAMINATION_SECTIONS",
]
