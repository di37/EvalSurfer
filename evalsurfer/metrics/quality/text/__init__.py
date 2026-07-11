"""Deterministic reference-text metrics: BLEU, ROUGE-N/L, METEOR.

These are *task-typed*: BLEU for translation, ROUGE for summarization, METEOR
for order-aware generation. They report a recognizable number against a gold
reference with **no judge**, at the known cost that they are stylistically
brittle and correlate only weakly with human judgment -- prefer them as a fast,
repeatable signal alongside the agent's judgment, not instead of it.

METEOR here matches on exact tokens plus a light dependency-free stem (see
:func:`evalsurfer.metrics.quality.tokenize.light_stem`); it carries **no WordNet synonym
lexicon**, so it under-credits synonym matches relative to full METEOR. BLEU is
corpus-accumulated with a brevity penalty and a simple **floor smoothing** (a
present n-gram order with no match is floored to ``1/(total+1)`` rather than
zeroing the product -- not the same as Chen & Cherry's ``epsilon/total``);
n-gram orders absent from the candidate are dropped from the geometric mean.

Everything here is pure and standard-library only -- no model calls. Value
objects are immutable; inputs are never mutated. Magic values come from
:mod:`evalsurfer.constants`.

The implementation is split across three focused modules -- :mod:`.helpers` (the
shared F1/LCS/coercion utilities), :mod:`.models` (the :class:`RougeScore` value
object), and :mod:`.service` (the :class:`TextMetrics` calculations) -- and
re-exported here so that ``from evalsurfer.metrics.quality.text import
TextMetrics`` keeps working.
"""

from evalsurfer.metrics.quality.text.models import RougeScore
from evalsurfer.metrics.quality.text.service import TextMetrics

__all__ = [
    "RougeScore",
    "TextMetrics",
]
