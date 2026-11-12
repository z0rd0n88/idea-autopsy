"""End to end through the helpers: brief, judgment, revision, re-judgment, stop.

Deterministic contracts only; this does not measure model judgment.
"""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "_shared"))
import policy
import state

FIXTURE = json.loads((ROOT / "tests/fixtures/workflow_cases.json").read_text())
LENSES = [
    {
        "id": lens,
        "examine": f"How the entry does on {lens}",
        "evidence": "Text in the entry",
        "out_of_scope": "",
        "origin": "fixed",
    }
    for lens in policy.FIXED_LENSES
]
BRIEF = {
    "goal": "A two-minute demo that runs on a laptop",
    "goal_provisional": False,
    "requirements": [
        {
            "id": "R1",
            "text": "Runs offline",
            "provenance": "user",
            "support": [],
            "contradicted_by": [],
        }
    ],
    "hypotheses": [],
    "constraints": "One weekend, two people",
    "standard": "",
    "provenance": {"goal": "user", "constraints": "user", "standard": "not_stated"},
    "weakly_supported": False,
    "example_hashes": [],
    "confirmation": None,
}


def summary(response, flags_rewritable=None):
    """The route summary the router builds from a status response."""
    ledger = response["state"]
    version = ledger["current_version"]
    judgments = [
        r for r in ledger["reports"] if r["version"] == version and r["kind"] == "judgment"
    ]
    latest = judgments[-1]["result"] if judgments else {}
    return {
        "current_version": int(version[1:]),
        "stage": ledger["reports"][-1]["kind"] if ledger["reports"] else "snapshot",
        "has_document": True,
        "has_brief": bool(ledger["brief"].get("confirmation")),
        "has_judgment": bool(judgments),
        "rewritable": ledger["rewritable"],
        "decision": latest.get("decision"),
        "assessment_status": latest.get("assessment_status", "complete"),
        "can_revise": latest.get("decision") in ("not_yet", "no"),
    }


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.entry = Path(self.temp.name) / "plan.md"
        self.entry.write_text("Plan: a hosted demo that needs the venue Wi-Fi.\n")
        self.request = {"slug": "plan", "source": str(self.entry)}

    def call(self, operation, **fields):
        return state.execute(operation, {**self.request, **fields})

    def judge(self, response, findings, records):
        roles = [lens["id"] for lens in LENSES] + ["verifier"]
        observed = [
            policy.execute(
                "model_observation",
                {
                    "preflight": policy.execute(
                        "model_preflight", {"role": role, "dispatch_path": "inline"}
                    ),
                    "actual_model": "unknown",
                },
            )
            for role in roles
        ]
        return policy.execute(
            "judgment",
            {
                "findings": findings,
                "lenses": [lens["id"] for lens in LENSES],
                "requirement_ids": response["requirement_ids"],
                "coverage": {lens["id"]: "complete" for lens in LENSES},
                "requirement_records": records,
                "feasibility_label": "achievable",
                "quality_label": "adequate",
                "brief": {
                    "sha256": response["brief_sha256"],
                    "constraints_stated": True,
                    "standard_stated": False,
                },
                "lens_set_sha256": response["lens_set_sha256"],
                "expected_model_roles": [{"role": r, "caller_policy": None} for r in roles],
                "review_protocol": {"roles": observed},
            },
        )

    def route(self, flags=()):
        return policy.execute(
            "route", {"flags": list(flags), "state": summary(self.call("status"))}
        )["action"]

    def test_brief_then_judge_then_revision_round_trip(self):
        created = self.call("init", brief=BRIEF, lenses=LENSES)
        confirmation = {
            "decision_id": "brief-file",
            "brief_sha256": created["brief_sha256"],
            "review_protocol": {"roles": []},
        }
        self.call(
            "update",
            expected_generation=1,
            patch={
                "brief": dict(BRIEF, confirmation=confirmation),
                "rewritable": {"value": True, "decided_by": "default"},
            },
        )
        self.assertEqual("judge", self.route(["--loop"]))

        status = self.call("status")
        self.assertEqual(created["brief_sha256"], status["brief_sha256"])
        finding = deepcopy(FIXTURE["base_finding"])
        first = self.judge(
            status,
            [finding],
            [{"requirement_id": "R1", "status": "not_met", "evidence_location": "plan.md:1", "finding_ids": ["F-1"]}],
        )
        self.assertEqual("no", first["decision"])
        judged = self.call("report", version="v1", kind="judgment", text="v1 judgment", result=first)
        first_id = judged["state"]["reports"][-1]["id"]
        self.assertEqual("revise", self.route(["--loop"]))
        self.assertEqual("stop", self.route())

        revised = self.call(
            "snapshot",
            version="v2",
            parent_version="v1",
            expected_generation=judged["state"]["generation"],
            text="Plan: a demo that runs from a local build with no network.\n",
        )
        revision = self.call(
            "report",
            version="v2",
            kind="revision",
            text="Change record",
            input_report_ids=[first_id],
            result={"revision_changes": [{"finding_id": "F-1", "kind": "authorized_scope_change"}]},
        )
        revision_id = revision["state"]["reports"][-1]["id"]
        self.assertEqual("v2", revised["state"]["current_version"])
        self.assertEqual("judge", self.route(["--loop"]))

        second = self.judge(
            self.call("status"),
            [],
            [{"requirement_id": "R1", "status": "met", "evidence_location": "v2:1", "finding_ids": []}],
        )
        self.assertEqual("yes", second["decision"])
        final = self.call(
            "report",
            version="v2",
            kind="judgment",
            text="v2 judgment",
            input_report_ids=[revision_id],
            result=second,
        )["state"]
        self.assertEqual("stop", self.route(["--loop"]))

        judgments = [r for r in final["reports"] if r["kind"] == "judgment"]
        self.assertEqual(["v1", "v2"], [r["version"] for r in judgments])
        self.assertEqual(
            {created["brief_sha256"]},
            {r["result"]["brief_sha256"] for r in judgments},
        )
        self.assertEqual([first_id], final["reports"][1]["input_report_ids"])
        self.assertEqual([revision_id], final["reports"][2]["input_report_ids"])


if __name__ == "__main__":
    unittest.main()
