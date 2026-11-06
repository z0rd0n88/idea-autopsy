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


@unittest.skip("rewritten in Task 2")
class VerdictTests(unittest.TestCase):
    def test_decision_driving_finding_requires_a_planned_verifier(self):
        for changes in (
            {"severity": "High"},
            {"severity": "Medium", "affects_decision": True},
        ):
            with self.subTest(changes=changes):
                request = assessment([finding(**changes)])
                request["expected_model_roles"] = [
                    item
                    for item in request["expected_model_roles"]
                    if item["role"] != "verifier"
                ]
                request["review_protocol"]["roles"] = [
                    item
                    for item in request["review_protocol"]["roles"]
                    if item["role"] != "verifier"
                ]
                result = policy.execute("verdict", request)
                self.assertEqual("incomplete_coverage", result["assessment_status"])
                self.assertIsNone(result["verdict"])
                self.assertIn("verifier", result["review_role_gaps"])
        no_verifier_needed = policy.execute(
            "verdict",
            assessment([finding(severity="Medium", affects_decision=False)]),
        )
        self.assertEqual("complete", no_verifier_needed["assessment_status"])
        self.assertNotIn("verifier", no_verifier_needed["review_role_gaps"])

    def test_missing_mandatory_role_cannot_complete_a_verdict(self):
        expected = [
            {
                "role": axis,
                "caller_policy": (
                    {"model": "claude-opus-5-5", "mandatory": True}
                    if axis == "risk"
                    else None
                ),
            }
            for axis in policy.AXES
        ]
        observed = [
            policy.execute(
                "model_observation",
                {
                    "preflight": policy.execute(
                        "model_preflight", {"role": axis, "dispatch_path": "inline"}
                    ),
                    "actual_model": "unknown",
                },
            )
            for axis in policy.AXES
            if axis != "risk"
        ]
        for protocol in (
            None,
            {"roles": observed},
            assessment()["review_protocol"],
        ):
            with self.subTest(protocol=protocol):
                request = assessment(expected_model_roles=expected)
                if protocol is None:
                    del request["review_protocol"]
                else:
                    request["review_protocol"] = protocol
                result = policy.execute("verdict", request)
                self.assertEqual("incomplete_coverage", result["assessment_status"])
                self.assertIsNone(result["verdict"])
                self.assertIn("risk", result["model_policy_gaps"])

    def test_complete_verdict_requires_a_predispatch_role_plan(self):
        request = assessment()
        del request["expected_model_roles"]
        result = policy.execute("verdict", request)
        self.assertEqual("incomplete_coverage", result["assessment_status"])
        self.assertIsNone(result["verdict"])
        self.assertEqual(sorted(policy.AXES), result["review_role_gaps"])

    def test_blocked_reviewer_cannot_count_as_complete_coverage(self):
        request = assessment()
        request["expected_model_roles"][policy.AXES.index("risk")]["caller_policy"] = {
            "model": "opus",
            "mandatory": False,
        }
        prepared = policy.execute(
            "model_preflight",
            {
                "role": "risk",
                "dispatch_path": "registered",
                "caller_policy": {"model": "opus", "mandatory": False},
                "agent_model_pin": "sonnet",
                "agent_pin_known": True,
                "host_can_select": True,
                "host_can_reveal": True,
            },
        )
        self.assertFalse(prepared["dispatch_allowed"])
        request["review_protocol"]["roles"][policy.AXES.index("risk")] = policy.execute(
            "model_observation",
            {"preflight": prepared, "actual_model": "unknown"},
        )
        result = policy.execute("verdict", request)
        self.assertEqual("incomplete_coverage", result["assessment_status"])
        self.assertIsNone(result["verdict"])
        self.assertIn("risk", result["review_role_gaps"])

    def test_mandatory_model_gap_uses_incomplete_coverage_path(self):
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
        role = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        request = assessment()
        request["expected_model_roles"][policy.AXES.index("risk")]["caller_policy"] = {
            "model": "claude-opus-5-5",
            "mandatory": True,
        }
        request["review_protocol"]["roles"][policy.AXES.index("risk")] = role
        result = policy.execute("verdict", request)
        self.assertEqual("incomplete_coverage", result["assessment_status"])
        self.assertIsNone(result["verdict"])
        self.assertEqual(["risk"], result["model_policy_gaps"])
        self.assertEqual(
            role, result["review_protocol"]["roles"][policy.AXES.index("risk")]
        )

    def test_confirmed_mandatory_alias_can_complete_a_verdict(self):
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
        role = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "claude-opus-5-5",
                "host_resolved_model": "claude-opus-5-5",
            },
        )
        request = assessment()
        request["expected_model_roles"][policy.AXES.index("risk")]["caller_policy"] = {
            "model": "opus",
            "mandatory": True,
        }
        request["review_protocol"]["roles"][policy.AXES.index("risk")] = role
        result = policy.execute("verdict", request)
        self.assertEqual("complete", result["assessment_status"])
        self.assertEqual("Invest", result["verdict"])
        self.assertEqual([], result["model_policy_gaps"])

    def test_no_model_requirement_does_not_create_a_coverage_gap(self):
        prepared = policy.execute(
            "model_preflight", {"role": "risk", "dispatch_path": "inline"}
        )
        role = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        request = assessment()
        request["review_protocol"]["roles"][policy.AXES.index("risk")] = role
        result = policy.execute("verdict", request)
        self.assertEqual("complete", result["assessment_status"])
        self.assertEqual("Invest", result["verdict"])
        self.assertEqual([], result["model_policy_gaps"])

    def test_shared_assumption_is_not_independent_corroboration(self):
        result = policy.execute(
            "verdict", assessment([finding(), finding(id="F-2", issue_id="I-2")])
        )
        self.assertEqual("insufficient_evidence", result["assessment_status"])
        self.assertIsNone(result["verdict"])
        self.assertEqual({"A-1": ["I-1", "I-2"]}, result["shared_critical_assumptions"])

    def test_independence_explanation_preserves_shared_assumption_ids(self):
        proof = {
            "A-1": {
                "issue_ids": ["I-1", "I-2"],
                "reason": "Separate causal mechanisms remain failing when the other is fixed; synthetic evidence.",
                "sources": FIXTURE["evidence"]["sources"],
            }
        }
        result = policy.execute(
            "verdict",
            assessment(
                [finding(), finding(id="F-2", issue_id="I-2")],
                independence_evidence=proof,
            ),
        )
        self.assertEqual("Skip", result["verdict"])
        self.assertEqual(proof, result["independence_evidence"])
        self.assertEqual({"A-1": ["I-1", "I-2"]}, result["shared_critical_assumptions"])
        proof["A-1"]["issue_ids"] = ["I-1"]
        with self.assertRaises(policy.PolicyError):
            policy.execute(
                "verdict",
                assessment(
                    [finding(), finding(id="F-2", issue_id="I-2")],
                    independence_evidence=proof,
                ),
            )

    def test_unsourced_independence_cannot_unlock_multiple_criticals(self):
        proof = {
            "A-1": {
                "issue_ids": ["I-1", "I-2"],
                "reason": "Merely asserted independence",
                "sources": [],
            }
        }
        with self.assertRaises(policy.PolicyError):
            policy.execute(
                "verdict",
                assessment(
                    [finding(), finding(id="F-2", issue_id="I-2")],
                    independence_evidence=proof,
                ),
            )

    def test_fixture_decision_table(self):
        for case in FIXTURE["verdict_cases"]:
            with self.subTest(case=case["name"]):
                request = assessment([finding(**f) for f in case["findings"]])
                request["coverage"].update(case.get("coverage", {}))
                request["decision_evidence"]["sufficient"] = case.get(
                    "sufficient", True
                )
                if case.get("assets"):
                    request["reusable_assets"] = [
                        {
                            "description": "Synthetic capability",
                            "sources": deepcopy(FIXTURE["evidence"]["sources"]),
                        }
                    ]
                output = policy.execute("verdict", request)
                self.assertEqual(case["status"], output["assessment_status"])
                self.assertEqual(case["verdict"], output["verdict"])
                self.assertEqual(output["verdict"], output["mechanical_verdict"])

    def test_override_separate_audit_without_streak_cap(self):
        override = {
            "verdict": "Proceed with caution",
            "reason": "Reserve lowers confidence.",
            "sources": deepcopy(FIXTURE["evidence"]["sources"]),
        }
        for _ in range(3):
            output = policy.execute("verdict", assessment(override=override))
            self.assertEqual("Invest", output["mechanical_verdict"])
            self.assertEqual(override, output["override"])

    def test_override_cannot_bypass_axis_or_invest_evidence(self):
        override = {
            "verdict": "Invest",
            "reason": "Invalid shortcut.",
            "sources": FIXTURE["evidence"]["sources"],
        }
        request = assessment(override=override)
        request["coverage"]["feasibility"] = "failed"
        with self.assertRaises(policy.PolicyError):
            policy.execute("verdict", request)
        with self.assertRaises(policy.PolicyError):
            policy.execute(
                "verdict",
                assessment(
                    [finding()],
                    decision_evidence={"sufficient": False},
                    override=override,
                ),
            )

    def test_claim_removal_cannot_close_risk(self):
        with self.assertRaises(policy.PolicyError):
            policy.execute(
                "verdict",
                assessment([finding(status="resolved", resolution="claim_removed")]),
            )

    def test_refutation_recomputes_without_approval(self):
        before = policy.execute("verdict", assessment([finding()]))
        after = policy.execute(
            "verdict", assessment([finding(status="refuted", doc_support="refuted")])
        )
        self.assertEqual("Proceed with caution", before["verdict"])
        self.assertEqual("Invest", after["verdict"])
        self.assertEqual(["F-1"], after["excluded_ids"])

    def test_sourced_user_report_is_conditional_not_external_verification(self):
        f = finding(
            origin="user",
            evidence_basis="user_report",
            sources=[
                {
                    "type": "user",
                    "ref": "reply:4",
                    "quote": "My available budget is 100; costs are 160.",
                }
            ],
        )
        output = policy.execute("verdict", assessment([f]))
        self.assertEqual("Proceed with caution", output["verdict"])
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


