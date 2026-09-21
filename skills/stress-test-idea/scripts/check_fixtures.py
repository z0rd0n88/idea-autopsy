#!/usr/bin/env python3
"""Cross-check a doc's thresholds table against the numbers used elsewhere in it.

Catches the case where a document's own fixtures or worked examples violate its
own stated minimums -- a mechanical find that should not cost a reviewer panel.

Usage: python3 check_fixtures.py DOC.md
       python3 check_fixtures.py --self-test
"""

import re
import sys

# unit -> (dimension, factor into the dimension's base unit)
UNITS = {
    "sec": ("time", 1 / 60),
    "secs": ("time", 1 / 60),
    "second": ("time", 1 / 60),
    "seconds": ("time", 1 / 60),
    "min": ("time", 1),
    "mins": ("time", 1),
    "minute": ("time", 1),
    "minutes": ("time", 1),
    "hr": ("time", 60),
    "hrs": ("time", 60),
    "hour": ("time", 60),
    "hours": ("time", 60),
    "day": ("time", 1440),
    "days": ("time", 1440),
    "week": ("time", 10080),
    "weeks": ("time", 10080),
    "bar": ("bars", 1),
    "bars": ("bars", 1),
    "%": ("percent", 1),
    "percent": ("percent", 1),
    "pct": ("percent", 1),
    "word": ("words", 1),
    "words": ("words", 1),
    "user": ("users", 1),
    "users": ("users", 1),
}

NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"
CONSTRAINT_RE = re.compile(r"(>=|<=|≥|≤|>|<)\s*(" + NUM + r")\s*(%|[A-Za-z]+)")
MENTION_RE = re.compile(r"(" + NUM + r")\s*(%|[A-Za-z]+)")
HEADER_RE = re.compile(r"param|constant|threshold|limit|value|min|max", re.I)
SEP_RE = re.compile(r"^[\s|:\-]+$")
# A "Reason | Rule" table lists rejection conditions, not requirements.
REASON_RE = re.compile(r"reason", re.I)
OP = r"(?:>=|<=|≥|≤|>|<)"
REJECT_OR_RE = re.compile(OP + r"[^|]*\bor\b[^|]*" + OP, re.I)
# Sentences that stand in for the whole fixture set are checked against everything.
FIXTURE_RE = re.compile(r"fixture|every case|test vector|example|conformance", re.I)
WORD_RE = re.compile(r"[^a-z0-9]+")


def _num(s):
    return float(s.replace(",", ""))


def _clean(s):
    return s.strip().strip("`*# ").strip()


def _keys(name):
    """Words that must appear near a number for this threshold to apply to it."""
    n = _clean(name).lower()
    return {w for w in WORD_RE.split(n) if len(w) >= 4} | ({n} if n else set())


def _violates(op, value, limit):
    if op in (">=", "≥"):
        return value < limit
    if op == ">":
        return value <= limit
    if op in ("<=", "≤"):
        return value > limit
    return value >= limit  # "<"


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _tables(lines):
    """Yield (start_index, [row_cells, ...]) for each pipe table."""
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            start = i
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                if not SEP_RE.match(lines[i]):
                    rows.append(_cells(lines[i]))
                i += 1
            yield start, rows
        else:
            i += 1


