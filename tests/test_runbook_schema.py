from src.agents.runbooks.catalog import builtin_runbook_items
from src.agents.runbooks.schema import is_valid_runbook, validate_runbook


class TestValidateRunbook:
    def test_minimal_valid_with_actions(self):
        item = {"runbook_id": "rb-1", "actions": ["AWS-RestartEKSPod"]}
        assert validate_runbook(item) == []
        assert is_valid_runbook(item)

    def test_minimal_valid_with_capabilities(self):
        item = {"runbook_id": "rb-1", "capabilities": ["restart_workload"]}
        assert validate_runbook(item) == []

    def test_missing_runbook_id(self):
        problems = validate_runbook({"actions": ["x"]})
        assert any("runbook_id" in p for p in problems)

    def test_empty_runbook_id(self):
        problems = validate_runbook({"runbook_id": "  ", "actions": ["x"]})
        assert any("runbook_id" in p for p in problems)

    def test_requires_actions_or_capabilities(self):
        problems = validate_runbook({"runbook_id": "rb-1"})
        assert any("actions" in p and "capabilities" in p for p in problems)

    def test_empty_actions_and_capabilities_is_invalid(self):
        problems = validate_runbook({"runbook_id": "rb-1", "actions": [], "capabilities": []})
        assert any("actions" in p and "capabilities" in p for p in problems)

    def test_list_fields_must_be_lists_of_str(self):
        problems = validate_runbook({"runbook_id": "rb-1", "actions": [1, 2]})
        assert any("actions must be a list of strings" in p for p in problems)

    def test_rto_sec_must_be_int_or_none(self):
        assert validate_runbook({"runbook_id": "rb-1", "actions": ["x"], "rto_sec": None}) == []
        assert validate_runbook({"runbook_id": "rb-1", "actions": ["x"], "rto_sec": 60}) == []
        problems = validate_runbook({"runbook_id": "rb-1", "actions": ["x"], "rto_sec": "60"})
        assert any("rto_sec" in p for p in problems)

    def test_provider_must_be_str(self):
        problems = validate_runbook({"runbook_id": "rb-1", "actions": ["x"], "provider": 1})
        assert any("provider" in p for p in problems)

    def test_non_dict_is_invalid(self):
        assert validate_runbook(["not", "a", "dict"])
        assert not is_valid_runbook("nope")

    def test_require_alarm_name(self):
        item = {"runbook_id": "rb-1", "actions": ["x"]}
        assert validate_runbook(item) == []
        problems = validate_runbook(item, require_alarm_name=True)
        assert any("alarm_name" in p for p in problems)
        item["alarm_name"] = "MyAlarm"
        assert validate_runbook(item, require_alarm_name=True) == []


class TestBuiltinRunbooksSatisfyContract:
    def test_all_builtin_items_are_valid_registry_items(self):
        for item in builtin_runbook_items():
            assert validate_runbook(item, require_alarm_name=True) == [], item["runbook_id"]


# --- DynamoDB numeric boundary (live-surfaced production defect) -------------
#
# DynamoDB returns every number as Decimal. A strict `isinstance(x, int)` check
# therefore rejected every registry runbook that declared an rto_sec, so the
# decision stage dropped them from the candidate set and EVERY incident fell back
# to generic-recovery (notify only). Only generic-recovery survived — its rto_sec
# is null. Found by running a real incident against the live table (4 of 5 rows
# rejected); these guards keep the storage type from silently disarming the agent.

from decimal import Decimal  # noqa: E402

from src.agents.runbooks.schema import normalise_runbook  # noqa: E402


def _runbook(**overrides):
    item = {
        "runbook_id": "rb",
        "alarm_name": "rb",
        "actions": ["A"],
    }
    item.update(overrides)
    return item


class TestRtoSecAcceptsStorageNumerics:
    def test_decimal_rto_is_valid(self):
        assert validate_runbook(_runbook(rto_sec=Decimal("180")), require_alarm_name=True) == []

    def test_plain_int_still_valid(self):
        assert validate_runbook(_runbook(rto_sec=180), require_alarm_name=True) == []

    def test_null_still_valid(self):
        assert validate_runbook(_runbook(rto_sec=None), require_alarm_name=True) == []

    def test_fractional_decimal_is_rejected(self):
        problems = validate_runbook(_runbook(rto_sec=Decimal("180.5")), require_alarm_name=True)
        assert any("rto_sec" in p for p in problems)

    def test_string_is_still_rejected(self):
        """Accepting the storage type must not turn into parsing text."""
        problems = validate_runbook(_runbook(rto_sec="180"), require_alarm_name=True)
        assert any("rto_sec" in p for p in problems)

    def test_bool_is_rejected_despite_being_an_int_subclass(self):
        problems = validate_runbook(_runbook(rto_sec=True), require_alarm_name=True)
        assert any("rto_sec" in p for p in problems)


class TestNormaliseRunbook:
    def test_decimal_is_coerced_to_int(self):
        item = normalise_runbook(_runbook(rto_sec=Decimal("180")))
        assert item["rto_sec"] == 180
        assert isinstance(item["rto_sec"], int)

    def test_original_item_is_not_mutated(self):
        original = _runbook(rto_sec=Decimal("180"))
        normalise_runbook(original)
        assert isinstance(original["rto_sec"], Decimal), "must not mutate the caller's dict"

    def test_passthrough_for_int_none_and_non_dict(self):
        assert normalise_runbook(_runbook(rto_sec=42))["rto_sec"] == 42
        assert normalise_runbook(_runbook(rto_sec=None))["rto_sec"] is None
        assert normalise_runbook("not-a-dict") == "not-a-dict"

    def test_unconvertible_value_is_left_for_validation_to_reject(self):
        item = normalise_runbook(_runbook(rto_sec="180"))
        assert item["rto_sec"] == "180"
        assert validate_runbook(item, require_alarm_name=True)
