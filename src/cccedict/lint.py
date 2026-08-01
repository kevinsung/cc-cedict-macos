"""Structural checks on the generated XML.

These are the invariants the RelaxNG schema does not express: that ids are
unique and well-formed, that every entry is reachable through at least one
non-empty index, and that no cross-reference points at an id that does not
exist.  A dangling ``x-dictionary:r:`` link compiles fine and then dead-ends in
the UI, so it has to be caught here.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from .render import DICT_NS, XHTML_NS

# The XML ID datatype: a name that may not start with a digit.
XML_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")

ENTRY = f"{{{DICT_NS}}}entry"
INDEX = f"{{{DICT_NS}}}index"
D_VALUE = f"{{{DICT_NS}}}value"
ANCHOR = f"{{{XHTML_NS}}}a"

REF_SCHEME = "x-dictionary:r:"


class Problems:
    """Collected findings, capped so a systematic fault does not flood stdout."""

    LIMIT = 20

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.samples: dict[str, list[str]] = {}

    def add(self, kind: str, detail: str) -> None:
        self.counts[kind] += 1
        samples = self.samples.setdefault(kind, [])
        if len(samples) < self.LIMIT:
            samples.append(detail)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def report(self, out) -> None:
        for kind, count in self.counts.most_common():
            print(f"{kind}: {count}", file=out)
            for sample in self.samples[kind]:
                print(f"    {sample}", file=out)
            if count > len(self.samples[kind]):
                print(f"    ... and {count - len(self.samples[kind])} more", file=out)


def lint(path: Path) -> tuple[Problems, dict[str, int]]:
    problems = Problems()
    ids: set[str] = set()
    references: list[tuple[str, str]] = []
    entry_count = 0
    index_count = 0

    for event, element in ElementTree.iterparse(path, events=("end",)):
        if element.tag != ENTRY:
            continue
        entry_count += 1
        entry_id = element.get("id")

        if not entry_id:
            problems.add("entry missing id", f"entry #{entry_count}")
        else:
            if entry_id in ids:
                problems.add("duplicate id", entry_id)
            ids.add(entry_id)
            if not XML_ID.match(entry_id):
                problems.add("id is not a valid XML ID", entry_id)

        indexes = element.findall(INDEX)
        if not indexes:
            problems.add("entry has no d:index", entry_id or f"#{entry_count}")
        for index in indexes:
            index_count += 1
            value = index.get(D_VALUE)
            if value is None or not value.strip():
                problems.add("empty d:value", entry_id or f"#{entry_count}")

        for anchor in element.iter(ANCHOR):
            href = anchor.get("href", "")
            if href.startswith(REF_SCHEME):
                references.append((entry_id or "?", href[len(REF_SCHEME) :]))

        # 80 MB of XML: drop each entry once it has been checked.
        element.clear()

    for source_id, target in references:
        if target not in ids:
            problems.add("dangling cross-reference", f"{source_id} -> {target}")

    stats = {
        "entries": entry_count,
        "indexes": index_count,
        "references": len(references),
    }
    return problems, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"not found: {args.path}", file=sys.stderr)
        return 1

    problems, stats = lint(args.path)
    print(
        f"{stats['entries']:,} entries, {stats['indexes']:,} indexes, "
        f"{stats['references']:,} cross-references"
    )
    if problems.total:
        problems.report(sys.stderr)
        print(f"\nlint FAILED: {problems.total} problems", file=sys.stderr)
        return 1
    print("lint OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
