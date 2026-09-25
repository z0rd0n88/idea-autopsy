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
        return self.call(
            "report", version="v1", kind="stress_test", text=text, **fields
        )

    def test_init_snapshots_and_nested_source_resolves_same_ledger(self):
        result = self.init()
        ledger = result["state"]
        self.assertEqual(
            (ledger["schema_version"], ledger["current_version"], ledger["generation"]),
            (2, "v1", 1),
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
        with self.assertRaisesRegex(state.StateError, "import-legacy"):
            self.call("status")
        self.assertFalse((root / ".lock").exists())

    def test_replaced_decision_and_context_remain_in_audit_history(self):
        initialized = self.call("init", investment_context={"budget": 10})["state"]
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
            patch={"decisions": [replacement], "investment_context": {"budget": 20}},
        )["state"]
        self.assertEqual(
            initialized["history"][0]["details"]["investment_context"], {"budget": 10}
        )
        changes = latest["history"][-1]["details"]["changes"]
        self.assertEqual(changes["decisions"]["before"], [decision])
        self.assertEqual(changes["decisions"]["after"], [replacement])
        self.assertEqual(changes["investment_context"]["before"], {"budget": 10})

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
            "axes": ["critical_thinking"],
            "affects_decision": True,
            "status": "active",
            "resolution": "unresolved",
            "bucket": "unique_real",
            "evidence_basis": "document_logic",
            "thesis_breaking": False,
            "plausibly_resolvable": True,
            "severity_reason": "The claimed revenue changes the budget decision",
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
        first = self.report(result={"summary": "first pass"})["state"]["reports"][-1]
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
                    "verdict": "Invest",
                    "assessment_status": "incomplete_coverage",
                }
            },
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(state.StateError):
                    self.report(**extra)
        self.assertEqual(self.call("status")["state"], before)

    def test_mandatory_model_gap_cannot_be_saved_as_complete_assessment(self):
        self.init()
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
        for actual in ("unknown", "claude-sonnet-5"):
            with self.subTest(actual=actual):
                role = policy.execute(
                    "model_observation",
                    {"preflight": prepared, "actual_model": actual},
                )
                with self.assertRaisesRegex(state.StateError, "mandatory model"):
                    self.report(
                        result={
                            "assessment_status": "complete",
                            "verdict": "Invest",
                            "review_protocol": {"roles": [role]},
                        }
                    )
        self.assertEqual([], self.call("status")["state"]["reports"])
        with self.assertRaisesRegex(state.StateError, "incomplete coverage"):
            self.report(
                result={
                    "assessment_status": "insufficient_evidence",
                    "verdict": None,
                    "review_protocol": {"roles": [role]},
                }
            )
        saved = self.report(
            result={
                "assessment_status": "incomplete_coverage",
                "verdict": None,
                "review_protocol": {"roles": [role]},
            }
        )
        self.assertEqual(
            "incomplete_coverage",
            saved["state"]["reports"][-1]["result"]["assessment_status"],
        )

    def test_new_complete_report_rejects_an_omitted_mandatory_role(self):
        self.init()
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
        for protocol in (None, {"roles": observed}):
            with self.subTest(protocol=protocol):
                result = {
                    "expected_model_roles": expected,
                    "assessment_status": "complete",
                    "verdict": "Invest",
                }
                if protocol is not None:
                    result["review_protocol"] = protocol
                with self.assertRaises(state.StateError):
                    self.call(
                        "report",
                        version="v1",
                        kind="evaluation",
                        text="Verdict",
                        result=result,
                    )
        self.assertEqual([], self.call("status")["state"]["reports"])

    def test_new_complete_report_needs_a_role_plan_but_legacy_results_remain_readable(
        self,
    ):
        self.init()
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
        legacy_result = {
            "assessment_status": "complete",
            "verdict": "Invest",
            "review_protocol": {"roles": observed},
        }
        state.validate_result(legacy_result)
        with self.assertRaisesRegex(state.StateError, "expected model role"):
            self.call(
                "report",
                version="v1",
                kind="evaluation",
                text="New verdict",
                result=legacy_result,
            )
        self.assertEqual([], self.call("status")["state"]["reports"])

    def test_historical_alias_observation_remains_readable(self):
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
        legacy_role = policy.execute(
            "model_observation",
            {
                "preflight": prepared,
                "actual_model": "claude-haiku-5",
                "host_resolved_model": "claude-haiku-5",
            },
        )
        legacy_role.update(status="compliant", policy_compliant=True, limitation=None)
        state.validate_result(
            {
                "assessment_status": "complete",
                "verdict": "Invest",
                "review_protocol": {"roles": [legacy_role]},
            }
        )

    def test_complete_strategy_without_business_verdict_does_not_need_four_axes(self):
        self.init()
        role = policy.execute(
            "model_observation",
            {
                "preflight": policy.execute(
                    "model_preflight",
                    {"role": "product-strategist", "dispatch_path": "registered"},
                ),
                "actual_model": "unknown",
            },
        )
        saved = self.call(
            "report",
            version="v1",
            kind="strategy",
            text="Strategy options",
            result={
                "assessment_status": "complete",
                "verdict": None,
                "expected_model_roles": [
                    {"role": "product-strategist", "caller_policy": None}
                ],
                "review_protocol": {"roles": [role]},
            },
        )
        self.assertEqual("strategy", saved["state"]["reports"][-1]["kind"])

    def test_generation_preconditions_prevent_lost_working_state_updates(self):
        self.init()
        with self.assertRaisesRegex(state.StateError, "requires expected_generation"):
            self.call("update", patch={"investment_context": {"budget": 10}})
        updated = self.call(
            "update",
            expected_generation=1,
            patch={"investment_context": {"budget": 10, "currency": "USD"}},
        )
        with self.assertRaisesRegex(state.StateError, "generation conflict"):
            self.call(
                "update",
                expected_generation=1,
                patch={"investment_context": {"budget": 20}},
            )
        self.assertEqual(self.call("status")["state"], updated["state"])
        self.report()
        self.assertEqual(
            self.call("status")["state"]["investment_context"]["budget"], 10
        )

    def test_nested_validation_rejects_bad_records_without_changing_ledger(self):
        self.init()
        bad_patches = [
            {"investment_context": []},
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
            {
                "experiments": [
                    {"id": "e", "hypothesis": "retention", "status": "imagined"}
                ]
            },
            {"findings": [{"id": "f", "statement": "missing nested evidence"}]},
            {"investment_context": {"budget": float("nan")}},
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
                "experiments": [
                    {"id": "e", "hypothesis": "retention", "status": "proposed"}
                ],
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

    def test_legacy_import_is_explicit_preserves_bytes_and_distrusts_verdicts(self):
        root = self.project / ".autopsy/demo"
        root.mkdir(parents=True)
        raw = b'{ "slug":"demo", "current_version":"v9", "word_counts":{"v9":2}, "verdict":"Invest" }\n'
        (root / "state.json").write_bytes(raw)
        (root / "v9.md").write_text("historical proposal")
        for operation in ("status", "counts"):
            with self.assertRaisesRegex(state.StateError, "import-legacy"):
                self.call(operation)
        with self.assertRaisesRegex(state.StateError, "acknowledge_untrusted"):
            self.call("import-legacy")
        self.assertEqual((root / "state.json").read_bytes(), raw)
        ledger = self.call("import-legacy", acknowledge_untrusted=True)["state"]
        self.assertEqual((root / ledger["legacy_backups"][0]["path"]).read_bytes(), raw)
        self.assertEqual(ledger["reports"], [])
        self.assertEqual(ledger["word_counts"], {})
        self.assertEqual(ledger["current_version"], "v1")
        self.assertEqual((root / "v9.md").read_text(), "historical proposal")

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
                "kind": "stress_test",
                "text": f"review {index}",
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
                "patch": {"investment_context": {"budget": budget}},
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
