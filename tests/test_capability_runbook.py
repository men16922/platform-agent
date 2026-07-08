"""
Tests for Capability-based runbook schema.
"""

from src.agents.runbooks.capability_schema import (
    CapabilityRunbook,
    RunbookStep,
    evaluate_condition,
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
