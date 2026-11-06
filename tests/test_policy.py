"""Deterministic contracts; these fixtures do not measure model judgment."""

import importlib.util
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "autopsy_policy", ROOT / "skills/_shared/policy.py"
)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)
FIXTURE = json.loads((ROOT / "tests/fixtures/workflow_cases.json").read_text())


def finding(**changes):
    result = deepcopy(FIXTURE["base_finding"])
    result.update(changes)
    return result


def rec(requirement_id, status="met", finding_ids=None):
    return {
        "requirement_id": requirement_id,
        "status": status,
        "evidence_location": "p1",
        "finding_ids": finding_ids or [],
    }


def assessment(findings=None, **changes):
    selected_findings = [] if findings is None else findings
    lenses = list(changes.get("lenses", policy.FIXED_LENSES))
    roles = lenses + ["verifier"]
    expected = [{"role": role, "caller_policy": None} for role in roles]
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
    result = {
        "findings": selected_findings,
        "lenses": lenses,
        "requirement_ids": ["R1"],
        "coverage": {lens: "complete" for lens in lenses},
        "requirement_records": [rec("R1")],
        "feasibility_label": "achievable",
        "quality_label": "adequate",
        "brief": {
            "sha256": "0" * 64,
            "constraints_stated": True,
            "standard_stated": True,
        },
        "lens_set_sha256": "0" * 64,
        "expected_model_roles": expected,
        "review_protocol": {"roles": observed},
    }
    result.update(changes)
    return result


def change(
    category="routine", description="Correct the arithmetic", required_facts=None
):
    item = {
        "category": category,
        "description": description,
        "required_facts": required_facts or [],
    }
    item.update(policy.execute("change_id", item))
    return item


class ModelDispatchTests(unittest.TestCase):
    def test_required_model_is_passed_for_registered_and_pasted_agents(self):
        for dispatch_path in ("registered", "pasted"):
            with self.subTest(dispatch_path=dispatch_path):
                prepared = policy.execute(
                    "model_preflight",
                    {
                        "role": "validator",
                        "dispatch_path": dispatch_path,
                        "caller_policy": {
                            "model": "claude-opus-5-5",
                            "mandatory": True,
                        },
                        "agent_model_pin": None,
                        "agent_pin_known": True,
                        "host_can_select": True,
                        "host_can_reveal": True,
                    },
                )
                self.assertTrue(prepared["dispatch_allowed"])
                self.assertEqual("claude-opus-5-5", prepared["model_argument"])
                observed = policy.execute(
                    "model_observation",
                    {"preflight": prepared, "actual_model": "claude-opus-5-5"},
                )
                self.assertEqual("compliant", observed["status"])
                self.assertEqual("claude-opus-5-5", observed["requested_model"])
                self.assertEqual("claude-opus-5-5", observed["actual_model"])

    def test_conflicting_agent_pin_is_rejected_before_dispatch(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "validator",
                "dispatch_path": "registered",
                "caller_policy": {"model": "opus", "mandatory": True},
                "agent_model_pin": "sonnet",
                "agent_pin_known": True,
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        self.assertFalse(prepared["dispatch_allowed"])
        self.assertIsNone(prepared["model_argument"])
        self.assertEqual("conflicting_pin", prepared["status"])

    def test_unknown_registered_agent_pin_blocks_mandatory_requirement(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "validator",
                "dispatch_path": "registered",
                "caller_policy": {"model": "claude-opus-5-5", "mandatory": True},
                "agent_pin_known": False,
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        self.assertFalse(prepared["dispatch_allowed"])
        self.assertEqual("pin_unknown", prepared["status"])

    def test_mandatory_requirement_blocks_unknown_host_capability(self):
        for capabilities, expected_status in (
            (
                {"host_can_select": None, "host_can_reveal": True},
                "selection_unavailable",
            ),
            (
                {"host_can_select": True, "host_can_reveal": False},
                "visibility_unavailable",
            ),
        ):
            with self.subTest(capabilities=capabilities):
                prepared = policy.execute(
                    "model_preflight",
                    {
                        "role": "risk",
                        "dispatch_path": "inline",
                        "caller_policy": {
                            "model": "claude-opus-5-5",
                            "mandatory": True,
                        },
                        **capabilities,
                    },
                )
                self.assertFalse(prepared["dispatch_allowed"])
                self.assertEqual(expected_status, prepared["status"])

    def test_unknown_or_mismatched_actual_model_is_not_compliant(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "risk",
                "dispatch_path": "inline",
                "caller_policy": {"model": "claude-opus-5-5", "mandatory": True},
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        for actual, expected in (
            ("unknown", "unknown"),
            ("claude-sonnet-5", "mismatch"),
        ):
            with self.subTest(actual=actual):
                observed = policy.execute(
                    "model_observation", {"preflight": prepared, "actual_model": actual}
                )
                self.assertEqual(expected, observed["status"])
                self.assertFalse(observed["policy_compliant"])
                self.assertEqual(actual, observed["actual_model"])

    def test_alias_needs_host_exposed_resolution_to_establish_compliance(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "risk",
                "dispatch_path": "inline",
                "caller_policy": {"model": "opus", "mandatory": True},
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        unknown = policy.execute(
            "model_observation",
            {"preflight": prepared, "actual_model": "claude-opus-5-5"},
        )
        self.assertEqual("unknown", unknown["status"])
        compliant = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "claude-opus-5-5",
                "host_resolved_model": "claude-opus-5-5",
            },
        )
        self.assertEqual("compliant", compliant["status"])

    def test_alias_resolution_to_another_family_is_a_mismatch(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "risk",
                "dispatch_path": "inline",
                "caller_policy": {"model": "opus", "mandatory": True},
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        observed = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "claude-haiku-5",
                "host_resolved_model": "claude-haiku-5",
            },
        )
        self.assertEqual("mismatch", observed["status"])
        self.assertFalse(observed["policy_compliant"])

    def test_exposed_alias_needs_matching_resolution(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "risk",
                "dispatch_path": "inline",
                "caller_policy": {"model": "opus", "mandatory": True},
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        alias_only = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "opus"}
        )
        self.assertEqual("unknown", alias_only["status"])
        self.assertFalse(alias_only["policy_compliant"])
        resolved = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "opus",
                "host_resolved_model": "claude-opus-5-5",
            },
        )
        self.assertEqual("compliant", resolved["status"])
        self.assertTrue(resolved["policy_compliant"])
        wrong_version = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "claude-opus-5-4",
                "host_resolved_model": "claude-opus-5-5",
            },
        )
        self.assertEqual("mismatch", wrong_version["status"])

    def test_no_caller_policy_keeps_dispatch_default_and_records_unknown(self):
        prepared = policy.execute(
            "model_preflight",
            {"role": "risk", "dispatch_path": "inline"},
        )
        self.assertTrue(prepared["dispatch_allowed"])
        self.assertIsNone(prepared["model_argument"])
        observed = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        self.assertEqual("no_requirement", observed["status"])
        self.assertIsNone(observed["requested_model"])
        self.assertEqual("unknown", observed["actual_model"])


