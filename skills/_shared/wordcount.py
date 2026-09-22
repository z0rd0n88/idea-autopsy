#!/usr/bin/env python3
"""Count all substantive source text; excerpt only by explicit line selection.

Counting never removes sections or fenced contents. Excerpts preserve exact kept
source lines and emit a JSON coverage map (OUT.map.json by default). Excerpt
counts never substitute for full-source admission counts. `record` requires an
initialized schema-v2 ledger and binds its count to the immutable version hash.

Exit codes: 0 admitted, 1 above refusal, 2 invalid arguments/configuration/state,
3 filesystem or encoding error. Warning is >= warn; refusal is > refuse.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REQUIRED_KEYS = (
    "review_refuse_words",
    "review_warn_words",
    "iterate_warn_combined",
    "iterate_refuse_combined",
)
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-{2,}[-:|\s]*$")
LINE_MARKER = re.compile(r"^\s*(#{1,6}|[-*+]|\d+[.)])\s+")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def load_thresholds(path=None):
    """Require positive integers (never bools) and strictly ordered limits."""
    with open(path or HERE / "thresholds.json", encoding="utf-8") as handle:
        result = json.load(handle)
    if not isinstance(result, dict):
        raise ValueError("thresholds must be a JSON object")
    for key in REQUIRED_KEYS:
        if type(result.get(key)) is not int or result[key] <= 0:
            raise ValueError(f"threshold {key} must be a positive integer")
    for warn, refuse in (
        ("review_warn_words", "review_refuse_words"),
        ("iterate_warn_combined", "iterate_refuse_combined"),
    ):
        if result[warn] >= result[refuse]:
            raise ValueError(f"{warn} must be less than {refuse}")
    return result


def read_doc(path):
    # Reject undecodable input rather than silently changing evidence bytes.
    return Path(path).read_bytes().decode("utf-8")


def strip_markup(text):
    """Ignore presentation delimiters while retaining all substantive content."""
    result, fence_char, fence_length = [], None, 0
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence_char is not None:
            if (
                match
                and match[1][0] == fence_char
                and len(match[1]) >= fence_length
                and not match[2].strip()
            ):
                fence_char = None
            else:
                result.append(line)
        elif match and not (match[1][0] == "`" and "`" in match[2]):
            fence_char, fence_length = match[1][0], len(match[1])
        elif not SEPARATOR_ROW.match(line):
            result.append(LINE_MARKER.sub("", line, count=1).replace("|", " "))
    return "\n".join(result)


def count_text(text):
    return len(strip_markup(text).split())


def reviewable(path):
    """Compatibility tuple: exact source, no implicit omissions, full count."""
    text = read_doc(path)
    return text, [], count_text(text)


def count(path):
    return count_text(read_doc(path))


def verdict(n, refuse_key, warn_key, thresholds=None):
    limits = thresholds if thresholds is not None else load_thresholds()
    if n > limits[refuse_key]:
        return f"OVER {refuse_key} ({limits[refuse_key]})", True
    if n >= limits[warn_key]:
        return f"at/above {warn_key} ({limits[warn_key]})", False
    return "ok", False


def _same_file(left, right):
    if Path(left).resolve() == Path(right).resolve():
        return True
    return (
        Path(left).exists() and Path(right).exists() and os.path.samefile(left, right)
    )


def excerpt(path, out, exclusions=None, map_out=None):
    """Write new output/map files, rejecting aliases and existing destinations.

    exclusions contains inclusive (start, end) source line ranges. Output bytes
    equal concatenated retained lines, including newlines. The two files are not
    a ledger transaction; a failed write removes only this call's new files.
    """
    source, output = Path(path), Path(out)
    mapping_path = Path(map_out) if map_out else Path(str(output) + ".map.json")
    for left, right in (
        (source, output),
        (source, mapping_path),
        (output, mapping_path),
    ):
        if _same_file(left, right):
            raise ValueError(
                "source, excerpt, and map destinations must be distinct files"
            )
    if (
        output.exists()
        or output.is_symlink()
        or mapping_path.exists()
        or mapping_path.is_symlink()
    ):
        raise ValueError("excerpt and map destinations must not already exist")
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    omitted = set()
    for pair in exclusions or []:
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or any(type(x) is not int for x in pair)
            or not 1 <= pair[0] <= pair[1] <= len(lines)
        ):
            raise ValueError(
                f"exclusion must be an inclusive source line range within 1..{len(lines)}"
            )
        omitted.update(range(pair[0], pair[1] + 1))
    kept, ranges, skipped = [], [], []
    for source_line, line in enumerate(lines, 1):
        if source_line in omitted:
            if skipped and skipped[-1]["source_end"] == source_line - 1:
                skipped[-1]["source_end"] = source_line
            else:
                skipped.append(
                    {
                        "source_start": source_line,
                        "source_end": source_line,
                        "reason": "explicit line exclusion",
                    }
                )
            continue
        kept.append(line)
        output_line = len(kept)
        if ranges and ranges[-1]["source_end"] == source_line - 1:
            ranges[-1].update(source_end=source_line, output_end=output_line)
        else:
            ranges.append(
                {
                    "source_start": source_line,
                    "source_end": source_line,
                    "output_start": output_line,
                    "output_end": output_line,
                }
            )
    rendered = "".join(kept).encode("utf-8")
    coverage = {
        "source": str(source.resolve()),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "output": str(output.resolve()),
        "output_sha256": hashlib.sha256(rendered).hexdigest(),
        "source_words": count_text(text),
        "excerpt_words": count_text(rendered.decode("utf-8")),
        "source_lines": len(lines),
        "kept_ranges": ranges,
        "excluded_ranges": skipped,
    }
    created = []
    try:
        for dest, data in (
            (output, rendered),
            (mapping_path, (json.dumps(coverage, indent=2) + "\n").encode()),
        ):
            with dest.open("xb") as handle:
                created.append(dest)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
    except OSError:
        for dest in created:
            dest.unlink(missing_ok=True)
        raise
    return coverage


def record(slug, version, path, root=None):
    """Count only an initialized immutable version; never create/migrate state."""
    from state import execute

    request = {"slug": slug, "version": version, "file": str(Path(path).resolve())}
    request["project_dir" if root is not None else "source"] = str(
        Path(root if root is not None else path).resolve()
    )
    result = execute("counts", request)
    return result["state"]["word_counts"][version]["words"]


def _range(value):
    try:
        start, end = value.split(":")
        return int(start), int(end)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "use inclusive START:END source line numbers"
        ) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "record", "excerpt"):
        command = commands.add_parser(name)
        command.add_argument("--file", required=True)
        if name == "check":
            command.add_argument("--combined")
        elif name == "record":
            command.add_argument("--slug", required=True)
            command.add_argument("--version", required=True)
            command.add_argument("--project-dir")
        else:
            command.add_argument("--out", required=True)
            command.add_argument("--map-out")
            command.add_argument(
                "--exclude-lines", action="append", type=_range, default=[]
            )
    args = parser.parse_args(argv)
    try:
        if args.command == "excerpt":
            print(
                json.dumps(
                    excerpt(args.file, args.out, args.exclude_lines, args.map_out),
                    indent=2,
                )
            )
            return 0
        limits = load_thresholds()
        n = (
            record(args.slug, args.version, args.file, args.project_dir)
            if args.command == "record"
            else count(args.file)
        )
        print(f"{args.file}: {n} full-source words")
        combined = args.command == "check" and args.combined
        if combined:
            other = count(args.combined)
            print(f"{args.combined}: {other} full-source words")
            n += other
        keys = (
            ("iterate_refuse_combined", "iterate_warn_combined")
            if combined
            else ("review_refuse_words", "review_warn_words")
        )
        message, refused = verdict(n, *keys, thresholds=limits)
        print(f"{'combined' if combined else 'admission'}: {n} words ({message})")
        return int(refused)
    except (OSError, UnicodeError) as error:
        print(f"wordcount: {error}", file=sys.stderr)
        return 3
    except ValueError as error:
        print(f"wordcount: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
