"""Extract a valid sub-document from the generated XML, for schema validation.

RelaxNG-validating the full 80 MB file takes minutes and a lot of memory, so the
default pre-flight check validates the front matter, the first N entries, and a
deterministic random sample of N more.  ``make validate-full`` still does the
whole file when that is what you want.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .render import document_footer, document_header

ENTRY_START = "<d:entry"


def _entry_lines(path: Path) -> tuple[list[str], list[str]]:
    """Return (front_matter_lines, entry_lines) from a generated document."""
    front: list[str] = []
    entries: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped.startswith(ENTRY_START):
                continue
            # The front matter is the first entry written; keep it always, since
            # Info.plist references its id.
            if not front and 'id="front_back_matter"' in stripped:
                front.append(stripped)
            else:
                entries.append(stripped)
    return front, entries


def sample(
    source: Path,
    target: Path,
    *,
    head: int = 5000,
    random_count: int = 5000,
    seed: int = 0,
) -> int:
    front, entries = _entry_lines(source)
    if not entries:
        raise SystemExit(f"no entries found in {source}")

    chosen = list(range(min(head, len(entries))))
    remaining = range(len(chosen), len(entries))
    if random_count and remaining:
        rng = random.Random(seed)
        chosen.extend(rng.sample(list(remaining), min(random_count, len(remaining))))
    chosen.sort()

    with target.open("w", encoding="utf-8", newline="\n") as out:
        out.write(document_header())
        for line in front:
            out.write(line + "\n")
        for position in chosen:
            out.write(entries[position] + "\n")
        out.write(document_footer())

    return len(front) + len(chosen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--head", type=int, default=5000)
    parser.add_argument("--random", dest="random_count", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"not found: {args.source}", file=sys.stderr)
        return 1

    args.target.parent.mkdir(parents=True, exist_ok=True)
    count = sample(
        args.source,
        args.target,
        head=args.head,
        random_count=args.random_count,
        seed=args.seed,
    )
    print(f"wrote {args.target} with {count:,} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
