"""Mirror Apple's RelaxNG dictionary schema for offline validation.

Apple no longer serves the schema at ``www.apple.com/DTDs/`` (that URL returns a
marketing 404 page), so the copy shipped with the Dictionary Development Kit is
used instead.  That schema pulls in 26 XHTML modules from ``thaiopensource.com``,
whose URLs 302-redirect; ``xmllint`` does not follow redirects, so validating
against the live URLs fails.

The fix is to mirror every module locally and rewrite each ``href`` to a bare
filename, flattening the graph into one directory.  Modules are deduplicated by
basename: ``thaiopensource.com/relaxng/xhtml/...`` and
``relaxng.org/jclark/xhtml/...`` are the same files under two hostnames.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "schema"

DDK_BASE = (
    "https://raw.githubusercontent.com/SebastianSzturo/"
    "Dictionary-Development-Kit/master/documents/DictionarySchema/"
)
MAIN_SCHEMA = DDK_BASE + "AppleDictionarySchema.rng"
MAIN_NAME = "AppleDictionarySchema.rng"

HREF = re.compile(r'href="([^"]+)"')

USER_AGENT = "cccedict-schema-mirror/1.0"


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # urllib follows the thaiopensource 302s that xmllint will not.
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def _local_name(url: str) -> str:
    """Flatten a module URL to the bare filename it will be stored under."""
    return url.rsplit("/", 1)[-1]


def mirror(target: Path = DEFAULT_DIR, *, verbose: bool = True) -> int:
    """Download the schema graph into ``target``. Returns the file count."""
    target.mkdir(parents=True, exist_ok=True)

    pending: list[tuple[str, str]] = [(MAIN_SCHEMA, MAIN_NAME)]
    done: set[str] = set()
    count = 0

    while pending:
        url, name = pending.pop()
        if name in done:
            continue
        done.add(name)

        try:
            text = _fetch(url)
        except (urllib.error.URLError, urllib.error.HTTPError) as error:
            raise SystemExit(f"failed to fetch {url}: {error}") from error

        for href in HREF.findall(text):
            child_url = urljoin(url, href)
            child_name = _local_name(child_url)
            if child_name not in done:
                pending.append((child_url, child_name))

        # Every reference becomes a sibling filename, so the whole graph
        # resolves inside this one directory.
        rewritten = HREF.sub(lambda m: f'href="{_local_name(m.group(1))}"', text)
        (target / name).write_text(rewritten, encoding="utf-8")
        count += 1
        if verbose:
            print(f"  {name}")

    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    print(f"mirroring RelaxNG schema into {args.target}", file=sys.stderr)
    count = mirror(args.target, verbose=not args.quiet)
    print(f"{count} files; entry point: {args.target / MAIN_NAME}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
