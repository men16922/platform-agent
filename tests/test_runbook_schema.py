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
