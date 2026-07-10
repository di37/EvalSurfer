"""Deterministic agent-trajectory evaluation for EvalSurfer.

An agent's *trajectory* is the ordered list of tool calls it made on the way to a
final answer. :class:`TrajectoryEvaluator` compares that actual trajectory
against an expected specification and reports structured, deterministic findings:
required tools that were never called, tools that were called but should not have
been, calls made out of the expected order, calls missing required arguments, and
errors the agent never recovered from.

The specification is intentionally partial: every field is optional, so a caller
can constrain only the tool sequence, only the forbidden tools, only the
parameters, or any combination. Whatever the caller does not declare is simply
not checked. The "expected toolset" against which extra tools are judged is the
union of the required, sequenced, and parameter-constrained tools -- but that
rule only fires when the caller positively declared a toolset via
``required_tools`` or ``tool_sequence``; declaring parameters alone never turns
every other tool into an "unnecessary" one.

This module is pure and standard-library-only. It makes no model calls, never
mutates its inputs, and refuses to fabricate the one judgment it cannot make
deterministically -- whether the final answer actually follows from the tool
results -- deferring that to a human or LLM judge via the
``final_answer_consistency`` flag. The finding type names come from
:mod:`constants` (``TRAJECTORY_*``) and error detection reuses
``constants.TOOL_FAILURE_KEYS`` so it stays consistent with the planner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = ["ToolCall", "Finding", "TrajectoryEvaluator"]

# --------------------------------------------------------------------------- #
# Input schema keys (the ``actual`` / ``expected`` mappings). These are this
# module's I/O contract, named here rather than inlined at every access site.
# --------------------------------------------------------------------------- #
ACTUAL_TOOL_CALLS_KEY = "tool_calls"
TOOL_NAME_KEY = "name"
TOOL_ARGUMENTS_KEY = "arguments"
EXPECTED_SEQUENCE_KEY = "tool_sequence"
EXPECTED_REQUIRED_KEY = "required_tools"
EXPECTED_FORBIDDEN_KEY = "forbidden_tools"
EXPECTED_PARAMETERS_KEY = "tool_parameters"
PARAMETERS_REQUIRED_KEY = "required"

# Output schema keys.
FINDINGS_KEY = "findings"
FINDING_TYPE_KEY = "type"
FINDING_DETAIL_KEY = "detail"
FINDING_TOOLS_KEY = "tools"
RECOVERED_AFTER_ERROR_KEY = "recovered_after_error"
FINAL_ANSWER_CONSISTENCY_KEY = "final_answer_consistency"
NEEDS_JUDGMENT_KEY = "needs_judgment"


@dataclass(frozen=True)
class ToolCall:
    """One parsed tool call from an actual trajectory.

    Only the fields the evaluator needs are retained: the tool ``name`` (or
    ``None`` when absent or non-string), the set of argument *names* the call
    supplied, and whether the call recorded an error.
    """

    name: str | None
    argument_names: frozenset[str]
    errored: bool


@dataclass(frozen=True)
class Finding:
    """A single deterministic trajectory finding.

    ``type`` is one of the ``constants.TRAJECTORY_*`` names, ``detail`` is a
    human-readable explanation, and ``tools`` lists the tool names the finding
    concerns in a deterministic order.
    """

    type: str
    detail: str
    tools: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Render the finding as a JSON-ready dict.

        Returns:
            ``{"type": <type>, "detail": <detail>, "tools": [<tool>, ...]}``.
        """
        return {
            FINDING_TYPE_KEY: self.type,
            FINDING_DETAIL_KEY: self.detail,
            FINDING_TOOLS_KEY: list(self.tools),
        }