SOURCES = [
    {
        "type": "document",
        "ref": "fixture.md:L2",
        "quote": "The prototype fits the stated allocation.",
    }
]


def without_role(request, role):
    request["expected_model_roles"] = [
        item for item in request["expected_model_roles"] if item["role"] != role
    ]
    request["review_protocol"]["roles"] = [
        item for item in request["review_protocol"]["roles"] if item["role"] != role
    ]
    return request


def role_index(request, role):
    return [item["role"] for item in request["expected_model_roles"]].index(role)


class JudgmentTests(unittest.TestCase):
    def test_fixture_judgment_table(self):
        for case in FIXTURE["judgment_cases"]:
            with self.subTest(case=case["name"]):
                request = assessment(
                    [finding(**f) for f in case["findings"]], **deepcopy(case["request"])
                )
                result = policy.execute("judgment", request)
                for key, value in case["expected"].items():
                    self.assertEqual(value, result[key], key)

    def test_requirement_records_must_cover_the_brief_exactly(self):
        for records in (
            [],
            [rec("R1")],
            [rec("R1"), rec("R1"), rec("R2")],
            [rec("R1"), rec("R3")],
        ):
            with self.subTest(records=records), self.assertRaisesRegex(
                policy.PolicyError, "requirement_records must cover"
            ):
                policy.execute(
                    "judgment",
                    assessment(requirement_ids=["R1", "R2"], requirement_records=records),
                )

    def test_critical_with_requirement_id_forces_not_met(self):
        f = finding()
        result = policy.execute(
            "judgment", assessment([f], requirement_records=[rec("R1", "met")])
        )
        self.assertEqual("not_met", result["requirement_results"]["R1"]["status"])
        self.assertEqual([f["id"]], result["requirement_results"]["R1"]["forced_by"])
        self.assertEqual("does_not_meet", result["fit"])
        self.assertEqual("no", result["decision"])

    def test_negative_record_without_established_finding_is_cannot_tell(self):
        result = policy.execute(
            "judgment",
            assessment(requirement_records=[rec("R1", "not_met", finding_ids=[])]),
        )
        self.assertEqual("cannot_tell", result["requirement_results"]["R1"]["status"])
        self.assertEqual("cannot_judge", result["fit"])

    def test_high_on_feasibility_raises_floor_but_never_lowers(self):
        high = finding(severity="High", axes=["feasibility"], lens="feasibility")
        raised = policy.execute("judgment", assessment([high]))
        self.assertEqual("achievable_with_changes", raised["feasibility"])
        self.assertEqual("not_yet", raised["decision"])
        kept = policy.execute(
            "judgment", assessment([high], feasibility_label="not_achievable")
        )
        self.assertEqual("not_achievable", kept["feasibility"])

    def test_quality_never_moves_decision(self):
        result = policy.execute("judgment", assessment(quality_label="weak"))
        self.assertEqual("weak", result["quality"])
        self.assertEqual("yes", result["decision"])

    def test_override_rederives_decision_and_needs_user_decision_to_improve(self):
        down = {
            "labels": {"fit": "does_not_meet"},
            "reason": "The chorus misses the brief's tempo rule.",
            "sources": SOURCES,
        }
        result = policy.execute("judgment", assessment(override=down))
        self.assertEqual("no", result["decision"])
        self.assertEqual("yes", result["mechanical"]["decision"])
        self.assertEqual(down, result["override"])
        up = {"labels": {"fit": "meets"}, "reason": "Reviewer misread R1.", "sources": SOURCES}
        with self.assertRaisesRegex(policy.PolicyError, "decision_id"):
            policy.execute("judgment", assessment([finding()], override=up))
        up["decision_id"] = "D-7"
        lifted = policy.execute("judgment", assessment([finding()], override=up))
        self.assertEqual("yes", lifted["decision"])
        self.assertEqual("no", lifted["mechanical"]["decision"])
        partial = assessment(override=down)
        partial["coverage"]["quality"] = "failed"
        with self.assertRaisesRegex(policy.PolicyError, "override cannot bypass"):
            policy.execute("judgment", partial)
        to_unknown = dict(down, labels={"fit": "cannot_judge"})
        with self.assertRaisesRegex(policy.PolicyError, "override cannot set"):
            policy.execute("judgment", assessment(override=to_unknown))

    def test_coverage_must_match_active_lenses(self):
        request = assessment(lenses=["fit", "feasibility", "quality", "mix"])
        del request["coverage"]["mix"]
        with self.assertRaisesRegex(policy.PolicyError, "coverage must name exactly"):
            policy.execute("judgment", request)

    def test_provisional_flags_follow_the_brief(self):
        result = policy.execute(
            "judgment",
            assessment(
                brief={"sha256": "0" * 64, "constraints_stated": False, "standard_stated": False}
            ),
        )
        self.assertTrue(result["feasibility_provisional"])
        self.assertTrue(result["quality_provisional"])
        stated = policy.execute("judgment", assessment())
        self.assertFalse(stated["feasibility_provisional"])
        self.assertFalse(stated["quality_provisional"])

    def test_verifier_required_for_any_decision(self):
        for findings, decision in (([], "yes"), ([finding()], "no")):
            with self.subTest(decision=decision):
                result = policy.execute(
                    "judgment", without_role(assessment(findings), "verifier")
                )
                self.assertEqual("incomplete_coverage", result["assessment_status"])
                self.assertEqual("cannot_judge", result["decision"])
                self.assertIn("verifier", result["review_role_gaps"])
        vacuous = assessment(
            requirement_ids=[], requirement_records=[], feasibility_label="cannot_judge"
        )
        result = policy.execute("judgment", without_role(vacuous, "verifier"))
        self.assertEqual("complete", result["assessment_status"])

    def test_missing_mandatory_role_cannot_complete_a_judgment(self):
        request = assessment()
        mandatory = {"model": "claude-opus-5-5", "mandatory": True}
        request["expected_model_roles"][role_index(request, "quality")]["caller_policy"] = mandatory
        for protocol in (None, "drop_quality", "keep"):
            with self.subTest(protocol=protocol):
                attempt = deepcopy(request)
                if protocol is None:
                    del attempt["review_protocol"]
                elif protocol == "drop_quality":
                    attempt["review_protocol"]["roles"] = [
                        r for r in attempt["review_protocol"]["roles"] if r["role"] != "quality"
                    ]
                result = policy.execute("judgment", attempt)
                self.assertEqual("incomplete_coverage", result["assessment_status"])
                self.assertEqual("cannot_judge", result["decision"])
                self.assertIn("quality", result["model_policy_gaps"])

    def test_complete_judgment_requires_a_predispatch_role_plan(self):
        request = assessment()
        del request["expected_model_roles"]
        result = policy.execute("judgment", request)
        self.assertEqual("incomplete_coverage", result["assessment_status"])
        self.assertEqual("cannot_judge", result["decision"])
        self.assertEqual(
            sorted(list(policy.FIXED_LENSES) + ["verifier"]), result["review_role_gaps"]
        )

    def test_blocked_reviewer_cannot_count_as_complete_coverage(self):
        request = assessment()
        index = role_index(request, "quality")
        request["expected_model_roles"][index]["caller_policy"] = {
            "model": "opus",
            "mandatory": False,
        }
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "quality",
                "dispatch_path": "registered",
                "caller_policy": {"model": "opus", "mandatory": False},
                "agent_model_pin": "sonnet",
                "agent_pin_known": True,
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        self.assertFalse(prepared["dispatch_allowed"])
        request["review_protocol"]["roles"][index] = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        result = policy.execute("judgment", request)
        self.assertEqual("incomplete_coverage", result["assessment_status"])
        self.assertEqual("cannot_judge", result["decision"])
        self.assertIn("quality", result["review_role_gaps"])

    def test_mandatory_model_gap_uses_incomplete_coverage_path(self):
        mandatory = {"model": "claude-opus-5-5", "mandatory": True}
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "quality",
                "dispatch_path": "inline",
                "caller_policy": mandatory,
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        role = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        request = assessment()
        index = role_index(request, "quality")
        request["expected_model_roles"][index]["caller_policy"] = mandatory
        request["review_protocol"]["roles"][index] = role
        result = policy.execute("judgment", request)
        self.assertEqual("incomplete_coverage", result["assessment_status"])
        self.assertEqual("cannot_judge", result["decision"])
        self.assertEqual(["quality"], result["model_policy_gaps"])
        self.assertEqual(role, result["review_protocol"]["roles"][index])

    def test_confirmed_mandatory_alias_can_complete_a_judgment(self):
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "quality",
                "dispatch_path": "inline",
                "caller_policy": {"model": "opus", "mandatory": True},
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        role = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "claude-opus-5-5",
                "host_resolved_model": "claude-opus-5-5",
            },
        )
        request = assessment()
        index = role_index(request, "quality")
        request["expected_model_roles"][index]["caller_policy"] = {
            "model": "opus",
            "mandatory": True,
        }
        request["review_protocol"]["roles"][index] = role
        result = policy.execute("judgment", request)
        self.assertEqual("complete", result["assessment_status"])
        self.assertEqual("yes", result["decision"])
        self.assertEqual([], result["model_policy_gaps"])

    def test_no_model_requirement_does_not_create_a_coverage_gap(self):
        prepared = policy.execute(
            "model_preflight", {"role": "quality", "dispatch_path": "inline"}
        )
        role = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        request = assessment()
        request["review_protocol"]["roles"][role_index(request, "quality")] = role
        result = policy.execute("judgment", request)
        self.assertEqual("complete", result["assessment_status"])
        self.assertEqual("yes", result["decision"])
        self.assertEqual([], result["model_policy_gaps"])

    def test_independence_explanation_preserves_shared_assumption_ids(self):
        proof = {
            "A-1": {
                "issue_ids": ["I-1", "I-2"],
                "reason": "Separate causal mechanisms remain failing when the other is fixed; synthetic evidence.",
                "sources": SOURCES,
            }
        }
        pair = [finding(), finding(id="F-2", issue_id="I-2")]
        result = policy.execute(
            "judgment", assessment(pair, independence_evidence=proof)
        )
        self.assertEqual("complete", result["assessment_status"])
        self.assertEqual("no", result["decision"])
        self.assertEqual(proof, result["independence_evidence"])
        self.assertEqual({"A-1": ["I-1", "I-2"]}, result["shared_critical_assumptions"])
        proof["A-1"]["issue_ids"] = ["I-1"]
        with self.assertRaisesRegex(policy.PolicyError, "exactly the affected issue ids"):
            policy.execute("judgment", assessment(pair, independence_evidence=proof))

    def test_unsourced_independence_cannot_unlock_multiple_criticals(self):
        proof = {
            "A-1": {
                "issue_ids": ["I-1", "I-2"],
                "reason": "Merely asserted independence",
                "sources": [],
            }
        }
        with self.assertRaisesRegex(policy.PolicyError, "require cited evidence"):
            policy.execute(
                "judgment",
                assessment(
                    [finding(), finding(id="F-2", issue_id="I-2")],
                    independence_evidence=proof,
                ),
            )

    def test_claim_removal_cannot_close_risk(self):
        with self.assertRaisesRegex(policy.PolicyError, "cannot mark the finding resolved"):
            policy.execute(
                "judgment",
                assessment([finding(status="resolved", resolution="claim_removed")]),
            )

    def test_refutation_recomputes_without_approval(self):
        before = policy.execute("judgment", assessment([finding()]))
        after = policy.execute(
            "judgment", assessment([finding(status="refuted", doc_support="refuted")])
        )
        self.assertEqual("no", before["decision"])
        self.assertEqual("yes", after["decision"])
        self.assertEqual(["F-1"], after["excluded_ids"])

    def test_sourced_user_report_is_conditional_not_external_verification(self):
        f = finding(
            origin="user",
            evidence_basis="user_report",
            sources=[
                {
                    "type": "user",
                    "ref": "reply:4",
                    "quote": "The venue only allows four minutes; the track runs six.",
                }
            ],
        )
        output = policy.execute("judgment", assessment([f]))
        self.assertEqual("no", output["decision"])
        self.assertEqual(["I-1"], output["user_report_dependencies"])
        self.assertTrue(
            any("not independently verified" in reason for reason in output["reasons"])
        )
        self.assertEqual("not_checked", f["external_status"])


