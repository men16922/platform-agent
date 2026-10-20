"""Check the saved-evidence replay against counterfactual record mutations."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from replay import replay

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads(Path(__file__).with_name("cases.json").read_text())
EXPECTED = json.loads(Path(__file__).with_name("expectations.json").read_text())
REPORTS = ROOT / "docs/evidence/dogfood-20261003/repeats/r4-envelope-proxy-j"


class SavedEvidenceReplay(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="platform-agent-replay-")
        self.addCleanup(self.temp.cleanup)
        self.reports = Path(self.temp.name)
        for case in CASES:
            shutil.copyfile(REPORTS / (case["id"] + ".json"), self.reports / (case["id"] + ".json"))

    def change(self, case_id, change):
        path = self.reports / (case_id + ".json")
        row = json.loads(path.read_text())
        change(row)
        path.write_text(json.dumps(row))
        return next(c for c in replay(CASES, EXPECTED, self.reports)["cases"] if c["case_id"] == case_id)

    def test_request_target_cannot_be_swapped_under_a_case_id(self):
        row = self.change("lookalike", lambda r: r["request"]["target"].update(namespace="other"))
        self.assertEqual(row["contract"], "fail")

    def test_fabricated_quote_does_not_keep_a_schema_success_label(self):
        row = self.change("lookalike", lambda r: r["output"]["observations"][0].update(quote="Invented confirmed common cause."))
        self.assertEqual(row["contract"], "fail")

    def test_withheld_source_must_not_have_a_model_request(self):
        row = self.change("stale-injection", lambda r: r.update(http_attempt_count=1))
        self.assertEqual(row["contract"], "fail")

    def test_blanket_recovery_abstention_fails_the_positive_control(self):
        row = self.change("supported-recovery", lambda r: r["output"].update(recovery="not_established"))
        self.assertEqual(row["contract"], "pass")
        self.assertEqual(row["recovery_fixture"], "fail")


if __name__ == "__main__":
    unittest.main()
