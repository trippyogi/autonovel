#!/usr/bin/env python3
"""
Smoke tests for the Phase 1 foundation generators (gen_world, gen_characters,
gen_outline, gen_outline_part2, gen_canon).

These stub out call_writer() so no live network/API calls are made. They
verify two contracts that matter for the multi-iteration foundation loop in
run_pipeline.py:

1. Each generator writes its output file(s) to disk.
2. gen_outline.py clears any stale `.outline_part1.md` snapshot from a prior
   iteration before generating a new one, and gen_outline_part2.py merges
   part1 + part2 into outline.md exactly once per run (no duplicated
   chapters on rerun).

Run with: python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import gen_canon  # noqa: E402
import gen_characters  # noqa: E402
import gen_outline  # noqa: E402
import gen_outline_part2  # noqa: E402
import gen_world  # noqa: E402


def _write(path: Path, name: str, content: str = "placeholder\n") -> None:
    (path / name).write_text(content, encoding="utf-8")


class FoundationFixtureTestCase(unittest.TestCase):
    """Base class that sets up a temp base_dir with the input files the
    Phase 1 generators expect, so each generator can be exercised in
    isolation without touching the real repo directory."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base_dir = Path(self._tmpdir.name)

        _write(self.base_dir, "seed.txt", "A boy who can hear the bells.\n")
        _write(
            self.base_dir,
            "voice.md",
            "# Voice\n\n## Part 1\ngeneric voice notes\n\n## Part 2\nnovel-specific voice notes\n",
        )
        _write(self.base_dir, "CRAFT.md", "craft reference notes\n")
        _write(self.base_dir, "MYSTERY.md", "the central mystery\n")
        _write(self.base_dir, "world.md", "# World\nplaceholder world bible\n")
        _write(self.base_dir, "characters.md", "# Characters\nplaceholder registry\n")


class TestGenWorld(FoundationFixtureTestCase):
    def test_writes_world_md(self):
        with mock.patch.object(gen_world, "call_writer", return_value="WORLD CONTENT"):
            result = gen_world.main(base_dir=self.base_dir)

        self.assertEqual(result, "WORLD CONTENT")
        out_path = self.base_dir / "world.md"
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.read_text(encoding="utf-8"), "WORLD CONTENT")


class TestGenCharacters(FoundationFixtureTestCase):
    def test_writes_characters_md(self):
        with mock.patch.object(gen_characters, "call_writer", return_value="CHARACTERS CONTENT"):
            result = gen_characters.main(base_dir=self.base_dir)

        self.assertEqual(result, "CHARACTERS CONTENT")
        out_path = self.base_dir / "characters.md"
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.read_text(encoding="utf-8"), "CHARACTERS CONTENT")


class TestGenCanon(FoundationFixtureTestCase):
    def test_writes_canon_md(self):
        with mock.patch.object(gen_canon, "call_writer", return_value="CANON CONTENT"):
            result = gen_canon.main(base_dir=self.base_dir)

        self.assertEqual(result, "CANON CONTENT")
        out_path = self.base_dir / "canon.md"
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.read_text(encoding="utf-8"), "CANON CONTENT")


class TestGenOutlineStaleSnapshot(FoundationFixtureTestCase):
    def test_clears_stale_snapshot_before_regenerating(self):
        snapshot = self.base_dir / ".outline_part1.md"
        snapshot.write_text("STALE PART 1 FROM A PRIOR ITERATION", encoding="utf-8")

        with mock.patch.object(gen_outline, "call_writer", return_value="FRESH PART 1"):
            result = gen_outline.main(base_dir=self.base_dir)

        self.assertEqual(result, "FRESH PART 1")
        # The stale snapshot must be gone and replaced with the fresh output,
        # never silently reused by gen_outline_part2.py.
        self.assertEqual(snapshot.read_text(encoding="utf-8"), "FRESH PART 1")
        self.assertNotIn("STALE", snapshot.read_text(encoding="utf-8"))

        outline_path = self.base_dir / "outline.md"
        self.assertEqual(outline_path.read_text(encoding="utf-8"), "FRESH PART 1")

    def test_writes_outline_and_snapshot_from_clean_state(self):
        snapshot = self.base_dir / ".outline_part1.md"
        self.assertFalse(snapshot.exists())

        with mock.patch.object(gen_outline, "call_writer", return_value="PART 1 TEXT"):
            gen_outline.main(base_dir=self.base_dir)

        self.assertTrue(snapshot.exists())
        self.assertEqual(snapshot.read_text(encoding="utf-8"), "PART 1 TEXT")
        self.assertEqual(
            (self.base_dir / "outline.md").read_text(encoding="utf-8"), "PART 1 TEXT"
        )


class TestGenOutlinePart2Merge(FoundationFixtureTestCase):
    def test_errors_without_snapshot(self):
        with self.assertRaises(SystemExit):
            gen_outline_part2.main(base_dir=self.base_dir)

    def test_merges_part1_and_part2_once(self):
        snapshot = self.base_dir / ".outline_part1.md"
        snapshot.write_text("CHAPTERS 1-17", encoding="utf-8")

        with mock.patch.object(gen_outline_part2, "call_writer", return_value="CHAPTERS 18-24 + LEDGER"):
            merged = gen_outline_part2.main(base_dir=self.base_dir)

        outline_path = self.base_dir / "outline.md"
        on_disk = outline_path.read_text(encoding="utf-8")
        self.assertEqual(merged, on_disk)
        self.assertIn("CHAPTERS 1-17", on_disk)
        self.assertIn("CHAPTERS 18-24 + LEDGER", on_disk)
        # Exactly one occurrence each -- no duplication.
        self.assertEqual(on_disk.count("CHAPTERS 1-17"), 1)
        self.assertEqual(on_disk.count("CHAPTERS 18-24 + LEDGER"), 1)

    def test_rerun_does_not_duplicate_chapters(self):
        """Re-running part 2 always reads from the untouched part-1 snapshot
        and overwrites outline.md wholesale, so chapters never accumulate
        across repeated runs (e.g. re-running after a foundation retry)."""
        snapshot = self.base_dir / ".outline_part1.md"
        snapshot.write_text("CHAPTERS 1-17", encoding="utf-8")

        with mock.patch.object(gen_outline_part2, "call_writer", return_value="RUN A CONTENT"):
            gen_outline_part2.main(base_dir=self.base_dir)

        with mock.patch.object(gen_outline_part2, "call_writer", return_value="RUN B CONTENT"):
            gen_outline_part2.main(base_dir=self.base_dir)

        on_disk = (self.base_dir / "outline.md").read_text(encoding="utf-8")
        self.assertEqual(on_disk.count("CHAPTERS 1-17"), 1)
        self.assertNotIn("RUN A CONTENT", on_disk)
        self.assertEqual(on_disk.count("RUN B CONTENT"), 1)


if __name__ == "__main__":
    unittest.main()