class FindingSchemaTests(unittest.TestCase):
    def test_generated_lens_in_axes_requires_lens_list(self):
        f = finding(axes=["arrangement"], lens="arrangement")
        with self.assertRaisesRegex(policy.PolicyError, "unknown axis"):
            policy.validate_finding(f)
        lenses = ("fit", "feasibility", "quality", "arrangement")
        self.assertEqual(
            ["arrangement"], policy.validate_finding(f, lenses=lenses)["axes"]
        )

    def test_business_only_fields_are_rejected(self):
        for key in ("thesis_breaking", "plausibly_resolvable"):
            with self.subTest(key=key), self.assertRaisesRegex(
                policy.PolicyError, "no longer accepted"
            ):
                policy.validate_finding(finding(**{key: True}))

    def test_lens_must_be_in_axes_and_requirement_id_in_brief(self):
        with self.assertRaisesRegex(policy.PolicyError, "finding.lens must be in axes"):
            policy.validate_finding(finding(lens="feasibility"))
        with self.assertRaisesRegex(policy.PolicyError, "unknown requirement_id"):
            policy.execute(
                "normalize",
                {"findings": [finding(requirement_id="R9")], "requirement_ids": ["R1"]},
            )

    def test_decisive_finding_needs_requirement_or_feasibility(self):
        f = finding(axes=["quality"], lens="quality", affects_decision=True)
        del f["requirement_id"]
        with self.assertRaisesRegex(policy.PolicyError, "affects_decision requires"):
            policy.execute("normalize", {"findings": [f], "requirement_ids": ["R1"]})

    def test_merge_is_order_independent_and_idempotent(self):
        a = finding(id="a", lens="fit", axes=["fit"], requirement_id="R1")
        b = finding(
            id="b", lens="feasibility", axes=["feasibility"], requirement_id="R1"
        )
        ab = policy.execute("normalize", {"findings": [a, b], "requirement_ids": ["R1"]})
        ba = policy.execute("normalize", {"findings": [b, a], "requirement_ids": ["R1"]})
        self.assertEqual(ab["findings"], ba["findings"])
        merged = ab["findings"][0]
        self.assertEqual(["feasibility", "fit"], merged["axes"])
        self.assertEqual(["feasibility", "fit"], merged["origin_lenses"])
        self.assertEqual("feasibility", merged["lens"])
        again = policy.execute(
            "normalize", {"findings": ab["findings"], "requirement_ids": ["R1"]}
        )
        self.assertEqual(ab["findings"], again["findings"])

    def test_requirement_id_conflict_is_reported_not_picked(self):
        a, b = finding(id="a", requirement_id="R1"), finding(id="b", requirement_id="R2")
        result = policy.execute(
            "normalize", {"findings": [a, b], "requirement_ids": ["R1", "R2"]}
        )
        self.assertEqual("requirement_id", result["conflicts"][0]["field"])

    def test_categories_are_routine_scope_approach(self):
        self.assertEqual(("routine", "scope", "approach"), policy.CATEGORIES)
        with self.assertRaisesRegex(policy.PolicyError, "invalid change category"):
            policy.change_id({"change": {"category": "pricing", "description": "x"}})

    def test_markdown_input_is_rejected(self):
        with self.assertRaisesRegex(policy.PolicyError, "structured findings only"):
            policy.execute("normalize", {"markdown": "## Findings\n- x"})


