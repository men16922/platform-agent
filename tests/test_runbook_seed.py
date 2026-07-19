from unittest.mock import MagicMock, patch

from src.agents.operations.aws.runbook_seed import _seed_runbooks, lambda_handler
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS


class TestRunbookSeedHandler:
    @patch("src.agents.operations.aws.runbook_seed._seed_runbooks", return_value=len(BUILTIN_RUNBOOKS))
    def test_create_event_seeds_runbooks(self, seed_runbooks):
        event = {
            "RequestType": "Create",
            "ResourceProperties": {
                "TableName": "incident-runbooks",
                "CatalogVersion": "2026-04-12",
            },
        }

        result = lambda_handler(event, None)

        assert result["PhysicalResourceId"] == "runbook-seed-2026-04-12"
        assert result["Data"]["SeededCount"] == len(BUILTIN_RUNBOOKS)
        assert result["Data"]["TableName"] == "incident-runbooks"
        seed_runbooks.assert_called_once_with("incident-runbooks")

    def test_delete_event_is_noop(self):
        event = {
            "RequestType": "Delete",
            "PhysicalResourceId": "runbook-seed-2026-04-12",
            "ResourceProperties": {
                "TableName": "incident-runbooks",
                "CatalogVersion": "2026-04-12",
            },
        }

        result = lambda_handler(event, None)

        assert result == {"PhysicalResourceId": "runbook-seed-2026-04-12"}


class TestSeedRunbooks:
    def test_seed_runbooks_puts_each_builtin_item(self):
        table = MagicMock()

        with patch("src.agents.operations.aws.runbook_seed._DYNAMO") as dynamo:
            dynamo.Table.return_value = table

            count = _seed_runbooks("incident-runbooks")

        assert count == len(BUILTIN_RUNBOOKS)
        dynamo.Table.assert_called_once_with("incident-runbooks")
        assert table.put_item.call_count == len(BUILTIN_RUNBOOKS)

        seeded_ids = {
            call.kwargs["Item"]["runbook_id"]
            for call in table.put_item.call_args_list
        }
        assert seeded_ids == set(BUILTIN_RUNBOOKS)
