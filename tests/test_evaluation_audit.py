"""Metric and persistence tests; synthetic records do not measure model quality."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills/_shared"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SHARED / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_module = load("evaluation_audit")
state = load("state")
FIXTURE = json.loads((ROOT / "tests/fixtures/evaluation_audit_cases.json").read_text())


class EvaluationAuditTests(unittest.TestCase):
    def setUp(self):
        self.request = deepcopy(FIXTURE)

    def test_metrics_distinguish_abstention_and_revision_regression(self):
        result = audit_module.audit(self.request)
        m = result["metrics"]
        self.assertEqual(
            m["reference_agreement"], {"numerator": 2, "denominator": 4, "rate": 0.5}
        )
        self.assertEqual(m["equivalent_outcome_changes"]["denominator"], 3)
        self.assertEqual(m["equivalent_outcome_changes"]["numerator"], 2)
        self.assertEqual(
            m["equivalent_verdict_changes"],
            {"numerator": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(m["abstention"]["numerator"], 1)
        self.assertEqual(m["coverage_complete"]["numerator"], 6)
        self.assertEqual(m["revision_corrections"]["rate"], 0.5)
        self.assertEqual(m["revision_regressions"]["rate"], 0.5)
        self.assertEqual(result["unlabeled_runs"], 2)
        self.assertEqual(result["data_kind"], "synthetic")

    def test_empty_denominators_are_unknown_not_zero_or_perfect(self):
        self.request.update(runs=[], comparisons=[])
        result = audit_module.audit(self.request)
        self.assertTrue(
            all(
                m == {"numerator": 0, "denominator": 0, "rate": None}
                for m in result["metrics"].values()
            )
        )

    def test_unlabeled_revision_is_excluded(self):
        del self.request["runs"][2]["reference"]
        result = audit_module.audit(self.request)
        self.assertEqual(result["unlabeled_revision_pairs"], 2)
        self.assertIsNone(result["metrics"]["revision_regressions"]["rate"])

    def test_incomplete_coverage_counts_as_abstention(self):
        r = self.request["runs"][4]
        r["coverage"]["roi"] = "failed"
        r["assessment_status"] = "incomplete_coverage"
        result = audit_module.audit(self.request)
        self.assertEqual(result["metrics"]["coverage_complete"]["numerator"], 5)
        self.assertEqual(result["metrics"]["abstention"]["numerator"], 1)

    def test_bad_records_fail_instead_of_changing_denominators(self):
        mutations = [
            lambda q: q.update(schema_version=True),
            lambda q: q.update(extra="typo"),
            lambda q: q["runs"].append(deepcopy(q["runs"][0])),
            lambda q: q["runs"][0].update(source_hash="not-a-hash"),
            lambda q: q["runs"][0].update(verdict=None),
            lambda q: q["runs"][0].update(verdict=[]),
            lambda q: q["runs"][0]["coverage"].update(roi="failed"),
            lambda q: q["runs"][0]["reference"].update(independent=False),
            lambda q: q["runs"][0]["reference"].update(source_hash="f" * 64),
            lambda q: q["comparisons"][0].update(after="absent"),
            lambda q: q["comparisons"][0].update(after="original"),
            lambda q: q["comparisons"][0].update(transform="unknown"),
            lambda q: q["comparisons"][0].update(reason=""),
            lambda q: q["comparisons"][3].update(transform="paraphrase"),
            lambda q: q["runs"][5].update(source_hash="f" * 64),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                request = deepcopy(FIXTURE)
                mutate(request)
                with self.assertRaises(audit_module.AuditError):
                    audit_module.audit(request)

    def test_scope_evidence_and_judge_changes_are_not_equivalent(self):
        for key in (
            "case_id",
            "decision_id",
            "evidence_id",
            "model",
            "protocol_id",
            "condition",
        ):
            with self.subTest(key=key):
                request = deepcopy(FIXTURE)
                request["runs"][1][key] = "changed"
                request["runs"][1].pop("reference")
                with self.assertRaises(audit_module.AuditError):
                    audit_module.audit(request)

    def test_reverse_duplicate_pair_rejected(self):
        pair = deepcopy(self.request["comparisons"][0])
        pair["before"], pair["after"] = pair["after"], pair["before"]
        self.request["comparisons"].append(pair)
        with self.assertRaisesRegex(audit_module.AuditError, "duplicate comparison"):
            audit_module.audit(self.request)

    def test_unknown_model_can_be_recorded_but_not_compared(self):
        for run in self.request["runs"]:
            run["model"] = "unknown"
        with self.assertRaisesRegex(audit_module.AuditError, "known model"):
            audit_module.audit(self.request)
        self.request["comparisons"] = []
        self.assertEqual(audit_module.audit(self.request)["run_count"], 6)

    def test_revision_may_change_evidence_with_version_specific_reference(self):
        self.request["runs"][2]["evidence_id"] = "new-evidence"
        self.request["runs"][2]["reference"]["evidence_id"] = "new-evidence"
        self.assertEqual(
            audit_module.audit(self.request)["metrics"]["revision_corrections"][
                "numerator"
            ],
            1,
        )

    def test_no_input_mutation(self):
        original = deepcopy(self.request)
        audit_module.audit(self.request)
        self.assertEqual(original, self.request)

    def test_cli_reads_stdin_and_errors_without_success_output(self):
        cmd = [sys.executable, str(SHARED / "evaluation_audit.py")]
        good = subprocess.run(
            cmd, input=json.dumps(self.request), capture_output=True, text=True
        )
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["run_count"], 6)
        for raw in ("{", "null", '{"schema_version": 1}'):
            bad = subprocess.run(cmd, input=raw, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertEqual(bad.stdout, "")
            self.assertIn("audit error:", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)

    def test_additive_review_metadata_round_trips_in_existing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            request = {"slug": "metadata", "project_dir": directory}
            state.execute("init", {**request, "text": "Synthetic proposal"})
            result = {
                "review_protocol": {
                    "protocol_id": "judgment-rubric-v1",
                    "model": "unknown",
                },
                "judgment_audit": {"F-1": {"counterevidence": "unknown"}},
                "forecast_checks": [
                    {"status": "unavailable", "reason": "No supplied comparator"}
                ],
                "success_case": {"hypothesis": "Synthetic, untested"},
                "revision_changes": [{"categories": ["presentation_only"]}],
            }
            saved = state.execute(
                "report",
                {
                    **request,
                    "version": "v1",
                    "kind": "validation",
                    "text": "Synthetic metadata fixture",
                    "result": result,
                },
            )
            loaded = state.execute("status", request)
            self.assertEqual(loaded["state"]["reports"][-1]["result"], result)
            self.assertEqual(saved["state"]["schema_version"], 2)


if __name__ == "__main__":
    unittest.main()