class NormalizationTests(unittest.TestCase):
    def test_causal_deduplication_keeps_members(self):
        result = policy.execute(
            "normalize",
            {
                "findings": [
                    finding(),
                    finding(id="F-2", axes=["feasibility"], lens="feasibility"),
                ]
            },
        )
        self.assertEqual([], result["conflicts"])
        self.assertEqual(1, len(result["findings"]))
        self.assertEqual(["F-1", "F-2"], result["findings"][0]["member_ids"])
        second = policy.execute("normalize", {"findings": result["findings"]})
        self.assertEqual(result["findings"], second["findings"])

    def test_severity_conflict_does_not_select_maximum(self):
        request = {"findings": [finding(severity="High"), finding(id="F-2")]}
        self.assertEqual(
            "High", policy.execute("normalize", request)["findings"][0]["severity"]
        )
        request["severity_resolutions"] = {
            "I-1": {
                "severity": "High",
                "reason": "Blocking but not fatal.",
                "sources": [
                    {
                        "type": "document",
                        "ref": "fixture.md:L2",
                        "quote": "The prototype fits the stated allocation.",
                    }
                ],
            }
        }
        output = policy.execute("normalize", request)
        self.assertEqual([], output["conflicts"])
        self.assertEqual("High", output["findings"][0]["severity"])

    def test_evidence_conflict_is_localized(self):
        request = {
            "findings": [
                finding(),
                finding(id="F-2", doc_support="refuted"),
                finding(id="F-3", issue_id="I-2"),
            ]
        }
        output = policy.execute("acceptance", request)
        self.assertEqual(
            ["defer", "accept"], [d["decision"] for d in output["decisions"]]
        )

    def test_invalid_source_types_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.execute(
                "normalize",
                {
                    "findings": [
                        finding(
                            sources=[
                                {"type": "imagined", "ref": "none", "quote": "none"}
                            ]
                        )
                    ]
                },
            )


