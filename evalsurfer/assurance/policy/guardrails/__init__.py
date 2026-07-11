"""Machine-readable release guardrails for EvalSurfer.

Where :class:`~evalsurfer.core.report.Gate` decides whether a report clears a
single minimum decision, a *guardrail policy* lets a team encode several release
rules in one ``guardrails.json`` file and have Assurance ``Guardrails`` /
``guardrail_gate`` enforce them (composing Core ``Gate`` + Analysis ``ReviewGate``)
deterministically: a minimum decision, a safety-category floor, a coverage floor,
a block on any critical issue, a fix-attempt cap, and a sensitive-path denylist
that forces human review when a release touches protected files.

:class:`Guardrails` *reuses* the existing :class:`Gate` and
:class:`~evalsurfer.analysis.diagnostics.review_gate.ReviewGate` rather than
reimplementing them; the policy only adds team-specific rules on top. Everything
here is deterministic, standard-library only (``json`` + ``fnmatch``), and makes
no model calls; inputs are never mutated. Path matching is case-insensitive and
uses :func:`fnmatch.fnmatchcase` semantics (``*`` matches across ``/``), so it is
identical on every platform.

The implementation is split across focused modules -- :mod:`.models` (the
:class:`GuardrailPolicy` value object and its validation) and :mod:`.guardrails`
(the :class:`Guardrails` enforcement service) -- and re-exported here so that
``from evalsurfer.assurance.policy.guardrails import Guardrails`` keeps working.
"""

from evalsurfer.assurance.policy.guardrails.guardrails import Guardrails
from evalsurfer.assurance.policy.guardrails.models import GuardrailPolicy

__all__ = ["GuardrailPolicy", "Guardrails"]
