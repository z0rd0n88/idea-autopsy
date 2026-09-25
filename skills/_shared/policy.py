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


AXES = ("critical_thinking", "feasibility", "risk", "roi")
VERDICTS = ("Invest", "Proceed with caution", "Pivot", "Skip")
CATEGORIES = (
    "routine",
    "target_customer",
    "pricing",
    "business_model",
    "core_thesis",
    "scope",
    "experiment",
)
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


def validate_finding(value):
    """Validate a normalized finding; never upgrade a legacy provenance tag."""
    f = deepcopy(obj(value, "finding"))
    for key in ("id", "issue_id", "statement", "severity_reason"):
        nonempty(f.get(key), f"finding.{key}")
    for key, values in ENUMS.items():
        require(f.get(key) in values, f"finding.{key} must be one of {values}")
    for key in ("affects_decision", "thesis_breaking"):
        boolean(f.get(key), f"finding.{key}")
    require(
        f.get("plausibly_resolvable") is None
        or type(f["plausibly_resolvable"]) is bool,
        "finding.plausibly_resolvable must be boolean or null",
    )
    for key in ("axes", "assumption_ids"):
        for item in sequence(f.get(key), f"finding.{key}"):
            nonempty(item, f"finding.{key} entry")
        require(len(set(f[key])) == len(f[key]), f"finding.{key} contains duplicates")
    require(set(f["axes"]) <= set(AXES), "finding.axes contains an unknown axis")
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


def markdown_candidates(markdown):
    """Import final synthesis only. Imported claims require source verification.

    This is a conservative compatibility reader, not semantic interpretation.
    JSON findings are the authoritative format for new reports.
    """
    nonempty(markdown, "markdown")
    rows = []
    fenced = False
    for number, line in enumerate(markdown.splitlines(), 1):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if not fenced:
            heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
            rows.append(
                (
                    number,
                    line,
                    (len(heading[1]), heading[2].lower()) if heading else None,
                )
            )
    canonical = [
        i
        for i, (_, _, h) in enumerate(rows)
        if h and h[1].startswith("normalized findings")
    ]
    synthesis = [i for i, (_, _, h) in enumerate(rows) if h and h[1] == "synthesis"]
    table = [
        i
        for i, (_, _, h) in enumerate(rows)
        if h and h[1].startswith("issue multiplicity table")
    ]
    anchors = canonical or synthesis or table
    if anchors:
        start = anchors[-1]
        level = rows[start][2][0]
        end = next(
            (
                i
                for i in range(start + 1, len(rows))
                if rows[i][2] and rows[i][2][0] <= level
            ),
            len(rows),
        )
        if synthesis and not canonical:
            end = next(
                (
                    i
                    for i in range(start + 1, len(rows))
                    if rows[i][2]
                    and rows[i][2][1].startswith(
                        (
                            "iteration recommendations",
                            "next step",
                            "verdict:",
                            "reviewer ",
                        )
                    )
                ),
                len(rows),
            )
        selected = rows[start + 1 : end]
        fmt = (
            "normalized"
            if canonical
            else "stress-test-idea"
            if synthesis
            else "evaluate-proposal-harsh"
        )
    else:
        selected, fmt = rows, "unknown"
    result, bucket = (
        [],
        "verdict" if table and not canonical and not synthesis else "unknown",
    )
    for number, line, heading in selected:
        if heading:
            name = heading[1]
            if name.startswith("consensus findings"):
                bucket = "consensus"
            elif name.startswith("unique"):
                bucket = (
                    "unique_reach"
                    if "likely reach" in name
                    else "unique_real"
                    if "(real)" in name
                    else "unique_unrated"
                )
            elif name.startswith(("what none caught", "what neither caught")):
                bucket = "speculative"
            else:
                bucket = "unknown"
            continue
        if fmt == "stress-test-idea" and bucket == "unknown":
            continue  # verification, contradictions and recommendations are not final finding rows
        match = re.match(
            r"^\s*[-*]\s+(?:\*\*)?\[(Critical|High|Medium)\](?:\*\*)?\s*(.*)",
            line,
            re.I,
        )
        if match:
            severity, statement = match[1].title(), match[2].strip()
        elif fmt == "evaluate-proposal-harsh" and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[1] not in ENUMS["severity"]:
                continue
            statement, severity = cells[:2]
        elif fmt == "unknown" and re.match(r"^\s*[-*]\s+\S", line):
            severity, statement = "Medium", re.sub(r"^\s*[-*]\s+", "", line)
        else:
            continue
        statement = re.sub(
            r"`?\[(?:verified|doc-claim|reviewer-inference)\]`?\s*", "", statement
        ).strip()
        if not statement:
            continue
        digest = hashlib.sha256(statement.casefold().encode()).hexdigest()[:16]
        result.append(
            {
                "id": "import-" + digest,
                "issue_id": "import-" + digest,
                "assumption_ids": [],
                "statement": statement,
                "kind": "question",
                "severity": severity,
                "severity_reason": "Imported severity; requires normalization against source and decision context.",
                "origin": "reviewer",
                "doc_support": "not_established",
                "external_status": "not_checked",
                "confidence": "low",
                "sources": [
                    {
                        "type": "critique",
                        "ref": f"critique:L{number}",
                        "quote": line.strip(),
                    }
                ],
                "axes": [],
                "affects_decision": True,
                "status": "active",
                "resolution": "unresolved",
                "bucket": bucket,
                "evidence_basis": "external_fact",
                "thesis_breaking": False,
                "plausibly_resolvable": None,
            }
        )
    return fmt, result


