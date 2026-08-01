"""Cross-references and classifiers inside definition text.

CC-CEDICT definitions embed references to other headwords in two shapes::

    see also 中文[Zhong1 wen2]
    classifier for ... 個|个[ge4]

i.e. a Han run, optionally ``traditional|simplified``, followed by a bracketed
reading.  17,899 definitions carry at least one.  Resolving them to
``x-dictionary:r:`` links makes those clickable inside Dictionary.app.

Resolution is two-pass by necessity: every entry must already own a stable id
before any definition can be rewritten, because a reference may point forward.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .cedict import Entry

# CJK ideographs plus the extension A block and the compatibility forms that
# actually occur as headword characters, followed by an optional |simplified
# and a bracketed reading.
_HAN = r"[㐀-䶿一-鿿豈-﫿〇]"
XREF = re.compile(rf"({_HAN}+)(?:\|({_HAN}+))?\[([^\]]*)\]")

# A sense that is purely a classifier listing, e.g. "CL:個|个[ge4],位[wei4]".
CLASSIFIER_PREFIX = "CL:"


@dataclass(slots=True)
class Index:
    """Lookup tables used to resolve a reference to an entry id."""

    by_pair: dict[tuple[str, str], str]
    by_traditional: dict[str, list[str]]
    by_simplified: dict[str, list[str]]

    def resolve(self, traditional: str, simplified: str | None) -> str | None:
        """Return the id a reference points at, or None if it is ambiguous.

        A reference that names both forms is matched exactly.  A single-form
        reference links only when exactly one entry can be meant — guessing
        between homographs would produce links that go somewhere wrong, which is
        worse than leaving the text plain.
        """
        if simplified is not None:
            if (found := self.by_pair.get((traditional, simplified))) is not None:
                return found
            # Some references write trad|simp where the two forms are identical
            # in our data, or name a pair we merged differently.
            if traditional == simplified:
                return self._unique(self.by_traditional.get(traditional))
            return None
        if (found := self.by_pair.get((traditional, traditional))) is not None:
            return found
        if (found := self._unique(self.by_traditional.get(traditional))) is not None:
            return found
        return self._unique(self.by_simplified.get(traditional))

    @staticmethod
    def _unique(ids: list[str] | None) -> str | None:
        if ids is not None and len(ids) == 1:
            return ids[0]
        return None


def assign_ids(entries: list[Entry]) -> None:
    """Give every entry a stable, XML-``ID``-valid id, in source order.

    ``e`` + a zero-padded sequence: letter-initial as the ID datatype demands,
    and identical across rebuilds of the same source file.
    """
    width = max(7, len(str(len(entries))))
    for number, entry in enumerate(entries):
        entry.id = f"e{number:0{width}d}"


def build_index(entries: list[Entry]) -> Index:
    """Build the reference-resolution tables. Requires ids to be assigned."""
    by_pair: dict[tuple[str, str], str] = {}
    by_traditional: dict[str, list[str]] = {}
    by_simplified: dict[str, list[str]] = {}
    for entry in entries:
        by_pair[entry.key] = entry.id
        by_traditional.setdefault(entry.traditional, []).append(entry.id)
        if entry.has_distinct_simplified:
            by_simplified.setdefault(entry.simplified, []).append(entry.id)
    return Index(
        by_pair=by_pair,
        by_traditional=by_traditional,
        by_simplified=by_simplified,
    )


def split_classifiers(senses: list[str]) -> tuple[list[str], list[str]]:
    """Separate ``CL:`` senses from the rest.

    Returns ``(ordinary_senses, classifier_blobs)``; the classifier text keeps
    its raw form so it can go through the same reference rewriting.
    """
    ordinary: list[str] = []
    classifiers: list[str] = []
    for sense in senses:
        if sense.startswith(CLASSIFIER_PREFIX):
            classifiers.append(sense[len(CLASSIFIER_PREFIX) :])
        else:
            ordinary.append(sense)
    return ordinary, classifiers


@dataclass(slots=True)
class Fragment:
    """A run of definition text: either plain, or a resolved reference."""

    text: str
    target: str | None = None
    reading: str | None = None


def parse_references(text: str, index: Index) -> list[Fragment]:
    """Split ``text`` into plain and reference fragments.

    Unresolvable references come back as plain text carrying their original
    spelling, so nothing is ever dropped from a definition.
    """
    fragments: list[Fragment] = []
    position = 0
    for match in XREF.finditer(text):
        if match.start() > position:
            fragments.append(Fragment(text[position : match.start()]))
        traditional, simplified, reading = match.groups()
        target = index.resolve(traditional, simplified)
        if target is None:
            fragments.append(Fragment(match.group(0)))
        else:
            display = traditional if simplified is None else f"{traditional}|{simplified}"
            fragments.append(Fragment(display, target=target, reading=reading))
        position = match.end()
    if position < len(text):
        fragments.append(Fragment(text[position:]))
    return fragments
