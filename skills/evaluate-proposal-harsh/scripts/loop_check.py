#!/usr/bin/env python3
"""Pre-dispatch loop check for evaluate-proposal-harsh.

Reads ./.autopsy/<slug>/state.json and refuses a re-run that cannot move the
verdict: the previous run's driving Critical is still quoted verbatim in the
doc (nothing was edited in its scope), or the rule has already been overridden
once on this slug.

Exit codes: 0 proceed, 2 stop and name the decision, 3 no override this run.

    python3 loop_check.py --slug <slug> [--doc <path>] [--since <git-ref>]
    python3 loop_check.py --self-test
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

HARSH = "evaluate-proposal-harsh"


def _norm(s):
    """Whitespace-insensitive, so a reflowed markdown line still matches."""
    return " ".join(s.split())


def _view(entry, block=None):
    """One run's fields. The top-level verdict block describes the LATEST run
    only, so it is passed as a fallback for that entry and no other."""
    v = dict(block or {})
    v.update({k: val for k, val in entry.items() if val is not None})
    v.setdefault("verdict", v.get("result"))
    return v


def _unchanged_since(ref, doc, root="."):
    try:
        return (
            subprocess.run(
                ["git", "diff", "--quiet", ref, "--", doc],
                cwd=root,
                capture_output=True,
            ).returncode
            == 0
        )
    except OSError:
        return False


def check(slug, doc=None, since=None, root="."):
    """Return (exit_code, message)."""
    path = os.path.join(root, ".autopsy", slug, "state.json")
    if not os.path.exists(path):
        return 0, "first run: no state at %s" % path

    with open(path, encoding="utf-8") as f:
        state = json.load(f)

    prior = [h for h in state.get("history", []) if h.get("skill") == HARSH]
    if not prior:
        return 0, "first run: no prior %s run for slug %r" % (HARSH, slug)

    views = [_view(e) for e in prior[:-1]] + [_view(prior[-1], state.get("verdict"))]
    n = len(views)
    last = views[-1]
    crit = last.get("driving_critical")
    anchor = last.get("driving_critical_anchor")

    if not crit or not anchor:
        return 0, (
            "WARNING: run %d predates driving_critical_anchor; loop check skipped. "
            "Record driving_critical, driving_critical_anchor, rule_output and "
            "verdict in the verdict block this run." % n
        )

    if doc and os.path.exists(doc):
        with open(doc, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if _norm(anchor) in _norm(text):
            extra = ""
            if since and _unchanged_since(since, doc, root):
                extra = " (%s is unchanged since %s)" % (doc, since)
            return 2, (
                'BLOCK: driving Critical "%s" untouched since run %d; the doc still '
                'says: "%s".%s Name the decision the founder owes instead of '
                "re-running." % (crit, n, anchor, extra)
            )

    # ponytail: "same direction" can only mean "this slug was already softened",
    # since this run's own rule output does not exist yet. Most recent override wins.
    for i in range(n - 1, -1, -1):
        rule_output, verdict = views[i].get("rule_output"), views[i].get("verdict")
        if rule_output and verdict and rule_output != verdict:
            return 3, (
                "OVERRIDE CAP: rule was overridden %s->%s on run %d; report the "
                "rule's output this time." % (rule_output, verdict, i + 1)
            )

    return 0, "prior verdicts: %s" % ", ".join(
        "run %d %s" % (i + 1, v.get("verdict") or "?") for i, v in enumerate(views)
    )


def _self_test():
    entry = lambda **kw: dict(
        {
            "ts": "2026-01-01T00:00:00Z",
            "skill": HARSH,
            "version": "v1",
            "output": "v1-verdict.md",
        },
        **kw,
    )

    with tempfile.TemporaryDirectory() as root:
        doc = os.path.join(root, "doc.md")
        state_dir = os.path.join(root, ".autopsy", "s")
        os.makedirs(state_dir)
        state_path = os.path.join(state_dir, "state.json")

        def write(
            history, verdict=None, text="intro\nno revenue arrives before month 30\nend"
        ):
            with open(state_path, "w") as f:
                json.dump(
                    {"slug": "s", "history": history, "verdict": verdict or {}}, f
                )
            with open(doc, "w") as f:
                f.write(text)

        anchored = {
            "driving_critical": "no revenue inside the horizon",
            "driving_critical_anchor": "no revenue arrives before month 30",
            "rule_output": "Skip",
            "verdict": "Skip",
        }

        # 1. first run — no state at all, then state with no harsh runs
        code, msg = check("s", doc, root=root)
        assert (code, msg.startswith("first run")) == (0, True), (code, msg)
        write([{"ts": "x", "skill": "stress-test-idea"}])
        code, msg = check("s", doc, root=root)
        assert (code, msg.startswith("first run")) == (0, True), (code, msg)

        # 2. prior run predates the anchor field
        write([entry(result="Skip")])
        code, msg = check("s", doc, root=root)
        assert code == 0 and msg.startswith("WARNING"), (code, msg)

        # 3. block: anchor still present verbatim (whitespace-insensitively)
        write(
            [entry(**anchored)], text="intro\nno revenue arrives\nbefore month 30\nend"
        )
        code, msg = check("s", doc, root=root)
        assert code == 2, (code, msg)
        assert "no revenue inside the horizon" in msg and "run 1" in msg, msg

        # 3b. anchor read from the top-level verdict block, not the history entry
        write([entry(result="Skip")], verdict=anchored)
        assert check("s", doc, root=root)[0] == 2

        # 4. pass: the anchored text was edited away
        write([entry(**anchored)], text="intro\nrevenue starts month 4\nend")
        code, msg = check("s", doc, root=root)
        assert code == 0 and msg == "prior verdicts: run 1 Skip", (code, msg)

        # 5. override cap: rule said Skip, verdict reported Pivot
        write([entry(**dict(anchored, verdict="Pivot"))], text="revenue starts month 4")
        code, msg = check("s", doc, root=root)
        assert code == 3, (code, msg)
        assert "Skip->Pivot on run 1" in msg, msg

        # 5b. an untouched anchor outranks the override cap
        write([entry(**dict(anchored, verdict="Pivot"))])
        assert check("s", doc, root=root)[0] == 2

        # 6. no --doc: anchor check is skipped, override cap still fires
        assert check("s", root=root)[0] == 3

    print("self-test: 10 assertions passed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slug")
    p.add_argument("--doc")
    p.add_argument("--since")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()

    if a.self_test:
        _self_test()
        return 0
    if not a.slug:
        p.error("--slug is required")

    code, msg = check(a.slug, a.doc, a.since)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