class TrajectoryEvaluator:
    """Compare an agent's actual tool-call trajectory to an expected spec.

    Stateless: every check is derived purely from the ``actual`` and ``expected``
    mappings passed to :meth:`evaluate`, so the class is a cohesive namespace of
    class/static methods rather than something to instantiate.
    """

    @classmethod
    def evaluate(
        cls, actual: Mapping[str, Any], expected: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Deterministically evaluate an actual trajectory against a spec.

        The checks, and the finding each raises, are:

        * required or sequenced tools absent from ``actual`` ->
          ``constants.TRAJECTORY_MISSING_TOOL``;
        * forbidden tools that were called, or -- when a toolset was declared via
          ``required_tools``/``tool_sequence`` -- tools outside the expected
          toolset -> ``constants.TRAJECTORY_UNNECESSARY_TOOL``;
        * the sequenced tools that are present appearing in a different relative
          order than ``tool_sequence`` -> ``constants.TRAJECTORY_OUT_OF_ORDER``;
        * a call to a parameter-constrained tool missing a required argument name
          -> ``constants.TRAJECTORY_BAD_PARAMETERS``;
        * a tool call that errored with no later successful call of the same tool
          -> ``constants.TRAJECTORY_NO_RECOVERY``.

        Whether the final answer is consistent with the tool results is *not*
        decided here; it is always deferred to judgment.

        Args:
            actual: The observed trajectory. Recognised keys are
                ``"tool_calls"`` (a list of ``{"name", "arguments"?, "error"?}``
                mappings) and ``"final_answer"``. Missing, ``None``, or
                malformed entries are tolerated.
            expected: The expected specification. All keys are optional:
                ``"tool_sequence"``, ``"required_tools"``, ``"forbidden_tools"``
                (lists of tool names) and ``"tool_parameters"`` (a mapping of
                tool name to ``{"required": [arg, ...]}``).

        Returns:
            ``{"findings": [{"type", "detail", "tools"}, ...],
            "recovered_after_error": bool | None,
            "final_answer_consistency": {"needs_judgment": True}}``. Findings are
            ordered missing, unnecessary, out-of-order, bad-parameters, then
            no-recovery. ``recovered_after_error`` is ``None`` when no call
            errored, ``True`` when every errored call was later retried
            successfully, and ``False`` otherwise. The inputs are never mutated.

        Raises:
            TypeError: If ``actual`` or ``expected`` is not a mapping.
        """
        if not isinstance(actual, Mapping):
            raise TypeError("actual must be a mapping")
        if not isinstance(expected, Mapping):
            raise TypeError("expected must be a mapping")

        calls = cls._parse_calls(actual.get(ACTUAL_TOOL_CALLS_KEY))
        actual_names = [call.name for call in calls if isinstance(call.name, str)]
        present = set(actual_names)

        sequence = cls._string_list(expected.get(EXPECTED_SEQUENCE_KEY))
        required = cls._string_list(expected.get(EXPECTED_REQUIRED_KEY))
        forbidden = cls._string_list(expected.get(EXPECTED_FORBIDDEN_KEY))
        parameters = cls._parameter_specs(expected.get(EXPECTED_PARAMETERS_KEY))

        findings = [
            finding
            for finding in (
                cls._missing_finding(sequence, required, present),
                cls._unnecessary_finding(actual_names, sequence, required, forbidden, parameters),
                cls._out_of_order_finding(sequence, actual_names),
                cls._bad_parameters_finding(calls, parameters),
            )
            if finding is not None
        ]
        recovered_after_error, recovery_finding = cls._recovery(calls)
        if recovery_finding is not None:
            findings.append(recovery_finding)

        return {
            FINDINGS_KEY: [finding.to_dict() for finding in findings],
            RECOVERED_AFTER_ERROR_KEY: recovered_after_error,
            FINAL_ANSWER_CONSISTENCY_KEY: {NEEDS_JUDGMENT_KEY: True},
        }

    # ----------------------------------------------------------------------- #
    # Input parsing
    # ----------------------------------------------------------------------- #
    @staticmethod
    def _parse_calls(raw: Any) -> list[ToolCall]:
        """Parse the raw ``tool_calls`` value into :class:`ToolCall` objects.

        Args:
            raw: The raw ``actual["tool_calls"]`` value. Anything that is not a
                list/tuple (``None``, a string, a mapping) yields no calls, and
                individual entries that are not mappings are skipped.

        Returns:
            The parsed tool calls, in trajectory order.
        """
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []
        calls: list[ToolCall] = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            name = item.get(TOOL_NAME_KEY)
            arguments = item.get(TOOL_ARGUMENTS_KEY)
            argument_names = (
                frozenset(key for key in arguments if isinstance(key, str))
                if isinstance(arguments, Mapping)
                else frozenset()
            )
            calls.append(
                ToolCall(
                    name=name if isinstance(name, str) else None,
                    argument_names=argument_names,
                    errored=any(bool(item.get(key)) for key in constants.TOOL_FAILURE_KEYS),
                )
            )
        return calls

    @staticmethod
    def _string_list(raw: Any) -> list[str]:
        """Coerce a raw value into a list of the string items it contains.

        Args:
            raw: A raw expected-spec value. Anything that is not a list/tuple
                (``None``, a string, a mapping) yields an empty list, and
                non-string members are dropped.

        Returns:
            The string members, in order (duplicates preserved).
        """
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []
        return [item for item in raw if isinstance(item, str)]

    @classmethod
    def _parameter_specs(cls, raw: Any) -> dict[str, list[str]]:
        """Parse ``tool_parameters`` into ``{tool: [required arg, ...]}``.

        Args:
            raw: The raw ``expected["tool_parameters"]`` value. A non-mapping
                yields an empty spec; entries whose value is not a mapping, or
                whose ``"required"`` is not a list of strings, contribute no
                required arguments.

        Returns:
            A mapping of tool name to its required argument names.
        """
        if not isinstance(raw, Mapping):
            return {}
        specs: dict[str, list[str]] = {}
        for tool, spec in raw.items():
            if not isinstance(tool, str):
                continue
            required = spec.get(PARAMETERS_REQUIRED_KEY) if isinstance(spec, Mapping) else None
            specs[tool] = cls._string_list(required)
        return specs

    # ----------------------------------------------------------------------- #
    # Individual checks
    # ----------------------------------------------------------------------- #
    @staticmethod
    def _missing_finding(
        sequence: Sequence[str], required: Sequence[str], present: set[str]
    ) -> Finding | None:
        """Flag required or sequenced tools that never appear in the trajectory.

        Args:
            sequence: The expected ordered tools.
            required: The required tools.
            present: The set of tool names actually called.

        Returns:
            A ``TRAJECTORY_MISSING_TOOL`` finding, or ``None`` when nothing is
            missing.
        """
        missing: list[str] = []
        for tool in list(sequence) + list(required):
            if tool not in present and tool not in missing:
                missing.append(tool)
        if not missing:
            return None
        detail = f"Expected tool(s) never called: {', '.join(missing)}."
        return Finding(constants.TRAJECTORY_MISSING_TOOL, detail, tuple(missing))

    @staticmethod
    def _unnecessary_finding(
        actual_names: Sequence[str],
        sequence: Sequence[str],
        required: Sequence[str],
        forbidden: Sequence[str],
        parameters: Mapping[str, Sequence[str]],
    ) -> Finding | None:
        """Flag forbidden tools and tools outside a declared expected toolset.

        A tool is unnecessary when it is forbidden, or -- only when the caller
        positively declared a toolset via ``required_tools`` or ``tool_sequence``
        -- when it is not among the expected tools (the union of the sequenced,
        required, and parameter-constrained tools).

        Args:
            actual_names: The tool names actually called, in order.
            sequence: The expected ordered tools.
            required: The required tools.
            forbidden: The forbidden tools.
            parameters: The parameter specs, keyed by tool name.

        Returns:
            A ``TRAJECTORY_UNNECESSARY_TOOL`` finding, or ``None`` when no call is
            unnecessary.
        """
        allowed = set(sequence) | set(required) | set(parameters)
        toolset_declared = bool(sequence) or bool(required)
        forbidden_set = set(forbidden)
        unnecessary: list[str] = []
        for name in actual_names:
            flagged = name in forbidden_set or (toolset_declared and name not in allowed)
            if flagged and name not in unnecessary:
                unnecessary.append(name)
        if not unnecessary:
            return None
        detail = f"Unexpected tool(s) called: {', '.join(unnecessary)}."
        return Finding(constants.TRAJECTORY_UNNECESSARY_TOOL, detail, tuple(unnecessary))

    @classmethod
    def _out_of_order_finding(
        cls, sequence: Sequence[str], actual_names: Sequence[str]
    ) -> Finding | None:
        """Flag sequenced tools that appear in the wrong relative order.

        Only the sequenced tools that are actually present are compared, so a
        missing sequenced tool is reported as missing rather than as a disorder.

        Args:
            sequence: The expected ordered tools; when empty, order is not
                checked.
            actual_names: The tool names actually called, in order.

        Returns:
            A ``TRAJECTORY_OUT_OF_ORDER`` finding, or ``None`` when the present
            sequenced tools keep their expected relative order.
        """
        if not sequence:
            return None
        expected_order, actual_order = cls._ordering(sequence, actual_names)
        if expected_order == actual_order:
            return None
        detail = (
            "Tools were called out of the expected order "
            f"(expected {' -> '.join(expected_order)}; "
            f"observed {' -> '.join(actual_order)})."
        )
        return Finding(constants.TRAJECTORY_OUT_OF_ORDER, detail, tuple(expected_order))

    @staticmethod
    def _ordering(
        sequence: Sequence[str], actual_names: Sequence[str]
    ) -> tuple[list[str], list[str]]:
        """Return the expected and observed first-occurrence order of shared tools.

        Args:
            sequence: The expected ordered tools.
            actual_names: The tool names actually called, in order.

        Returns:
            ``(expected_order, actual_order)`` -- the sequenced tools that are
            present, deduplicated, in expected order and in actual
            first-occurrence order respectively.
        """
        present = set(actual_names)
        seq_set = set(sequence)
        expected_order: list[str] = []
        for tool in sequence:
            if tool in present and tool not in expected_order:
                expected_order.append(tool)
        actual_order: list[str] = []
        for tool in actual_names:
            if tool in seq_set and tool not in actual_order:
                actual_order.append(tool)
        return expected_order, actual_order

    @staticmethod
    def _bad_parameters_finding(
        calls: Sequence[ToolCall], parameters: Mapping[str, Sequence[str]]
    ) -> Finding | None:
        """Flag calls to parameter-constrained tools missing a required argument.

        Args:
            calls: The parsed tool calls.
            parameters: The parameter specs, keyed by tool name.

        Returns:
            A ``TRAJECTORY_BAD_PARAMETERS`` finding whose ``tools`` are the
            offending tool names in first-offence order, or ``None`` when every
            constrained call supplied its required arguments.
        """
        order: list[str] = []
        missing_by_tool: dict[str, list[str]] = {}
        for call in calls:
            if call.name is None or call.name not in parameters:
                continue
            absent = [arg for arg in parameters[call.name] if arg not in call.argument_names]
            if not absent:
                continue
            if call.name not in missing_by_tool:
                missing_by_tool[call.name] = []
                order.append(call.name)
            for arg in absent:
                if arg not in missing_by_tool[call.name]:
                    missing_by_tool[call.name].append(arg)
        if not order:
            return None
        parts = [f"{tool} (missing {', '.join(missing_by_tool[tool])})" for tool in order]
        detail = f"Tool call(s) missing required argument(s): {'; '.join(parts)}."
        return Finding(constants.TRAJECTORY_BAD_PARAMETERS, detail, tuple(order))

    # ----------------------------------------------------------------------- #
    # Error recovery
    # ----------------------------------------------------------------------- #
    @classmethod
    def _recovery(cls, calls: Sequence[ToolCall]) -> tuple[bool | None, Finding | None]:
        """Assess whether every errored call was later retried successfully.

        An errored call is *recovered* when a later call of the same tool did not
        error. The trajectory as a whole counts as recovered only when every
        errored call was recovered.

        Args:
            calls: The parsed tool calls, in trajectory order.

        Returns:
            ``(recovered_after_error, finding)`` where ``recovered_after_error``
            is ``None`` when no call errored, ``True`` when all errors were
            recovered, and ``False`` otherwise. ``finding`` is a
            ``TRAJECTORY_NO_RECOVERY`` finding when at least one error was not
            recovered, else ``None``.
        """
        if not any(call.errored for call in calls):
            return None, None
        all_recovered = True
        unrecovered_tools: list[str] = []
        for index, call in enumerate(calls):
            if not call.errored or cls._has_later_success(calls, index, call.name):
                continue
            all_recovered = False
            if isinstance(call.name, str) and call.name not in unrecovered_tools:
                unrecovered_tools.append(call.name)
        if all_recovered:
            return True, None
        if unrecovered_tools:
            detail = (
                "Tool(s) errored with no later successful retry: "
                f"{', '.join(unrecovered_tools)}."
            )
        else:
            detail = "A tool errored with no later successful retry."
        return False, Finding(
            constants.TRAJECTORY_NO_RECOVERY, detail, tuple(unrecovered_tools)
        )

    @staticmethod
    def _has_later_success(
        calls: Sequence[ToolCall], index: int, name: str | None
    ) -> bool:
        """Report whether a later call of ``name`` succeeded after ``index``.

        Args:
            calls: The parsed tool calls, in trajectory order.
            index: The position of the errored call being checked.
            name: The errored call's tool name; an unnamed call cannot recover.

        Returns:
            ``True`` when some call after ``index`` has the same ``name`` and did
            not error, else ``False``.
        """
        if name is None:
            return False
        return any(
            later.name == name and not later.errored for later in calls[index + 1:]
        )
