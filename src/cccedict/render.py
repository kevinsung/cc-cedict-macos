"""Render Entry records as Apple Dictionary Services XHTML.

Three rules drive the shape of the output.  Two come from Apple's RelaxNG
schema:

* ``d:entry`` is ``zeroOrMore d:index`` *followed by* flow content, so every
  index element must be emitted before the body ``div``.
* Text nodes are XML, so ``&``, ``<`` and ``>`` must be escaped — with 124k
  entries of free text, an unescaped ``&`` is the realistic way to ship a file
  the DDK refuses to compile.

The third comes from the DDK itself: its build pass strips text nodes that are
*entirely* whitespace, so a space between two elements never reaches the
rendered entry (``<span>xìn</span> <span>kǒu</span>`` displays as ``xìnkǒu``).
Every separator here therefore shares a text node with real characters —
trailing it inside the preceding element rather than standing alone between
them.  A ``&#160;`` would survive too, but it would stop long readings from
wrapping in the lookup panel.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from . import pinyin
from .cedict import Entry, Source
from .xref import Index, parse_references, split_classifiers

DICT_NS = "http://www.apple.com/DTDs/DictionaryService-1.0.rng"
XHTML_NS = "http://www.w3.org/1999/xhtml"

FRONT_MATTER_ID = "front_back_matter"

# Han headwords rank above pinyin hits; see README on confirming this during the
# smoke test.
PINYIN_PRIORITY = "2"


def _text(value: str) -> str:
    """Escape a text node."""
    return escape(value)


def _attr(value: str) -> str:
    """Escape an attribute value (quotes included)."""
    return escape(value, {'"': "&quot;"})


def _index(value: str, title: str, priority: str | None = None) -> str:
    parts = [f'<d:index d:value="{_attr(value)}" d:title="{_attr(title)}"']
    if priority is not None:
        parts.append(f' d:priority="{priority}"')
    parts.append("/>")
    return "".join(parts)


def _pinyin_markup(reading: str) -> str:
    """Accented pinyin with each syllable in a tone-classed span.

    The separator lives *inside* the span rather than between spans: see the
    module docstring on whitespace-only text nodes.
    """
    syllables = pinyin.accented_syllables(reading)
    spans = []
    for position, (syllable, tone) in enumerate(syllables, start=1):
        if position < len(syllables):
            syllable += " "
        spans.append(f'<span class="tone{tone}">{_text(syllable)}</span>')
    return "".join(spans)


def _definition(text: str, index: Index) -> str:
    """Definition text with resolvable cross-references turned into links."""
    out = []
    for fragment in parse_references(text, index):
        if fragment.target is None:
            out.append(_text(fragment.text))
            continue
        link = (
            f'<a href="x-dictionary:r:{_attr(fragment.target)}" class="xref">'
            f"{_text(fragment.text)}</a>"
        )
        out.append(link)
        if fragment.reading:
            accented = pinyin.accented(fragment.reading)
            out.append(f'<span class="xref-pinyin">{_text(" " + accented)}</span>')
    return "".join(out)


def entry_indexes(entry: Entry) -> list[str]:
    """The search keys for one entry: Han forms plus toneless pinyin."""
    out = [_index(entry.traditional, entry.traditional)]
    if entry.has_distinct_simplified:
        out.append(
            _index(entry.simplified, f"{entry.simplified} ({entry.traditional})")
        )

    seen: set[str] = set()
    for reading in entry.readings:
        title = f"{entry.traditional} {pinyin.accented(reading.pinyin)}"
        for key in pinyin.toneless_keys(reading.pinyin):
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(_index(key, title, priority=PINYIN_PRIORITY))
    return out


def render_entry(entry: Entry, index: Index) -> str:
    """Render one ``d:entry`` element."""
    parts = [f'<d:entry id="{_attr(entry.id)}" d:title="{_attr(entry.traditional)}">']
    parts.extend(entry_indexes(entry))
    parts.append('<div class="entry">')

    # The separating space is inside the hw-trad span, not between the two.
    if entry.has_distinct_simplified:
        headword = (
            f'<span class="hw-trad">{_text(entry.traditional + " ")}</span>'
            f'<span class="hw-simp">{_text(entry.simplified)}</span>'
        )
    else:
        headword = f'<span class="hw-trad">{_text(entry.traditional)}</span>'
    parts.append(f"<h1>{headword}</h1>")

    for reading in entry.readings:
        parts.append('<div class="reading">')
        parts.append(f'<span class="pinyin">{_pinyin_markup(reading.pinyin)}</span>')

        senses, classifiers = split_classifiers(reading.senses)
        if senses:
            parts.append('<ol class="senses">')
            for sense in senses:
                parts.append(f"<li>{_definition(sense, index)}</li>")
            parts.append("</ol>")
        if classifiers:
            body = "; ".join(_definition(c, index) for c in classifiers)
            parts.append(
                '<div class="classifier">'
                '<span class="label">Classifier </span>'
                f'<span class="value">{body}</span></div>'
            )
        parts.append("</div>")

    parts.append("</div></d:entry>")
    return "".join(parts)


def render_front_matter(source: Source, version: str) -> str:
    """The license / attribution entry, linked from Info.plist.

    CC-CEDICT is CC BY-SA 4.0, so shipping this attribution is a license
    obligation, not a nicety.
    """
    date = _text(source.date or "unknown")
    entries = _text(source.headers.get("entries", "unknown"))
    return f"""<d:entry id="{FRONT_MATTER_ID}" d:title="CC-CEDICT">\
{_index("CC-CEDICT", "CC-CEDICT — About")}\
<div class="front-matter">\
<h1>CC-CEDICT Chinese-English Dictionary</h1>\
<p>A Chinese-English dictionary built from the community-maintained \
<b>CC-CEDICT</b> word list, published by MDBG.</p>\
<h2>Source</h2>\
<ul>\
<li>Source edition: <b>{date}</b> ({entries} entry lines)</li>\
<li>Bundle version: <b>{_text(version)}</b></li>\
<li>Download: <a href="https://www.mdbg.net/chinese/dictionary?page=cc-cedict">\
mdbg.net/chinese/dictionary?page=cc-cedict</a></li>\
<li>Project: <a href="https://cc-cedict.org/wiki/">cc-cedict.org</a></li>\
</ul>\
<h2>License</h2>\
<p>The CC-CEDICT data is distributed under the \
<a href="https://creativecommons.org/licenses/by-sa/4.0/">Creative Commons \
Attribution-ShareAlike 4.0 International License</a> (CC BY-SA 4.0). This \
dictionary bundle is a derivative work and is distributed under the same \
license.</p>\
<h2>Referenced works</h2>\
<p>CEDICT — Copyright &#169; 1997, 1998 Paul Andrew Denisowski.</p>\
<h2>Notes</h2>\
<p>Headwords are listed traditional first, then simplified where the two \
differ. Each entry can be found by its traditional form, its simplified form, \
or its toneless pinyin (with or without spaces, e.g. \
<i>hanyu</i> or <i>han yu</i>).</p>\
</div></d:entry>"""


def document_header() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<d:dictionary xmlns="{XHTML_NS}" xmlns:d="{DICT_NS}">\n'
    )


def document_footer() -> str:
    return "\n</d:dictionary>\n"
