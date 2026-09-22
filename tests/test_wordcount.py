"""Source coverage and admission behavior, not tests of evaluation judgment."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SHARED = Path(__file__).resolve().parents[1] / "skills" / "_shared"
sys.path.insert(0, str(SHARED))
import wordcount
import state


class WordcountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = self.root / "proposal.md"

    def write(self, text):
        self.doc.write_text(text, encoding="utf-8")
        return self.doc

    def test_all_sections_and_fence_contents_count(self):
        source = "# Proposal\nRevenue 100\n## Appendix\nEvidence one\n```csv\n1 2 3\n```\n## FAQ\nQuestion answer\n"
        self.write(source)
        self.assertEqual(wordcount.count(self.doc), 12)
        self.assertEqual(wordcount.reviewable(self.doc), (source, [], 12))
        for heading in (
            "Revision log",
            "Component spec",
            "User flow",
            "Glossary",
            "Diagram",
        ):
            with self.subTest(heading=heading):
                self.assertIn(
                    "decisive evidence",
                    wordcount.reviewable(
                        self.write(f"## {heading}\ndecisive evidence\n")
                    )[0],
                )

    def test_fence_contents_including_markdown_like_evidence_are_retained(self):
        text = "one\n````\n```\n# meaningful comment\na | b\n````\ntwo\n"
        self.assertEqual(wordcount.count_text(text), 9)
        self.assertEqual(
            wordcount.count_text("```\nimportant unresolved evidence\n"), 3
        )
        self.assertEqual(wordcount.count_text("~~~python\na b\n~~~\n"), 2)

    def test_markdown_presentation_does_not_inflate_count(self):
        self.assertEqual(
            wordcount.count_text(
                "# Title\n| a | b |\n|---|---|\n| one two | three |\n- four\n1. five\n"
            ),
            8,
        )

    def test_threshold_types_order_and_exact_boundaries(self):
        limits = wordcount.load_thresholds()
        for warn, refuse in (
            ("review_warn_words", "review_refuse_words"),
            ("iterate_warn_combined", "iterate_refuse_combined"),
        ):
            self.assertEqual(
                wordcount.verdict(limits[warn] - 1, refuse, warn, limits), ("ok", False)
            )
            self.assertIn(
                "at/above", wordcount.verdict(limits[warn], refuse, warn, limits)[0]
            )
            self.assertFalse(wordcount.verdict(limits[refuse], refuse, warn, limits)[1])
            self.assertTrue(
                wordcount.verdict(limits[refuse] + 1, refuse, warn, limits)[1]
            )
        path = self.root / "limits.json"
        for value in (True, 0, -1, 5000.5, "5000", None):
            with self.subTest(value=value):
                path.write_text(json.dumps({**limits, "review_warn_words": value}))
                with self.assertRaises(ValueError):
                    wordcount.load_thresholds(path)
        for value in (limits["review_refuse_words"], limits["review_refuse_words"] + 1):
            path.write_text(json.dumps({**limits, "review_warn_words": value}))
            with self.assertRaises(ValueError):
                wordcount.load_thresholds(path)
        for invalid in ({}, [], {"review_warn_words": 1}):
            path.write_text(json.dumps(invalid))
            with self.assertRaises(ValueError):
                wordcount.load_thresholds(path)

    def test_default_excerpt_is_byte_exact_and_maps_every_line(self):
        raw = b"# Heading\r\n\r\n## FAQ\r\nall evidence\r\n```\r\na b\r\n```"
        self.doc.write_bytes(raw)
        output = self.root / "copy.md"
        coverage = wordcount.excerpt(self.doc, output)
        self.assertEqual(output.read_bytes(), raw)
        self.assertEqual(coverage["excluded_ranges"], [])
        self.assertEqual(
            coverage["kept_ranges"],
            [{"source_start": 1, "source_end": 7, "output_start": 1, "output_end": 7}],
        )
        self.assertEqual(coverage["source_sha256"], coverage["output_sha256"])
        self.assertEqual(
            json.loads(Path(str(output) + ".map.json").read_text()), coverage
        )

    def test_explicit_exclusion_has_exact_source_ranges_and_full_admission_count(self):
        self.write("one\ntwo\nthree\nfour\nfive\n")
        output = self.root / "excerpt.md"
        coverage = wordcount.excerpt(self.doc, output, [(2, 3)])
        self.assertEqual(output.read_text(), "one\nfour\nfive\n")
        self.assertEqual((coverage["source_words"], coverage["excerpt_words"]), (5, 3))
        self.assertEqual(
            coverage["kept_ranges"],
            [
                {
                    "source_start": 1,
                    "source_end": 1,
                    "output_start": 1,
                    "output_end": 1,
                },
                {
                    "source_start": 4,
                    "source_end": 5,
                    "output_start": 2,
                    "output_end": 3,
                },
            ],
        )
        self.assertEqual(coverage["excluded_ranges"][0]["source_end"], 3)
        self.assertEqual(wordcount.count(self.doc), 5)

    def test_invalid_exclusions_do_not_write(self):
        self.write("a\nb\n")
        for ranges in ([(0, 1)], [(1, 3)], [(2, 1)], [(True, 2)], [(1, "2")]):
            with self.subTest(ranges=ranges):
                with self.assertRaises(ValueError):
                    wordcount.excerpt(self.doc, self.root / "bad.md", ranges)
                self.assertFalse((self.root / "bad.md").exists())

    def test_source_destination_and_map_aliases_never_overwrite(self):
        self.write("original evidence\n")
        symlink, hardlink = self.root / "sym.md", self.root / "hard.md"
        symlink.symlink_to(self.doc)
        os.link(self.doc, hardlink)
        for target in (self.doc, symlink, hardlink):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    wordcount.excerpt(self.doc, target)
                with self.assertRaises(ValueError):
                    wordcount.excerpt(self.doc, self.root / "copy.md", map_out=target)
        output = self.root / "same.md"
        with self.assertRaises(ValueError):
            wordcount.excerpt(self.doc, output, map_out=output)
        self.assertEqual(self.doc.read_text(), "original evidence\n")

    def test_write_failure_removes_only_new_partial_output(self):
        self.write("evidence")
        output = self.root / "copy.md"
        with self.assertRaises(OSError):
            wordcount.excerpt(
                self.doc, output, map_out=self.root / "missing" / "map.json"
            )
        self.assertFalse(output.exists())
        output.write_text("existing output")
        with self.assertRaises(ValueError):
            wordcount.excerpt(self.doc, output)
        self.assertEqual(output.read_text(), "existing output")

    def test_record_requires_explicit_state_and_rejects_stale_content(self):
        self.write("one two")
        with self.assertRaises(state.StateError):
            wordcount.record("demo", "v1", self.doc)
        initialized = state.execute("init", {"slug": "demo", "source": str(self.doc)})
        self.assertEqual(wordcount.record("demo", "v1", self.doc), 2)
        self.write("changed source with extra claims")
        with self.assertRaisesRegex(state.StateError, "source changed"):
            wordcount.record("demo", "v1", self.doc)
        immutable = (
            Path(initialized["root"]) / initialized["state"]["versions"]["v1"]["path"]
        )
        self.assertEqual(wordcount.record("demo", "v1", immutable), 2)

    def test_cli_errors_are_actionable_without_tracebacks(self):
        for name, expected in (("missing.md", 3), ("invalid.md", 3)):
            path = self.root / name
            if name == "invalid.md":
                path.write_bytes(b"\xff")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SHARED / "wordcount.py"),
                    "check",
                    "--file",
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, expected)
            self.assertIn("wordcount:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
