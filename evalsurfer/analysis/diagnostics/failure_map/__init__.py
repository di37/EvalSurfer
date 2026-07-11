"""Visual failure map for EvalSurfer reports.

Projects a produced report onto a linear application pipeline
(Prompt -> Retriever -> Ranker -> Generator -> Tool -> Response) and marks which
stages are weak. Each rubric criterion is mapped to the stage it exercises via
its ``(category, group)`` location (RAG criteria to the retriever and ranker,
generation / multi-turn / safety criteria to the generator, tool-use
criteria to the tool stage). A stage fails when any of its *assessed* criteria
scored below a threshold.

The result is renderable in three shapes: a structured list of stage diagnoses,
a Mermaid ``flowchart LR`` with failing stages styled, and a plain arrow chain
for terminals. Standard library only, no model calls -- it reads an existing
report and never mutates it. The pipeline, statuses, selectors, and default
threshold all come from :mod:`constants`.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`StageDiagnosis` value object) and :mod:`.map` (the :class:`FailureMap`
service and its rendering literals) -- and re-exported here so that
``from evalsurfer.analysis.diagnostics.failure_map import FailureMap`` keeps
working.
"""

from evalsurfer.analysis.diagnostics.failure_map.map import FailureMap
from evalsurfer.analysis.diagnostics.failure_map.models import StageDiagnosis

__all__ = ["StageDiagnosis", "FailureMap"]
