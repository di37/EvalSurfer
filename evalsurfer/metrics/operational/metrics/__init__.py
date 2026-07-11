"""Operational metrics for AI application evaluations.

The value objects (:class:`Pricing`, :class:`RequestTrace`, :class:`LatencyStats`,
:class:`OperationalSummary`) are immutable, provider-agnostic containers: pass
timestamps and token counts from your API logs, tracing system, or streaming
client instrumentation. :class:`OperationalMetrics` groups the stateless
calculations (latency, TTFT, throughput, cost, failure rate, percentiles) into a
single cohesive namespace.

Everything here is pure and standard-library-only -- no model calls. Magic
values are sourced from :mod:`constants`.

The implementation is split across three focused modules -- :mod:`.helpers` (the
:data:`Timestamp` alias and the timestamp/coercion utilities), :mod:`.models`
(the value objects), and :mod:`.service` (the :class:`OperationalMetrics`
calculations) -- and re-exported here so that ``from
evalsurfer.metrics.operational.metrics import OperationalMetrics`` keeps working.
"""

from evalsurfer.metrics.operational.metrics.helpers import (
    Timestamp,
    coerce_non_negative_int,
    coerce_optional_concurrency,
    duration_ms,
    get_nested,
    parse_bool,
    to_datetime,
)
from evalsurfer.metrics.operational.metrics.models import (
    LatencyStats,
    OperationalSummary,
    Pricing,
    RequestTrace,
)
from evalsurfer.metrics.operational.metrics.service import OperationalMetrics

__all__ = [
    "Timestamp",
    "Pricing",
    "RequestTrace",
    "LatencyStats",
    "OperationalSummary",
    "OperationalMetrics",
    "to_datetime",
    "duration_ms",
    "get_nested",
    "coerce_non_negative_int",
    "coerce_optional_concurrency",
    "parse_bool",
]
