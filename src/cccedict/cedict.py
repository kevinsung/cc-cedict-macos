"""Parse the CC-CEDICT source file into Entry records.

The source is a plain-text, CRLF-terminated file whose data lines all take the
shape ``TRAD SIMP [pinyin] /sense/sense/``.  Comment lines start with ``#``; a
subset of those (``#! key=value``) carry the header metadata we use for the
version string and front matter.

Entries are keyed on the ``(traditional, simplified)`` pair: a pair that appears
on several source lines (和, 著, 欸, ...) becomes one Entry holding several
Readings, in source order.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Confirmed to match every one of the 124,726 data lines in the source file.
LINE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/$")

HEADER = re.compile(r"^#!\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


class ParseError(Exception):
    """A non-comment line did not match the canonical entry grammar."""


@dataclass(slots=True)
class Reading:
    """One pronunciation of a headword, with the senses recorded under it."""

    pinyin: str
    senses: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Entry:
    """A unique (traditional, simplified) headword and all of its readings."""

    traditional: str
    simplified: str
    readings: list[Reading] = field(default_factory=list)
    # Assigned by build.py once every entry is known; see xref.assign_ids.
    id: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.traditional, self.simplified)

    @property
    def has_distinct_simplified(self) -> bool:
        return self.simplified != self.traditional


@dataclass(slots=True)
class Source:
    """The parsed source file: header metadata plus merged entries."""

    headers: dict[str, str]
    entries: list[Entry]
    lines_consumed: int
    lines_rejected: int

    @property
    def date(self) -> str:
        """The upstream build timestamp, e.g. ``2026-07-29T07:36:56Z``."""
        return self.headers.get("date", "")

    @property
    def declared_entries(self) -> int:
        try:
            return int(self.headers.get("entries", "0"))
        except ValueError:
            return 0


def _open_text(path: Path) -> Iterator[str]:
    """Yield decoded lines from either the .txt or the .txt.gz form."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            yield from fh
    else:
        with path.open("r", encoding="utf-8") as fh:
            yield from fh


def parse(path: Path | str) -> Source:
    """Parse ``path`` into a :class:`Source`.

    Raises :class:`ParseError` on the first unparseable non-comment line — a
    silently dropped entry is the failure mode we least want to ship, so this is
    deliberately fatal rather than a warning.
    """
    path = Path(path)
    headers: dict[str, str] = {}
    entries: list[Entry] = []
    by_key: dict[tuple[str, str], Entry] = {}
    consumed = 0

    for lineno, raw in enumerate(_open_text(path), start=1):
        # The file is CRLF; strip both so the trailing `/` anchors the regex.
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            if (header := HEADER.match(line)) is not None:
                headers[header.group(1)] = header.group(2).strip()
            continue

        match = LINE.match(line)
        if match is None:
            raise ParseError(f"{path}:{lineno}: unparseable entry line: {line!r}")

        traditional, simplified, pinyin, senses_blob = match.groups()
        senses = [s for s in senses_blob.split("/") if s]
        consumed += 1

        key = (traditional, simplified)
        entry = by_key.get(key)
        if entry is None:
            entry = Entry(traditional=traditional, simplified=simplified)
            by_key[key] = entry
            entries.append(entry)
        entry.readings.append(Reading(pinyin=pinyin, senses=senses))

    return Source(
        headers=headers,
        entries=entries,
        lines_consumed=consumed,
        lines_rejected=0,
    )