def normalize(request):
    require(
        ("findings" in request) != ("markdown" in request),
        "supply findings or markdown, not both",
    )
    fmt, raw = (
        ("structured", request["findings"])
        if "findings" in request
        else markdown_candidates(request["markdown"])
    )
    resolutions = obj(request.get("severity_resolutions", {}), "severity_resolutions")
    groups, seen_ids = {}, {}
    for value in sequence(raw, "findings"):
        f = validate_finding(value)
        if f["id"] in seen_ids:
            previous = seen_ids[f["id"]]
            if fmt != "structured":
                previous["sources"] = unique(previous["sources"] + f["sources"])
                continue
            require(previous == f, f"conflicting records for finding id {f['id']}")
            continue
        seen_ids[f["id"]] = f
        groups.setdefault(f["issue_id"], []).append(f)
    require(
        set(resolutions) <= set(groups), "severity resolution names an unknown issue"
    )
    merged, conflicts = [], []
    for issue_id, members in groups.items():
        f = deepcopy(members[0])
        f["member_ids"] = unique(
            [member for m in members for member in m.get("member_ids", [m["id"]])]
        )
        for key in ("axes", "assumption_ids", "sources"):
            f[key] = unique([item for m in members for item in m[key]])
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
            "thesis_breaking",
            "plausibly_resolvable",
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
        "format": fmt,
        "findings": merged,
        "conflicts": conflicts,
        "requires_source_review": fmt != "structured",
    }