class AcceptanceTests(unittest.TestCase):
    def test_inline_wins_without_approving_remedy(self):
        for flag, explicit in (("--accept-all", "reject"), ("--accept-none", "accept")):
            output = policy.execute(
                "acceptance",
                {
                    "findings": [finding()],
                    "flags": [flag],
                    "inline": {"F-1": {"decision": explicit}},
                },
            )
            self.assertEqual(explicit, output["decisions"][0]["decision"])
            self.assertFalse(output["decisions"][0]["remedy_approved"])

    def test_inline_cannot_resurrect_refutation(self):
        output = policy.execute(
            "acceptance",
            {
                "findings": [finding(status="refuted")],
                "flags": ["--accept-all"],
                "inline": {"F-1": {"decision": "accept"}},
            },
        )
        self.assertEqual("exclude", output["decisions"][0]["decision"])

    def test_unknown_unrated_reach_defer(self):
        for bucket in ("unknown", "unique_unrated", "unique_reach", "speculative"):
            output = policy.execute(
                "acceptance", {"findings": [finding(bucket=bucket)]}
            )
            self.assertEqual("defer", output["decisions"][0]["decision"])

    def test_conflicting_flags_or_causal_alias_decisions_error(self):
        for request in (
            {"findings": [finding()], "flags": ["--accept-all", "--accept-none"]},
            {
                "findings": [finding(), finding(id="F-2")],
                "inline": {
                    "F-1": {"decision": "accept"},
                    "F-2": {"decision": "reject"},
                },
            },
        ):
            with self.assertRaises(policy.PolicyError):
                policy.execute("acceptance", request)


