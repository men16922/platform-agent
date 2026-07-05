from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS, builtin_runbook_items


class TestBuiltinRunbookItems:
    def test_builtin_runbook_items_include_dynamo_partition_key(self):
        items = builtin_runbook_items()

        assert len(items) == len(BUILTIN_RUNBOOKS)
        assert {item["runbook_id"] for item in items} == set(BUILTIN_RUNBOOKS)
        assert all(item["alarm_name"] == item["runbook_id"] for item in items)
        assert all("capabilities" in item for item in items)
        assert all("provider" in item for item in items)
        assert all("resource_types" in item for item in items)

    def test_builtin_runbook_items_are_deep_copied(self):
        items = builtin_runbook_items()

        items[0]["capabilities"].append("custom-capability")

        first_runbook_id = items[0]["runbook_id"]
        assert "custom-capability" not in BUILTIN_RUNBOOKS[first_runbook_id]["capabilities"]