def verdict(request):
    normalized = normalize(
        {
            "findings": request.get("findings"),
            "severity_resolutions": request.get("severity_resolutions", {}),
        }
    )
    coverage = obj(request.get("coverage"), "coverage")
    require(set(coverage) == set(AXES), "coverage must include exactly all four axes")
    require(
        all(
            v in ("complete", "partial", "not_run", "failed") for v in coverage.values()
        ),
        "invalid coverage status",
    )
    review_protocol = request.get("review_protocol")
    required_roles = set(AXES)
    if verifier_required(normalized["findings"]):
        required_roles.add("verifier")
    model_coverage = review_model_coverage(
        request.get("expected_model_roles"),
        review_protocol,
        required_roles=required_roles,
    )
    model_gaps = model_coverage["model_policy_gaps"]
    review_role_gaps = model_coverage["review_role_gaps"]
    evidence = obj(request.get("decision_evidence", {}), "decision_evidence")
    sufficient = boolean(
        evidence.get("sufficient", False), "decision_evidence.sufficient"
    )
    if sufficient:
        nonempty(evidence.get("rationale"), "decision_evidence.rationale")
        require(
            bool(sources(evidence.get("sources"))),
            "sufficient decision evidence needs sources",
        )
    assets = sequence(request.get("reusable_assets", []), "reusable_assets")
    for asset in assets:
        obj(asset, "asset")
        nonempty(asset.get("description"), "asset.description")
        require(bool(sources(asset.get("sources"))), "reusable asset needs sources")
    findings = normalized["findings"]
    active = [f for f in findings if not excluded(f)]
    decisive = [f for f in active if f["affects_decision"]]
    gaps = [
        f["issue_id"]
        for f in decisive
        if f["kind"] in ("missing_evidence", "question") or not established(f)
    ]
    criticals = [
        f
        for f in decisive
        if f["severity"] == "Critical"
        and established(f)
        and f["kind"] not in ("missing_evidence", "question")
    ]
    highs = [
        f
        for f in decisive
        if f["severity"] == "High"
        and established(f)
        and f["kind"] not in ("missing_evidence", "question")
    ]
    assumption_issues = {}
    for finding in criticals:
        for assumption_id in finding["assumption_ids"]:
            assumption_issues.setdefault(assumption_id, []).append(finding["issue_id"])
    shared_assumptions = {
        key: issues for key, issues in assumption_issues.items() if len(issues) > 1
    }
    independence = obj(
        request.get("independence_evidence", {}), "independence_evidence"
    )
    require(
        set(independence) <= set(shared_assumptions),
        "independence evidence names an unknown shared assumption",
    )
    for assumption_id, explanation in independence.items():
        obj(explanation, "independence explanation")
        nonempty(explanation.get("reason"), "independence explanation.reason")
        cited_ids = sequence(
            explanation.get("issue_ids"), "independence explanation.issue_ids"
        )
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
    result = {
        "schema_version": 2,
        "assessment_status": "complete",
        "mechanical_verdict": None,
        "verdict": None,
        "reasons": [],
        "critical_issue_ids": [f["issue_id"] for f in criticals],
        "blocking_high_issue_ids": [f["issue_id"] for f in highs],
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
        "expected_model_roles": deepcopy(request.get("expected_model_roles") or []),
    }
    if review_protocol is not None:
        result["review_protocol"] = deepcopy(review_protocol)
    if model_gaps or review_role_gaps:
        reasons = []
        if model_gaps:
            reasons.append(
                "Mandatory model policy was not confirmed for: " + ", ".join(model_gaps)
            )
        if review_role_gaps:
            reasons.append(
                "Expected review roles were not observed with their declared policies: "
                + ", ".join(review_role_gaps)
            )
        result.update(
            assessment_status="incomplete_coverage",
            reasons=reasons,
        )
    elif any(value != "complete" for value in coverage.values()):
        result.update(
            assessment_status="incomplete_coverage",
            reasons=[
                "All four current review axes must complete before a business verdict."
            ],
        )
    elif normalized["conflicts"] or gaps:
        result.update(
            assessment_status="insufficient_evidence",
            reasons=[
                "Resolve conflicting findings or decision-relevant evidence gaps."
            ],
        )
    elif unresolved_dependence:
        result.update(
            assessment_status="insufficient_evidence",
            reasons=[
                "Critical findings share a causal assumption. Consolidate the underlying issue or document independent evidence before counting separate blockers."
            ],
        )
    elif any(f["plausibly_resolvable"] is None for f in criticals):
        result.update(
            assessment_status="insufficient_evidence",
            reasons=[
                "Classify each Critical's resolvability against current resources."
            ],
        )
    elif len(criticals) >= 2:
        result.update(
            mechanical_verdict="Skip",
            reasons=["Multiple independent established Critical issues remain."],
        )
    elif len(criticals) == 1:
        critical = criticals[0]
        feasibility_clean = not any(
            "feasibility" in f["axes"] and f["severity"] in ("Critical", "High")
            for f in active
        )
        if critical["thesis_breaking"] and assets and feasibility_clean:
            result.update(
                mechanical_verdict="Pivot",
                reasons=[
                    "One established thesis-breaking issue; documented reusable assets and complete clean feasibility."
                ],
            )
        elif not critical["thesis_breaking"] and critical["plausibly_resolvable"]:
            result.update(
                mechanical_verdict="Proceed with caution",
                reasons=[
                    "One established non-thesis Critical is plausibly resolvable."
                ],
            )
        else:
            result.update(
                mechanical_verdict="Skip",
                reasons=[
                    "The established Critical has no supported continuation or asset-backed pivot under current constraints."
                ],
            )
    elif highs:
        result.update(
            mechanical_verdict="Proceed with caution",
            reasons=["Established blocking High findings remain."],
        )
    elif sufficient:
        result.update(
            mechanical_verdict="Invest",
            reasons=[
                "No established blocking issue remains and decision evidence is explicitly sufficient."
            ],
        )
    else:
        result.update(
            assessment_status="insufficient_evidence",
            reasons=["An empty issue list is not sufficient evidence to invest."],
        )
    result["verdict"] = result["mechanical_verdict"]
    result["user_report_dependencies"] = [
        f["issue_id"] for f in decisive if f["evidence_basis"] == "user_report"
    ]
    if result["user_report_dependencies"]:
        result["reasons"].append(
            "Assessment is conditional on the cited user reports; these were not independently verified."
        )
    if "override" in request:
        override = obj(request["override"], "override")
        require(
            result["assessment_status"] == "complete",
            "override cannot bypass evidence or coverage gates",
        )
        require(override.get("verdict") in VERDICTS, "invalid override verdict")
        require(
            override["verdict"] != "Invest" or sufficient,
            "An Invest override requires explicit sufficient decision evidence with rationale and sources",
        )
        nonempty(override.get("reason"), "override.reason")
        require(bool(sources(override.get("sources"))), "override needs evidence")
        result.update(verdict=override["verdict"], override=deepcopy(override))
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