def analyze(path):
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()

    units = dict(UNITS)
    if re.search(r"minute\s+bars", text, re.I):
        units["bar"] = units["bars"] = ("time", 1)

    thresholds = []  # (name, op, limit_number, unit, dimension, base_limit, keys)
    skip = set()  # line numbers belonging to a thresholds table
    header_of = {}  # line number -> header row of the table that line sits in
    for start, rows in _tables(lines):
        if not rows:
            continue
        end = start
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        header = " | ".join(rows[0])
        for i in range(start, end):
            header_of[i] = header.lower()

        # A thresholds table announces itself in its header. A "Reason" table,
        # or a row pairing two operators with "or", lists rejection conditions --
        # the inverse of a requirement -- so reading it literally inverts the check.
        if not HEADER_RE.search(header) or REASON_RE.search(header):
            continue
        body = rows[1:]
        if any(REJECT_OR_RE.search(" | ".join(r)) for r in body):
            continue

        found = []
        for row in body:
            name = _clean(row[0])
            if not name or name.replace(".", "").isdigit():
                continue  # a numbered row is a case, not a threshold
            for op, n, unit in CONSTRAINT_RE.findall(" | ".join(row[1:])):
                u = unit.lower()
                if u not in units:
                    continue
                dim, factor = units[u]
                found.append(
                    (row[0], op, _num(n), unit, dim, _num(n) * factor, _keys(name))
                )
        if found:
            thresholds.extend(found)
            skip.update(range(start, end))

    if not thresholds:
        return None, []

    dims = {t[4] for t in thresholds}
    violations = []
    for i, line in enumerate(lines):
        if i in skip:
            continue
        # A matching unit is not a matching subject: check a number only against
        # thresholds this line (or its table header) actually names. Fixture
        # sentences are the exception -- they stand in for every case.
        hay = (line + " " + header_of.get(i, "")).lower()
        fixture = bool(FIXTURE_RE.search(line))
        for n, unit in MENTION_RE.findall(line):
            u = unit.lower()
            if u not in units:
                continue
            dim, factor = units[u]
            if dim not in dims:
                continue
            value = _num(n) * factor
            for name, op, limit, lunit, ldim, base, keys in thresholds:
                if ldim != dim:
                    continue
                if not fixture and not any(k in hay for k in keys):
                    continue
                if _violates(op, value, base):
                    violations.append(
                        "%s:%d: %s requires %s %s %s; found %s %s"
                        % (
                            path,
                            i + 1,
                            name,
                            op,
                            _fmt(limit),
                            lunit,
                            _fmt(_num(n)),
                            unit,
                        )
                    )
    return thresholds, violations


def _fmt(x):
    return str(int(x)) if x == int(x) else str(x)


def main(argv):
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    thresholds, violations = analyze(argv[0])
    if thresholds is None:
        print("no thresholds table found")
        return 0
    for v in violations:
        print(v)
    print(
        "%d threshold(s) checked, %d violation(s)" % (len(thresholds), len(violations))
    )
    return 1 if violations else 0


DIRTY = """# Rulebook

| Parameter | Bound | Ref |
|---|---|---|
| Horizon | >= 60 minutes, <= 365 days | S6 |

## Fixtures

Every case uses a reference of 100, minute bars, and a deadline of t0 + 10 bars.
"""

CLEAN = DIRTY.replace("t0 + 10 bars", "t0 + 120 bars")

NO_TABLE = "# Notes\n\nA deadline of t0 + 10 bars, give or take.\n"

# Shaped like the real rulebook: a rejection-reasons table, a receipt line of
# unrelated percentages, and one real constants table. Nothing here is a
# violation -- every finding this used to produce was a false positive.
SHAPED = """# Rulebook

## 6. Not gradeable

| Reason | Rule |
|---|---|
| `horizon` | `horizon > 365 days`, or `horizon < 60 minutes`. |
| `below-minimum-move` | `distance < 2%`. |

## 8. The receipt

Right 64% - 24 of 38 graded, median target distance 6.5%, median horizon 14 days.

## 10. Constants

| Parameter | Value | Where used |
|---|---|---|
| Completeness | <= 5% missing | S3 |
| Horizon | >= 60 minutes, <= 365 days | S6 |
"""


def self_test():
    import os
    import tempfile

    def run(text):
        fd, p = tempfile.mkstemp(suffix=".md")
        os.write(fd, text.encode())
        os.close(fd)
        try:
            return analyze(p)
        finally:
            os.unlink(p)

    t, v = run(DIRTY)
    assert t and len(v) == 1, v
    assert "Horizon requires >= 60 minutes; found 10 bars" in v[0], v[0]

    t, v = run(CLEAN)
    assert t and v == [], v

    t, v = run(NO_TABLE)
    assert t is None, t

    t, v = run(SHAPED)
    assert t and v == [], v

    print("self-test: 4 cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if sys.argv[1:2] == ["--self-test"] else main(sys.argv[1:]))
