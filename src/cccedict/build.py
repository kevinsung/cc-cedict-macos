"""Generate the AppleDict source project under build/.

The output directory holds the three files the Dictionary Development Kit is
handed — ``CCCEDICT.xml``, ``CCCEDICT.css``, ``Info.plist`` — which the root
``Makefile`` then compiles into the bundle.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from . import render
from .cedict import parse
from .xref import assign_ids, build_index

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"

DEFAULT_SOURCE = ROOT / "data" / "cedict.txt"
DEFAULT_OUTPUT = ROOT / "build" / "CC-CEDICT.dictionary-src"

BUNDLE_ID = "org.cc-cedict.dictionary.CC-CEDICT"
BUNDLE_NAME = "CC-CEDICT"
BUNDLE_DISPLAY_NAME = "CC-CEDICT Chinese-English"
MANUFACTURER = "CC-CEDICT / MDBG"
COPYRIGHT = (
    "CC-CEDICT is licensed under the Creative Commons "
    "Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0). "
    "Published by MDBG. Referenced work: CEDICT, "
    "Copyright © 1997, 1998 Paul Andrew Denisowski."
)

# Expected shape of the upstream file, asserted so that a silently truncated or
# reformatted download fails the build instead of shipping a partial dictionary.
EXPECTED_MIN_LINES = 120_000


def version_from_date(date: str) -> str:
    """Turn the upstream ``#! date`` into a CFBundleShortVersionString.

    ``2026-07-29T07:36:56Z`` -> ``2026.7.29``.  Falls back to ``0.0.0`` when the
    header is missing or unrecognizable.
    """
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date or "")
    if match is None:
        return "0.0.0"
    year, month, day = match.groups()
    return f"{year}.{int(month)}.{int(day)}"


def render_info_plist(version: str) -> str:
    template = (ASSETS / "Info.plist.tmpl").read_text(encoding="utf-8")
    substitutions = {
        "@BUNDLE_ID@": BUNDLE_ID,
        "@BUNDLE_NAME@": BUNDLE_NAME,
        "@BUNDLE_DISPLAY_NAME@": BUNDLE_DISPLAY_NAME,
        "@VERSION@": version,
        "@COPYRIGHT@": COPYRIGHT,
        "@MANUFACTURER@": MANUFACTURER,
        "@FRONT_MATTER_ID@": render.FRONT_MATTER_ID,
    }
    for placeholder, value in substitutions.items():
        template = template.replace(placeholder, value)
    return template


def build(source_path: Path, output_dir: Path, *, strict: bool = True) -> dict[str, int]:
    """Generate the source project. Returns a few counts for reporting."""
    source = parse(source_path)

    if strict:
        if source.lines_consumed < EXPECTED_MIN_LINES:
            raise SystemExit(
                f"only {source.lines_consumed} entry lines parsed from {source_path}; "
                f"expected at least {EXPECTED_MIN_LINES}. Refusing to build a "
                "partial dictionary."
            )
        declared = source.declared_entries
        if declared and declared != source.lines_consumed:
            raise SystemExit(
                f"header declares {declared} entries but {source.lines_consumed} "
                "lines were parsed."
            )

    assign_ids(source.entries)
    index = build_index(source.entries)
    version = version_from_date(source.date)

    output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = output_dir / "CCCEDICT.xml"

    with xml_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write(render.document_header())
        out.write(render.render_front_matter(source, version))
        out.write("\n")
        for entry in source.entries:
            out.write(render.render_entry(entry, index))
            out.write("\n")
        out.write(render.document_footer())

    shutil.copyfile(ASSETS / "CCCEDICT.css", output_dir / "CCCEDICT.css")
    (output_dir / "Info.plist").write_text(render_info_plist(version), encoding="utf-8")

    return {
        "lines": source.lines_consumed,
        "entries": len(source.entries),
        "bytes": xml_path.stat().st_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="skip the entry-count sanity checks (for building from a sample)",
    )
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"source not found: {args.source}\nRun `make fetch` first.", file=sys.stderr)
        return 1

    stats = build(args.source, args.output, strict=not args.no_strict)
    print(
        f"parsed {stats['lines']:,} lines -> {stats['entries']:,} entries\n"
        f"wrote {args.output}/CCCEDICT.xml ({stats['bytes'] / 1e6:.1f} MB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
