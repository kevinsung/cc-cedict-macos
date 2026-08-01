# CC-CEDICT for macOS Dictionary.app

Build a `.dictionary` bundle for Dictionary.app from
[CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict), the
community-maintained Chinese-English dictionary published by MDBG.

## Why macOS only

The bundle's binary payload (`Body.data`, `KeyText.index`, `KeyText.data`,
`EntryID.index`) is written by Apple's Dictionary Development Kit, which ships
only as macOS Mach-O binaries. There is no open-source writer for it — the
`KeyText.index` trie has never been fully reverse-engineered, and pyglossary's
AppleDict writer also emits source and then shells out to the DDK. So the whole
build runs on a Mac: fetch, parse, romanize, render, compile, install.

Before the DDK ever sees it, the generated XML can be validated against
**Apple's own RelaxNG schema** (`make check`), which establishes acceptance of
the file independently of the DDK's error reporting.

## Requirements

- macOS, with the Xcode command line tools: `xcode-select --install`
- The Dictionary Development Kit at
  `/Applications/Utilities/Dictionary Development Kit`, from
  ["Additional Tools for Xcode"](https://developer.apple.com/download/all/?q=Additional%20Tools)
  (download the disk image matching your Xcode version and copy
  `Dictionary Development Kit` out of `Utilities`), or from the community mirror
  at [SebastianSzturo/Dictionary-Development-Kit](https://github.com/SebastianSzturo/Dictionary-Development-Kit).
  `make check-ddk` reports whether it is where the build expects.
- Python 3, standard library only — no third-party packages. Exercised on 3.14;
  nothing newer than 3.9 syntax is used, so the system `python3` should do.
- `curl`, `make`, `gzip`, and `xmllint`, all of which macOS ships.

## Usage

```sh
make            # fetch, generate, and compile (a few minutes for 122k entries)
make install    # -> ~/Library/Dictionaries
```

Enable **CC-CEDICT** in Dictionary.app > Settings (a relaunch is sometimes
needed).

Re-running `make` asks MDBG whether a newer edition has been published; if not,
the download is skipped and nothing rebuilds. So `make install` is also how you
update. If MDBG is unreachable, the build warns and continues from the cached
copy in `data/`.

### Individual targets

| Target | Does |
|---|---|
| `fetch` | download the source into `data/`, if MDBG has a newer edition |
| `source` | generate `build/CC-CEDICT.dictionary-src/` |
| `check-ddk` | report whether the Dictionary Development Kit is present |
| `bundle` | compile `build/CC-CEDICT.dictionary-src/objects/CC-CEDICT.dictionary` |
| `install` / `uninstall` | copy into / remove from `~/Library/Dictionaries` |
| `schema` | mirror Apple's RelaxNG schema into `schema/` |
| `wellformed` | `xmllint --noout` on the generated XML |
| `validate` | full-file RelaxNG validation (~20s, ~1.1 GB RAM) |
| `validate-sample` | front matter + 5,000 head + 5,000 random (~1s) |
| `lint` | id uniqueness, index coverage, dangling cross-references |
| `test` | unit tests |
| `check` | `test` + `wellformed` + `lint` + `validate` |
| `clean` / `distclean` | remove `build/` (and `data/` `schema/`) |

Validation is deliberately off the default path — the full RelaxNG pass alone
costs ~20s and ~1.1 GB, which is not worth paying on every rebuild.

## Smoke test

After `make install`, in Dictionary.app:

| Lookup | Expected |
|---|---|
| `漢語` / `汉语` | the same single entry from either script |
| `hanyu`, `han yu` | the same entry via toneless pinyin |
| `和` | one entry with several readings stacked |
| `一律` | displays `yī lǜ` with the u-umlaut |
| `信口開河` | `xìn kǒu kāi hé` — spaced, and no numbered form beside it |
| `上級` | a Classifier row, with a clickable link |
| `11區` | the non-syllabic pinyin token survived |
| `不起眼兒` | erhua renders as a bare r |
| About/front matter | license and attribution reachable |

If the DDK reports an error it names the offending entry id (`eNNNNNNN`), which
maps back to the entry's position in the source file.

## Design decisions

**One entry per (traditional, simplified) pair.** 124,726 source lines collapse
to 122,235 entries; 2,267 pairs have more than one reading (和 has six) and
those stack as separate reading blocks inside a single entry rather than
appearing as duplicate search results. Traditional is the primary headword.

**Search keys.** Every entry is indexed under its traditional form, its
simplified form (omitted when identical, which is ~85% of entries), and its
**toneless** pinyin in both spaced and unspaced form — `han yu` and `hanyu` both
find 漢語. The accented reading is *displayed* but not indexed: indexing it
would multiply the key count without matching how people type. `ü` folds to `u`
in keys, so `lu` finds 律 lǜ.

Pinyin indexes carry `d:priority="2"` so that Han matches rank above them.

**Cross-references.** Definitions embed references as `中文[Zhong1 wen2]` or
`個|个[ge4]`. Ids are assigned in a first pass so that forward references work,
then 19,114 of 19,683 references (97.1%) resolve to `x-dictionary:r:` links.
The remaining 569 name a headword that is ambiguous or absent; those stay as
plain text rather than linking somewhere wrong.

**Classifiers.** 1,481 senses that begin with `CL:` are lifted out into a
separate Classifier row. 90 others appear parenthetically mid-sense
(`light; ray (CL:道[dao4])`) and are left in place — the classifier headword is
still linked, but removing the text would break the surrounding sentence.

**Readings display accented only.** `xìn kǒu kāi hé`, not the source's
`xin4 kou3 kai1 he2` alongside it. The numbered form is what the *data* looks
like, not what a reader wants to read, and it cost 5.4 MB of XML.

**No whitespace between elements.** The DDK's build pass strips text nodes that
are entirely whitespace, so `<span>xìn</span> <span>kǒu</span>` compiles to
`xìnkǒu`. Every separator in the markup instead shares a text node with real
characters — the space after a syllable is *inside* that syllable's span. A
`&#160;` would survive too, but it would stop long readings from wrapping in the
lookup panel. `tests/test_render.py` asserts no whitespace-only text node
survives rendering, since the failure is invisible until the bundle is compiled
and opened.

**Tone colors** ship in `assets/CCCEDICT.css` but commented out. Each pinyin
syllable is wrapped in `<span class="tone1">`…`tone5` (`tone0` for non-syllabic
tokens like the `11` of 11區), so enabling color is a CSS edit and a rebuild,
not a regeneration of the XML.

**Entry ids** are `e` + a zero-padded sequence in source order: a valid XML `ID`
(letter-initial) and stable across rebuilds, so a DDK error naming `e0066338`
maps straight back to an entry.

## Awkward data this handles

The source is not uniformly well-behaved, and these are the cases worth knowing
about:

| Input | Output | Why it matters |
|---|---|---|
| `yi1 lu:4` | `yī lǜ` | `u:` is the ASCII spelling of `ü` |
| `Ou1` (歐) | `Ōu` | proper nouns capitalize the vowel that takes the mark |
| `jiu3` | `jiǔ` | the mark goes on the *last* vowel of `iu`, not the first |
| `11 Qu1` (11區) | `11 Qū` | not every token is a syllable |
| `ke1 CP` (磕CP) | `kē CP` | Latin letters appear in readings |
| `bu4 qi3 yan3 r5` | `bù qǐ yǎn r` | erhua is a toneless `r` |
| `m2` (呣) | `ḿ` | syllabic consonants have no vowel to mark |
| `xx5` | `xx` | placeholder readings exist |

The parser **fails the build** on any non-comment line it cannot parse, rather
than skipping it — a silently dropped entry is the failure mode least likely to
be noticed.

## Verification status

`make check` passes against the 2026-08-01 source edition:

- 74 unit tests
- 124,726 lines parsed, 0 rejected, 122,235 entries emitted
- 75.5 MB of XML, well-formed
- validates against Apple's RelaxNG schema (**full file**, not a sample)
- lint: 122,236 entries, 432,380 indexes, 0 duplicate ids, 0 dangling references

The DDK compile has not yet been run in this repo, so the smoke-test table above
is what to check the first time it is.

One item to confirm there: `d:priority="2"` is legal per Apple's schema and is
intended to rank Han matches above pinyin ones, but the actual ranking behavior
is only observable in Dictionary.app. Drop the attribute from `render.py` if it
does not behave as intended.

## Layout

```
Makefile                  the whole build: fetch, generate, compile, install
assets/
  CCCEDICT.css            styling (tone colors commented out)
  Info.plist.tmpl         bundle metadata template
src/cccedict/
  cedict.py               source file -> Entry records
  pinyin.py               u: -> ü, numbered -> accented, toneless keys
  xref.py                 cross-references and classifiers
  render.py               Entry -> XHTML
  build.py                orchestration
  lint.py                 structural checks
  sample.py               sub-document extraction for fast validation
  schema.py               mirror Apple's RelaxNG schema
tests/
```

## License

The source code in this repository is licensed under the [MIT License](LICENSE).

CC-CEDICT is distributed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The generated
dictionary is a derivative work under the same license, and carries the
attribution and the CEDICT copyright notice in its front matter.