@unittest.skip("rewritten in Task 4")
class RoutingTests(unittest.TestCase):
    def test_fixture_routes(self):
        for case in FIXTURE["route_cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(
                    case["action"], policy.execute("route", case["request"])["action"]
                )

    def test_loop_flags_propagate_only_to_applicable_stage(self):
        flags = ["--loop", "--verify-claims", "--accept-all"]
        output = policy.execute(
            "route",
            {"flags": flags, "state": {"has_document": True, "has_critique": True}},
        )
        self.assertEqual(["--accept-all"], output["pass_flags"])
        self.assertEqual(sorted(flags), output["loop_flags"])

    def test_invalid_flags_and_state_fail(self):
        requests = [
            {"flags": ["--status", "--loop"]},
            {"flags": ["--reset", "--status"]},
            {"flags": ["--accept-none", "--accept-all"]},
            {"flags": ["--unknown"]},
            {
                "intent": "stress_test",
                "flags": ["--accept-all"],
                "state": {"has_document": True},
            },
            {
                "intent": "evaluate",
                "flags": ["--validate"],
                "state": {"has_document": True},
            },
            {"intent": "evaluate", "flags": ["--status"]},
            {"state": {"current_version": True}},
            {"state": {"has_document": "true"}},
            {"state": {"current_version": "v2"}},
            {"state": {"stage": "waiting_for_user_rewrite"}},
        ]
        for request in requests:
            with self.subTest(request=request), self.assertRaises(policy.PolicyError):
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

    @unittest.skip("rewritten in Task 2")
    def test_pure_operations_do_not_mutate_input(self):
        request = assessment([finding()])
        before = deepcopy(request)
        policy.execute("verdict", request)
        self.assertEqual(before, request)


if __name__ == "__main__":
    unittest.main()
