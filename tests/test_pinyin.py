import unittest

from cccedict import pinyin


class TestUmlaut(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(pinyin.normalize_umlaut("lu:4"), "lü4")

    def test_uppercase(self):
        self.assertEqual(pinyin.normalize_umlaut("LU:4"), "LÜ4")

    def test_full_reading(self):
        self.assertEqual(pinyin.accented("yi1 lu:4"), "yī lǜ")

    def test_nu_hai(self):
        self.assertEqual(pinyin.accented("nu:3 hai2"), "nǚ hái")


class TestTonePlacement(unittest.TestCase):
    def test_a_wins(self):
        self.assertEqual(pinyin.accent_syllable("hao3"), "hǎo")
        self.assertEqual(pinyin.accent_syllable("wai4"), "wài")

    def test_e_beats_later_vowels(self):
        self.assertEqual(pinyin.accent_syllable("xue2"), "xué")
        self.assertEqual(pinyin.accent_syllable("lüe4"), "lüè")

    def test_ou_marks_the_o(self):
        self.assertEqual(pinyin.accent_syllable("gou3"), "gǒu")
        self.assertEqual(pinyin.accent_syllable("you3"), "yǒu")

    def test_otherwise_last_vowel(self):
        # iu and ui are the cases a naive "first vowel" rule gets wrong.
        self.assertEqual(pinyin.accent_syllable("jiu3"), "jiǔ")
        self.assertEqual(pinyin.accent_syllable("gui4"), "guì")
        self.assertEqual(pinyin.accent_syllable("shui3"), "shuǐ")
        self.assertEqual(pinyin.accent_syllable("yu3"), "yǔ")
        self.assertEqual(pinyin.accent_syllable("zhong1"), "zhōng")

    def test_uppercase_initial_can_carry_the_mark(self):
        # 歐 Ou1: the marked vowel is the capitalized first letter.
        self.assertEqual(pinyin.accent_syllable("Ou1"), "Ōu")
        self.assertEqual(pinyin.accent_syllable("Zhong1"), "Zhōng")
        self.assertEqual(pinyin.accent_syllable("An1"), "Ān")

    def test_all_four_tones(self):
        self.assertEqual(
            [pinyin.accent_syllable(f"ma{t}") for t in "12345"],
            ["mā", "má", "mǎ", "mà", "ma"],
        )

    def test_syllabic_consonant(self):
        # 呣 m2 has no vowel to mark.
        self.assertEqual(pinyin.accent_syllable("m2"), "ḿ")
        self.assertEqual(pinyin.accent_syllable("hm5"), "hm")


class TestNeutralTone(unittest.TestCase):
    def test_tone_five_is_bare(self):
        self.assertEqual(pinyin.accent_syllable("r5"), "r")
        self.assertEqual(pinyin.accent_syllable("xx5"), "xx")

    def test_tone_zero_is_bare(self):
        self.assertEqual(pinyin.accent_syllable("de0"), "de")


class TestPassthrough(unittest.TestCase):
    def test_digits_survive(self):
        self.assertEqual(pinyin.accented("11 Qu1"), "11 Qū")

    def test_latin_survives(self):
        self.assertEqual(pinyin.accented("ke1 CP"), "kē CP")


class TestTonelessKeys(unittest.TestCase):
    def test_spaced_and_unspaced(self):
        self.assertEqual(pinyin.toneless_keys("han4 yu3"), ["han yu", "hanyu"])

    def test_single_syllable_yields_one_key(self):
        self.assertEqual(pinyin.toneless_keys("he2"), ["he"])

    def test_umlaut_folds_to_u(self):
        # Typing "lu" must find 律 lǜ.
        self.assertEqual(pinyin.toneless_keys("yi1 lu:4"), ["yi lu", "yilu"])

    def test_lowercased(self):
        self.assertEqual(pinyin.toneless_keys("Zhong1 wen2"), ["zhong wen", "zhongwen"])

    def test_erhua(self):
        self.assertEqual(
            pinyin.toneless_keys("bu4 qi3 yan3 r5"),
            ["bu qi yan r", "buqiyanr"],
        )

    def test_non_syllabic_tokens_kept(self):
        self.assertEqual(pinyin.toneless_keys("11 Qu1"), ["11 qu", "11qu"])

    def test_empty_reading(self):
        self.assertEqual(pinyin.toneless_keys(""), [])


class TestSyllableTone(unittest.TestCase):
    def test_tones(self):
        self.assertEqual(pinyin.syllable_tone("ma1"), 1)
        self.assertEqual(pinyin.syllable_tone("ma4"), 4)
        self.assertEqual(pinyin.syllable_tone("ma5"), 5)

    def test_zero_normalizes_to_five(self):
        self.assertEqual(pinyin.syllable_tone("de0"), 5)

    def test_non_syllabic_is_zero(self):
        self.assertEqual(pinyin.syllable_tone("CP"), 0)
        self.assertEqual(pinyin.syllable_tone("11"), 0)


if __name__ == "__main__":
    unittest.main()