def flag_set(flags):
    flags = sequence(flags, "flags")
    known = {
        "--loop",
        "--verify-claims",
        "--validate",
        "--accept-all",
        "--accept-none",
        "--status",
        "--reset",
    }
    require(
        all(isinstance(flag, str) and flag in known for flag in flags), "unknown flag"
    )
    require(len(set(flags)) == len(flags), "duplicate flag")
    flags = set(flags)
    require(
        not {"--accept-all", "--accept-none"} <= flags,
        "--accept-all and --accept-none conflict",
    )
    require(
        not ({"--status", "--reset"} & flags and len(flags) > 1),
        "--status/--reset cannot combine with action flags",
    )
    return flags


def route(request):
    intent = request.get("intent", "auto")
    require(
        intent
        in (
            "auto",
            "stress_test",
            "revise",
            "evaluate",
            "strategy",
            "status",
            "reset",
            "stop",
        ),
        "unknown intent",
    )
    flags = flag_set(request.get("flags", []))
    state = obj(request.get("state", {}), "state")
    version = state.get("current_version", 1)
    require(
        type(version) is int and version >= 1,
        "current_version must be a positive integer",
    )
    stage = state.get("stage", "snapshot")
    require(
        stage in ("snapshot", "stress_test", "revision", "evaluation", "strategy"),
        "invalid stage",
    )
    for field in ("has_document", "has_critique", "has_verdict", "can_revise"):
        if field in state:
            boolean(state[field], field)
    for field in ("pending_questions", "pending_experiments"):
        if field in state:
            sequence(state[field], field)
    if "verdict" in state:
        require(
            state["verdict"] is None or state["verdict"] in VERDICTS,
            "invalid state verdict",
        )
    if "assessment_status" in state:
        require(
            state["assessment_status"]
            in ("complete", "insufficient_evidence", "incomplete_coverage"),
            "invalid assessment_status",
        )
    inputs = sequence(request.get("inputs", []), "inputs")
    types = []
    for item in inputs:
        obj(item, "input")
        require(
            item.get("type") in ("document", "critique", "verdict"),
            "input type must be explicit",
        )
        nonempty(item.get("ref"), "input.ref")
        types.append(item["type"])
    if "--status" in flags or "--reset" in flags:
        selected = "status" if "--status" in flags else "reset"
        require(
            intent in ("auto", selected),
            "administrative flag conflicts with explicit intent",
        )
        intent = selected
    if intent in ("status", "reset", "stop"):
        require(
            flags <= {"--status", "--reset"},
            "administrative/stop intent cannot combine with action flags",
        )
        return {
            "action": {"status": "status", "reset": "archive_state", "stop": "stop"}[
                intent
            ],
            "reason": "Explicit user intent.",
            "pass_flags": [],
        }
    require(
        "--validate" not in flags
        or intent == "strategy"
        or intent == "auto"
        and ("verdict" in types or state.get("has_verdict", False)),
        "--validate requires strategy intent or a supplied/stored assessment",
    )
    if (
        types.count("document") > 1
        or types.count("critique") > 1
        or types.count("verdict") > 1
    ):
        return {
            "action": "ask_input_roles",
            "reason": "Select the current document and authoritative critique/verdict explicitly.",
            "pass_flags": [],
        }
    has_doc = "document" in types or state.get("has_document", False)
    has_critique = "critique" in types or state.get("has_critique", False)
    has_verdict = "verdict" in types or state.get("has_verdict", False)
    if intent == "auto" and "--validate" in flags and has_verdict:
        intent = "strategy"
    loop = "--loop" in flags

    def answer(action, reason):
        allowed = {
            "stress-test-idea": {"--verify-claims"},
            "evaluate-proposal-harsh": {"--verify-claims"},
            "iterate-to-v2": {"--accept-all", "--accept-none"},
            "strategize-from-verdict": {"--validate"},
        }.get(action, set())
        action_flags = flags - {"--loop"}
        # Loop flags remain on router state for later review/revision stages.
        require(
            loop
            or action
            not in (
                "stress-test-idea",
                "evaluate-proposal-harsh",
                "iterate-to-v2",
                "strategize-from-verdict",
            )
            or action_flags <= allowed,
            "flag is incompatible with the selected skill",
        )
        return {
            "action": action,
            "reason": reason,
            "pass_flags": sorted(action_flags & allowed),
            "loop_flags": sorted(flags) if loop else [],
            "current_version": version,
        }

    def revise():
        if state.get("pending_questions"):
            return answer(
                "ask_user",
                "Resolve pending choices or missing facts; the agent writes the revision.",
            )
        if state.get("pending_experiments"):
            return answer(
                "await_evidence",
                "A required experiment cannot be replaced by rewritten prose.",
            )
        if version >= 3:
            return answer(
                "version_limit",
                "Three total versions reached; retain findings and choose a new scoped task explicitly.",
            )
        return answer(
            "iterate-to-v2" if has_critique or has_verdict else "stress-test-idea",
            "Generate the next revision from normalized findings."
            if has_critique or has_verdict
            else "Generate findings before revision.",
        )

    if (
        not has_doc
        and intent != "strategy"
        and not (intent == "auto" and "verdict" in types)
    ):
        return answer(
            "ask_document", "Provide idea material or a slug with an existing snapshot."
        )
    if intent == "stress_test":
        return answer(
            "stress-test-idea",
            "Explicit re-test takes precedence over stored verdicts.",
        )
    if intent == "evaluate":
        return answer(
            "evaluate-proposal-harsh",
            "Explicit evaluation takes precedence over stored stage.",
        )
    if intent == "strategy":
        return answer(
            "strategize-from-verdict"
            if has_verdict
            else "evaluate-proposal-harsh"
            if has_doc
            else "ask_document",
            "Strategy requires an assessment and its findings.",
        )
    if intent == "revise":
        return revise()
    if "verdict" in types:
        return answer(
            "strategize-from-verdict",
            "Typed verdict input selects strategy; path count does not determine intent.",
        )
    if state.get("pending_questions"):
        return answer(
            "ask_user",
            "Pending consequential choices or missing facts require user input.",
        )
    if state.get("pending_experiments"):
        return answer(
            "await_evidence",
            "Pending empirical evidence stops automatic text iteration.",
        )
    if stage == "revision" and not has_verdict:
        return answer(
            "evaluate-proposal-harsh", "Evaluate the generated current revision."
        )
    if stage == "strategy" and state.get("can_revise", False):
        return revise()
    if has_verdict:
        if state.get("assessment_status") == "incomplete_coverage":
            return answer(
                "stop",
                "Restore missing review coverage before explicitly reevaluating.",
            )
        if state.get("assessment_status") == "insufficient_evidence":
            return answer(
                "await_evidence",
                "Resolve the assessment's evidence gaps before another automatic pass.",
            )
        if (
            state.get("verdict") in ("Proceed with caution", "Pivot", "Skip")
            and loop
            and state.get("can_revise", False)
        ):
            return revise()
        return answer(
            "stop",
            "Assessment completed; strategy or another review requires explicit intent.",
        )
    if has_critique:
        return revise()
    if loop or state.get("has_document", False):
        return answer(
            "stress-test-idea", "Start or resume the review from its snapshot."
        )
    return answer(
        "ask_intent",
        "Choose critique, an agent-written revision, or a decision assessment.",
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


def review_model_coverage(expected_roles, protocol, *, required_roles=AXES):
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
        "verdict",
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
