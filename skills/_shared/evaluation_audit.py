#!/usr/bin/env python3
"""Offline metrics for explicitly recorded evaluations; no model calls or writes.

Validates comparison structure, not semantic equivalence or human label quality.
Empty denominators produce null rates. Label synthetic datasets explicitly.
"""

import argparse
import json
from pathlib import Path
import sys

VERDICTS = {"Invest", "Proceed with caution", "Pivot", "Skip"}
STATUSES = {"complete", "insufficient_evidence", "incomplete_coverage"}
AXES = {"critical_thinking", "feasibility", "risk", "roi"}
TRANSFORMS = {"order", "paraphrase", "framing", "verbosity", "attribution", "repeat"}


class AuditError(ValueError):
    """Invalid or incomparable records."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), "record must be an object")
    require(
        set(required) <= obj.keys(), f"missing fields: {set(required) - obj.keys()}"
    )
    require(obj.keys() <= set(required) | set(optional), "unknown record fields")


def text(value):
    require(isinstance(value, str) and bool(value.strip()), "expected nonempty string")


def outcome(record):
    status, verdict = record["assessment_status"], record["verdict"]
    require(isinstance(status, str) and status in STATUSES, "invalid assessment status")
    require(verdict is None or isinstance(verdict, str), "invalid verdict type")
    require(
        (status == "complete" and verdict in VERDICTS)
        or (status != "complete" and verdict is None),
        "status and verdict disagree",
    )
    return status, verdict


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def audit(request):
    fields(request, {"schema_version", "data_kind", "runs", "comparisons"})
    require(
        type(request["schema_version"]) is int and request["schema_version"] == 1,
        "unsupported schema_version",
    )
    require(request["data_kind"] in ("synthetic", "recorded"), "invalid data_kind")
    require(isinstance(request["runs"], list), "runs must be a list")
    require(isinstance(request["comparisons"], list), "comparisons must be a list")
    runs = {}
    required = {
        "id",
        "case_id",
        "decision_id",
        "evidence_id",
        "source_hash",
        "model",
        "protocol_id",
        "condition",
        "assessment_status",
        "verdict",
        "coverage",
    }
    for run in request["runs"]:
        fields(run, required, {"reference"})
        for key in required - {"verdict", "coverage"}:
            text(run[key])
        require(run["id"] not in runs, "duplicate run id")
        source_hash = run["source_hash"]
        require(
            len(source_hash) == 64
            and all(c in "0123456789abcdef" for c in source_hash),
            "source_hash must be a lowercase SHA-256",
        )
        outcome(run)
        coverage = run["coverage"]
        require(
            isinstance(coverage, dict) and set(coverage) == AXES,
            "invalid coverage axes",
        )
        require(
            all(
                isinstance(v, str) and v in ("complete", "partial", "failed", "not_run")
                for v in coverage.values()
            ),
            "invalid coverage state",
        )
        complete = all(v == "complete" for v in coverage.values())
        require(
            complete == (run["assessment_status"] != "incomplete_coverage"),
            "coverage and assessment status disagree",
        )
        if "reference" in run:
            reference = run["reference"]
            fields(
                reference,
                {
                    "assessment_status",
                    "verdict",
                    "source",
                    "independent",
                    "source_hash",
                    "decision_id",
                    "evidence_id",
                },
            )
            outcome(reference)
            text(reference["source"])
            require(
                reference["independent"] is True,
                "reference must be independently supplied",
            )
            for key in ("source_hash", "decision_id", "evidence_id"):
                require(reference[key] == run[key], f"reference {key} mismatch")
        runs[run["id"]] = run

    require(
        len({(r["model"], r["protocol_id"], r["condition"]) for r in runs.values()})
        <= 1,
        "audit one model/protocol/condition group per request",
    )

    variants, revisions, details, seen = [], [], [], set()
    for pair in request["comparisons"]:
        fields(pair, {"kind", "before", "after", "reason", "source"}, {"transform"})
        for key in ("kind", "before", "after", "reason", "source"):
            text(pair[key])
        require(pair["kind"] in ("equivalent", "revision"), "invalid comparison kind")
        require(
            pair["before"] in runs and pair["after"] in runs, "unknown comparison run"
        )
        require(pair["before"] != pair["after"], "cannot compare a run to itself")
        identity = tuple(sorted((pair["before"], pair["after"])))
        require(identity not in seen, "duplicate comparison pair")
        seen.add(identity)
        before, after = runs[pair["before"]], runs[pair["after"]]
        for key in ("case_id", "decision_id", "model", "protocol_id", "condition"):
            require(before[key] == after[key], f"comparison {key} mismatch")
        require(
            before["model"] != "unknown" and before["protocol_id"] != "unknown",
            "comparison requires known model and protocol identities",
        )
        detail = {
            "before": pair["before"],
            "after": pair["after"],
            "kind": pair["kind"],
        }
        if pair["kind"] == "equivalent":
            require(
                isinstance(pair.get("transform"), str)
                and pair["transform"] in TRANSFORMS,
                "equivalent comparison requires transform",
            )
            require(
                before["evidence_id"] == after["evidence_id"],
                "comparison evidence_id mismatch",
            )
            if pair["transform"] == "repeat":
                require(
                    before["source_hash"] == after["source_hash"],
                    "repeat source_hash mismatch",
                )
            both_complete = (
                before["assessment_status"] == after["assessment_status"] == "complete"
            )
            detail.update(
                transform=pair["transform"],
                outcome_changed=outcome(before) != outcome(after),
                verdict_changed=(before["verdict"] != after["verdict"])
                if both_complete
                else None,
            )
            variants.append(detail)
        else:
            require(
                "transform" not in pair,
                "revision must not declare equivalence transform",
            )
            require(
                before["source_hash"] != after["source_hash"],
                "revision requires changed source",
            )
            result = "unlabeled"
            if "reference" in before and "reference" in after:
                was_correct = outcome(before) == outcome(before["reference"])
                now_correct = outcome(after) == outcome(after["reference"])
                result = (
                    ("still_correct" if was_correct else "correction")
                    if now_correct
                    else ("regression" if was_correct else "still_incorrect")
                )
            detail["reference_transition"] = result
            revisions.append(detail)
        details.append(detail)

    labeled = [r for r in runs.values() if "reference" in r]
    eligible = [p for p in variants if p["verdict_changed"] is not None]
    paired_labels = [p for p in revisions if p["reference_transition"] != "unlabeled"]
    metrics = {
        "coverage_complete": rate(
            sum(
                all(v == "complete" for v in r["coverage"].values())
                for r in runs.values()
            ),
            len(runs),
        ),
        "abstention": rate(sum(r["verdict"] is None for r in runs.values()), len(runs)),
        "reference_agreement": rate(
            sum(outcome(r) == outcome(r["reference"]) for r in labeled), len(labeled)
        ),
        "equivalent_outcome_changes": rate(
            sum(p["outcome_changed"] for p in variants), len(variants)
        ),
        "equivalent_verdict_changes": rate(
            sum(p["verdict_changed"] for p in eligible), len(eligible)
        ),
        "revision_corrections": rate(
            sum(p["reference_transition"] == "correction" for p in paired_labels),
            len(paired_labels),
        ),
        "revision_regressions": rate(
            sum(p["reference_transition"] == "regression" for p in paired_labels),
            len(paired_labels),
        ),
    }
    return {
        "schema_version": 1,
        "data_kind": request["data_kind"],
        "run_count": len(runs),
        "metrics": metrics,
        "comparisons": details,
        "unlabeled_runs": len(runs) - len(labeled),
        "unlabeled_revision_pairs": len(revisions) - len(paired_labels),
        "limitations": [
            "Equivalence and reference independence are supplied assertions, not verified by this helper.",
            "Agreement with supplied labels does not establish business outcome validity.",
            "Rates are descriptive; repeated runs and shared cases are not independent observations.",
            "Compare model/protocol/condition groups separately; no automatic pass threshold is applied.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, help="JSON request; defaults to stdin")
    args = parser.parse_args()
    try:
        raw = (
            args.request.read_text(encoding="utf-8")
            if args.request
            else sys.stdin.read()
        )
        print(json.dumps(audit(json.loads(raw)), indent=2, allow_nan=False))
    except (AuditError, ValueError, OSError) as exc:
        print(f"audit error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
