"""
Tests for Capability-based runbook schema.
"""

from src.agents.runbooks.capability_schema import (
    CapabilityRunbook,
    RunbookStep,
    VerificationResult,
    evaluate_condition,
    resolution_verdict,
    validate_capability_runbook,
)
from src.agents.runbooks.catalog import CAPABILITY_RUNBOOKS


class TestRunbookStep:
    def test_from_dict_minimal(self):
        step = RunbookStep.from_dict({"name": "restart", "capability": "restart_workload"})
        assert step.name == "restart"
        assert step.capability == "restart_workload"
        assert step.on_failure == "abort"
        assert step.parameters == {}

    def test_from_dict_full(self):
        step = RunbookStep.from_dict({
            "name": "scale",
            "capability": "scale_out",
            "description": "Scale nodes",
            "parameters": {"increment": 2},
            "condition": {"previous_step_failed": True},
            "on_failure": "continue",
            "timeout_sec": 120,
        })
        assert step.parameters == {"increment": 2}
        assert step.condition == {"previous_step_failed": True}
        assert step.on_failure == "continue"
        assert step.timeout_sec == 120

    def test_to_dict_omits_defaults(self):
        step = RunbookStep(name="notify", capability="open_change_request")
        d = step.to_dict()
        assert "on_failure" not in d  # abort is default, omitted
        assert "condition" not in d
        assert "parameters" not in d

    def test_roundtrip(self):
        original = {
            "name": "restart",
            "capability": "restart_workload",
            "description": "Restart pod",
            "parameters": {"grace_period_sec": 30},
            "on_failure": "continue",
        }
        step = RunbookStep.from_dict(original)
        result = step.to_dict()
        assert result["name"] == "restart"
        assert result["capability"] == "restart_workload"
        assert result["on_failure"] == "continue"


class TestCapabilityRunbook:
    def test_from_dict(self):
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS["eks-pod-oom"])
        assert rb.runbook_id == "eks-pod-oom"
        assert len(rb.steps) == 2
        assert rb.capabilities == ["restart_workload", "scale_out"]
        assert rb.rto_sec == 180

    def test_capabilities_derived_from_steps(self):
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS["rds-cpu-high"])
        assert rb.capabilities == ["scale_database_primary", "scale_database_read"]

    def test_to_dict_roundtrip(self):
        original = CAPABILITY_RUNBOOKS["lambda-throttle"]
        rb = CapabilityRunbook.from_dict(original)
        d = rb.to_dict()
        assert d["runbook_id"] == "lambda-throttle"
        assert d["capabilities"] == ["increase_function_concurrency"]
        assert len(d["steps"]) == 1
        assert d["steps"][0]["name"] == "increase_concurrency"

    def test_all_catalog_entries_parse(self):
        for runbook_id, data in CAPABILITY_RUNBOOKS.items():
            rb = CapabilityRunbook.from_dict(data)
            assert rb.runbook_id == runbook_id
            assert len(rb.steps) > 0


class TestValidation:
    def test_valid_runbook(self):
        problems = validate_capability_runbook(CAPABILITY_RUNBOOKS["eks-pod-oom"])
        assert problems == []

    def test_missing_runbook_id(self):
        problems = validate_capability_runbook({"steps": [{"name": "x", "capability": "y"}]})
        assert any("runbook_id" in p for p in problems)

    def test_empty_steps(self):
        problems = validate_capability_runbook({"runbook_id": "test", "steps": []})
        assert any("non-empty" in p for p in problems)

    def test_missing_step_name(self):
        problems = validate_capability_runbook({
            "runbook_id": "test",
            "steps": [{"capability": "restart_workload"}],
        })
        assert any("name" in p for p in problems)

    def test_duplicate_step_names(self):
        problems = validate_capability_runbook({
            "runbook_id": "test",
            "steps": [
                {"name": "dup", "capability": "a"},
                {"name": "dup", "capability": "b"},
            ],
        })
        assert any("duplicated" in p for p in problems)

    def test_invalid_on_failure(self):
        problems = validate_capability_runbook({
            "runbook_id": "test",
            "steps": [{"name": "x", "capability": "y", "on_failure": "explode"}],
        })
        assert any("on_failure" in p for p in problems)

    def test_all_catalog_entries_valid(self):
        for runbook_id, data in CAPABILITY_RUNBOOKS.items():
            problems = validate_capability_runbook(data)
            assert problems == [], f"{runbook_id}: {problems}"


class TestConditionEvaluation:
    def test_none_condition_always_true(self):
        assert evaluate_condition(None, {}) is True

    def test_previous_step_failed_match(self):
        assert evaluate_condition(
            {"previous_step_failed": True},
            {"previous_step_failed": True},
        ) is True

    def test_previous_step_failed_no_match(self):
        assert evaluate_condition(
            {"previous_step_failed": True},
            {"previous_step_failed": False},
        ) is False

    def test_severity_in_match(self):
        assert evaluate_condition(
            {"severity_in": ["P1", "P2"]},
            {"severity": "P1"},
        ) is True

    def test_severity_in_no_match(self):
        assert evaluate_condition(
            {"severity_in": ["P1"]},
            {"severity": "P3"},
        ) is False

    def test_provider_match(self):
        assert evaluate_condition(
            {"provider": "aws"},
            {"provider": "aws"},
        ) is True

    def test_provider_no_match(self):
        assert evaluate_condition(
            {"provider": "gcp"},
            {"provider": "aws"},
        ) is False

    def test_combined_conditions(self):
        assert evaluate_condition(
            {"previous_step_failed": True, "severity_in": ["P1", "P2"]},
            {"previous_step_failed": True, "severity": "P2"},
        ) is True

        assert evaluate_condition(
            {"previous_step_failed": True, "severity_in": ["P1"]},
            {"previous_step_failed": True, "severity": "P3"},
        ) is False


