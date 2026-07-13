"""Judge-calibration metrics ("eval of the eval").

Basic calibration metric names plus chance-corrected inter-rater agreement and
judge-vs-human error/correlation metric ids.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Judge-calibration metrics ("eval of the eval")
# --------------------------------------------------------------------------- #
CALIBRATION_METRICS: Final = ("agreement", "false_pass_rate", "false_fail_rate", "score_variance")

# --------------------------------------------------------------------------- #
# Chance-corrected agreement & judge-vs-human calibration
# --------------------------------------------------------------------------- #
# Chance-corrected inter-rater agreement (replaces / augments raw boolean
# agreement, which is ~50% by chance on a binary call).
METRIC_COHEN_KAPPA: Final = "cohen_kappa"  # 2 raters, categorical
METRIC_FLEISS_KAPPA: Final = "fleiss_kappa"  # n raters, categorical
METRIC_KRIPPENDORFF_ALPHA: Final = "krippendorff_alpha"  # general, nominal
CHANCE_CORRECTED_METRICS: Final = (
    METRIC_COHEN_KAPPA,
    METRIC_FLEISS_KAPPA,
    METRIC_KRIPPENDORFF_ALPHA,
)
# Judge-vs-human (gold) error and correlation.
METRIC_JUDGE_HUMAN_MAE: Final = "judge_human_mae"  # mean absolute error vs gold
METRIC_RANK_CORRELATION: Final = "rank_correlation"  # Spearman's rho vs gold

# --------------------------------------------------------------------------- #
# Harness-invariant judgment reliability (target x harness x replication
# variance decomposition -- see docs/design/harness-invariance.md)
# --------------------------------------------------------------------------- #
METRIC_HARNESS_INVARIANCE: Final = "harness_invariance"
# Variance-component / share keys in the decomposition output.
FACET_TARGET: Final = "target"
FACET_HARNESS: Final = "harness"
FACET_INTERACTION: Final = "interaction"
FACET_REPLICATION: Final = "replication"
# With one replication per cell, interaction and replication noise are
# mathematically confounded and reported as a single residual.
FACET_RESIDUAL: Final = "residual"
# D-study: the dependability level a study aims for, and the default search grid.
DEFAULT_DEPENDABILITY_TARGET: Final = 0.8
DSTUDY_MAX_HARNESSES: Final = 5
DSTUDY_MAX_REPLICATIONS: Final = 5
# Upper bound accepted for the caller-supplied dstudy_max_* options: the D-study
# grid is materialized point by point, so unbounded caps would let a payload
# allocate harnesses x replications result objects without limit.
DSTUDY_MAX_LIMIT: Final = 100
# A criterion whose harness-linked variance share (harness + interaction)
# strictly exceeds this is flagged harness-sensitive (a rubric defect).
HARNESS_SENSITIVITY_SHARE: Final = 0.25

__all__ = [
    "CALIBRATION_METRICS",
    "METRIC_COHEN_KAPPA",
    "METRIC_FLEISS_KAPPA",
    "METRIC_KRIPPENDORFF_ALPHA",
    "CHANCE_CORRECTED_METRICS",
    "METRIC_JUDGE_HUMAN_MAE",
    "METRIC_RANK_CORRELATION",
    "METRIC_HARNESS_INVARIANCE",
    "FACET_TARGET",
    "FACET_HARNESS",
    "FACET_INTERACTION",
    "FACET_REPLICATION",
    "FACET_RESIDUAL",
    "DEFAULT_DEPENDABILITY_TARGET",
    "DSTUDY_MAX_HARNESSES",
    "DSTUDY_MAX_REPLICATIONS",
    "DSTUDY_MAX_LIMIT",
    "HARNESS_SENSITIVITY_SHARE",
]
