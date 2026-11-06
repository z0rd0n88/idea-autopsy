"""Ledger durability, provenance, concurrency, and explicit migration checks."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SHARED = Path(__file__).resolve().parents[1] / "skills" / "_shared"
sys.path.insert(0, str(SHARED))
import state
import policy


def make_brief(goal="Ship a two-minute demo", requirements=("Runs offline",)):
    return {
        "goal": goal,
        "goal_provisional": False,
        "requirements": [
            {
                "id": f"R{number}",
                "text": text,
                "provenance": "user",
                "support": [],
                "contradicted_by": [],
            }
            for number, text in enumerate(requirements, 1)
        ],
        "hypotheses": [],
        "constraints": "",
        "standard": "",
        "provenance": {
            "goal": "user",
            "constraints": "not_stated",
            "standard": "not_stated",
        },
        "weakly_supported": False,
        "example_hashes": [],
        "confirmation": None,
    }


def confirmed(brief):
    brief = dict(brief)
    brief["confirmation"] = {
        "decision_id": "brief-ok",
        "brief_sha256": state.brief_sha256(brief),
        "review_protocol": {"roles": []},
    }
    return brief


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
GENERATED = {
    "id": "mix",
    "examine": "Balance between instruments",
    "evidence": "The mix notes",
    "out_of_scope": "",
    "origin": "generated",
}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.doc = self.project / "proposal.md"
        self.doc.write_text("Original proposal\n## Appendix\nmaterial evidence\n")
        self.request = {"slug": "demo", "source": str(self.doc)}

    def init(self):
        return state.execute("init", self.request)

    def call(self, operation, **fields):
        return state.execute(operation, {**self.request, **fields})

    def report(self, text="Review", **fields):
        fields.setdefault(
            "result",
            {
                "assessment_status": "incomplete_coverage",
                "expected_model_roles": [],
                "review_protocol": {"roles": []},
            },
        )
        return self.call(
            "report", version="v1", kind="revision", text=text, **fields
        )

    def test_init_snapshots_and_nested_source_resolves_same_ledger(self):
        result = self.init()
        ledger = result["state"]
        self.assertEqual(
            (ledger["schema_version"], ledger["current_version"], ledger["generation"]),
            (3, "v1", 1),
        )
        snapshot = Path(result["root"]) / "versions" / "v1.md"
        self.assertEqual(snapshot.read_bytes(), self.doc.read_bytes())
        self.assertEqual(
            state.execute("status", {"slug": "demo", "source": str(snapshot)})["root"],
            result["root"],
        )
        self.assertFalse(self.call("status")["source_changed"])
        self.doc.write_text("modified externally")
        self.assertTrue(self.call("status")["source_changed"])
        self.assertIn("Original proposal", snapshot.read_text())
        with self.assertRaisesRegex(state.StateError, "different .autopsy slug"):
            state.execute("status", {"slug": "other", "source": str(snapshot)})

    def test_pasted_input_requires_explicit_project_and_snapshots_increment(self):
        request = {"slug": "paste", "project_dir": str(self.project)}
        result = state.execute("init", request)
        self.assertIsNone(result["state"]["current_version"])
        v1 = state.execute(
            "snapshot",
            {**request, "version": "v1", "text": "draft one", "expected_generation": 1},
        )
        v2 = state.execute(
            "snapshot",
            {
                **request,
                "version": "v2",
                "parent_version": "v1",
                "text": "draft two",
                "expected_generation": 2,
            },
        )
        self.assertEqual(v2["state"]["versions"]["v2"]["parent_version"], "v1")
        self.assertEqual((Path(v1["root"]) / "versions/v1.md").read_text(), "draft one")
        with self.assertRaises(state.StateError):
            state.execute(
                "snapshot",
                {
                    **request,
                    "version": "v2",
                    "text": "overwrite",
                    "expected_generation": 3,
                },
            )

    def test_same_slug_cannot_silently_reuse_another_source(self):
        self.init()
        other = self.project / "other.md"
        other.write_text("a different idea")
        with self.assertRaisesRegex(state.StateError, "does not belong"):
            state.execute("status", {"slug": "demo", "source": str(other)})
        report = self.report()["state"]["reports"][-1]
        root = self.project / ".autopsy/demo"
        self.assertEqual(
            state.execute(
                "status", {"slug": "demo", "source": str(root / report["path"])}
            )["root"],
            str(root),
        )

    def test_original_hash_updates_only_when_original_file_is_captured(self):
        self.init()
        original = self.doc.read_bytes()
        self.doc.write_text("new user draft")
        self.call(
            "snapshot",
            version="v2",
            parent_version="v1",
            file=str(self.doc),
            expected_generation=1,
        )
        self.assertFalse(self.call("status")["source_changed"])
        self.call(
            "snapshot",
            version="v3",
            parent_version="v2",
            text="agent revision",
            expected_generation=2,
        )
        self.assertFalse(self.call("status")["source_changed"])
        self.assertEqual(
            (self.project / ".autopsy/demo/versions/v1.md").read_bytes(), original
        )
        self.assertEqual(self.doc.read_text(), "new user draft")

    def test_identical_child_does_not_consume_generation_or_version(self):
        before = self.init()["state"]
        with self.assertRaisesRegex(state.StateError, "identical"):
            self.call(
                "snapshot",
                version="v2",
                parent_version="v1",
                file=str(self.doc),
                expected_generation=1,
            )
        self.assertEqual(self.call("status")["state"], before)
        with self.assertRaisesRegex(state.StateError, "parent_version"):
            self.call(
                "snapshot",
                version="v2",
                text="changed without parent",
                expected_generation=1,
            )

    def test_unknown_request_fields_and_invalid_lineage_are_rejected(self):
        result = self.init()
        with self.assertRaisesRegex(state.StateError, "unknown report request fields"):
            self.report(inputReportIds=["silently-ignored-typo"])
        candidate = json.loads(json.dumps(result["state"]))
        candidate["source"]["sha256"] = None
        with self.assertRaisesRegex(state.StateError, "source hash"):
            state.validate_state(candidate)
        candidate = json.loads(json.dumps(result["state"]))
        candidate["versions"]["v1"]["parent_version"] = "v1"
        with self.assertRaisesRegex(state.StateError, "precede"):
            state.validate_state(candidate)

    def test_status_does_not_create_a_lock_for_missing_or_legacy_state(self):
        root = self.project / ".autopsy/demo"
        root.mkdir(parents=True)
        before = list(root.iterdir())
        with self.assertRaisesRegex(state.StateError, "lock is missing"):
            self.call("status")
        self.assertEqual(list(root.iterdir()), before)
        (root / "state.json").write_text('{"slug":"demo"}')
        with self.assertRaisesRegex(state.StateError, "another Idea Autopsy version"):
            self.call("status")
        self.assertFalse((root / ".lock").exists())

    def test_replaced_decision_and_context_remain_in_audit_history(self):
        initialized = self.call("init", brief=make_brief("first"))["state"]
        decision = {
            "id": "d1",
            "change_id": "a" * 64,
            "choice": "remain B2C",
            "approved": False,
            "source": "user",
        }
        self.call("update", expected_generation=1, patch={"decisions": [decision]})
        replacement = {**decision, "choice": "choose B2B", "approved": True}
        latest = self.call(
            "update",
            expected_generation=2,
            patch={"decisions": [replacement], "brief": make_brief("second")},
        )["state"]
        self.assertEqual(
            initialized["history"][0]["details"]["brief_sha256"],
            state.brief_sha256(make_brief("first")),
        )
        changes = latest["history"][-1]["details"]["changes"]
        self.assertEqual(changes["decisions"]["before"], [decision])
        self.assertEqual(changes["decisions"]["after"], [replacement])
        self.assertEqual(changes["brief"]["before"], make_brief("first"))

    def test_findings_validate_source_types_axes_and_resolution(self):
        self.init()
        finding = {
            "id": "f1",
            "issue_id": "i1",
            "assumption_ids": [],
            "statement": "Document arithmetic contradicts itself",
            "kind": "contradiction",
            "severity": "High",
            "origin": "reviewer",
            "doc_support": "supported",
            "external_status": "not_checked",
            "confidence": "high",
            "sources": [{"type": "calculation", "ref": "v1:3", "quote": "2 + 2 = 5"}],
            "axes": ["fit"],
            "lens": "fit",
            "requirement_id": "R1",
            "affects_decision": True,
            "status": "active",
            "resolution": "unresolved",
            "bucket": "unique_real",
            "evidence_basis": "document_logic",
            "severity_reason": "The arithmetic changes whether R1 is met",
        }
        for fields in (
            {"axes": ["unknown"]},
            {"sources": [{"type": "imagined", "ref": "v1:3", "quote": "claim"}]},
            {"sources": [{"type": "document", "ref": "", "quote": "claim"}]},
            {"status": "resolved", "resolution": "claim_removed"},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(state.StateError):
                    self.call(
                        "update",
                        expected_generation=1,
                        patch={"findings": [{**finding, **fields}]},
                    )
        self.assertEqual(
            self.call("update", expected_generation=1, patch={"findings": [finding]})[
                "state"
            ]["findings"],
            [finding],
        )

    def test_report_hashes_unique_ids_and_upstream_report_links(self):
        self.init()
        first = self.report(
            result={
                "summary": "first pass",
                "assessment_status": "incomplete_coverage",
                "expected_model_roles": [],
                "review_protocol": {"roles": []},
            }
        )["state"]["reports"][-1]
        second = self.report("Second review", input_report_ids=[first["id"]])["state"][
            "reports"
        ][-1]
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(second["input_report_ids"], [first["id"]])
        root = Path(self.call("status")["root"])
        self.assertEqual((root / first["path"]).read_text(), "Review")
        before = self.call("status")["state"]
        for extra in (
            {"input_report_ids": ["unknown"]},
            {"input_sha256": "0" * 64},
            {
                "result": {
                    "decision": "yes",
                    "assessment_status": "incomplete_coverage",
                }
            },
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(state.StateError):
                    self.report(**extra)
        self.assertEqual(self.call("status")["state"], before)

    def judgment_result(self, brief, lenses, **changes):
        roles = [lens["id"] for lens in lenses] + ["verifier"]
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
        request = {
            "findings": [],
            "lenses": [lens["id"] for lens in lenses],
            "requirement_ids": [item["id"] for item in brief["requirements"]],
            "coverage": {lens["id"]: "complete" for lens in lenses},
            "requirement_records": [
                {
                    "requirement_id": item["id"],
                    "status": "met",
                    "evidence_location": "p1",
                    "finding_ids": [],
                }
                for item in brief["requirements"]
            ],
            "feasibility_label": "achievable",
            "quality_label": "adequate",
            "brief": {
                "sha256": state.brief_sha256(brief),
                "constraints_stated": False,
                "standard_stated": False,
            },
            "lens_set_sha256": state.lens_set_sha256(lenses),
            "expected_model_roles": [{"role": r, "caller_policy": None} for r in roles],
            "review_protocol": {"roles": observed},
        }
        request.update(changes)
        return policy.execute("judgment", request)

    def judged_ledger(self, brief=None, lenses=None):
        brief = brief or make_brief()
        lenses = lenses or LENSES
        self.call("init", brief=brief, lenses=lenses)
        result = self.judgment_result(brief, lenses)
        report = self.call(
            "report", version="v1", kind="judgment", text="Judgment", result=result
        )
        return report["state"], result

    def test_init_stores_brief_rewritable_and_lenses(self):
        brief = make_brief()
        rewritable = {"value": True, "decided_by": "default"}
        ledger = self.call("init", brief=brief, rewritable=rewritable, lenses=LENSES)[
            "state"
        ]
        self.assertEqual(1, ledger["generation"])
        status = self.call("status")["state"]
        self.assertEqual(
            (brief, rewritable, LENSES),
            (status["brief"], status["rewritable"], status["lenses"]),
        )

    def test_schema_mismatch_is_refused_before_lock_and_journal(self):
        root = self.project / ".autopsy/demo"
        root.mkdir(parents=True)
        for version in (2, 4):
            raw = json.dumps({"schema_version": version, "slug": "demo"}).encode()
            (root / "state.json").write_bytes(raw)
            for operation in ("status", "init"):
                with self.subTest(version=version, operation=operation):
                    with self.assertRaisesRegex(
                        state.StateError, rf"another Idea Autopsy version \(schema {version}\)"
                    ):
                        self.call(operation)
            self.assertFalse((root / ".lock").exists())
            self.assertFalse((root / ".transaction.json").exists())
            self.assertEqual(raw, (root / "state.json").read_bytes())

    def test_slugify_rules(self):
        self.assertEqual("my-entry-v2-md", state.slugify("My Entry (v2).md"))
        self.assertEqual(80, len(state.slugify("a" * 100)))
        self.assertEqual("brief-plan", state.slugify("brief-" + "plan"))
        with self.assertRaisesRegex(state.StateError, "cannot derive a slug"):
            state.slugify("!!!")

    def test_list_files_refuses_symlinks_and_skips_dotfiles(self):
        entries = self.project / "entries"
        entries.mkdir()
        for name in ("b.md", "a.md", ".hidden.md"):
            (entries / name).write_text(name)
        (entries / "nested").mkdir()
        brief = entries / "brief.md"
        brief.write_text("brief")
        self.assertEqual(
            ["a.md", "b.md"],
            [path.name for path in state.list_files(entries, exclude=[brief])],
        )
        secret = self.project / "secret.txt"
        secret.write_text("GH_TOKEN=x")
        (entries / "c.md").symlink_to(secret)
        with self.assertRaisesRegex(state.StateError, "symlinks are not accepted.*c.md"):
            state.list_files(entries)

    def test_symlinked_source_is_refused(self):
        link = self.project / "link.md"
        link.symlink_to(self.doc)
        with self.assertRaisesRegex(state.StateError, "must not be a symlink"):
            state.execute("init", {"slug": "linked", "source": str(link)})

    def test_brief_patch_is_refused_after_confirmation_or_judgment(self):
        self.call("init", brief=make_brief())
        self.call("update", expected_generation=1, patch={"brief": make_brief("second")})
        self.call(
            "update", expected_generation=2, patch={"brief": confirmed(make_brief("third"))}
        )
        with self.assertRaisesRegex(state.StateError, "brief is fixed for this slug"):
            self.call("update", expected_generation=3, patch={"brief": make_brief("fourth")})
        other = self.project / "other.md"
        other.write_text("other entry")
        request = {"slug": "other", "source": str(other)}
        brief = make_brief()
        state.execute("init", {**request, "brief": brief, "lenses": LENSES})
        state.execute(
            "report",
            {
                **request,
                "version": "v1",
                "kind": "judgment",
                "text": "J",
                "result": self.judgment_result(brief, LENSES),
            },
        )
        with self.assertRaisesRegex(state.StateError, "brief is fixed for this slug"):
            state.execute(
                "update",
                {**request, "expected_generation": 2, "patch": {"brief": make_brief("x")}},
            )

    def test_lens_patch_after_judgment_needs_user_edited_origin(self):
        lenses = LENSES + [GENERATED]
        ledger, _ = self.judged_ledger(lenses=lenses)
        edited = dict(GENERATED, examine="Balance of the mix at low volume")
        with self.assertRaisesRegex(state.StateError, "origin user_edited"):
            self.call(
                "update",
                expected_generation=ledger["generation"],
                patch={"lenses": LENSES + [edited]},
            )
        with self.assertRaisesRegex(state.StateError, "same lens IDs"):
            self.call(
                "update", expected_generation=ledger["generation"], patch={"lenses": LENSES}
            )
        saved = self.call(
            "update",
            expected_generation=ledger["generation"],
            patch={"lenses": LENSES + [dict(edited, origin="user_edited")]},
        )["state"]
        self.assertEqual("user_edited", saved["lenses"][-1]["origin"])

    def test_new_judgment_report_must_match_stored_lenses_and_hashes(self):
        brief, lenses = make_brief(), LENSES + [GENERATED]
        self.call("init", brief=brief, lenses=lenses)
        wrong_brief = self.judgment_result(brief, lenses)
        wrong_brief["brief_sha256"] = "1" * 64
        wrong_lenses = self.judgment_result(brief, lenses)
        wrong_lenses["lens_set_sha256"] = "1" * 64
        for result, message in (
            (self.judgment_result(brief, LENSES), "stored lens panel"),
            (wrong_brief, "brief_sha256 does not match"),
            (wrong_lenses, "lens_set_sha256 does not match"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(state.StateError, message):
                    self.call("report", version="v1", kind="judgment", text="J", result=result)
        partial = self.judgment_result(
            brief,
            lenses,
            coverage={"fit": "complete", "feasibility": "complete", "quality": "complete", "mix": "partial"},
        )
        self.assertEqual("incomplete_coverage", partial["assessment_status"])
        saved = self.call("report", version="v1", kind="judgment", text="J", result=partial)
        self.assertEqual("cannot_judge", saved["state"]["reports"][-1]["result"]["decision"])

    def test_new_judgment_report_requires_verifier_for_any_decision(self):
        brief = make_brief()
        self.call("init", brief=brief, lenses=LENSES)
        result = self.judgment_result(brief, LENSES)
        self.assertEqual("yes", result["decision"])
        for field in ("expected_model_roles",):
            result[field] = [r for r in result[field] if r["role"] != "verifier"]
        result["review_protocol"]["roles"] = [
            r for r in result["review_protocol"]["roles"] if r["role"] != "verifier"
        ]
        with self.assertRaisesRegex(state.StateError, "require incomplete coverage"):
            self.call("report", version="v1", kind="judgment", text="J", result=result)

    def test_judgment_gate_ports(self):
        brief = make_brief()
        self.call("init", brief=brief, lenses=LENSES)
        no_plan = self.judgment_result(brief, LENSES)
        del no_plan["expected_model_roles"]
        with self.assertRaisesRegex(state.StateError, "requires expected_model_roles"):
            self.call("report", version="v1", kind="judgment", text="J", result=no_plan)
        no_findings = self.judgment_result(brief, LENSES)
        del no_findings["findings"]
        with self.assertRaisesRegex(state.StateError, "requires findings"):
            self.call("report", version="v1", kind="judgment", text="J", result=no_findings)
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
        gap = self.judgment_result(brief, LENSES)
        index = [r["role"] for r in gap["expected_model_roles"]].index("quality")
        gap["expected_model_roles"][index]["caller_policy"] = mandatory
        gap["review_protocol"]["roles"][index] = policy.execute(
            "model_observation", {"preflight": prepared, "actual_model": "unknown"}
        )
        with self.assertRaisesRegex(state.StateError, "mandatory model gap"):
            self.call("report", version="v1", kind="judgment", text="J", result=gap)

    def test_brief_level_ledger_has_no_document(self):
        request = {"slug": "brief-plan", "project_dir": str(self.project)}
        ledger = state.execute("init", {**request, "brief": confirmed(make_brief())})[
            "state"
        ]
        self.assertIsNone(ledger["current_version"])
        self.assertEqual({}, ledger["versions"])
        self.assertIsNone(state.execute("status", request)["state"]["current_version"])

    def test_ranking_report_saves_without_version_and_checks_cited_reports(self):
        brief = confirmed(make_brief())
        entry = self.project / "a.md"
        entry.write_text("Entry A")
        entry_request = {"slug": "a", "source": str(entry)}
        state.execute("init", {**entry_request, "brief": brief, "lenses": LENSES})
        judged = self.judgment_result(brief, LENSES)
        entry_state = state.execute(
            "report",
            {**entry_request, "version": "v1", "kind": "judgment", "text": "J", "result": judged},
        )["state"]
        brief_request = {"slug": "brief-plan", "project_dir": str(self.project)}
        state.execute("init", {**brief_request, "brief": brief, "lenses": LENSES})
        row = {
            "rank": 1,
            "entry": "a",
            "separated_by": None,
            "reason": "Only entry.",
            "overridden": False,
            "decision": "yes",
            "fit": "meets",
            "feasibility": "achievable",
            "quality": "adequate",
            "critical_count": 0,
            "high_count": 0,
        }
        ranking = {
            "ranked": [row],
            "unranked": [],
            "ties": [],
            "tiebreaks": [],
            "entries": [
                {
                    "slug": "a",
                    "version_sha256": entry_state["versions"]["v1"]["sha256"],
                    "brief_sha256": state.brief_sha256(brief),
                    "lens_set_sha256": state.lens_set_sha256(LENSES),
                    "judgment_report_id": entry_state["reports"][-1]["id"],
                }
            ],
            "brief_sha256": state.brief_sha256(brief),
            "expected_model_roles": [],
            "review_protocol": {"roles": []},
        }
        for changes, message in (
            ({"ranked": [dict(row, decision="no")]}, "does not match its judgment"),
            (
                {"entries": [dict(ranking["entries"][0], judgment_report_id="nope")]},
                "judgment report not found",
            ),
            (
                {"tiebreaks": [{"entries": ["a"], "order": None, "reason": "x", "sources": []}]},
                "tiebreak roles were not observed",
            ),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(state.StateError, message):
                    state.execute(
                        "report",
                        {**brief_request, "kind": "ranking", "text": "R", "result": {**ranking, **changes}},
                    )
        saved = state.execute(
            "report", {**brief_request, "kind": "ranking", "text": "R", "result": ranking}
        )["state"]["reports"][-1]
        self.assertIsNone(saved["version"])
        self.assertEqual(f"reports/ranking-{saved['id']}.md", saved["path"])

    def test_responses_carry_ledger_hashes_and_requirement_ids(self):
        brief = make_brief(requirements=("Runs offline", "Under two minutes"))
        for operation in ("init", "status"):
            with self.subTest(operation=operation):
                fields = {"brief": brief, "lenses": LENSES} if operation == "init" else {}
                response = self.call(operation, **fields)
                self.assertEqual(state.brief_sha256(brief), response["brief_sha256"])
                self.assertEqual(state.lens_set_sha256(LENSES), response["lens_set_sha256"])
                self.assertEqual(["R1", "R2"], response["requirement_ids"])

    def test_list_files_operation_returns_paths_and_slugs(self):
        entries = self.project / "entries"
        entries.mkdir()
        (entries / "Track One.md").write_text("one")
        (entries / "brief.md").write_text("brief")
        result = state.execute(
            "list-files",
            {"directory": str(entries), "exclude": [str(entries / "brief.md")]},
        )
        self.assertEqual(
            [{"path": str((entries / "Track One.md").resolve()), "slug": "track-one"}],
            result["files"],
        )
        (entries / "x.md").symlink_to(self.doc)
        with self.assertRaisesRegex(state.StateError, "symlinks are not accepted"):
            state.execute("list-files", {"directory": str(entries)})

    def test_patch_fields_are_the_schema_three_set(self):
        self.call("init", brief=make_brief())
        for patch in ({"investment_context": {}}, {"experiments": []}):
            with self.subTest(patch=patch):
                with self.assertRaisesRegex(state.StateError, "patch may contain only"):
                    self.call("update", expected_generation=1, patch=patch)
        self.call("update", expected_generation=1, patch={"brief": make_brief("next")})

    def test_generation_preconditions_prevent_lost_working_state_updates(self):
        self.init()
        with self.assertRaisesRegex(state.StateError, "requires expected_generation"):
            self.call("update", patch={"brief": make_brief("budget 10")})
        updated = self.call(
            "update",
            expected_generation=1,
            patch={"brief": make_brief("budget 10")},
        )
        with self.assertRaisesRegex(state.StateError, "generation conflict"):
            self.call(
                "update",
                expected_generation=1,
                patch={"brief": make_brief("budget 20")},
            )
        self.assertEqual(self.call("status")["state"], updated["state"])
        self.report()
        self.assertEqual(
            self.call("status")["state"]["brief"]["goal"], "budget 10"
        )

    def test_nested_validation_rejects_bad_records_without_changing_ledger(self):
        self.init()
        bad_patches = [
            {"brief": []},
            {"word_counts": {}},
            {
                "questions": [
                    {
                        "id": "q",
                        "change_id": "a" * 64,
                        "prompt": "Choose",
                        "status": "answered",
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "id": "d",
                        "change_id": "a" * 64,
                        "choice": "pivot",
                        "approved": "yes",
                        "source": "user",
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "id": "d",
                        "change_id": "old-remedy",
                        "choice": "pivot",
                        "approved": True,
                        "source": "user",
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "id": "d",
                        "change_id": "a" * 64,
                        "choice": "pivot",
                        "approved": True,
                        "source": "agent",
                    }
                ]
            },
            {"findings": [{"id": "f", "statement": "missing nested evidence"}]},
            {"brief": {"goal": float("nan")}},
        ]
        before = self.call("status")["state"]
        for patch in bad_patches:
            with self.subTest(patch=patch):
                with self.assertRaises(state.StateError):
                    self.call("update", expected_generation=1, patch=patch)
        self.assertEqual(self.call("status")["state"], before)
        decision = {
            "id": "d",
            "change_id": "a" * 64,
            "choice": "pivot",
            "approved": True,
            "source": "user",
        }
        question = {
            "id": "q",
            "change_id": "a" * 64,
            "prompt": "Choose",
            "status": "answered",
            "answer": "pivot",
        }
        result = self.call(
            "update",
            expected_generation=1,
            patch={
                "decisions": [decision],
                "questions": [question],
            },
        )
        self.assertEqual(result["state"]["decisions"], [decision])

    def test_source_hash_bound_counts_do_not_reuse_stale_source(self):
        result = self.init()
        counted = self.call("counts", version="v1")["state"]["word_counts"]["v1"]
        self.assertEqual(counted["sha256"], result["state"]["versions"]["v1"]["sha256"])
        self.doc.write_text("new content")
        with self.assertRaisesRegex(state.StateError, "source changed"):
            self.call("counts", version="v1", file=str(self.doc))
        self.assertEqual(
            self.call("counts", version="v1")["state"]["word_counts"]["v1"], counted
        )

    def test_paths_aliases_and_corrupt_artifacts_fail_closed(self):
        for slug in ("../escape", "", "demo/child", "Demo", "a\\b"):
            with self.subTest(slug=slug):
                with self.assertRaises(state.StateError):
                    state.execute("init", {**self.request, "slug": slug})
        result = self.init()
        root = Path(result["root"])
        snapshot = root / "versions/v1.md"
        snapshot.write_text("tampered")
        with self.assertRaisesRegex(state.StateError, "immutable artifact changed"):
            self.call("status")
        snapshot.unlink()
        snapshot.symlink_to(self.doc)
        with self.assertRaisesRegex(state.StateError, "symlink"):
            self.call("status")
        snapshot.unlink()
        os.link(self.doc, snapshot)
        with self.assertRaisesRegex(state.StateError, "hardlink"):
            self.call("status")

    def test_state_nested_path_tampering_is_rejected(self):
        result = self.init()
        path = Path(result["root"]) / "state.json"
        data = result["state"]
        data["versions"]["v1"]["path"] = "../outside.md"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(state.StateError, "safe relative path"):
            self.call("status")

    def test_interrupted_artifact_publish_requires_explicit_hash_checked_recovery(self):
        result = self.init()
        root = Path(result["root"])
        original_atomic = state._atomic

        def fail_ledger(path, data):
            if path.name == "state.json":
                raise OSError("simulated interruption before ledger commit")
            return original_atomic(path, data)

        with mock.patch.object(state, "_atomic", side_effect=fail_ledger):
            with self.assertRaises(OSError):
                self.report("published but not committed")
        self.assertTrue((root / ".transaction.json").exists())
        self.assertEqual(json.loads((root / "state.json").read_text())["generation"], 1)
        with self.assertRaisesRegex(state.StateError, "recover explicitly"):
            self.call("status")
        recovered = self.call("recover")["state"]
        self.assertEqual(recovered["generation"], 2)
        self.assertEqual(len(recovered["reports"]), 1)
        self.assertFalse((root / ".transaction.json").exists())

    def test_recovery_handles_interruption_between_link_and_unlink(self):
        self.init()
        original_link = os.link

        def link_then_interrupt(source, destination):
            original_link(source, destination)
            raise OSError("interrupted after exclusive publication")

        with mock.patch.object(state.os, "link", side_effect=link_then_interrupt):
            with self.assertRaises(OSError):
                self.report()
        result = self.call("recover")
        self.assertEqual(len(result["state"]["reports"]), 1)
        self.assertEqual(
            (Path(result["root"]) / result["state"]["reports"][0]["path"])
            .stat()
            .st_nlink,
            1,
        )

    def test_recovery_refuses_changed_published_bytes(self):
        result = self.init()
        root = Path(result["root"])
        original_atomic = state._atomic
        with mock.patch.object(
            state,
            "_atomic",
            side_effect=lambda path, data: (
                (_ for _ in ()).throw(OSError("stop"))
                if path.name == "state.json"
                else original_atomic(path, data)
            ),
        ):
            with self.assertRaises(OSError):
                self.report()
        journal = json.loads((root / ".transaction.json").read_text())
        (root / journal["artifacts"][0]["path"]).write_text("corruption")
        with self.assertRaisesRegex(state.StateError, "hash differs"):
            self.call("recover")
        self.assertTrue((root / ".transaction.json").exists())

    def test_multiple_processes_append_without_losing_reports_or_history(self):
        self.init()
        processes = []
        for index in range(8):
            request = {
                **self.request,
                "version": "v1",
                "kind": "revision",
                "text": f"review {index}",
                "result": {
                    "assessment_status": "incomplete_coverage",
                    "expected_model_roles": [],
                    "review_protocol": {"roles": []},
                },
            }
            process = subprocess.Popen(
                [sys.executable, str(SHARED / "state.py"), "report", "--request", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process.stdin.write(json.dumps(request))
            process.stdin.close()
            process.stdin = None
            processes.append(process)
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("state", json.loads(stdout))
        ledger = self.call("status")["state"]
        self.assertEqual(
            (len(ledger["reports"]), len(ledger["history"]), ledger["generation"]),
            (8, 9, 9),
        )
        self.assertEqual(len({item["id"] for item in ledger["reports"]}), 8)

    def test_concurrent_replacement_requires_rebase_instead_of_lost_update(self):
        self.init()
        processes = []
        for budget in (10, 20):
            request = {
                **self.request,
                "expected_generation": 1,
                "patch": {"brief": make_brief(f"budget {budget}")},
            }
            process = subprocess.Popen(
                [sys.executable, str(SHARED / "state.py"), "update", "--request", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process.stdin.write(json.dumps(request))
            process.stdin.close()
            process.stdin = None
            processes.append(process)
        results = [(process, process.communicate(timeout=20)) for process in processes]
        self.assertEqual(sorted(process.returncode for process, _ in results), [0, 2])
        self.assertIn(
            "generation conflict",
            next(output[1] for process, output in results if process.returncode),
        )
        self.assertEqual(self.call("status")["state"]["generation"], 2)


if __name__ == "__main__":
    unittest.main()
