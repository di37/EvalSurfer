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

__all__ = [
    "CALIBRATION_METRICS",
    "METRIC_COHEN_KAPPA",
    "METRIC_FLEISS_KAPPA",
    "METRIC_KRIPPENDORFF_ALPHA",
    "CHANCE_CORRECTED_METRICS",
    "METRIC_JUDGE_HUMAN_MAE",
    "METRIC_RANK_CORRELATION",
]