class TestStepVerification:
    """`verify` is the "did it actually help?" slot — absent by default (back-compat)."""

    def test_absent_by_default(self):
        step = RunbookStep.from_dict({"name": "restart", "capability": "restart_workload"})
        assert step.verify is None
        assert "verify" not in step.to_dict()

    def test_parsed_from_dict(self):
        step = RunbookStep.from_dict({
            "name": "restart",
            "capability": "restart_workload",
            "verify": {
                "capability": "assert_workload_ready",
                "description": "must reach Ready",
                "parameters": {"timeout_sec": 120},
            },
        })
        assert step.verify is not None
        assert step.verify.capability == "assert_workload_ready"
        assert step.verify.parameters == {"timeout_sec": 120}
        assert step.verify.required is True

    def test_advisory_verification_roundtrip(self):
        original = {
            "name": "cleanup",
            "capability": "cleanup_disk_space",
            "verify": {"capability": "assert_disk_headroom", "required": False},
        }
        step = RunbookStep.from_dict(original)
        assert step.verify is not None
        assert step.verify.required is False
        assert step.to_dict()["verify"] == {
            "capability": "assert_disk_headroom",
            "required": False,
        }

    def test_malformed_verify_is_ignored_not_crashed(self):
        step = RunbookStep.from_dict({
            "name": "restart",
            "capability": "restart_workload",
            "verify": "assert_workload_ready",  # string, not dict
        })
        assert step.verify is None

    def test_validation_rejects_verify_without_capability(self):
        problems = validate_capability_runbook({
            "runbook_id": "rb",
            "steps": [{"name": "s", "capability": "restart_workload", "verify": {}}],
        })
        assert any("verify.capability" in p for p in problems)

    def test_validation_rejects_non_bool_required(self):
        problems = validate_capability_runbook({
            "runbook_id": "rb",
            "steps": [{
                "name": "s",
                "capability": "restart_workload",
                "verify": {"capability": "assert_workload_ready", "required": "yes"},
            }],
        })
        assert any("verify.required" in p for p in problems)

    def test_catalog_verifications_are_valid(self):
        """Every catalog runbook (verify slots included) still validates."""
        for runbook_id, data in CAPABILITY_RUNBOOKS.items():
            assert validate_capability_runbook(data) == [], runbook_id

    def test_catalog_verify_slots_roundtrip(self):
        """A catalog verify slot survives from_dict -> to_dict unchanged."""
        for data in CAPABILITY_RUNBOOKS.values():
            rb = CapabilityRunbook.from_dict(data)
            for original_step, parsed_step in zip(data["steps"], rb.steps, strict=True):
                assert parsed_step.to_dict().get("verify") == original_step.get("verify")


class TestResolutionVerdict:
    """
    Resolution has two axes: dispatched (historical) and verified (new).
    An unverified dispatch must never be reported as a proven recovery.
    """

    def test_no_verifications_matches_historical_rule(self):
        # Exactly `bool(executed) and not skipped`, with verified honestly unknown.
        v = resolution_verdict(["A"], [])
        assert v.resolved is True
        assert v.dispatched is True
        assert v.verified is None

    def test_no_verifications_partial_skip_not_resolved(self):
        v = resolution_verdict(["A"], ["B"])
        assert v.resolved is False
        assert v.verified is None

    def test_no_verifications_nothing_executed(self):
        v = resolution_verdict([], [])
        assert v.resolved is False
        assert v.dispatched is False

    def test_required_verification_failure_withholds_resolution(self):
        v = resolution_verdict(
            ["A"], [],
            [VerificationResult(step_name="restart", capability="assert_workload_ready", passed=False)],
        )
        assert v.dispatched is True   # the action DID run
        assert v.verified is False    # but it did not help
        assert v.resolved is False
        assert "restart" in v.reason

    def test_passing_verification_resolves_with_evidence(self):
        v = resolution_verdict(
            ["A"], [],
            [VerificationResult(step_name="restart", capability="assert_workload_ready", passed=True)],
        )
        assert v.resolved is True
        assert v.verified is True
        assert v.reason == "dispatched and verified"

    def test_advisory_failure_does_not_block(self):
        v = resolution_verdict(
            ["A"], [],
            [VerificationResult(
                step_name="cleanup", capability="assert_disk_headroom",
                passed=False, required=False,
            )],
        )
        assert v.resolved is True
        assert v.verified is True

    def test_skip_dominates_passing_verification(self):
        v = resolution_verdict(
            ["A"], ["B"],
            [VerificationResult(step_name="restart", capability="assert_workload_ready", passed=True)],
        )
        assert v.resolved is False
        assert v.reason == "not all actions dispatched"

    def test_verdict_serialises_both_axes(self):
        v = resolution_verdict(["A"], [])
        assert v.to_dict() == {
            "resolved": True,
            "dispatched": True,
            "verified": None,
            "reason": "dispatched",
        }
