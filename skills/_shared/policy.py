#!/usr/bin/env python3
"""Pure, auditable workflow policy. No filesystem writes or network access.

Call execute(operation, request), or pass one JSON object on stdin / --request.
The helper validates supplied judgments; it cannot verify evidence or infer intent.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import re
import sys
from pathlib import Path


FIXED_LENSES = ("fit", "feasibility", "quality")
RESERVED_PREFIXES = ("verifier", "derive", "tiebreak", "fact-checker")
LENS_ID = re.compile(r"[a-z][a-z0-9-]{1,31}\Z")
LABELS = {
    "fit": ("meets", "partly_meets", "does_not_meet", "cannot_judge"),
    "feasibility": (
        "achievable",
        "achievable_with_changes",
        "not_achievable",
        "cannot_judge",
    ),
    "quality": ("strong", "adequate", "weak", "cannot_judge"),
    "decision": ("yes", "not_yet", "no", "cannot_judge"),
}
CATEGORIES = ("routine", "scope", "approach")
ENUMS = {
    "kind": ("contradiction", "missing_evidence", "risk", "question"),
    "severity": ("Critical", "High", "Medium"),
    "origin": ("document", "user", "reviewer", "external"),
    "doc_support": ("supported", "refuted", "not_established"),
    "external_status": ("not_checked", "verified", "contradicted", "unverifiable"),
    "confidence": ("high", "medium", "low"),
    "status": ("active", "refuted", "resolved"),
    "resolution": (
        "unresolved",
        "claim_removed",
        "scope_changed",
        "evidence_obtained",
        "resolved",
    ),
    "bucket": (
        "consensus",
        "unique_real",
        "unique_unrated",
        "unique_reach",
        "speculative",
        "verdict",
        "unknown",
    ),
    "evidence_basis": ("document_logic", "external_fact", "user_report"),
}


class PolicyError(ValueError):
    """Malformed input or a contradiction that must not be guessed away."""


def require(condition, message):
    if not condition:
        raise PolicyError(message)


def obj(value, label):
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def sequence(value, label):
    require(isinstance(value, list), f"{label} must be a list")
    return value


def nonempty(value, label):
    require(
        isinstance(value, str) and bool(value.strip()),
        f"{label} must be a nonempty string",
    )
    return value


def boolean(value, label):
    require(type(value) is bool, f"{label} must be boolean")
    return value


def sources(value, label="sources"):
    for item in sequence(value, label):
        obj(item, label)
        for key in ("type", "ref", "quote"):
            nonempty(item.get(key), f"{label}.{key}")
        require(
            item["type"] in ("document", "user", "external", "calculation", "critique"),
            "unknown source type",
        )
    return value


def validate_finding(value, lenses=FIXED_LENSES):
    """Validate a normalized finding; never upgrade a legacy provenance tag."""
    f = deepcopy(obj(value, "finding"))
    for key in ("thesis_breaking", "plausibly_resolvable"):
        require(key not in f, f"finding.{key} is no longer accepted")
    for key in ("id", "issue_id", "statement", "severity_reason"):
        nonempty(f.get(key), f"finding.{key}")
    for key, values in ENUMS.items():
        require(f.get(key) in values, f"finding.{key} must be one of {values}")
    boolean(f.get("affects_decision"), "finding.affects_decision")
    for key in ("axes", "assumption_ids"):
        for item in sequence(f.get(key), f"finding.{key}"):
            nonempty(item, f"finding.{key} entry")
        require(len(set(f[key])) == len(f[key]), f"finding.{key} contains duplicates")
    require(set(f["axes"]) <= set(lenses), "finding.axes contains an unknown axis")
    nonempty(f.get("lens"), "finding.lens")
    require(f["lens"] in f["axes"], "finding.lens must be in axes")
    if "origin_lenses" in f:
        origin = sequence(f["origin_lenses"], "finding.origin_lenses")
        require(
            bool(origin) and origin == sorted(set(origin)) and set(origin) <= set(f["axes"]),
            "finding.origin_lenses must be a sorted list of lenses in axes",
        )
    if "requirement_id" in f:
        nonempty(f["requirement_id"], "finding.requirement_id")
    sources(f.get("sources"))
    if "member_ids" in f:
        for member in sequence(f["member_ids"], "finding.member_ids"):
            nonempty(member, "member finding id")
        require(f["id"] in f["member_ids"], "finding.member_ids must include its id")
    require(
        not (
            f["status"] == "resolved"
            and f["resolution"] in ("claim_removed", "unresolved")
        ),
        "Removing a claim or leaving its risk unresolved cannot mark the finding resolved",
    )
    return f


def excluded(f):
    return (
        f["status"] in ("refuted", "resolved")
        or f["doc_support"] == "refuted"
        or f["external_status"] == "contradicted"
    )


def established(f):
    if excluded(f) or f["confidence"] == "low":
        return False
    if f["evidence_basis"] == "external_fact":
        return f["external_status"] == "verified" and any(
            s["type"] == "external" and re.match(r"https?://", s["ref"])
            for s in f["sources"]
        )
    if f["evidence_basis"] == "document_logic":
        return f["doc_support"] == "supported" and any(
            s["type"] in ("document", "user", "calculation") for s in f["sources"]
        )
    # User-supplied constraints/data can support a conditional assessment without
    # converting a report into independent external verification.
    return f["doc_support"] == "supported" and any(
        s["type"] == "user" for s in f["sources"]
    )


def unique(items):
    result = []
    seen = set()
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


def normalize(request):
    require(
        "markdown" not in request and "findings" in request,
        "normalize accepts structured findings only",
    )
    lenses = tuple(sequence(request.get("lenses", list(FIXED_LENSES)), "lenses"))
    requirement_ids = request.get("requirement_ids")
    if requirement_ids is not None:
        requirement_ids = set(sequence(requirement_ids, "requirement_ids"))
    resolutions = obj(request.get("severity_resolutions", {}), "severity_resolutions")
    groups, seen_ids = {}, {}
    for value in sequence(request["findings"], "findings"):
        f = validate_finding(value, lenses)
        if requirement_ids is not None and "requirement_id" in f:
            require(
                f["requirement_id"] in requirement_ids,
                f"unknown requirement_id {f['requirement_id']}",
            )
        require(
            not f["affects_decision"]
            or "requirement_id" in f
            or "feasibility" in f["axes"],
            "affects_decision requires a requirement_id or the feasibility axis",
        )
        if f["id"] in seen_ids:
            require(
                seen_ids[f["id"]] == f, f"conflicting records for finding id {f['id']}"
            )
            continue
        seen_ids[f["id"]] = f
        groups.setdefault(f["issue_id"], []).append(f)
    require(
        set(resolutions) <= set(groups), "severity resolution names an unknown issue"
    )
    merged, conflicts = [], []
    for issue_id in sorted(groups):
        # Sorting makes the merge independent of dispatch order.
        members = sorted(groups[issue_id], key=lambda m: m["id"])
        f = deepcopy(members[0])
        f["member_ids"] = unique(
            [member for m in members for member in m.get("member_ids", [m["id"]])]
        )
        for key in ("assumption_ids", "sources"):
            f[key] = unique([item for m in members for item in m[key]])
        f["axes"] = sorted({item for m in members for item in m["axes"]})
        f["origin_lenses"] = sorted(
            {lens for m in members for lens in m.get("origin_lenses", [m["lens"]])}
        )
        f["lens"] = f["origin_lenses"][0]
        requirement_ids_seen = sorted(
            {m["requirement_id"] for m in members if "requirement_id" in m}
        )
        f.pop("requirement_id", None)
        if len(requirement_ids_seen) == 1:
            f["requirement_id"] = requirement_ids_seen[0]
        elif requirement_ids_seen:
            conflicts.append(
                {
                    "issue_id": issue_id,
                    "field": "requirement_id",
                    "values": requirement_ids_seen,
                }
            )
        severities = sorted({m["severity"] for m in members})
        if issue_id in resolutions:
            choice = obj(resolutions[issue_id], "severity resolution")
            require(
                choice.get("severity") in ENUMS["severity"], "invalid resolved severity"
            )
            nonempty(choice.get("reason"), "severity resolution.reason")
            require(
                bool(sources(choice.get("sources"))),
                "severity resolution needs evidence",
            )
            f["severity"], f["severity_reason"] = choice["severity"], choice["reason"]
            f["severity_resolution"] = deepcopy(choice)
        elif len(severities) > 1:
            conflicts.append(
                {"issue_id": issue_id, "field": "severity", "values": severities}
            )
        for key in (
            "kind",
            "evidence_basis",
            "doc_support",
            "external_status",
            "status",
            "affects_decision",
        ):
            values = unique([m[key] for m in members])
            if len(values) > 1:
                conflicts.append({"issue_id": issue_id, "field": key, "values": values})
        # Agreement never boosts confidence; use the least confident unresolved observation.
        f["confidence"] = min(
            (m["confidence"] for m in members), key=("low", "medium", "high").index
        )
        merged.append(f)
    return {
        "format": "structured",
        "findings": merged,
        "conflicts": conflicts,
        "requires_source_review": False,
    }


RECORD_STATUSES = ("met", "partly_met", "not_met", "cannot_tell")


def decide(fit, feasibility):
    if "cannot_judge" in (fit, feasibility):
        return "cannot_judge"
    if fit == "does_not_meet" or feasibility == "not_achievable":
        return "no"
    if fit == "partly_meets" or feasibility == "achievable_with_changes":
        return "not_yet"
    return "yes"


def judgment(request):
    lenses = list(sequence(request.get("lenses"), "lenses"))
    require(
        set(FIXED_LENSES) <= set(lenses) and len(set(lenses)) == len(lenses),
        "lenses must include fit, feasibility and quality exactly once",
    )
    for lens in lenses:
        require(isinstance(lens, str) and LENS_ID.match(lens), f"invalid lens id {lens}")
    requirement_ids = list(sequence(request.get("requirement_ids"), "requirement_ids"))
    for requirement_id in requirement_ids:
        nonempty(requirement_id, "requirement id")
    require(len(set(requirement_ids)) == len(requirement_ids), "duplicate requirement id")
    normalized = normalize(
        {
            "findings": request.get("findings"),
            "severity_resolutions": request.get("severity_resolutions", {}),
            "lenses": lenses,
            "requirement_ids": requirement_ids,
        }
    )
    coverage = obj(request.get("coverage"), "coverage")
    require(set(coverage) == set(lenses), "coverage must name exactly the active lenses")
    require(
        all(v in ("complete", "partial", "not_run", "failed") for v in coverage.values()),
        "invalid coverage status",
    )
    records = sequence(request.get("requirement_records"), "requirement_records")
    for record in records:
        obj(record, "requirement record")
        nonempty(record.get("requirement_id"), "requirement record.requirement_id")
        require(record.get("status") in RECORD_STATUSES, "invalid requirement record status")
        nonempty(record.get("evidence_location"), "requirement record.evidence_location")
        for item in sequence(record.get("finding_ids"), "requirement record.finding_ids"):
            nonempty(item, "requirement record finding id")
    record_ids = [record["requirement_id"] for record in records]
    require(
        len(set(record_ids)) == len(record_ids) and set(record_ids) == set(requirement_ids),
        "requirement_records must cover each brief requirement exactly once",
    )
    feasibility_label = request.get("feasibility_label")
    require(feasibility_label in LABELS["feasibility"], "invalid feasibility_label")
    quality_label = request.get("quality_label")
    require(quality_label in LABELS["quality"], "invalid quality_label")
    brief = obj(request.get("brief"), "brief")
    nonempty(brief.get("sha256"), "brief.sha256")
    boolean(brief.get("constraints_stated"), "brief.constraints_stated")
    boolean(brief.get("standard_stated"), "brief.standard_stated")
    nonempty(request.get("lens_set_sha256"), "lens_set_sha256")

    findings = normalized["findings"]
    active = [f for f in findings if not excluded(f)]
    decisive = [f for f in active if f["affects_decision"]]
    gaps = [
        f["issue_id"]
        for f in decisive
        if f["kind"] in ("missing_evidence", "question") or not established(f)
    ]
    solid = [
        f
        for f in decisive
        if established(f) and f["kind"] not in ("missing_evidence", "question")
    ]
    criticals = [f for f in solid if f["severity"] == "Critical"]
    highs = [f for f in solid if f["severity"] == "High"]
    cited_ok = {
        m
        for f in active
        if established(f) and f["kind"] not in ("missing_evidence", "question")
        for m in f["member_ids"]
    }

    assumption_issues = {}
    for f in criticals:
        for assumption_id in f["assumption_ids"]:
            assumption_issues.setdefault(assumption_id, []).append(f["issue_id"])
    shared_assumptions = {
        key: issues for key, issues in assumption_issues.items() if len(issues) > 1
    }
    independence = obj(request.get("independence_evidence", {}), "independence_evidence")
    require(
        set(independence) <= set(shared_assumptions),
        "independence evidence names an unknown shared assumption",
    )
    for assumption_id, explanation in independence.items():
        obj(explanation, "independence explanation")
        nonempty(explanation.get("reason"), "independence explanation.reason")
        cited_ids = sequence(explanation.get("issue_ids"), "independence explanation.issue_ids")
        require(
            all(isinstance(item, str) for item in cited_ids)
            and sorted(cited_ids) == sorted(shared_assumptions[assumption_id]),
            "independence explanation must name exactly the affected issue ids",
        )
        require(
            bool(sources(explanation.get("sources"))),
            "independent failure mechanisms require cited evidence",
        )
    unresolved_dependence = sorted(set(shared_assumptions) - set(independence))

    reasons = []
    requirement_results = {}
    for record in records:
        requirement_id = record["requirement_id"]
        status = record["status"]
        if status in ("not_met", "partly_met") and not set(record["finding_ids"]) & cited_ok:
            status = "cannot_tell"
            reasons.append(
                f"{requirement_id}: a {record['status']} record cites no established finding, so it counts as cannot_tell."
            )
        forced_by = sorted(
            f["id"] for f in criticals if f.get("requirement_id") == requirement_id
        )
        if forced_by:
            status = "not_met"
        requirement_results[requirement_id] = {
            "status": status,
            "evidence_location": record["evidence_location"],
            "forced_by": forced_by,
            "cited": list(record["finding_ids"]),
        }
    statuses = {r["status"] for r in requirement_results.values()}
    fit_vacuous = not requirement_ids
    if fit_vacuous:
        fit = "meets"
        reasons.append("The brief states no requirements, so fit is vacuous.")
    elif "not_met" in statuses:
        fit = "does_not_meet"
    elif "cannot_tell" in statuses:
        fit = "cannot_judge"
    elif "partly_met" in statuses:
        fit = "partly_meets"
    else:
        fit = "meets"

    feasibility = feasibility_label
    if any("feasibility" in f["axes"] for f in criticals):
        feasibility = "not_achievable"
    elif feasibility == "achievable" and any("feasibility" in f["axes"] for f in highs):
        feasibility = "achievable_with_changes"
    quality = quality_label
    decision = decide(fit, feasibility)

    required_roles = set(lenses)
    if decision != "cannot_judge" or verifier_required(findings):
        required_roles.add("verifier")
    review_protocol = request.get("review_protocol")
    model_coverage = review_model_coverage(
        request.get("expected_model_roles"), review_protocol, required_roles=required_roles
    )
    model_gaps = model_coverage["model_policy_gaps"]
    review_role_gaps = model_coverage["review_role_gaps"]

    status = "complete"
    if model_gaps or review_role_gaps:
        status = "incomplete_coverage"
        if model_gaps:
            reasons.append("Mandatory model policy was not confirmed for: " + ", ".join(model_gaps))
        if review_role_gaps:
            reasons.append(
                "Expected review roles were not observed with their declared policies: "
                + ", ".join(review_role_gaps)
            )
    elif any(value != "complete" for value in coverage.values()):
        status = "incomplete_coverage"
        reasons.append("Every active lens must complete before a judgment.")
    elif normalized["conflicts"] or gaps:
        status = "insufficient_evidence"
        reasons.append("Resolve conflicting findings or decision-relevant evidence gaps.")
    elif unresolved_dependence:
        status = "insufficient_evidence"
        reasons.append(
            "Critical findings share a causal assumption. Consolidate the underlying issue or document independent evidence."
        )
    if status != "complete":
        fit = feasibility = quality = decision = "cannot_judge"

    mechanical = {"fit": fit, "feasibility": feasibility, "quality": quality, "decision": decision}
    result = {
        "schema_version": 3,
        "assessment_status": status,
        "fit": fit,
        "fit_vacuous": fit_vacuous,
        "feasibility": feasibility,
        "feasibility_provisional": not brief["constraints_stated"],
        "quality": quality,
        "quality_provisional": not brief["standard_stated"],
        "decision": decision,
        "mechanical": deepcopy(mechanical),
        "reasons": reasons,
        "requirement_results": requirement_results,
        "critical_issue_ids": [f["issue_id"] for f in criticals],
        "high_issue_ids": [f["issue_id"] for f in highs],
        "evidence_gaps": gaps,
        "excluded_ids": [m for f in findings if excluded(f) for m in f["member_ids"]],
        "conflicts": normalized["conflicts"],
        "coverage": deepcopy(coverage),
        "override": None,
        "shared_critical_assumptions": shared_assumptions,
        "independence_evidence": deepcopy(independence),
        "unresolved_dependence": unresolved_dependence,
        "model_policy_gaps": model_gaps,
        "review_role_gaps": review_role_gaps,
        "findings": deepcopy(findings),
        "lenses": lenses,
        "brief_sha256": brief["sha256"],
        "lens_set_sha256": request["lens_set_sha256"],
        "expected_model_roles": deepcopy(request.get("expected_model_roles") or []),
    }
    if review_protocol is not None:
        result["review_protocol"] = deepcopy(review_protocol)
    result["user_report_dependencies"] = [
        f["issue_id"] for f in decisive if f["evidence_basis"] == "user_report"
    ]
    if result["user_report_dependencies"]:
        reasons.append(
            "Judgment is conditional on the cited user reports; these were not independently verified."
        )
    if "override" in request:
        override = obj(request["override"], "override")
        require(
            status == "complete" and "cannot_judge" not in mechanical.values(),
            "override cannot bypass evidence or coverage gates",
        )
        labels = obj(override.get("labels"), "override.labels")
        require(
            bool(labels) and set(labels) <= {"fit", "feasibility", "quality"},
            "override.labels names fit, feasibility or quality",
        )
        for key, value in labels.items():
            require(value in LABELS[key], f"invalid override label for {key}")
            require(value != "cannot_judge", "override cannot set a label to cannot_judge")
        nonempty(override.get("reason"), "override.reason")
        require(bool(sources(override.get("sources"))), "override needs evidence")
        improves = any(
            LABELS[key].index(value) < LABELS[key].index(mechanical[key])
            for key, value in labels.items()
        )
        if improves:
            nonempty(override.get("decision_id"), "override.decision_id")
        result.update(labels)
        result["decision"] = decide(result["fit"], result["feasibility"])
        result["override"] = deepcopy(override)
    return result


def acceptance(request):
    flags = flag_set(request.get("flags", []))
    require(
        flags <= {"--accept-all", "--accept-none"},
        "acceptance only accepts acceptance flags",
    )
    normalized = normalize(
        {
            "findings": request.get("findings"),
            "severity_resolutions": request.get("severity_resolutions", {}),
        }
    )
    inline = obj(request.get("inline", {}), "inline")
    all_ids = {m for f in normalized["findings"] for m in f["member_ids"]}
    require(set(inline) <= all_ids, "inline decision names an unknown finding")
    conflict_ids = {c["issue_id"] for c in normalized["conflicts"]}
    results = []
    for f in normalized["findings"]:
        choices = [
            obj(inline[m], "inline decision") for m in f["member_ids"] if m in inline
        ]
        for choice in choices:
            require(
                choice.get("decision") in ("accept", "reject", "defer"),
                "invalid inline decision",
            )
            if "reason" in choice:
                nonempty(choice["reason"], "inline reason")
        require(
            len({c["decision"] for c in choices}) <= 1,
            f"conflicting inline decisions for {f['issue_id']}",
        )
        if excluded(f):
            decision, reason = (
                "exclude",
                "Refuted or resolved evidence cannot be resurrected by acceptance.",
            )
        elif choices and choices[0]["decision"] == "reject":
            decision, reason = (
                "reject",
                choices[0].get("reason", "User did not state a reason."),
            )
        elif f["issue_id"] in conflict_ids:
            decision, reason = (
                "defer",
                "Resolve this causal issue's conflicting normalization first.",
            )
        elif choices:
            decision, reason = (
                choices[0]["decision"],
                choices[0].get(
                    "reason",
                    "Explicit user finding decision; evidence status unchanged.",
                ),
            )
        elif "--accept-none" in flags:
            decision, reason = "reject", "Explicit --accept-none."
        elif "--accept-all" in flags:
            decision, reason = (
                "accept",
                "Explicit --accept-all; evidence status unchanged.",
            )
        elif established(f) and (
            f["bucket"] in ("consensus", "unique_real")
            or f["bucket"] == "verdict"
            and f["severity"] in ("Critical", "High")
        ):
            decision, reason = (
                "accept",
                "Supported finding in an actionable synthesis bucket.",
            )
        else:
            decision, reason = (
                "defer",
                "Unknown, unrated or unsupported finding requires explicit review.",
            )
        results.append(
            {
                "id": f["id"],
                "issue_id": f["issue_id"],
                "member_ids": f["member_ids"],
                "decision": decision,
                "reason": reason,
                "remedy_approved": False,
                "evidence_established": established(f),
            }
        )
    return {"decisions": results, "conflicts": normalized["conflicts"]}


def change_id(request):
    change = obj(request.get("change", request), "change")
    require(change.get("category") in CATEGORIES, "invalid change category")
    nonempty(change.get("description"), "change.description")
    facts = sequence(change.get("required_facts", []), "change.required_facts")
    for fact in facts:
        nonempty(fact, "required fact id")
    require(len(set(facts)) == len(facts), "duplicate required fact")
    canonical = {
        "category": change["category"],
        "description": change["description"],
        "required_facts": sorted(facts),
    }
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    return {"id": digest}


def gate(request):
    changes = sequence(request.get("changes"), "changes")
    decisions = sequence(request.get("decisions", []), "decisions")
    facts = obj(request.get("facts", {}), "facts")
    by_change, decision_ids = {}, set()
    for decision in decisions:
        obj(decision, "decision")
        for key in ("id", "change_id", "choice"):
            nonempty(decision.get(key), f"decision.{key}")
        boolean(decision.get("approved"), "decision.approved")
        require(
            decision.get("source") == "user",
            "Only user decisions approve consequential changes",
        )
        require(decision["id"] not in decision_ids, "duplicate decision id")
        decision_ids.add(decision["id"])
        by_change[decision["change_id"]] = decision  # append order is authoritative
    for key, fact in facts.items():
        nonempty(key, "fact id")
        obj(fact, "fact")
        require(
            fact.get("origin") in ("document", "user", "external"),
            "invalid fact origin",
        )
        nonempty(fact.get("source"), "fact.source")
    result = {
        "ready": [],
        "pending_questions": [],
        "rejected": [],
        "reused_decisions": [],
    }
    seen = set()
    for change in changes:
        digest = change_id({"change": change})["id"]
        require(
            change.get("id") == digest,
            "change.id must match change_id output; changed remedies require a new decision",
        )
        require(digest not in seen, "duplicate change id")
        seen.add(digest)
        decision = by_change.get(digest)
        if decision:
            result["reused_decisions"].append(decision["id"])
            if not decision["approved"]:
                result["rejected"].append(digest)
                continue
        missing = [
            key
            for key in change.get("required_facts", [])
            if key not in facts
            or facts[key].get("value") is None
            or facts[key].get("value") == ""
        ]
        reasons = []
        if change["category"] != "routine" and not decision:
            reasons.append("material_choice")
        if missing:
            reasons.append("missing_facts")
        if reasons:
            result["pending_questions"].append(
                {"change_id": digest, "reason": reasons, "missing_facts": missing}
            )
        else:
            result["ready"].append(digest)
    return result


THRESHOLDS = json.loads(Path(__file__).with_name("thresholds.json").read_text())
ACTION_FLAGS = {
    "--critique-only",
    "--rewrite",
    "--loop",
    "--verify-claims",
    "--accept-all",
    "--accept-none",
}
INPUT_FLAGS = {"--brief", "--entries", "--examples", "--slug"}
ADMIN_FLAGS = {"--status", "--reset"}
SKILL_FLAGS = {
    "brief": {"--examples"},
    "judge": {"--verify-claims", "--critique-only", "--rewrite"},
    "revise": {"--accept-all", "--accept-none"},
    "rank": {"--verify-claims", "--critique-only"},
}
INTERIM_BRIEF_STOP = (
    "Supply the brief with --brief PATH. "
    "The interview and example-derived briefs arrive in 4.2.0."
)
INTERIM_RANK_STOP = "Ranking arrives in 4.1.0."


def flag_set(flags):
    """Flag tokens only: '--slug name' and '--slug=name' both become '--slug'."""
    tokens = [
        re.split(r"[ =]", flag, maxsplit=1)[0] if isinstance(flag, str) else flag
        for flag in sequence(flags, "flags")
    ]
    known = ACTION_FLAGS | INPUT_FLAGS | ADMIN_FLAGS
    require(all(isinstance(t, str) and t in known for t in tokens), "unknown flag")
    require(len(set(tokens)) == len(tokens), "duplicate flag")
    tokens = set(tokens)
    require(
        not {"--accept-all", "--accept-none"} <= tokens,
        "--accept-all and --accept-none conflict",
    )
    require(
        not (tokens & ADMIN_FLAGS and (tokens & ACTION_FLAGS or ADMIN_FLAGS <= tokens)),
        "--status/--reset cannot combine with action flags",
    )
    return tokens


def route(request):
    intent = request.get("intent", "auto")
    require(
        intent
        in ("auto", "brief", "judge", "revise", "rank", "status", "reset", "stop"),
        "unknown intent",
    )
    flags = flag_set(request.get("flags", []))
    state = obj(request.get("state", {}), "state")
    version = state.get("current_version", 1)
    require(
        version is None or (type(version) is int and version >= 1),
        "current_version must be a positive integer or null",
    )
    require(
        state.get("stage", "snapshot") in ("snapshot", "judgment", "revision", "ranking"),
        "invalid stage",
    )
    for field in ("has_document", "has_brief", "has_judgment", "can_revise"):
        if field in state:
            boolean(state[field], field)
    for field in ("pending_questions", "evidence_gaps", "entry_slugs"):
        if field in state:
            sequence(state[field], field)
    require(
        state.get("decision") is None or state["decision"] in LABELS["decision"],
        "invalid state decision",
    )
    if "assessment_status" in state:
        require(
            state["assessment_status"]
            in ("complete", "insufficient_evidence", "incomplete_coverage"),
            "invalid assessment_status",
        )
    rewritable = state.get("rewritable")
    if rewritable is not None:
        obj(rewritable, "rewritable")
        boolean(rewritable.get("value"), "rewritable.value")
        require(
            rewritable.get("decided_by") in ("default", "flag", "user", "rank"),
            "invalid rewritable.decided_by",
        )
    inputs = sequence(request.get("inputs", []), "inputs")
    types = []
    for item in inputs:
        obj(item, "input")
        require(
            item.get("type") in ("document", "brief", "examples", "judgment"),
            "input type must be explicit",
        )
        nonempty(item.get("ref"), "input.ref")
        types.append(item["type"])

    if flags & ADMIN_FLAGS:
        selected = "status" if "--status" in flags else "reset"
        require(
            intent in ("auto", selected),
            "administrative flag conflicts with explicit intent",
        )
        intent = selected
    if intent in ("status", "reset", "stop"):
        require(
            not flags & ACTION_FLAGS,
            "administrative/stop intent cannot combine with action flags",
        )
        return {
            "action": {"status": "status", "reset": "archive_state", "stop": "stop"}[
                intent
            ],
            "reason": "Explicit user intent.",
            "pass_flags": [],
            "loop_flags": [],
            "current_version": version,
            "rewritable": None,
        }

    loop = "--loop" in flags
    new_rewritable = None

    def answer(action, reason):
        allowed = SKILL_FLAGS.get(action, set())
        checked = flags & ACTION_FLAGS - {"--loop", "--critique-only", "--rewrite"}
        require(
            loop or action not in SKILL_FLAGS or checked <= allowed,
            "flag is incompatible with the selected skill",
        )
        return {
            "action": action,
            "reason": reason,
            "pass_flags": sorted(flags & ACTION_FLAGS & allowed),
            "loop_flags": sorted(flags & ACTION_FLAGS) if loop else [],
            "current_version": version,
            "rewritable": new_rewritable,
        }

    if any(types.count(kind) > 1 for kind in set(types)):
        return answer(
            "ask_input_roles", "Select one input of each kind explicitly."
        )
    require(
        not {"--critique-only", "--rewrite"} <= flags,
        "--critique-only and --rewrite conflict",
    )
    slugs = list(state.get("entry_slugs", []))
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if state.get("brief_slug") in slugs:
        duplicates.append(state["brief_slug"])
    require(
        not duplicates,
        "entry slugs must be unique and differ from the brief ledger: "
        + ", ".join(duplicates),
    )
    if len(slugs) > 1:
        require(
            not flags & {"--loop", "--rewrite", "--accept-all", "--accept-none"},
            "rank mode judges only; it never revises",
        )
    cap = THRESHOLDS["rank_max_entries"]
    require(len(slugs) <= cap, f"at most {cap} entries can be ranked in one run")
    require("--examples" not in flags, "--examples arrives in 4.2.0")
    if intent == "brief":
        return answer("brief", "Explicit brief intent.")
    if not state.get("has_brief", False):
        if "--brief" in flags:
            return answer("brief", "Read and store the supplied brief first.")
        return answer("stop", INTERIM_BRIEF_STOP)
    if intent == "rank" or len(slugs) > 1:
        return answer("stop", INTERIM_RANK_STOP)
    if not state.get("has_document", False):
        return answer("ask_document", "Provide the entry or a slug with a snapshot.")
    flag_value = (
        False if "--critique-only" in flags else True if "--rewrite" in flags else None
    )
    if flag_value is not None:
        if rewritable is not None and rewritable["decided_by"] == "user":
            if rewritable["value"] != flag_value:
                return answer(
                    "ask_user",
                    "The flag contradicts your earlier choice about rewriting this entry.",
                )
        elif rewritable is None or rewritable["value"] != flag_value or rewritable[
            "decided_by"
        ] in ("default", "rank"):
            new_rewritable = {"value": flag_value, "decided_by": "flag"}
            rewritable = new_rewritable
    if state.get("pending_questions"):
        return answer("ask_user", "Pending choices or missing facts need your input.")
    if intent == "judge":
        return answer("judge", "Explicit judge intent.")
    rewritable_false = rewritable is not None and rewritable["value"] is False
    has_judgment = state.get("has_judgment", False)
    if intent == "revise":
        if not has_judgment:
            return answer("judge", "Judge the current version before revising it.")
        if rewritable_false:
            return answer("critique_complete", "This entry is not rewritten; the improvement record is the output.")
        if version is not None and version >= THRESHOLDS["max_versions"]:
            return answer("version_limit", "The version cap is reached; start a new slug to continue.")
        return answer("revise", "Explicit revise intent.")
    if not has_judgment:
        return answer("judge", "No judgment exists for the current version.")
    gaps = ", ".join(state.get("evidence_gaps", [])) or "unspecified"
    if state.get("assessment_status") == "incomplete_coverage":
        return answer("stop", f"Review coverage is incomplete: {gaps}. Restore it, then judge again explicitly.")
    if state.get("assessment_status") == "insufficient_evidence":
        return answer("stop", f"Evidence gaps remain: {gaps}. Resolve them, then judge again explicitly.")
    if state.get("decision") == "cannot_judge":
        return answer("stop", f"Cannot judge yet. Supply what is missing to continue: {gaps}.")
    if rewritable_false:
        return answer("critique_complete", "This entry is not rewritten; the improvement record is the output.")
    if loop and state.get("decision") in ("not_yet", "no") and state.get("can_revise", False):
        if version is not None and version >= THRESHOLDS["max_versions"]:
            return answer("version_limit", "The version cap is reached; start a new slug to continue.")
        return answer("revise", "Loop: revise the entry toward the brief.")
    return answer(
        "stop",
        f"Judged {state.get('decision')}. An explicit revise or judge request continues.",
    )


def prioritize(request):
    normalized = normalize(
        {
            "findings": request.get("findings"),
            "severity_resolutions": request.get("severity_resolutions", {}),
        }
    )
    conflicts = {c["issue_id"] for c in normalized["conflicts"]}
    active = [f for f in normalized["findings"] if not excluded(f)]
    # Consequence first, then evidence/uncertainty; no mention-count multiplier.
    ordered = sorted(
        active,
        key=lambda f: (
            not f["affects_decision"],
            ENUMS["severity"].index(f["severity"]),
            not established(f),
            ("high", "medium", "low").index(f["confidence"]),
            f["issue_id"],
        ),
    )
    return {
        "ordered_issue_ids": [f["issue_id"] for f in ordered],
        "needs_resolution": sorted(conflicts),
        "rationale": "Decision consequence, severity, evidence support, confidence, stable issue id. Effort and dependencies require explicit change planning; reviewer mentions never vote.",
    }


def model_preflight(request):
    """Resolve an exposed caller requirement before any judgment-agent dispatch."""
    role = nonempty(request.get("role"), "role")
    dispatch_path = request.get("dispatch_path")
    require(
        dispatch_path in ("registered", "pasted", "inline"),
        "invalid dispatch_path",
    )
    pin = request.get("agent_model_pin")
    if pin is not None:
        pin = nonempty(pin, "agent_model_pin").strip()
    pin_known = request.get("agent_pin_known")
    if dispatch_path == "inline" and pin_known is None:
        pin_known = True
    require(pin_known is None or type(pin_known) is bool, "invalid agent_pin_known")
    require(
        pin_known is not False or pin is None, "unknown agent pin cannot have a value"
    )
    caller_policy = request.get("caller_policy")
    if caller_policy is None:
        requested_model = None
        mandatory = False
    else:
        caller_policy = obj(caller_policy, "caller_policy")
        requested_model = nonempty(
            caller_policy.get("model"), "caller_policy.model"
        ).strip()
        mandatory = boolean(caller_policy.get("mandatory"), "caller_policy.mandatory")
    can_select = request.get("host_can_select")
    can_reveal = request.get("host_can_reveal")
    require(can_select is None or type(can_select) is bool, "invalid host_can_select")
    require(can_reveal is None or type(can_reveal) is bool, "invalid host_can_reveal")

    if requested_model is None:
        status, allowed, limitation = "no_requirement", True, None
    elif pin_known is not True:
        status, allowed = "pin_unknown", not mandatory
        limitation = "The selected agent definition's model pin was not inspected."
    elif pin not in (None, "inherit", requested_model):
        status, allowed = "conflicting_pin", False
        limitation = "The selected agent definition pins a different model."
    elif can_select is not True:
        status, allowed = "selection_unavailable", not mandatory
        limitation = "The host cannot confirm per-dispatch model selection."
    elif can_reveal is False:
        status, allowed = "visibility_unavailable", not mandatory
        limitation = "The host cannot expose the model used by this role."
    else:
        status, allowed, limitation = "ready", True, None
    return {
        "role": role,
        "dispatch_path": dispatch_path,
        "requested_model": requested_model,
        "mandatory": mandatory,
        "agent_model_pin": pin,
        "agent_pin_known": pin_known,
        "host_can_select": can_select,
        "host_can_reveal": can_reveal,
        "model_argument": requested_model if allowed and can_select is True else None,
        "dispatch_allowed": allowed,
        "status": status,
        "limitation": limitation,
    }


def model_observation(request):
    """Record only host-exposed model identity and evidenced policy compliance."""
    prepared = obj(request.get("preflight"), "preflight")
    expected = model_preflight(
        {
            "role": prepared.get("role"),
            "dispatch_path": prepared.get("dispatch_path"),
            "caller_policy": (
                {
                    "model": prepared["requested_model"],
                    "mandatory": prepared.get("mandatory"),
                }
                if prepared.get("requested_model") is not None
                else None
            ),
            "agent_model_pin": prepared.get("agent_model_pin"),
            "agent_pin_known": prepared.get("agent_pin_known"),
            "host_can_select": prepared.get("host_can_select"),
            "host_can_reveal": prepared.get("host_can_reveal"),
        }
    )
    require(prepared == expected, "preflight record is inconsistent")
    actual = nonempty(request.get("actual_model", "unknown"), "actual_model").strip()
    resolved = request.get("host_resolved_model")
    if resolved is not None:
        resolved = nonempty(resolved, "host_resolved_model").strip()
        require(
            prepared["requested_model"] in ("opus", "sonnet", "haiku", "fable"),
            "host_resolved_model requires a requested family alias",
        )
    if not prepared["dispatch_allowed"]:
        require(actual == "unknown", "a blocked dispatch cannot have an actual model")
    if prepared["host_can_reveal"] is False:
        require(actual == "unknown", "model cannot be exposed by this host")

    status = prepared["status"]
    limitation = prepared["limitation"]
    requested = prepared["requested_model"]
    if status == "ready":
        if actual == "unknown":
            status, limitation = "unknown", "The host did not expose the actual model."
        elif resolved is not None and requested in ("opus", "sonnet", "haiku", "fable"):
            families = {
                family
                for family in ("opus", "sonnet", "haiku", "fable")
                if re.search(rf"(?<![a-z]){family}(?![a-z])", resolved.casefold())
            }
            if len(families) != 1:
                status = "unknown"
                limitation = (
                    "The host's alias resolution does not identify one model family."
                )
            elif requested not in families or actual not in (requested, resolved):
                status = "mismatch"
                limitation = "The exposed model or alias resolution differs from the requested model."
            else:
                status, limitation = "compliant", None
        elif actual == requested and requested not in (
            "opus",
            "sonnet",
            "haiku",
            "fable",
        ):
            status, limitation = "compliant", None
        elif requested in ("opus", "sonnet", "haiku", "fable"):
            status = "unknown"
            limitation = "The host did not expose how the requested alias resolved."
        else:
            status = "mismatch"
            limitation = "The exposed model differs from the requested model."
    return {
        **prepared,
        "actual_model": actual,
        "host_resolved_model": resolved,
        "status": status,
        "policy_compliant": None if requested is None else status == "compliant",
        "limitation": limitation,
    }


def review_model_roles(protocol):
    """Validate observed role records before they affect a verdict or report."""
    if protocol is None:
        return []
    protocol = obj(protocol, "review_protocol")
    roles = sequence(protocol.get("roles", []), "review_protocol.roles")
    for role in roles:
        role = obj(role, "review_protocol role")
        prepared = {
            key: role.get(key)
            for key in (
                "role",
                "dispatch_path",
                "requested_model",
                "mandatory",
                "agent_model_pin",
                "agent_pin_known",
                "host_can_select",
                "host_can_reveal",
                "model_argument",
                "dispatch_allowed",
                "status",
                "limitation",
            )
        }
        # The observed status replaces the preflight status; recompute preflight
        # from its inputs rather than trusting the serialized outcome.
        prepared = model_preflight(
            {
                "role": prepared["role"],
                "dispatch_path": prepared["dispatch_path"],
                "caller_policy": (
                    {
                        "model": prepared["requested_model"],
                        "mandatory": prepared["mandatory"],
                    }
                    if prepared["requested_model"] is not None
                    else None
                ),
                "agent_model_pin": prepared["agent_model_pin"],
                "agent_pin_known": prepared["agent_pin_known"],
                "host_can_select": prepared["host_can_select"],
                "host_can_reveal": prepared["host_can_reveal"],
            }
        )
        observed = model_observation(
            {
                "preflight": prepared,
                "actual_model": role.get("actual_model", "unknown"),
                "host_resolved_model": role.get("host_resolved_model"),
            }
        )
        require(role == observed, "review_protocol role record is inconsistent")
    return roles


def verifier_required(findings):
    """A fresh verifier covers consequential or severe findings."""
    return any(
        finding["severity"] in ("Critical", "High") or finding["affects_decision"]
        for finding in findings
    )


def review_model_coverage(expected_roles, protocol, *, required_roles=()):
    """Compare the pre-dispatch role plan with post-dispatch observations."""
    roles = review_model_roles(protocol)
    expected = sequence(
        [] if expected_roles is None else expected_roles, "expected_model_roles"
    )
    planned = {}
    for item in expected:
        item = obj(item, "expected_model_roles entry")
        require(
            set(item) == {"role", "caller_policy"},
            "expected_model_roles entry needs role and caller_policy",
        )
        name = nonempty(item["role"], "expected_model_roles.role")
        require(name not in planned, "duplicate expected model role")
        caller_policy = item["caller_policy"]
        if caller_policy is None:
            planned[name] = (None, False)
        else:
            caller_policy = obj(caller_policy, "expected_model_roles.caller_policy")
            require(
                set(caller_policy) == {"model", "mandatory"},
                "expected caller policy needs model and mandatory",
            )
            planned[name] = (
                nonempty(caller_policy["model"], "expected model").strip(),
                boolean(caller_policy["mandatory"], "expected mandatory"),
            )
    observed = {}
    for role in roles:
        name = role["role"]
        require(name not in observed, "duplicate observed model role")
        observed[name] = role
    role_gaps = set(required_roles) - set(planned)
    role_gaps.update(set(planned) ^ set(observed))
    model_gaps = {
        role["role"]
        for role in roles
        if role["mandatory"] and not role["policy_compliant"]
    }
    for name, (requested, mandatory) in planned.items():
        role = observed.get(name)
        if role is None:
            if mandatory:
                model_gaps.add(name)
            continue
        if not role["dispatch_allowed"]:
            role_gaps.add(name)
        if (role["requested_model"], role["mandatory"]) != (requested, mandatory):
            role_gaps.add(name)
            if mandatory:
                model_gaps.add(name)
        elif mandatory and not role["policy_compliant"]:
            model_gaps.add(name)
    return {
        "review_role_gaps": sorted(role_gaps),
        "model_policy_gaps": sorted(model_gaps),
    }


OPERATIONS = {
    name: globals()[name]
    for name in (
        "normalize",
        "judgment",
        "acceptance",
        "change_id",
        "gate",
        "route",
        "prioritize",
        "model_preflight",
        "model_observation",
    )
}


def execute(operation, request):
    require(operation in OPERATIONS, "unknown operation")
    return OPERATIONS[operation](obj(request, "request"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--request", "--file", dest="request_file", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = (
            args.request_file.read_text(encoding="utf-8")
            if args.request_file
            else sys.stdin.read()
        )
        result = execute(args.operation, json.loads(payload))
    except (PolicyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
