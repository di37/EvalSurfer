"""Central constants for EvalSurfer.

Every fixed value the framework relies on lives here as an uppercase module-level
constant, so scoring thresholds, the rubric catalog, decision names, and the like
are defined exactly once and imported everywhere else (DRY).

The package holds data only -- no behavior, no imports beyond typing helpers. It
is split into cohesive domain modules (categories, signals, scoring, rubric, ...);
this ``__init__`` re-exports every constant so ``import evalsurfer.constants as
constants; constants.X`` keeps working exactly as before.
"""

from __future__ import annotations

# Dependency order: categories/signals before rubric; categories before diagnostics.
from evalsurfer.constants.categories import *  # noqa: F401,F403
from evalsurfer.constants.signals import *  # noqa: F401,F403
from evalsurfer.constants.scoring import *  # noqa: F401,F403
from evalsurfer.constants.rubric import *  # noqa: F401,F403
from evalsurfer.constants.diagnostics import *  # noqa: F401,F403
from evalsurfer.constants.operational import *  # noqa: F401,F403
from evalsurfer.constants.policy import *  # noqa: F401,F403
from evalsurfer.constants.safety import *  # noqa: F401,F403
from evalsurfer.constants.trajectory import *  # noqa: F401,F403
from evalsurfer.constants.calibration import *  # noqa: F401,F403
from evalsurfer.constants.adapters import *  # noqa: F401,F403
from evalsurfer.constants.quality import *  # noqa: F401,F403
from evalsurfer.constants.dataset import *  # noqa: F401,F403
from evalsurfer.constants.framework import *  # noqa: F401,F403
