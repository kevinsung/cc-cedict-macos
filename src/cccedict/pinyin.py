"""Pinyin romanization: ASCII CC-CEDICT notation to display and index forms.

CC-CEDICT writes pinyin as space-separated syllables with a trailing tone digit
(1-4, 5 or 0 for neutral) and spells ü as ``u:``.  Three conversions are needed:

* ``accented``  — ``han4 yu3`` to ``hàn yǔ``, for display.
* ``toneless_keys`` — ``hanyu`` / ``han yu``, what the user actually types.

Not every whitespace-separated token is a syllable.  ``11區 [11 Qu1]``,
``磕CP [ke1 CP]`` and ``[xx5]`` all occur, so anything that does not match the
syllable grammar is passed through untouched rather than mangled.
"""

from __future__ import annotations

import re

# Tone marks for every vowel that can carry one, in both cases.  Proper nouns
# (歐 Ou1, 中 Zhong1) capitalize the first letter, and for Ou1 that letter *is*
# the marked vowel, so the uppercase rows are load-bearing.
_MARKS: dict[str, tuple[str, str, str, str]] = {
    "a": ("ā", "á", "ǎ", "à"),
    "o": ("ō", "ó", "ǒ", "ò"),
    "e": ("ē", "é", "ě", "è"),
    "i": ("ī", "í", "ǐ", "ì"),
    "u": ("ū", "ú", "ǔ", "ù"),
    "ü": ("ǖ", "ǘ", "ǚ", "ǜ"),
    "v": ("ǖ", "ǘ", "ǚ", "ǜ"),
    "A": ("Ā", "Á", "Ǎ", "À"),
    "O": ("Ō", "Ó", "Ǒ", "Ò"),
    "E": ("Ē", "É", "Ě", "È"),
    "I": ("Ī", "Í", "Ǐ", "Ì"),
    "U": ("Ū", "Ú", "Ǔ", "Ù"),
    "Ü": ("Ǖ", "Ǘ", "Ǚ", "Ǜ"),
    "V": ("Ǖ", "Ǘ", "Ǚ", "Ǜ"),
}

# Syllabic consonants: 呣 m2, 嘸 m1 and friends carry the tone on the consonant
# itself.  Only 7 toned occurrences corpus-wide, but they would otherwise lose
# their mark entirely.  Precomposed where Unicode has it, combining otherwise.
_SYLLABIC: dict[str, tuple[str, str, str, str]] = {
    "n": ("n̄", "ń", "ň", "ǹ"),
    "m": ("m̄", "ḿ", "m̌", "m̀"),
    "N": ("N̄", "Ń", "Ň", "Ǹ"),
    "M": ("M̄", "Ḿ", "M̌", "M̀"),
}

# Vowels searched last-to-first by rule 4 below.  Plain u must be here: without
# it yu3 comes out unmarked and jiu3 marks the wrong vowel (jǐu, not jiǔ).
_VOWELS = "aoeiuüv"

# A syllable is letters (possibly containing ü) plus one tone digit.
_SYLLABLE = re.compile(r"^([A-Za-züÜvV]+)([0-5])$")


def normalize_umlaut(text: str) -> str:
    """``u:`` to ``ü`` and ``U:`` to ``Ü`` (1,000+ entries, e.g. 一律 lu:4)."""
    return text.replace("u:", "ü").replace("U:", "Ü")


def _mark_index(base: str) -> int:
    """Return the index of the vowel that carries the tone mark.

    Standard placement: a wins; else e; else the o of ou; else the last vowel.
    """
    lowered = base.lower()
    if (i := lowered.find("a")) != -1:
        return i
    if (i := lowered.find("e")) != -1:
        return i
    if (i := lowered.find("ou")) != -1:
        return i
    for i in range(len(base) - 1, -1, -1):
        if lowered[i] in _VOWELS:
            return i
    return -1


def accent_syllable(token: str) -> str:
    """Accent a single already-umlaut-normalized token, or return it unchanged.

    ``yi1`` -> ``yī``, ``lü4`` -> ``lǜ``, ``Ou1`` -> ``Ōu``, ``r5`` -> ``r``,
    ``CP`` -> ``CP``, ``11`` -> ``11``.
    """
    match = _SYLLABLE.match(token)
    if match is None:
        return token
    base, tone = match.group(1), int(match.group(2))
    # Neutral tone (5, or 0 in a handful of entries) carries no mark; this is
    # also the erhua path, r5 -> r.
    if tone in (0, 5):
        return base
    index = _mark_index(base)
    if index == -1:
        # No vowel: a syllabic consonant such as m2 (呣) or hng5.
        for i in range(len(base) - 1, -1, -1):
            if (marks := _SYLLABIC.get(base[i])) is not None:
                return base[:i] + marks[tone - 1] + base[i + 1 :]
        return base
    marks = _MARKS.get(base[index])
    if marks is None:
        return base
    return base[:index] + marks[tone - 1] + base[index + 1 :]


def syllable_tone(token: str) -> int:
    """Tone number of a token, or 0 for anything non-syllabic."""
    match = _SYLLABLE.match(token)
    if match is None:
        return 0
    tone = int(match.group(2))
    return 5 if tone == 0 else tone


def tokens(pinyin: str) -> list[str]:
    """Split a pinyin string into umlaut-normalized tokens."""
    return normalize_umlaut(pinyin).split()


def accented(pinyin: str) -> str:
    """Full accented reading, e.g. ``han4 yu3`` -> ``hàn yǔ``."""
    return " ".join(accent_syllable(t) for t in tokens(pinyin))


def accented_syllables(pinyin: str) -> list[tuple[str, int]]:
    """``[(accented_token, tone)]``, for per-syllable tone-colored markup."""
    return [(accent_syllable(t), syllable_tone(t)) for t in tokens(pinyin)]


def _toneless_token(token: str) -> str:
    """Strip the tone digit from a syllable; leave other tokens alone."""
    match = _SYLLABLE.match(token)
    if match is None:
        # 11, CP, and friends: lowercase for matching, but keep the characters.
        return token.lower()
    # ü folds to plain u so that typing "lu" finds 律 lǜ.
    return match.group(1).lower().replace("ü", "u").replace("v", "u")


def toneless_keys(pinyin: str) -> list[str]:
    """Lowercase toneless search keys: the spaced and unspaced forms.

    ``han4 yu3`` -> ``["han yu", "hanyu"]``.  Returns one entry when the two
    forms coincide (single-syllable readings), and an empty list for an empty
    reading.
    """
    parts = [_toneless_token(t) for t in tokens(pinyin)]
    parts = [p for p in parts if p]
    if not parts:
        return []
    spaced = " ".join(parts)
    unspaced = "".join(parts)
    return [spaced] if spaced == unspaced else [spaced, unspaced]
