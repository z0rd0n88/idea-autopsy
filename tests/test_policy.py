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


def assessment(findings=None, **changes):
    expected = [{"role": axis, "caller_policy": None} for axis in policy.AXES]
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
    ]
    result = {
        "findings": [] if findings is None else findings,
        "coverage": deepcopy(FIXTURE["coverage"]),
        "decision_evidence": deepcopy(FIXTURE["evidence"]),
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


class VerdictTests(unittest.TestCase):
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


class NormalizationTests(unittest.TestCase):
    def test_causal_deduplication_keeps_members(self):
        result = policy.execute(
            "normalize", {"findings": [finding(), finding(id="F-2", axes=["roi"])]}
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
                "sources": FIXTURE["evidence"]["sources"],
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

    def test_legacy_heading_levels_and_no_triple_count(self):
        for heading in ("##", "###", "####"):
            with self.subTest(heading=heading):
                markdown = "\n".join(
                    [
                        "# Stress test",
                        "## Reviewer A",
                        "- **[Critical]** Raw claim.",
                        "## Synthesis",
                        heading + " Consensus findings (two reviewers)",
                        "- **[High]** `[verified]` Final issue.",
                        heading + " Unique to Reviewer B",
                        "- **[Medium]** Unrated issue.",
                        "## Iteration recommendations for v2",
                        "- **[High]** Final issue.",
                    ]
                )
                output = policy.execute("normalize", {"markdown": markdown})
                self.assertEqual("stress-test-idea", output["format"])
                self.assertEqual(
                    ["Final issue.", "Unrated issue."],
                    [f["statement"] for f in output["findings"]],
                )
                self.assertTrue(output["requires_source_review"])
                self.assertTrue(
                    all(not policy.established(f) for f in output["findings"])
                )

    def test_verdict_table_over_raw_axes(self):
        markdown = "## Critical thinking\n- **[High]** Repeated issue.\n## Issue multiplicity table\n| Issue | Severity | Axes |\n| --- | --- | --- |\n| One actual issue | High | ROI |\n## Verdict: Proceed with caution\n- **[High]** Repeated issue."
        output = policy.execute("normalize", {"markdown": markdown})
        self.assertEqual(
            ["One actual issue"], [f["statement"] for f in output["findings"]]
        )

    def test_unknown_markdown_never_autoaccepts(self):
        imported = policy.execute(
            "normalize",
            {
                "markdown": "- Review numbers\n- **[Critical]** [verified] Demand exists."
            },
        )
        output = policy.execute("acceptance", {"findings": imported["findings"]})
        self.assertEqual(
            ["defer", "defer"], [d["decision"] for d in output["decisions"]]
        )

    def test_fenced_fake_synthesis_is_ignored(self):
        markdown = "```md\n## Synthesis\n### Consensus findings\n- **[Critical]** fake\n```\n## Synthesis\n### Consensus findings\n- **[High]** actual"
        output = policy.execute("normalize", {"markdown": markdown})
        self.assertEqual(["actual"], [f["statement"] for f in output["findings"]])

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
        routine, material = change(), change("target_customer", "Serve clinics")
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
            change("pricing", "Price 30 dollars monthly"),
            change("pricing", "Price 300 dollars monthly"),
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


class IntegrationTests(unittest.TestCase):
    def test_agent_written_revision_is_evaluated_and_preserves_history(self):
        state_spec = importlib.util.spec_from_file_location(
            "integration_state", ROOT / "skills/_shared/state.py"
        )
        ledger = importlib.util.module_from_spec(state_spec)
        state_spec.loader.exec_module(ledger)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "idea.md"
            original = "# Synthetic idea\nBudget cap 100; required costs 80 + 80.\n"
            source.write_text(original)
            base = {"slug": "integration", "source": str(source)}
            initialized = ledger.execute("init", base)
            root = Path(initialized["root"])
            findings = policy.execute("normalize", {"findings": [finding()]})[
                "findings"
            ]
            reviewed = ledger.execute(
                "report",
                {
                    **base,
                    "version": "v1",
                    "kind": "stress_test",
                    "text": "Synthetic findings\n" + json.dumps(findings),
                    "result": {"findings": findings},
                },
            )
            prior_report = reviewed["state"]["reports"][-1]
            prior_bytes = (root / prior_report["path"]).read_bytes()

            routine = change(description="State the arithmetic total as 160")
            material = change(
                "scope", "Drop the second component, leaving one 80-cost component"
            )
            first_gate = policy.execute("gate", {"changes": [routine, material]})
            self.assertEqual([routine["id"]], first_gate["ready"])
            # This is the user's decision fixture; the user supplies no rewritten text.
            decision = {
                "id": "D1",
                "change_id": material["id"],
                "choice": "Drop the second component",
                "approved": True,
                "source": "user",
            }
            accepted = policy.execute(
                "gate", {"changes": [routine, material], "decisions": [decision]}
            )
            self.assertEqual(2, len(accepted["ready"]))
            updated = ledger.execute(
                "update",
                {
                    **base,
                    "expected_generation": reviewed["state"]["generation"],
                    "patch": {"decisions": [decision], "findings": findings},
                },
            )
            generated = "# Synthetic idea v2\nBudget cap 100; retain one component costing 80.\nThe second component is outside this scope, as chosen by the user.\n"
            revised = ledger.execute(
                "snapshot",
                {
                    **base,
                    "version": "v2",
                    "parent_version": "v1",
                    "text": generated,
                    "expected_generation": updated["state"]["generation"],
                },
            )
            self.assertEqual(
                generated,
                (root / revised["state"]["versions"]["v2"]["path"]).read_text(),
            )
            revision = ledger.execute(
                "report",
                {
                    **base,
                    "version": "v2",
                    "kind": "revision",
                    "text": "Agent wrote v2 using decision D1; resource mismatch resolved by scope change.",
                    "input_report_ids": [prior_report["id"]],
                    "result": {"decision_ids": ["D1"]},
                },
            )

            def projection(stored):
                version = stored["current_version"]
                current = [
                    report
                    for report in stored["reports"]
                    if report["version"] == version
                ]
                evaluations = [
                    report for report in current if report["kind"] == "evaluation"
                ]
                result = evaluations[-1]["result"] if evaluations else {}
                return {
                    "current_version": int(version[1:]),
                    "has_document": version in stored["versions"],
                    "has_critique": any(
                        report["kind"] == "stress_test" for report in current
                    ),
                    "has_verdict": bool(evaluations),
                    "stage": current[-1]["kind"] if current else "snapshot",
                    **{
                        key: result[key]
                        for key in ("assessment_status", "verdict")
                        if key in result
                    },
                }

            next_route = policy.execute(
                "route", {"flags": ["--loop"], "state": projection(revision["state"])}
            )
            self.assertEqual("evaluate-proposal-harsh", next_route["action"])
            self.assertEqual(2, next_route["current_version"])
            resolved = finding(
                status="resolved",
                resolution="scope_changed",
                sources=[
                    {
                        "type": "document",
                        "ref": "versions/v2.md:L2",
                        "quote": "Budget cap 100; retain one component costing 80.",
                    }
                ],
            )
            result = policy.execute("verdict", assessment([resolved]))
            self.assertEqual("Invest", result["verdict"])
            evaluated = ledger.execute(
                "report",
                {
                    **base,
                    "version": "v2",
                    "kind": "evaluation",
                    "input_sha256": revision["state"]["versions"]["v2"]["sha256"],
                    "text": "Synthetic bounded assessment\n" + json.dumps(result),
                    "result": {**result, "findings": [resolved]},
                    "input_report_ids": [revision["state"]["reports"][-1]["id"]],
                },
            )
            resumed = policy.execute(
                "route", {"flags": ["--loop"], "state": projection(evaluated["state"])}
            )
            self.assertEqual("stop", resumed["action"])
            self.assertEqual(original, source.read_text())
            self.assertEqual(original, (root / "versions/v1.md").read_text())
            self.assertEqual(prior_bytes, (root / prior_report["path"]).read_bytes())
            self.assertEqual(3, len(evaluated["state"]["reports"]))
            self.assertEqual([decision], evaluated["state"]["decisions"])


class PriorityAndCLITests(unittest.TestCase):
    def test_worked_example_hashes_and_output_contracts(self):
        cases = [
            (
                "consumer-app-pitch/v2-verdict.md",
                "v2.md",
                "complete",
                "Proceed with caution",
            ),
            ("b2b-saas-pivot/v1-verdict.md", "v1.md", "complete", "Pivot"),
            (
                "unsupported-tam-skip/v1-verdict.md",
                "v1.md",
                "insufficient_evidence",
                "null",
            ),
        ]
        for relative, source_name, status, verdict in cases:
            with self.subTest(example=relative):
                report = ROOT / "examples" / relative
                content = report.read_text(encoding="utf-8")
                source_hash = hashlib.sha256(
                    (report.parent / source_name).read_bytes()
                ).hexdigest()
                self.assertIn(f"SHA-256: `{source_hash}`", content)
                self.assertIn(f"`assessment_status={status}`", content)
                self.assertIn(f"`mechanical_verdict={verdict}`", content)
                self.assertIn(f"`verdict={verdict}`", content)
                self.assertIn("Synthetic illustrative output", content)
                self.assertIn("Report ID:", content)

    def test_worked_example_economics_match_the_fixture_text(self):
        consumer = (ROOT / "examples/consumer-app-pitch/v2.md").read_text(
            encoding="utf-8"
        )
        b2b = (ROOT / "examples/b2b-saas-pivot/v1-verdict.md").read_text(
            encoding="utf-8"
        )
        annual_revenue = 8 * 12
        self.assertAlmostEqual(512, annual_revenue * 0.8 / 0.15)
        self.assertAlmostEqual(640, annual_revenue / 0.15)
        self.assertIn("15% annual churn", consumer)
        self.assertIn("$96 × 80% / 15% = $512", consumer)
        self.assertIn("$96 / 15% = $640", consumer)
        self.assertIn("not measured LTV estimates", consumer)
        self.assertEqual(2880, 8 * 30 * 12)
        self.assertEqual(34560, 12 * 8 * 30 * 12)
        self.assertIn("`$2,880`", b2b)
        self.assertIn("`$34,560`", b2b)

    def test_critical_precedes_five_medium_mentions(self):
        findings = [
            finding(id=f"M-{i}", issue_id="medium-cause", severity="Medium")
            for i in range(5)
        ] + [finding()]
        output = policy.execute("prioritize", {"findings": findings})
        self.assertEqual(["I-1", "medium-cause"], output["ordered_issue_ids"])

    def test_fixture_arithmetic(self):
        arr, churn = FIXTURE["arithmetic_cases"]
        self.assertEqual(arr["expected_arr"], arr["seats"] * arr["monthly_price"] * 12)
        self.assertEqual(
            churn["expected_revenue_ltv"],
            churn["monthly_revenue"] / churn["monthly_churn"],
        )
        self.assertAlmostEqual(
            churn["expected_annual_churn"], 1 - (1 - churn["monthly_churn"]) ** 12
        )

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
        policy.execute("verdict", request)
        self.assertEqual(before, request)


if __name__ == "__main__":
    unittest.main()
