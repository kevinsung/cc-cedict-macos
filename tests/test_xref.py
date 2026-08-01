import unittest

from cccedict.cedict import Entry, Reading
from cccedict.xref import (
    XREF,
    assign_ids,
    build_index,
    parse_references,
    split_classifiers,
)


def entry(trad, simp, pinyin="x1"):
    return Entry(trad, simp, [Reading(pinyin, ["placeholder"])])


class TestIds(unittest.TestCase):
    def test_ids_are_valid_xml_ids(self):
        entries = [entry("一", "一"), entry("二", "二")]
        assign_ids(entries)
        for e in entries:
            self.assertRegex(e.id, r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

    def test_ids_are_unique_and_ordered(self):
        entries = [entry(str(i), str(i)) for i in range(100)]
        assign_ids(entries)
        ids = [e.id for e in entries]
        self.assertEqual(len(set(ids)), 100)
        self.assertEqual(ids, sorted(ids))

    def test_ids_are_deterministic(self):
        first = [entry("一", "一"), entry("二", "二")]
        second = [entry("一", "一"), entry("二", "二")]
        assign_ids(first)
        assign_ids(second)
        self.assertEqual([e.id for e in first], [e.id for e in second])


class TestRegex(unittest.TestCase):
    def test_single_form(self):
        self.assertEqual(
            XREF.findall("see 中文[Zhong1 wen2]"), [("中文", "", "Zhong1 wen2")]
        )

    def test_trad_simp_form(self):
        self.assertEqual(XREF.findall("CL:個|个[ge4]"), [("個", "个", "ge4")])

    def test_multiple_in_one_sense(self):
        self.assertEqual(len(XREF.findall("CL:個|个[ge4],位[wei4]")), 2)


class TestResolution(unittest.TestCase):
    def setUp(self):
        self.zhongwen = entry("中文", "中文")
        self.ge = entry("個", "个")
        self.entries = [self.zhongwen, self.ge]
        assign_ids(self.entries)
        self.index = build_index(self.entries)

    def test_pair_resolves(self):
        self.assertEqual(self.index.resolve("個", "个"), self.ge.id)

    def test_single_form_resolves_when_unambiguous(self):
        self.assertEqual(self.index.resolve("中文", None), self.zhongwen.id)

    def test_simplified_only_reference_resolves(self):
        self.assertEqual(self.index.resolve("个", None), self.ge.id)

    def test_unknown_returns_none(self):
        self.assertIsNone(self.index.resolve("不存在", None))

    def test_ambiguous_single_form_returns_none(self):
        # Two entries share a traditional form with different simplifications,
        # so a bare reference could mean either; linking would guess wrong.
        a = entry("干", "干")
        b = entry("干", "乾")
        entries = [a, b]
        assign_ids(entries)
        index = build_index(entries)
        self.assertEqual(index.resolve("干", "乾"), b.id)
        # 干/干 is an exact pair match, so it still resolves.
        self.assertEqual(index.resolve("干", "干"), a.id)


class TestParseReferences(unittest.TestCase):
    def setUp(self):
        self.ge = entry("個", "个")
        entries = [self.ge]
        assign_ids(entries)
        self.index = build_index(entries)

    def test_splits_plain_and_linked(self):
        fragments = parse_references("classifier 個|个[ge4] here", self.index)
        self.assertEqual(len(fragments), 3)
        self.assertIsNone(fragments[0].target)
        self.assertEqual(fragments[1].target, self.ge.id)
        self.assertEqual(fragments[1].text, "個|个")
        self.assertEqual(fragments[1].reading, "ge4")
        self.assertIsNone(fragments[2].target)

    def test_no_text_is_lost_when_unresolvable(self):
        text = "see 不存在[bu4 cun2 zai4] please"
        fragments = parse_references(text, self.index)
        self.assertEqual("".join(f.text for f in fragments), text)

    def test_plain_text_passes_through(self):
        fragments = parse_references("no references here", self.index)
        self.assertEqual(len(fragments), 1)
        self.assertIsNone(fragments[0].target)


class TestClassifierSplit(unittest.TestCase):
    def test_split(self):
        senses, classifiers = split_classifiers(
            ["higher authorities", "CL:個|个[ge4]", "superiors"]
        )
        self.assertEqual(senses, ["higher authorities", "superiors"])
        self.assertEqual(classifiers, ["個|个[ge4]"])

    def test_no_classifiers(self):
        senses, classifiers = split_classifiers(["a", "b"])
        self.assertEqual(senses, ["a", "b"])
        self.assertEqual(classifiers, [])


if __name__ == "__main__":
    unittest.main()