class GateTests(unittest.TestCase):
    def test_routine_proceeds_while_material_waits(self):
        routine, material = change(), change("scope", "Cut the second deliverable")
        output = policy.execute("gate", {"changes": [routine, material]})
        self.assertEqual([routine["id"]], output["ready"])
        self.assertEqual(["material_choice"], output["pending_questions"][0]["reason"])

    def test_all_material_categories_need_choices(self):
        for category in policy.CATEGORIES[1:]:
            output = policy.execute("gate", {"changes": [change(category)]})
            self.assertEqual([], output["ready"])
            self.assertEqual(1, len(output["pending_questions"]))

    def test_bound_answer_reused_but_changed_remedy_not_approved(self):
        old, new = (
            change("approach", "Record live instead of sequencing"),
            change("approach", "Record live with one overdub"),
        )
        decision = {
            "id": "D1",
            "change_id": old["id"],
            "choice": "Use 30 dollars",
            "approved": True,
            "source": "user",
        }
        output = policy.execute("gate", {"changes": [old], "decisions": [decision]})
        self.assertEqual([old["id"]], output["ready"])
        self.assertEqual(["D1"], output["reused_decisions"])
        self.assertEqual(
            [],
            policy.execute("gate", {"changes": [new], "decisions": [decision]})[
                "ready"
            ],
        )
        new["id"] = old["id"]
        with self.assertRaises(policy.PolicyError):
            policy.execute("gate", {"changes": [new], "decisions": [decision]})

    def test_missing_facts_not_invented_and_zero_is_present(self):
        item = change(required_facts=["pilot_count"])
        output = policy.execute("gate", {"changes": [item]})
        self.assertEqual(
            ["pilot_count"], output["pending_questions"][0]["missing_facts"]
        )
        facts = {
            "pilot_count": {"value": 0, "origin": "user", "source": "User reply D2"}
        }
        before = deepcopy(facts)
        self.assertEqual(
            [item["id"]],
            policy.execute("gate", {"changes": [item], "facts": facts})["ready"],
        )
        self.assertEqual(before, facts)

    def test_rejected_change_has_no_pending_fact_question(self):
        item = change("scope", required_facts=["unused"])
        decision = {
            "id": "D1",
            "change_id": item["id"],
            "choice": "Keep scope",
            "approved": False,
            "source": "user",
        }
        output = policy.execute("gate", {"changes": [item], "decisions": [decision]})
        self.assertEqual([item["id"]], output["rejected"])
        self.assertEqual([], output["pending_questions"])

    def test_agent_cannot_mint_user_approval(self):
        item = change("scope")
        with self.assertRaises(policy.PolicyError):
            policy.execute(
                "gate",
                {
                    "changes": [item],
                    "decisions": [
                        {
                            "id": "D1",
                            "change_id": item["id"],
                            "choice": "Yes",
                            "approved": True,
                            "source": "agent",
                        }
                    ],
                },
            )


