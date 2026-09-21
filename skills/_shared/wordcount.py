#!/usr/bin/env python3
"""Shared word-count guard for the idea-autopsy skills.

The thresholds live in thresholds.json beside this file, so the review skills
and iterate-to-v2 read one set of numbers instead of each stating its own.
`record` writes the count into ./.autopsy/<slug>/state.json at write time, so a
v2 that outgrew the next stage's refusal limit fails here, when it is written,
rather than one stage later, and the next stage reads the number from state.json
instead of recounting the document.

    wordcount.py record --slug <slug> --version <vN> --file <path>
    wordcount.py check --file <path> [--combined <critique>]
    wordcount.py --self-test
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "thresholds.json"), encoding="utf-8") as _f:
    T = json.load(_f)


def count(path):
    with open(path, encoding="utf-8") as f:
        return len(f.read().split())


def verdict(n, refuse_key, warn_key):
    """Return (message, over_refuse_limit)."""
    if n > T[refuse_key]:
        return "OVER %s (%d)" % (refuse_key, T[refuse_key]), True
    if n > T[warn_key]:
        return "over %s (%d)" % (warn_key, T[warn_key]), False
    return "ok", False


def record(slug, version, path, root="."):
    """Count path and store it as word_counts[version] in the slug's state.json."""
    n = count(path)
    state_path = os.path.join(root, ".autopsy", slug, "state.json")
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    state = {}
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    state.setdefault("word_counts", {})[version] = n
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
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
    a = p.parse_args(argv)

    if a.cmd == "record":
        n = record(a.slug, a.version, a.file)
        msg, over = verdict(n, "review_refuse_words", "review_warn_words")
        print("%s: %d words (%s)" % (a.version, n, msg))
        return 1 if over else 0

    n = count(a.file)
    if a.combined:
        m = count(a.combined)
        msg, over = verdict(n + m, "iterate_refuse_combined", "iterate_warn_combined")
        print("%s: %d words" % (a.file, n))
        print("%s: %d words" % (a.combined, m))
        print("combined: %d words (%s)" % (n + m, msg))
    else:
        msg, over = verdict(n, "review_refuse_words", "review_warn_words")
        print("%s: %d words (%s)" % (a.file, n, msg))
    return 1 if over else 0


def self_test():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "v2.md")
        state_path = os.path.join(d, ".autopsy", "demo", "state.json")

        # record creates word_counts
        with open(doc, "w") as f:
            f.write("word " * 30)
        assert record("demo", "v2", doc, d) == 30
        with open(state_path) as f:
            assert json.load(f)["word_counts"] == {"v2": 30}

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

    print("self-test ok")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    sys.exit(main(sys.argv[1:]))
