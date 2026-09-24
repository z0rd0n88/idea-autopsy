#!/usr/bin/env python3
"""Locked, versioned idea-autopsy ledger using only the Python standard library.

CLI: state.py OPERATION --request FILE (or '-' for JSON stdin).
Python: execute(operation, request) -> {root, state}; status adds source_changed.
All requests identify slug and exactly one of source/project_dir. init snapshots
source as v1; pasted init needs project_dir and may optionally supply text.
snapshot and update require expected_generation. report/counts append under the
lock and optionally accept that precondition. Existing snapshots/reports never
change. An interrupted artifact transaction leaves .transaction.json; all normal
operations stop until explicit recover validates hashes and completes its intent.
Legacy import preserves raw state and artifacts without trusting old assessments.

This is a single-host filesystem ledger. flock coordinates cooperating local
processes; it is not a distributed branch merge protocol. Never hand-merge JSON.
No operation edits the source document or deletes historical artifacts.
"""

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import uuid

_POLICY_SPEC = importlib.util.spec_from_file_location(
    "autopsy_state_policy", Path(__file__).with_name("policy.py")
)
policy = importlib.util.module_from_spec(_POLICY_SPEC)
_POLICY_SPEC.loader.exec_module(policy)

SCHEMA_VERSION = 2
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
VERSION = re.compile(r"v[1-9][0-9]*\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
KINDS = {
    "stress_test",
    "revision",
    "evaluation",
    "strategy",
    "validation",
    "review_copy",
}
PATCH_FIELDS = {
    "investment_context",
    "decisions",
    "questions",
    "findings",
    "experiments",
}
ASSESSMENTS = {"complete", "insufficient_evidence", "incomplete_coverage"}
VERDICTS = {"Invest", "Proceed with caution", "Pivot", "Skip"}
REQUEST_FIELDS = {
    "init": {"text", "investment_context"},
    "status": set(),
    "snapshot": {"version", "parent_version", "file", "text", "expected_generation"},
    "report": {
        "version",
        "kind",
        "file",
        "text",
        "result",
        "input_report_ids",
        "input_sha256",
        "expected_generation",
    },
    "update": {"patch", "expected_generation"},
    "counts": {"version", "file", "expected_generation"},
    "import-legacy": {"text", "acknowledge_untrusted"},
    "recover": set(),
}


class StateError(ValueError):
    """An actionable ledger/operation error, displayed without a CLI traceback."""


def require(condition, message):
    if not condition:
        raise StateError(message)


def string(value, label):
    require(
        isinstance(value, str) and bool(value.strip()),
        f"{label} must be a nonempty string",
    )
    return value


def enum(value, allowed, label):
    require(isinstance(value, str) and value in allowed, f"invalid {label}: {value!r}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hash_value(value, label):
    require(
        isinstance(value, str) and HASH.fullmatch(value),
        f"{label} must be a lowercase SHA256",
    )


def version_value(value):
    require(
        isinstance(value, str) and VERSION.fullmatch(value),
        "version must be v followed by a positive integer",
    )


def json_value(value, label="value"):
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float:
        require(math.isfinite(value), f"{label} contains a non-finite number")
    elif isinstance(value, list):
        for item in value:
            json_value(item, label)
    elif isinstance(value, dict):
        require(
            all(isinstance(key, str) for key in value), f"{label} keys must be strings"
        )
        for item in value.values():
            json_value(item, label)
    else:
        raise StateError(f"{label} must contain only JSON values")


def string_list(value, label):
    require(isinstance(value, list), f"{label} must be a list")
    for item in value:
        string(item, label)
    require(len(value) == len(set(value)), f"{label} must not contain duplicates")


def records(value, label):
    require(isinstance(value, list), f"{label} must be a list")
    ids = []
    for item in value:
        require(isinstance(item, dict), f"{label} entries must be objects")
        ids.append(string(item.get("id"), f"{label}.id"))
    require(len(ids) == len(set(ids)), f"{label} IDs must be unique")
    return value


def validate_findings(value):
    enums = {
        "kind": {"contradiction", "missing_evidence", "risk", "question"},
        "severity": {"Critical", "High", "Medium"},
        "origin": {"document", "user", "reviewer", "external"},
        "doc_support": {"supported", "refuted", "not_established"},
        "external_status": {"not_checked", "verified", "contradicted", "unverifiable"},
        "confidence": {"high", "medium", "low"},
        "status": {"active", "refuted", "resolved"},
        "resolution": {
            "unresolved",
            "claim_removed",
            "scope_changed",
            "evidence_obtained",
            "resolved",
        },
        "bucket": {
            "consensus",
            "unique_real",
            "unique_unrated",
            "unique_reach",
            "speculative",
            "verdict",
            "unknown",
        },
        "evidence_basis": {"document_logic", "external_fact", "user_report"},
    }
    for finding in records(value, "findings"):
        for field in ("issue_id", "statement", "severity_reason"):
            string(finding.get(field), "finding." + field)
        for field, choices in enums.items():
            enum(finding.get(field), choices, "finding." + field)
        for field in ("assumption_ids", "axes"):
            string_list(finding.get(field), "finding." + field)
        require(
            set(finding["axes"]) <= {"critical_thinking", "feasibility", "risk", "roi"},
            "finding.axes contains an unknown axis",
        )
        for field in ("affects_decision", "thesis_breaking"):
            require(
                type(finding.get(field)) is bool,
                "finding." + field + " must be boolean",
            )
        require(
            "plausibly_resolvable" in finding
            and (
                finding["plausibly_resolvable"] is None
                or type(finding["plausibly_resolvable"]) is bool
            ),
            "finding.plausibly_resolvable must be boolean or null",
        )
        require(
            isinstance(finding.get("sources"), list), "finding.sources must be a list"
        )
        for source in finding["sources"]:
            require(isinstance(source, dict), "finding source must be an object")
            enum(
                source.get("type"),
                {"document", "user", "external", "calculation", "critique"},
                "finding source.type",
            )
            for field in ("type", "ref", "quote"):
                string(source.get(field), f"finding source.{field}")
        if "member_ids" in finding:
            string_list(finding["member_ids"], "finding.member_ids")
            require(
                finding["id"] in finding["member_ids"],
                "finding.member_ids must contain its id",
            )
        require(
            not (
                finding["status"] == "resolved"
                and finding["resolution"] in {"claim_removed", "unresolved"}
            ),
            "removing a claim or leaving a risk unresolved cannot resolve a finding",
        )


def validate_working_fields(state):
    require(
        isinstance(state.get("investment_context"), dict),
        "investment_context must be an object",
    )
    for decision in records(state.get("decisions"), "decisions"):
        hash_value(decision.get("change_id"), "decision.change_id")
        string(decision.get("choice"), "decision.choice")
        require(
            type(decision.get("approved")) is bool, "decision.approved must be boolean"
        )
        require(decision.get("source") == "user", "decision.source must be user")
    for question in records(state.get("questions"), "questions"):
        hash_value(question.get("change_id"), "question.change_id")
        string(question.get("prompt"), "question.prompt")
        enum(question.get("status"), {"pending", "answered"}, "question.status")
        if question["status"] == "answered":
            string(question.get("answer"), "answered question.answer")
        else:
            require(
                question.get("answer") is None,
                "pending question cannot already contain an answer",
            )
    for experiment in records(state.get("experiments"), "experiments"):
        string(experiment.get("hypothesis"), "experiment.hypothesis")
        enum(
            experiment.get("status"),
            {"proposed", "approved", "running", "complete", "failed"},
            "experiment.status",
        )
    validate_findings(state.get("findings"))


def relative_path(value):
    string(value, "artifact.path")
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and "\\" not in value
        and all(part not in (".", "..") for part in value.split("/"))
        and "" not in value.split("/"),
        "artifact path must be a safe relative path",
    )
    return path


def owned_path(root, relative, allow_recovery_link=False):
    relative_path(relative)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        require(
            not current.is_symlink(), f"state paths must not be symlinks: {current}"
        )
    require(
        current.resolve().is_relative_to(root.resolve()),
        "artifact path escapes state directory",
    )
    if current.exists() and current.is_file() and not allow_recovery_link:
        require(
            current.stat().st_nlink == 1,
            f"state file must not be a hardlink: {current}",
        )
    return current


def validate_state(state):
    require(isinstance(state, dict), "state must be an object")
    require(
        type(state.get("schema_version")) is int
        and state["schema_version"] == SCHEMA_VERSION,
        "legacy/unknown state schema; use explicit import-legacy, never silently migrate",
    )
    json_value(state, "state")
    require(
        isinstance(state.get("slug"), str) and NAME.fullmatch(state["slug"]),
        "invalid state slug",
    )
    require(
        type(state.get("generation")) is int and state["generation"] >= 1,
        "generation must be a positive integer",
    )
    source = state.get("source")
    require(isinstance(source, dict), "source must be an object")
    require({"path", "sha256"} <= set(source), "source requires path and sha256 fields")
    require(
        source.get("path") is None
        or (isinstance(source["path"], str) and Path(source["path"]).is_absolute()),
        "source.path must be absolute or null",
    )
    if source.get("sha256") is not None:
        hash_value(source["sha256"], "source.sha256")
    versions = state.get("versions")
    require(isinstance(versions, dict), "versions must be an object")
    for version, artifact in versions.items():
        version_value(version)
        validate_artifact(artifact)
        require(
            artifact["path"] == f"versions/{version}.md",
            "snapshot path does not match its version",
        )
        parent = artifact.get("parent_version")
        require(
            parent is None or parent in versions,
            "snapshot parent must reference an existing version",
        )
        if parent is not None:
            require(
                int(parent[1:]) < int(version[1:]),
                "snapshot parent must precede its version",
            )
    current = state.get("current_version")
    require(
        (not versions and current is None)
        or (isinstance(current, str) and current in versions),
        "current_version must reference an existing snapshot",
    )
    if versions:
        ordered = sorted(versions, key=lambda value: int(value[1:]))
        require(
            ordered == [f"v{number}" for number in range(1, len(ordered) + 1)],
            "snapshot versions must be contiguous from v1",
        )
        require(current == ordered[-1], "current_version must be the latest snapshot")
        require(
            source["sha256"] in {item["sha256"] for item in versions.values()},
            "source hash must identify a captured snapshot",
        )
        for index, version in enumerate(ordered):
            require(
                versions[version].get("parent_version")
                == (ordered[index - 1] if index else None),
                "snapshot lineage must follow the preceding version",
            )
    reports = records(state.get("reports"), "reports")
    seen_ids = set()
    for report in reports:
        validate_artifact(report)
        enum(report.get("kind"), KINDS, "report.kind")
        require(
            report.get("version") in versions,
            "report.version must reference a snapshot",
        )
        require(
            report.get("input_sha256") == versions[report["version"]]["sha256"],
            "report input hash must match its version",
        )
        require(
            report["path"]
            == f"reports/{report['version']}-{report['kind']}-{report['id']}.md",
            "report path does not match its identity",
        )
        string_list(report.get("input_report_ids"), "report.input_report_ids")
        require(
            set(report["input_report_ids"]) <= seen_ids,
            "report inputs must reference earlier reports",
        )
        require(
            isinstance(report.get("result"), dict), "report.result must be an object"
        )
        validate_result(report["result"])
        seen_ids.add(report["id"])
    counts = state.get("word_counts")
    require(isinstance(counts, dict), "word_counts must be an object")
    for version, record in counts.items():
        require(
            version in versions and isinstance(record, dict),
            "word count must reference an existing snapshot",
        )
        require(
            record.get("sha256") == versions[version]["sha256"],
            "word count hash must match its snapshot",
        )
        require(
            type(record.get("words")) is int and record["words"] >= 0,
            "words must be a nonnegative integer",
        )
    validate_working_fields(state)
    history = records(state.get("history"), "history")
    require(len(history) == state["generation"], "history length must match generation")
    for generation, event in enumerate(history, 1):
        require(
            event.get("generation") == generation,
            "history generations must be contiguous",
        )
        string(event.get("operation"), "history.operation")
        string(event.get("at"), "history.at")
        require(
            isinstance(event.get("details"), dict), "history.details must be an object"
        )
    require(
        isinstance(state.get("legacy_backups", []), list),
        "legacy_backups must be a list",
    )
    for artifact in state.get("legacy_backups", []):
        validate_artifact(artifact)
        require(
            artifact["path"].startswith("legacy/"),
            "legacy backup path must be under legacy/",
        )
    return state


def validate_artifact(artifact):
    require(isinstance(artifact, dict), "artifact must be an object")
    relative_path(artifact.get("path"))
    hash_value(artifact.get("sha256"), "artifact.sha256")
    string(artifact.get("created_at"), "artifact.created_at")


def validate_result(result):
    if "assessment_status" in result:
        enum(result["assessment_status"], ASSESSMENTS, "assessment_status")
    if result.get("verdict") is not None:
        enum(result["verdict"], VERDICTS, "verdict")
        require(
            result.get("assessment_status") == "complete",
            "a verdict requires a complete assessment",
        )
    if "findings" in result:
        validate_findings(result["findings"])
    if "review_protocol" in result:
        try:
            roles = policy.review_model_roles(result["review_protocol"])
        except policy.PolicyError as exc:
            raise StateError(str(exc)) from exc
        if any(role["mandatory"] and not role["policy_compliant"] for role in roles):
            require(
                result.get("assessment_status") in (None, "incomplete_coverage")
                and result.get("verdict") is None,
                "mandatory model gap requires incomplete coverage and no verdict",
            )


def canonical_root(request):
    slug = request.get("slug")
    require(
        isinstance(slug, str) and NAME.fullmatch(slug),
        "slug must use lowercase letters, digits and hyphens (max 80)",
    )
    require(
        ("source" in request) != ("project_dir" in request),
        "provide exactly one of source or project_dir",
    )
    key = "source" if "source" in request else "project_dir"
    raw = Path(string(request[key], key))
    require(raw.is_absolute(), f"{key} must be an absolute path")
    path = raw.resolve(strict=True)
    if key == "source":
        require(path.is_file(), "source must be a file")
        for parent in path.parents:
            if parent.parent.name == ".autopsy":
                require(
                    parent.name == slug, "source belongs to a different .autopsy slug"
                )
                base = parent.parent.parent
                break
        else:
            base = path.parent
    else:
        require(path.is_dir(), "project_dir must be a directory")
        base = path
    root = base / ".autopsy" / slug
    require(
        not (base / ".autopsy").is_symlink() and not root.is_symlink(),
        "state root must not be a symlink",
    )
    return root


def _bytes(request):
    require(
        ("file" in request) != ("text" in request),
        "provide exactly one of file or text",
    )
    if "file" in request:
        path = Path(string(request["file"], "file"))
        require(path.is_absolute(), "file must be absolute")
        data = path.read_bytes()
    else:
        require(isinstance(request["text"], str), "text must be a string")
        data = request["text"].encode("utf-8")
    data.decode("utf-8")
    return data


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(data):
    return (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def _read(path):
    return json.loads(path.read_bytes().decode("utf-8"))


def _sync(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic(path, data):
    """Unique same-directory temporary plus fsync/replace; caller holds lock."""
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _artifacts(state):
    return (
        list(state["versions"].values())
        + state["reports"]
        + state.get("legacy_backups", [])
    )


def _verify(root, state):
    for artifact in _artifacts(state):
        path = owned_path(root, artifact["path"])
        require(path.is_file(), f"missing immutable artifact: {path}")
        require(
            digest(path.read_bytes()) == artifact["sha256"],
            f"immutable artifact changed: {path}",
        )


def _load(root):
    path = owned_path(root, "state.json")
    require(path.exists(), "state is not initialized; run init explicitly")
    state = validate_state(_read(path))
    require(state["slug"] == root.name, "state slug does not match its directory")
    _verify(root, state)
    return state


def _check_source(root, state, request):
    if "source" in request:
        supplied = str(Path(request["source"]).resolve())
        registered = {state["source"]["path"]} | {
            str((root / artifact["path"]).resolve()) for artifact in _artifacts(state)
        }
        require(
            supplied in registered,
            "source does not belong to this slug; use its registered source, snapshot/report, or an explicit project_dir lookup",
        )


def _advance(state, operation, details=None):
    state["generation"] += 1
    state["history"].append(
        {
            "id": uuid.uuid4().hex,
            "at": _now(),
            "operation": operation,
            "generation": state["generation"],
            "details": details or {},
        }
    )


def _fresh(slug, source_path=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "generation": 0,
        "source": {"path": source_path, "sha256": None},
        "current_version": None,
        "versions": {},
        "reports": [],
        "word_counts": {},
        "investment_context": {},
        "decisions": [],
        "questions": [],
        "findings": [],
        "experiments": [],
        "history": [],
    }


def _snapshot(state, version, data, parent):
    version_value(version)
    require(
        version not in state["versions"],
        f"snapshot {version} already exists and is immutable",
    )
    expected = (
        f"v{int(state['current_version'][1:]) + 1}"
        if state["current_version"]
        else "v1"
    )
    require(version == expected, f"next snapshot must be {expected}")
    require(
        parent == state["current_version"],
        "parent_version must be the current version (null for v1)",
    )
    if parent is not None:
        require(
            digest(data) != state["versions"][parent]["sha256"],
            "snapshot is identical to its parent; do not consume a version without a change",
        )
    artifact = {
        "path": f"versions/{version}.md",
        "sha256": digest(data),
        "created_at": _now(),
        "parent_version": parent,
    }
    state["versions"][version] = artifact
    state["current_version"] = version
    if state["source"]["sha256"] is None:
        state["source"]["sha256"] = artifact["sha256"]
    # Findings describe one version; the previous report remains authoritative.
    state["findings"] = []
    return artifact["path"], data


def _commit(root, state, files, previous_raw):
    """Write durable intent before publishing new artifacts, then advance ledger."""
    validate_state(state)
    journal_path = owned_path(root, ".transaction.json")
    require(
        not journal_path.exists(), "pending transaction exists; run recover explicitly"
    )
    staged = []
    for relative, data in files:
        destination = owned_path(root, relative)
        require(
            not destination.exists(),
            f"immutable destination already exists: {relative}",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_relative = ".pending-" + uuid.uuid4().hex
        temporary = owned_path(root, temporary_relative)
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        staged.append(
            {
                "path": relative,
                "staged_path": temporary_relative,
                "sha256": digest(data),
            }
        )
    # A crash before this point can leave unreferenced .pending-* files. They are
    # harmless; preserve them for manual inspection, never guess a transaction.
    journal = {
        "previous_sha256": digest(previous_raw) if previous_raw is not None else None,
        "state": state,
        "artifacts": staged,
    }
    _atomic(journal_path, _json(journal))
    _finish(root, journal)


def _finish(root, journal):
    require(isinstance(journal, dict), "transaction must be an object")
    state = validate_state(journal.get("state"))
    require(state["slug"] == root.name, "transaction slug does not match its directory")
    state_path = owned_path(root, "state.json")
    current_raw = state_path.read_bytes() if state_path.exists() else None
    already_committed = current_raw == _json(state)
    require(
        already_committed
        or (digest(current_raw) if current_raw is not None else None)
        == journal.get("previous_sha256"),
        "ledger changed since pending transaction; preserve files and reconcile explicitly",
    )
    entries = journal.get("artifacts")
    require(isinstance(entries, list), "transaction artifacts must be a list")
    expected_files = {item["path"]: item["sha256"] for item in _artifacts(state)}
    for item in entries:
        require(isinstance(item, dict), "transaction artifact must be an object")
        require(
            item.get("path") in expected_files
            and item.get("sha256") == expected_files[item["path"]],
            "transaction artifact not present in candidate ledger",
        )
        staged_name = item.get("staged_path")
        require(
            isinstance(staged_name, str)
            and re.fullmatch(r"\.pending-[0-9a-f]{32}", staged_name),
            "invalid staged artifact path",
        )
        destination, staged = (
            owned_path(root, item["path"], allow_recovery_link=True),
            owned_path(root, staged_name, allow_recovery_link=True),
        )
        for candidate in (destination, staged):
            if candidate.exists() and candidate.stat().st_nlink > 1:
                require(
                    candidate.stat().st_nlink == 2
                    and destination.exists()
                    and staged.exists()
                    and os.path.samefile(destination, staged),
                    "pending artifact has an unexpected hardlink",
                )
        if not destination.exists():
            require(
                staged.is_file() and digest(staged.read_bytes()) == item["sha256"],
                "pending artifact is missing or corrupt; preserve transaction for inspection",
            )
            os.link(staged, destination)  # exclusive publication, never overwrite
            staged.unlink()
            _sync(destination.parent)
        else:
            # A crash between link and unlink leaves exactly these two links.
            if staged.exists() and os.path.samefile(destination, staged):
                staged.unlink()
            require(
                digest(destination.read_bytes()) == item["sha256"],
                "published artifact hash differs from transaction",
            )
        staged.unlink(missing_ok=True)
    _verify(root, state)
    if not already_committed:
        _atomic(state_path, _json(state))
    owned_path(root, ".transaction.json").unlink()
    _sync(root)
    return state


def _legacy(root, request):
    state_path = owned_path(root, "state.json")
    require(
        state_path.is_file(), "import-legacy requires an existing legacy state.json"
    )
    raw = state_path.read_bytes()
    legacy = json.loads(raw.decode("utf-8"))
    require(
        isinstance(legacy, dict) and legacy.get("schema_version") != SCHEMA_VERSION,
        "state is not a legacy object",
    )
    require(
        request.get("acknowledge_untrusted") is True,
        "import-legacy requires acknowledge_untrusted:true",
    )
    state = _fresh(
        root.name,
        str(Path(request["source"]).resolve()) if "source" in request else None,
    )
    stamp = _now()
    backup = {
        "path": f"legacy/state-{uuid.uuid4().hex}.json",
        "sha256": digest(raw),
        "created_at": stamp,
    }
    state["legacy_backups"] = [backup]
    files = [(backup["path"], raw)]
    # Caller selects source explicitly; legacy current_version/verdict/counts are
    # not reliable enough to promote. Existing loose artifacts remain untouched.
    if "source" in request:
        files.append(_snapshot(state, "v1", Path(request["source"]).read_bytes(), None))
    elif "text" in request:
        files.append(_snapshot(state, "v1", _bytes({"text": request["text"]}), None))
    _advance(
        state,
        "import-legacy",
        {
            "backup": backup["path"],
            "trusted": False,
            "note": "Legacy context, findings, counts and verdicts require explicit revalidation.",
        },
    )
    return state, files, raw


def execute(operation, request):
    require(isinstance(request, dict), "request must be a JSON object")
    json_value(request, "request")
    enum(
        operation,
        {
            "init",
            "status",
            "snapshot",
            "report",
            "update",
            "counts",
            "import-legacy",
            "recover",
        },
        "operation",
    )
    allowed = REQUEST_FIELDS[operation] | {"slug", "source", "project_dir"}
    require(
        set(request) <= allowed,
        f"unknown {operation} request fields: {sorted(set(request) - allowed)}",
    )
    root = canonical_root(request)
    if operation == "init":
        root.mkdir(parents=True, exist_ok=True)
    require(root.is_dir(), "state directory is not initialized; run init explicitly")
    lock_path = owned_path(root, ".lock")
    if operation == "status":
        require(
            lock_path.is_file(),
            "state lock is missing; legacy state requires explicit import-legacy; status creates no files",
        )
    descriptor = os.open(
        lock_path,
        os.O_NOFOLLOW
        | (os.O_RDONLY if operation == "status" else os.O_RDWR | os.O_CREAT),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "r" if operation == "status" else "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH if operation == "status" else fcntl.LOCK_EX)
            require(
                os.fstat(lock.fileno()).st_nlink == 1,
                "state lock must not be a hardlink",
            )
            journal_path = owned_path(root, ".transaction.json")
            if operation == "recover":
                require(journal_path.is_file(), "no pending transaction to recover")
                journal = _read(journal_path)
                require(isinstance(journal, dict), "transaction must be an object")
                _check_source(root, validate_state(journal.get("state")), request)
                return {"root": str(root), "state": _finish(root, journal)}
            require(
                not journal_path.exists(),
                "pending transaction detected; run recover explicitly before continuing",
            )
            state_path = owned_path(root, "state.json")
            if operation == "init":
                require(
                    not state_path.exists(),
                    "state already exists; use status or explicit import-legacy",
                )
                state = _fresh(
                    root.name,
                    str(Path(request["source"]).resolve())
                    if "source" in request
                    else None,
                )
                state["investment_context"] = copy.deepcopy(
                    request.get("investment_context", {})
                )
                files = []
                if "source" in request:
                    require(
                        "text" not in request,
                        "init source and pasted text are mutually exclusive",
                    )
                    data = Path(request["source"]).read_bytes()
                    data.decode("utf-8")
                    files.append(_snapshot(state, "v1", data, None))
                elif "text" in request:
                    files.append(
                        _snapshot(state, "v1", _bytes({"text": request["text"]}), None)
                    )
                _advance(
                    state,
                    "init",
                    {"investment_context": copy.deepcopy(state["investment_context"])},
                )
                _commit(root, state, files, None)
                return {"root": str(root), "state": state}
            if operation == "import-legacy":
                state, files, previous_raw = _legacy(root, request)
                _commit(root, state, files, previous_raw)
                return {"root": str(root), "state": state}
            state = _load(root)
            _check_source(root, state, request)
            if operation == "status":
                original = state["source"]["path"]
                changed = (
                    None
                    if original is None
                    else (
                        not Path(original).is_file()
                        or digest(Path(original).read_bytes())
                        != state["source"]["sha256"]
                    )
                )
                return {"root": str(root), "state": state, "source_changed": changed}
            if operation in {"snapshot", "update"}:
                require(
                    "expected_generation" in request,
                    f"{operation} requires expected_generation from status",
                )
            if "expected_generation" in request:
                require(
                    type(request["expected_generation"]) is int
                    and request["expected_generation"] == state["generation"],
                    "generation conflict; reload status and reconsider the change before retrying",
                )
            files, details = [], {}
            if operation == "snapshot":
                version = request.get("version")
                files.append(
                    _snapshot(
                        state, version, _bytes(request), request.get("parent_version")
                    )
                )
                details["version"] = version
                if (
                    "file" in request
                    and str(Path(request["file"]).resolve()) == state["source"]["path"]
                ):
                    state["source"]["sha256"] = state["versions"][version]["sha256"]
            elif operation == "report":
                version, kind = request.get("version"), request.get("kind")
                require(
                    version in state["versions"],
                    "report version must reference an immutable snapshot",
                )
                enum(kind, KINDS, "report.kind")
                if "input_sha256" in request:
                    require(
                        request["input_sha256"] == state["versions"][version]["sha256"],
                        "stale report input hash",
                    )
                data, report_id = _bytes(request), uuid.uuid4().hex
                relative = f"reports/{version}-{kind}-{report_id}.md"
                report = {
                    "id": report_id,
                    "kind": kind,
                    "version": version,
                    "path": relative,
                    "sha256": digest(data),
                    "input_sha256": state["versions"][version]["sha256"],
                    "created_at": _now(),
                    "input_report_ids": request.get("input_report_ids", []),
                    "result": copy.deepcopy(request.get("result", {})),
                }
                state["reports"].append(report)
                files.append((relative, data))
                details["report_id"] = report_id
            elif operation == "update":
                patch = request.get("patch")
                require(
                    isinstance(patch, dict) and patch and set(patch) <= PATCH_FIELDS,
                    "patch must contain only investment_context, decisions, questions, findings, experiments",
                )
                details["changes"] = {
                    field: {
                        "before": copy.deepcopy(state[field]),
                        "after": copy.deepcopy(value),
                    }
                    for field, value in patch.items()
                }
                state.update(copy.deepcopy(patch))
            elif operation == "counts":
                from wordcount import count

                version = request.get("version", state["current_version"])
                require(
                    version in state["versions"],
                    "count version must reference an immutable snapshot",
                )
                artifact = state["versions"][version]
                if "file" in request:
                    require(
                        digest(Path(request["file"]).read_bytes())
                        == artifact["sha256"],
                        "source changed; create a new snapshot before recording a count",
                    )
                state["word_counts"][version] = {
                    "sha256": artifact["sha256"],
                    "words": count(owned_path(root, artifact["path"])),
                }
                details["version"] = version
            _advance(state, operation, details)
            _commit(root, state, files, state_path.read_bytes())
            return {"root": str(root), "state": state}
    except OSError:
        # The OS releases flock when the descriptor/context closes. Durable
        # journals remain intact for explicit recovery after publication failures.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=[
            "init",
            "status",
            "snapshot",
            "report",
            "update",
            "counts",
            "import-legacy",
            "recover",
        ],
    )
    parser.add_argument(
        "--request", required=True, help="JSON request file, or - for stdin"
    )
    args = parser.parse_args(argv)
    try:
        request = (
            json.load(sys.stdin) if args.request == "-" else _read(Path(args.request))
        )
        print(json.dumps(execute(args.operation, request), indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"state: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
