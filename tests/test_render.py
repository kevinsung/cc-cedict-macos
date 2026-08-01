import unittest
from xml.etree import ElementTree

from cccedict import render
from cccedict.cedict import Entry, Reading
from cccedict.xref import assign_ids, build_index


def make_index(entries):
    assign_ids(entries)
    return build_index(entries)


def whitespace_only_nodes(xml):
    """Tags owning a text node that is non-empty but entirely whitespace."""
    root = ElementTree.fromstring(
        f'<root xmlns:d="{render.DICT_NS}" xmlns="{render.XHTML_NS}">{xml}</root>'
    )
    return [
        element.tag
        for element in root.iter()
        for node in (element.text, element.tail)
        if node and not node.strip()
    ]


class TestEscaping(unittest.TestCase):
    """An unescaped & in 124k entries of free text breaks the whole build."""

    def test_ampersand_and_angles_in_sense(self):
        entry = Entry("測試", "测试", [Reading("ce4 shi4", ["A & B < C > D"])])
        xml = render.render_entry(entry, make_index([entry]))
        self.assertIn("A &amp; B &lt; C &gt; D", xml)
        self.assertNotIn("A & B", xml)

    def test_escaped_output_is_parseable(self):
        entry = Entry("測試", "测试", [Reading("ce4 shi4", ['R&D "quoted" <tag>'])])
        xml = render.render_entry(entry, make_index([entry]))
        ElementTree.fromstring(
            f'<root xmlns:d="{render.DICT_NS}" xmlns="{render.XHTML_NS}">{xml}</root>'
        )

    def test_ampersand_in_headword_attribute(self):
        entry = Entry("A&B", "A&B", [Reading("a1", ["x"])])
        xml = render.render_entry(entry, make_index([entry]))
        self.assertIn('d:title="A&amp;B"', xml)


class TestStructure(unittest.TestCase):
    def setUp(self):
        self.entry = Entry("漢語", "汉语", [Reading("Han4 yu3", ["Chinese language"])])
        self.index = make_index([self.entry])
        self.xml = render.render_entry(self.entry, self.index)

    def test_indexes_precede_the_body(self):
        # The schema is `zeroOrMore index` then flow content.
        self.assertLess(self.xml.index("<d:index"), self.xml.index("<div"))
        self.assertLess(self.xml.rindex("<d:index"), self.xml.index("<div"))

    def test_traditional_and_simplified_indexed(self):
        self.assertIn('<d:index d:value="漢語"', self.xml)
        self.assertIn('<d:index d:value="汉语"', self.xml)

    def test_toneless_pinyin_indexed_both_ways(self):
        self.assertIn('d:value="han yu"', self.xml)
        self.assertIn('d:value="hanyu"', self.xml)

    def test_pinyin_is_deprioritized(self):
        self.assertIn('d:value="hanyu" d:title="漢語 Hàn yǔ" d:priority="2"', self.xml)

    def test_han_index_has_no_priority(self):
        self.assertIn('<d:index d:value="漢語" d:title="漢語"/>', self.xml)

    def test_only_the_accented_reading_is_displayed(self):
        self.assertIn("Hàn", self.xml)
        self.assertNotIn("Han4 yu3", self.xml)
        self.assertNotIn('class="numbered"', self.xml)

    def test_tone_classes(self):
        # The space after a syllable is inside its span: the DDK drops text
        # nodes that are entirely whitespace, so " " between two spans is lost.
        self.assertIn('<span class="tone4">Hàn </span>', self.xml)
        self.assertIn('<span class="tone3">yǔ</span>', self.xml)


class TestSimplifiedOmission(unittest.TestCase):
    def test_identical_forms_are_not_duplicated(self):
        entry = Entry("和", "和", [Reading("he2", ["and"])])
        xml = render.render_entry(entry, make_index([entry]))
        self.assertEqual(xml.count("<d:index"), 2)  # 和 + "he"
        self.assertNotIn("hw-simp", xml)


