import tempfile
import unittest
from pathlib import Path

from cccedict import cedict

SAMPLE = (
    "# CC-CEDICT\r\n"
    "#! version=1\r\n"
    "#! entries=5\r\n"
    "#! date=2026-07-29T07:36:56Z\r\n"
    "漢語 汉语 [Han4 yu3] /Chinese language/\r\n"
    "和 和 [He2] /surname He/\r\n"
    "和 和 [he2] /and/(math.) sum/\r\n"
    "和 和 [he4] /to join in the singing/\r\n"
    "一律 一律 [yi1 lu:4] /same; identical/uniformly/\r\n"
)


class TempSource:
    """Write a source file to a temp dir for the duration of a test."""

    def __init__(self, text):
        self.text = text

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        path = Path(self._dir.name) / "cedict.txt"
        path.write_text(self.text, encoding="utf-8", newline="")
        return path

    def __exit__(self, *exc):
        self._dir.cleanup()


class TestParse(unittest.TestCase):
    def test_counts(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        self.assertEqual(source.lines_consumed, 5)
        self.assertEqual(source.lines_rejected, 0)
        # 和 appears three times but is one entry.
        self.assertEqual(len(source.entries), 3)

    def test_headers(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        self.assertEqual(source.date, "2026-07-29T07:36:56Z")
        self.assertEqual(source.declared_entries, 5)

    def test_readings_merge_in_order(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        he = next(e for e in source.entries if e.traditional == "和")
        self.assertEqual([r.pinyin for r in he.readings], ["He2", "he2", "he4"])

    def test_senses_split(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        he = next(e for e in source.entries if e.traditional == "和")
        self.assertEqual(he.readings[1].senses, ["and", "(math.) sum"])

    def test_source_order_preserved(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        self.assertEqual(
            [e.traditional for e in source.entries], ["漢語", "和", "一律"]
        )

    def test_distinct_simplified(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        self.assertTrue(source.entries[0].has_distinct_simplified)
        self.assertFalse(source.entries[1].has_distinct_simplified)

    def test_crlf_stripped(self):
        with TempSource(SAMPLE) as path:
            source = cedict.parse(path)
        self.assertEqual(source.entries[0].readings[0].senses, ["Chinese language"])

    def test_bad_line_is_fatal(self):
        # A silently dropped entry is the failure we most want to avoid.
        with TempSource(SAMPLE + "this is not an entry\r\n") as path:
            with self.assertRaises(cedict.ParseError):
                cedict.parse(path)

    def test_comments_ignored(self):
        with TempSource("# just a comment\r\n漢語 汉语 [Han4 yu3] /x/\r\n") as path:
            source = cedict.parse(path)
        self.assertEqual(source.lines_consumed, 1)


class TestRegex(unittest.TestCase):
    def test_matches_awkward_headwords(self):
        for line in [
            "11區 11区 [11 Qu1] /Japan/",
            "磕CP 磕CP [ke1 CP] /to ship a couple/",
            "· · [xx5] /interpunct/",
        ]:
            self.assertIsNotNone(cedict.LINE.match(line), line)

    def test_empty_pinyin_allowed(self):
        self.assertIsNotNone(cedict.LINE.match("x x [] /y/"))


if __name__ == "__main__":
    unittest.main()