class RoutingTests(unittest.TestCase):
    BASE = {"has_document": True, "has_brief": True}

    def test_fixture_routes(self):
        for case in FIXTURE["route_cases"]:
            with self.subTest(case=case["name"]):
                if "error" in case:
                    with self.assertRaisesRegex(policy.PolicyError, case["error"]):
                        policy.execute("route", case["request"])
                    continue
                result = policy.execute("route", case["request"])
                self.assertEqual(case["action"], result["action"])
                if "rewritable" in case:
                    self.assertEqual(case["rewritable"], result["rewritable"])

    def test_interim_stop_texts_are_exact(self):
        brief = policy.execute("route", {"state": {"has_document": True}})
        self.assertEqual(policy.INTERIM_BRIEF_STOP, brief["reason"])
        rank = policy.execute(
            "route", {"state": dict(self.BASE, entry_slugs=["a", "b"])}
        )
        self.assertEqual("Ranking arrives in 4.1.0.", rank["reason"])

    def test_revision_flags_with_several_entries_are_rejected(self):
        for flag in ("--loop", "--rewrite", "--accept-all", "--accept-none"):
            with self.subTest(flag=flag), self.assertRaisesRegex(
                policy.PolicyError, "rank mode judges only"
            ):
                policy.execute(
                    "route",
                    {"flags": [flag], "state": dict(self.BASE, entry_slugs=["a", "b"])},
                )
        accepted = policy.execute(
            "route",
            {"flags": ["--critique-only"], "state": dict(self.BASE, entry_slugs=["a", "b"])},
        )
        self.assertEqual("stop", accepted["action"])

    def test_entry_cap_from_thresholds(self):
        cap = policy.THRESHOLDS["rank_max_entries"]
        self.assertEqual(12, cap)
        slugs = [f"e{n}" for n in range(cap + 1)]
        with self.assertRaisesRegex(policy.PolicyError, f"at most {cap} entries"):
            policy.execute("route", {"state": dict(self.BASE, entry_slugs=slugs)})

    def test_input_flags_bypass_the_allowlist(self):
        result = policy.execute(
            "route",
            {"flags": ["--brief", "--slug plan", "--entries"], "state": self.BASE},
        )
        self.assertEqual("judge", result["action"])
        self.assertEqual([], result["pass_flags"])

    def test_stored_judgment_never_rejudges_without_intent(self):
        for decision in ("yes", "not_yet", "no", "cannot_judge"):
            for flags in ([], ["--loop"]):
                with self.subTest(decision=decision, flags=flags):
                    result = policy.execute(
                        "route",
                        {
                            "flags": flags,
                            "state": dict(
                                self.BASE,
                                has_judgment=True,
                                assessment_status="complete",
                                decision=decision,
                                can_revise=False,
                                rewritable={"value": True, "decided_by": "default"},
                            ),
                        },
                    )
                    self.assertNotEqual("judge", result["action"])

    def test_flags_override_default_rewritable_but_not_user(self):
        state = dict(self.BASE, has_judgment=True, assessment_status="complete", decision="no")
        for decided_by, action in (("default", "critique_complete"), ("rank", "critique_complete"), ("user", "ask_user")):
            with self.subTest(decided_by=decided_by):
                result = policy.execute(
                    "route",
                    {
                        "flags": ["--critique-only"],
                        "state": dict(state, rewritable={"value": True, "decided_by": decided_by}),
                    },
                )
                self.assertEqual(action, result["action"])

    def test_loop_flags_propagate_only_to_judge_and_revise(self):
        judge = policy.execute(
            "route",
            {"flags": ["--loop", "--verify-claims", "--accept-all"], "state": self.BASE},
        )
        self.assertEqual("judge", judge["action"])
        self.assertEqual(["--verify-claims"], judge["pass_flags"])
        self.assertEqual(["--accept-all", "--loop", "--verify-claims"], judge["loop_flags"])
        revise = policy.execute(
            "route",
            {
                "flags": ["--loop", "--verify-claims", "--accept-all"],
                "state": dict(
                    self.BASE,
                    has_judgment=True,
                    assessment_status="complete",
                    decision="not_yet",
                    can_revise=True,
                    rewritable={"value": True, "decided_by": "default"},
                ),
            },
        )
        self.assertEqual("revise", revise["action"])
        self.assertEqual(["--accept-all"], revise["pass_flags"])
        with self.assertRaisesRegex(policy.PolicyError, "incompatible"):
            policy.execute("route", {"flags": ["--accept-all"], "state": self.BASE})

    def test_invalid_flags_and_state_fail(self):
        for request, message in (
            ({"flags": ["--unknown"]}, "unknown flag"),
            ({"flags": ["--loop", "--loop"]}, "duplicate flag"),
            ({"flags": ["--accept-all", "--accept-none"]}, "conflict"),
            ({"flags": ["--status", "--loop"]}, "cannot combine"),
            ({"flags": ["--status", "--reset"]}, "cannot combine"),
            ({"intent": "strategy"}, "unknown intent"),
            ({"state": {"stage": "evaluation"}}, "invalid stage"),
            ({"state": {"decision": "Invest"}}, "invalid state decision"),
            ({"state": {"rewritable": {"value": True, "decided_by": "agent"}}}, "decided_by"),
            ({"inputs": [{"type": "verdict", "ref": "x"}]}, "input type"),
        ):
            with self.subTest(request=request), self.assertRaisesRegex(
                policy.PolicyError, message
            ):
                policy.execute("route", request)