class TestMultipleReadings(unittest.TestCase):
    def test_readings_stack_in_one_entry(self):
        entry = Entry(
            "和",
            "和",
            [
                Reading("He2", ["surname He"]),
                Reading("he4", ["to join in the singing"]),
                Reading("hu2", ["to complete a set in mahjong"]),
            ],
        )
        xml = render.render_entry(entry, make_index([entry]))
        self.assertEqual(xml.count('<div class="reading">'), 3)
        self.assertEqual(xml.count("<d:entry"), 1)

    def test_duplicate_toneless_keys_deduped(self):
        entry = Entry("和", "和", [Reading("He2", ["a"]), Reading("he2", ["b"])])
        xml = render.render_entry(entry, make_index([entry]))
        self.assertEqual(xml.count('d:value="he"'), 1)


class TestClassifiers(unittest.TestCase):
    def test_classifier_row_split_out(self):
        entry = Entry("上級", "上级", [Reading("shang4 ji2", ["superiors", "CL:個|个[ge4]"])])
        target = Entry("個", "个", [Reading("ge4", ["classifier"])])
        xml = render.render_entry(entry, make_index([entry, target]))
        self.assertIn('<div class="classifier">', xml)
        self.assertIn("Classifier", xml)
        # The CL: sense must not also appear in the numbered sense list.
        self.assertNotIn("CL:", xml)
        self.assertEqual(xml.count("<li>"), 1)


class TestCrossReferences(unittest.TestCase):
    def test_reference_becomes_a_link(self):
        target = Entry("中文", "中文", [Reading("Zhong1 wen2", ["Chinese"])])
        entry = Entry("華語", "华语", [Reading("Hua2 yu3", ["see 中文[Zhong1 wen2]"])])
        xml = render.render_entry(entry, make_index([entry, target]))
        self.assertIn(f'href="x-dictionary:r:{target.id}"', xml)

    def test_unresolvable_reference_stays_plain_text(self):
        entry = Entry("華語", "华语", [Reading("Hua2 yu3", ["see 不存在[bu4 cun2 zai4]"])])
        xml = render.render_entry(entry, make_index([entry]))
        self.assertNotIn("x-dictionary:r:", xml)
        self.assertIn("不存在", xml)


class TestSeparatingSpaces(unittest.TestCase):
    """The DDK strips text nodes that are entirely whitespace.

    A space standing alone between two elements never reaches the rendered
    entry, so `<span>xìn</span> <span>kǒu</span>` displays as `xìnkǒu`. Every
    separator has to share a text node with real characters instead.
    """

    def setUp(self):
        target = Entry("個", "个", [Reading("ge4", ["classifier"])])
        entry = Entry(
            "上級",
            "上级",
            [Reading("shang4 ji2", ["superiors; see 個|个[ge4]", "CL:個|个[ge4]"])],
        )
        self.xml = render.render_entry(entry, make_index([entry, target]))

    def test_no_whitespace_only_text_nodes(self):
        self.assertEqual(whitespace_only_nodes(self.xml), [])

    def test_syllables_carry_their_own_space(self):
        self.assertIn('<span class="tone4">shàng </span>', self.xml)
        self.assertIn('<span class="tone2">jí</span>', self.xml)

    def test_headword_forms_are_separated(self):
        self.assertIn('<span class="hw-trad">上級 </span>', self.xml)

    def test_classifier_label_is_separated(self):
        self.assertIn('<span class="label">Classifier </span>', self.xml)

    def test_cross_reference_pinyin_is_separated(self):
        self.assertIn('<span class="xref-pinyin"> gè</span>', self.xml)


class TestFrontMatter(unittest.TestCase):
    def test_carries_license_and_attribution(self):
        from cccedict.cedict import Source

        source = Source(
            headers={"date": "2026-07-29T07:36:56Z", "entries": "124726"},
            entries=[],
            lines_consumed=0,
            lines_rejected=0,
        )
        xml = render.render_front_matter(source, "2026.7.29")
        self.assertIn(render.FRONT_MATTER_ID, xml)
        self.assertIn("Attribution-ShareAlike 4.0", xml)
        self.assertIn("MDBG", xml)
        self.assertIn("Denisowski", xml)
        self.assertIn("2026-07-29", xml)
        self.assertEqual(whitespace_only_nodes(xml), [])


if __name__ == "__main__":
    unittest.main()
