#!/usr/bin/env python3
"""Shared word-count guard for the idea-autopsy skills.

The thresholds live in thresholds.json beside this file, so the review skills
and iterate-to-v2 read one set of numbers instead of each stating its own.
`record` records the count into ./.autopsy/<slug>/state.json and exits 1 if it
is over the refusal limit, so a v2 that outgrew the next stage's limit fails
here, when it is written, rather than one stage later. The count is kept even
when it is over the limit: a record of the oversized doc is the useful part.
The next stage reads the number from state.json instead of recounting.

The count is the reviewable count: fenced blocks, markup tokens (table
separator rows, pipes, heading and bullet markers) and whole sections a verdict
never turns on (explainers, revision logs, diagrams, UI flows, component specs,
motion, glossaries, appendices) are dropped first. `excerpt` writes that review
copy to a file with the dropped headings listed at the top, so reviewers read
what matters and the verdict says what they did not see.

    wordcount.py record --slug <slug> --version <vN> --file <path>
    wordcount.py check --file <path> [--combined <critique>]
    wordcount.py --self-test

Exit codes:
    0  ok, or a warn-level count
    1  over the refusal limit
    2  usage error, including a --slug or --version containing / \\ or ..
    3  a file named on the command line is missing or unreadable
    4  thresholds.json or state.json is unusable
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIRED_KEYS = (
    "review_refuse_words",
    "review_warn_words",
    "iterate_warn_combined",
    "iterate_refuse_combined",
)


def die(code, msg):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def load_thresholds(path=None):
    """Load thresholds.json and confirm it carries the four expected keys."""
    path = path or os.path.join(HERE, "thresholds.json")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            t = json.load(f)
    except OSError as e:
        die(4, "thresholds at %s is unreadable: %s" % (path, e))
    except ValueError:
        die(4, "thresholds at %s is not valid JSON; fix it" % path)
    missing = [k for k in REQUIRED_KEYS if not isinstance(t, dict) or k not in t]
    if missing:
        die(4, "thresholds at %s is missing: %s" % (path, ", ".join(missing)))
    return t


T = load_thresholds()


def strip_fences(text):
    """Drop fenced blocks (``` and ~~~) so only prose is counted."""
    out = []
    fence = None
    for line in text.splitlines():
        stripped = line.strip()
        if fence is None:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence = stripped[:3]
                continue
            out.append(line)
        elif stripped.startswith(fence):
            fence = None
    return "\n".join(out)


def read_doc(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        die(3, "cannot read %s: %s" % (path, e.strerror or e))


def reviewable(path):
    """Return (kept_text, dropped_headings, word_count) for the review copy."""
    kept, dropped = strip_sections(strip_fences(read_doc(path)))
    return kept, dropped, len(strip_markup(kept).split())


def count(path):
    return reviewable(path)[2]


def excerpt(path, out):
    """Write the review copy: the doc minus dropped sections, headed by the
    list of what was dropped so the verdict can name it."""
    kept, dropped, n = reviewable(path)
    head = "<!-- review excerpt of %s: %d reviewable words; dropped sections: %s -->\n\n" % (
        os.path.basename(path), n, "; ".join(dropped) or "none")
    with open(out, "w", encoding="utf-8") as f:
        f.write(head + kept)
    return dropped, n


SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-{2,}[-:|\s]*$")
LINE_MARKER = re.compile(r"^\s*(#{1,6}|[-*+]|\d+[.)])\s+")


DROP_SECTIONS = re.compile(
    r"(explain like|eli5|revision log|changelog|change log|in pictures|diagram|"
    r"wirefram|mockup|user flow|user journey|trust journey|screens?\b|component spec|"
    r"motion|haptic|animation|glossary|table of contents|appendix|acknowledg|"
    r"faq|frequently asked)",
    re.I,
)


def strip_sections(text):
    """Drop whole sections whose heading names review-irrelevant material
    (explainers, revision logs, diagrams, UI flows, component specs, motion,
    glossaries, appendices). A verdict never turns on these, so reviewers
    should not pay to read them. Returns (kept_text, dropped_headings)."""
    out, dropped, skip_level = [], [], None
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and DROP_SECTIONS.search(m.group(2)):
                skip_level = level
                dropped.append(m.group(2).strip())
                continue
        if skip_level is None:
            out.append(line)
    return "\n".join(out) + "\n", dropped


def strip_markup(text):
    """Drop tokens that are markup, not words: table separator rows, pipe
    characters, and heading or bullet markers at line start. Table cell text,
    inline code and links stay, since a reviewer reads those."""
    out = []
    for line in text.splitlines():
        if SEPARATOR_ROW.match(line):
            continue
        line = LINE_MARKER.sub("", line, count=1)
        out.append(line.replace("|", " "))
    return "\n".join(out)


def check_name(label, value):
    """Keep record() writing inside ./.autopsy/<slug>/."""
    if "/" in value or "\\" in value or ".." in value:
        die(2, "%s may not contain / \\ or ..: %s" % (label, value))


def read_state(state_path):
    """Return the existing state dict, or {} if there is no file yet."""
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, encoding="utf-8", errors="replace") as f:
            state = json.load(f)
    except OSError as e:
        die(3, "cannot read %s: %s" % (state_path, e.strerror or e))
    except ValueError:
        state = None
    if not isinstance(state, dict):
        die(
            4, "state.json at %s is not a JSON object; fix it or delete it" % state_path
        )
    return state


def verdict(n, refuse_key, warn_key):
    """Return (message, over_refuse_limit)."""
    if n > T[refuse_key]:
        return "OVER %s (%d)" % (refuse_key, T[refuse_key]), True
    if n > T[warn_key]:
        return "over %s (%d)" % (warn_key, T[warn_key]), False
    return "ok", False


def record(slug, version, path, root="."):
    """Count path and store it as word_counts[version] in the slug's state.json."""
    check_name("--slug", slug)
    check_name("--version", version)
    n = count(path)
    state_path = os.path.join(root, ".autopsy", slug, "state.json")
    state = read_state(state_path)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    state.setdefault("word_counts", {})[version] = n
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, state_path)
    return n


def main(argv):
    p = argparse.ArgumentParser(prog="wordcount.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="count a doc and store it in state.json")
    r.add_argument("--slug", required=True)
    r.add_argument("--version", required=True)
    r.add_argument("--file", required=True)
    c = sub.add_parser("check", help="count a doc and print the verdict, no write")
    c.add_argument("--file", required=True)
    c.add_argument("--combined", help="second doc; verdict uses the iterate thresholds")
    e = sub.add_parser("excerpt", help="write the review copy with irrelevant sections dropped")
    e.add_argument("--file", required=True)
    e.add_argument("--out", required=True)
    a = p.parse_args(argv)

    if a.cmd == "excerpt":
        dropped, n = excerpt(a.file, a.out)
        print("%s: %d reviewable words; dropped %d section(s): %s" % (
            a.out, n, len(dropped), "; ".join(dropped) or "none"))
        return 0

    if a.cmd == "record":
        n = record(a.slug, a.version, a.file)
        msg, over = verdict(n, "review_refuse_words", "review_warn_words")
        print("%s: %d words (%s)" % (a.version, n, msg))
        return 1 if over else 0

    _, dropped, n = reviewable(a.file)
    if dropped:
        print("dropped from the count: %s" % "; ".join(dropped))
    if a.combined:
        print("%s: %d words" % (a.file, n))
        m = count(a.combined)
        print("%s: %d words" % (a.combined, m))
        msg, over = verdict(n + m, "iterate_refuse_combined", "iterate_warn_combined")
        print("combined: %d words (%s)" % (n + m, msg))
    else:
        msg, over = verdict(n, "review_refuse_words", "review_warn_words")
        print("%s: %d words (%s)" % (a.file, n, msg))
    return 1 if over else 0


def is_self_test(argv):
    """--self-test is a whole invocation, not a flag smuggled into another one."""
    return argv[:1] == ["--self-test"]


def self_test():
    import contextlib
    import io
    import tempfile

    def run(fn, *args):
        """Return (exit code or None, stdout) for fn(*args)."""
        out = io.StringIO()
        code = None
        try:
            with (
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                fn(*args)
        except SystemExit as e:
            code = e.code
        return code, out.getvalue()

    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "v2.md")
        state_path = os.path.join(d, ".autopsy", "demo", "state.json")

        # record creates word_counts
        with open(doc, "w") as f:
            f.write("word " * 30)
        assert record("demo", "v2", doc, d) == 30
        with open(state_path) as f:
            assert json.load(f)["word_counts"] == {"v2": 30}

        # fix 9: the temp file is replaced, not left behind
        assert not os.path.exists(state_path + ".tmp")

        # record preserves everything else already in state.json
        with open(state_path) as f:
            state = json.load(f)
        state["slug"] = "demo"
        state["history"] = [{"skill": "stress-test-idea"}]
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        with open(doc, "w") as f:
            f.write("word " * 40)
        record("demo", "v3", doc, d)
        with open(state_path) as f:
            state = json.load(f)
        assert state["slug"] == "demo"
        assert state["history"] == [{"skill": "stress-test-idea"}]
        assert state["word_counts"] == {"v2": 30, "v3": 40}

        # over the refuse limit exits 1
        big = os.path.join(d, "big.md")
        with open(big, "w") as f:
            f.write("word " * (T["review_refuse_words"] + 1))
        assert main(["check", "--file", big]) == 1
        assert main(["check", "--file", doc]) == 0

        # fix 10: fenced blocks are not counted
        fenced = os.path.join(d, "fenced.md")
        with open(fenced, "w") as f:
            f.write("one two\n```\nthree four five\n```\nsix\n~~~\nseven\n~~~\n")
        assert count(fenced) == 3

        # fix 12: non-UTF-8 bytes are replaced, not fatal
        binary = os.path.join(d, "binary.md")
        with open(binary, "wb") as f:
            f.write(b"alpha \xff\xfe beta\n")
        assert count(binary) == 3

        # fix 5: a missing file exits 3 with a message, no traceback
        assert run(count, os.path.join(d, "nope.md"))[0] == 3

        # fix 7: check --combined prints the first count before the second read fails
        code, out = run(
            main, ["check", "--file", doc, "--combined", os.path.join(d, "nope.md")]
        )
        assert code == 3 and "v2.md: 40 words" in out

        # fix 6: a traversing slug or version is refused before any write
        assert run(record, "../../x", "v2", doc, d)[0] == 2
        assert run(record, "demo", "../v2", doc, d)[0] == 2

        # fix 4: malformed, empty, and non-object state.json all exit 4 untouched
        for bad in ("{oops", "", "[1, 2]", "null"):
            with open(state_path, "w") as f:
                f.write(bad)
            assert run(record, "demo", "v4", doc, d)[0] == 4
            with open(state_path) as f:
                assert f.read() == bad

        # fix 13: thresholds.json missing an expected key exits 4
        bad_t = os.path.join(d, "thresholds.json")
        with open(bad_t, "w") as f:
            json.dump({"review_refuse_words": 1}, f)
        assert run(load_thresholds, bad_t)[0] == 4

        # fix 11: --self-test counts only as the first argument
        assert is_self_test(["--self-test"])
        assert not is_self_test(["check", "--file", doc, "--self-test"])

    sec = "# T\n\nkeep one\n\n## Revision log\n\nx y z\n\n### sub\n\nq\n\n## Real\n\nkeep two\n"
    kept, dropped = strip_sections(sec)
    assert dropped == ["Revision log"] and "keep two" in kept and "x y z" not in kept, kept
    md = "# Title\n\n| a | b |\n|---|---|\n| one two | three |\n- four\n1. five\n"
    assert len(strip_markup(strip_fences(md)).split()) == 8, strip_markup(md)
    print("self-test ok")
    return 0


if __name__ == "__main__":
    if is_self_test(sys.argv[1:]):
        sys.exit(self_test())
    sys.exit(main(sys.argv[1:]))