class PriorityAndCLITests(unittest.TestCase):
    def test_critical_precedes_five_medium_mentions(self):
        findings = [
            finding(id=f"M-{i}", issue_id="medium-cause", severity="Medium")
            for i in range(5)
        ] + [finding()]
        output = policy.execute("prioritize", {"findings": findings})
        self.assertEqual(["I-1", "medium-cause"], output["ordered_issue_ids"])

    def test_cli_stdin_and_file_aliases(self):
        cli = ROOT / "skills/_shared/policy.py"
        payload = json.dumps({"flags": ["--status"]})
        proc = subprocess.run(
            [sys.executable, str(cli), "route"],
            input=payload,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("status", json.loads(proc.stdout)["action"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(payload)
            for option in ("--request", "--file"):
                proc = subprocess.run(
                    [sys.executable, str(cli), "route", option, str(path)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, proc.returncode, proc.stderr)
        bad = subprocess.run(
            [sys.executable, str(cli), "route"],
            input="[]",
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, bad.returncode)
        self.assertEqual("", bad.stdout)
        self.assertIn("error", json.loads(bad.stderr))

    def test_pure_operations_do_not_mutate_input(self):
        request = assessment([finding()])
        before = deepcopy(request)
        policy.execute("judgment", request)
        self.assertEqual(before, request)


if __name__ == "__main__":
    unittest.main()
