"""Input and output schema keys for trajectory evaluation.

These name the dict keys of the ``actual`` / ``expected`` mappings that
:class:`~evalsurfer.assurance.trajectory.agent_trace.evaluator.TrajectoryEvaluator`
reads and of the result it returns. They are this feature's I/O contract, shared
by the value objects in :mod:`evalsurfer.assurance.trajectory.agent_trace.models`
and the evaluator in :mod:`evalsurfer.assurance.trajectory.agent_trace.evaluator`.
"""

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
