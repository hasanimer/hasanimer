"""Glyph-reusing text setter for cards.py.

Why: outline.py turns every character into its own path, so a text-heavy card
(the system index lists ~40 names) outlines to ~200 KB. Here each distinct glyph
(per font, weight and size) is written once, as a one-character <text> inside
<defs>, and every occurrence is a <use> of it. The sources still contain only
<text> for type, so outline.py and compact.py run unchanged; afterwards the
<defs> hold one outlined path per glyph and the card is ~2-3x smaller.

Glyph positions come from the same HarfBuzz shaping outline.py uses (same fonts,
features and language), so the result is identical to outlining whole runs.
A glyph that cannot be reached from a single character (a ligature or a
contextual form) makes its run fall back to an ordinary <text>.
"""
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen

import outline

B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _f(v, nd=2):
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _id(n):
    s = ""
    while True:
        s = B36[n % 36] + s
        n //= 36
        if not n:
            return s


class Setter:
    def __init__(self, prefix="t"):
        self.prefix = prefix
        self.ids = {}        # (family, weight, size, glyph name) -> id
        self.defs = []       # one-glyph <text> sources
        self._iso = {}       # (family, weight) -> {glyph name: char}
        self._seen = {}      # (family, weight) -> set of chars already probed
        self._blank = {}     # glyph name -> True if it has no outline (space)
        self.fallbacks = []  # runs that had to stay plain <text>

    # -- shaping (mirrors outline.shape_run)
    @staticmethod
    def shape(text, family, weight, size, ls=0.0):
        font, tt, upem, glyphset, order = outline.load_font(family, weight)
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        buf.language = "tr"
        hb.shape(font, buf, {"kern": True, "liga": True})
        scale = size / upem
        out, x = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            # (glyph name, glyph x, glyph y, pen x, cluster = index of its first character)
            out.append((order[info.codepoint], x + pos.x_offset * scale, -pos.y_offset * scale, x, info.cluster))
            x += pos.x_advance * scale + ls * size
        return out, x

    def width(self, text, size, weight=400, family="Geist", ls=0.0):
        return self.shape(text, family, weight, size, ls)[1] if text else 0.0

    def _is_blank(self, family, weight, gname):
        key = (family, weight, gname)
        if key not in self._blank:
            font, tt, upem, glyphset, order = outline.load_font(family, weight)
            pen = SVGPathPen(glyphset)
            glyphset[gname].draw(pen)
            self._blank[key] = not pen.getCommands()
        return self._blank[key]

    def _char_for(self, family, weight, gname, text):
        fw = (family, weight)
        m = self._iso.setdefault(fw, {})
        seen = self._seen.setdefault(fw, set())
        for c in text:
            if c in seen or c.isspace():
                continue
            seen.add(c)
            g, _ = self.shape(c, family, weight, 10)
            if len(g) == 1 and g[0][1] == 0 and g[0][2] == 0:
                m.setdefault(g[0][0], c)
        return m.get(gname)

    def _glyph_id(self, family, weight, size, gname, char):
        key = (family, weight, size, gname)
        if key not in self.ids:
            gid = self.prefix + _id(len(self.ids))
            self.ids[key] = gid
            a = f'id="{gid}" x="0" y="0" font-family="{family}" font-size="{_f(size)}"'
            if weight != 400:
                a += f' font-weight="{weight}"'
            self.defs.append(f"<text {a}>{escape(char)}</text>")
        return self.ids[key]

    # -- public
    def runs_width(self, runs, size, weight=400, family="Geist", ls=0.0):
        w = 0.0
        for r in runs:
            w += r.get("dx", 0.0) + self.width(r["t"], r.get("size", size), r.get("weight", weight), family, ls)
        return w

    def line(self, x, y, content, size, fill, weight=400, family="Geist", ls=0.0, anchor=None):
        """One line of text. `content` is a string or a list of runs {t, fill, weight, size, dx}."""
        runs = [{"t": content}] if isinstance(content, str) else content
        placed, pen = [], 0.0
        for r in runs:
            pen += r.get("dx", 0.0)
            rs, rw, rf = r.get("size", size), r.get("weight", weight), r.get("fill", fill)
            glyphs, adv = self.shape(r["t"], family, rw, rs, ls)
            placed.append((r, rs, rw, rf, pen, glyphs))
            pen += adv
        off = {"end": -pen, "middle": -pen / 2}.get(anchor, 0.0)
        x0 = x + off
        out = [f'<g transform="translate({_f(x0)} {_f(y)})" fill="{fill}">']
        for r, rs, rw, rf, start, glyphs in placed:
            text = r["t"]
            # word index of every character (spaces are -1), so a fallback stays word-sized
            wid, k = [], 0
            for i, c in enumerate(text):
                if c == " ":
                    wid.append(-1)
                    if i and text[i - 1] != " ":
                        k += 1
                else:
                    wid.append(k)
            words = text.split()
            groups = {}
            for g in glyphs:
                w = wid[g[4]] if g[4] < len(wid) else -1
                if w >= 0:
                    groups.setdefault(w, []).append(g)
            uses = []
            for w in sorted(groups):
                gl = groups[w]
                mapped = []
                for gname, gx, gy, px, cl in gl:
                    if self._is_blank(family, rw, gname):
                        continue
                    ch = self._char_for(family, rw, gname, text)
                    if ch is None:
                        mapped = None
                        break
                    mapped.append((self._glyph_id(family, rw, rs, gname, ch), gx, gy))
                if mapped is None:
                    # ligature / contextual form: keep this word as plain <text>, which
                    # outline.py shapes exactly as above (same fonts, features, language)
                    self.fallbacks.append(words[w])
                    a = f'x="{_f(start + gl[0][3], 2)}" y="0" font-family="{family}" font-size="{_f(rs)}"'
                    if rw != 400:
                        a += f' font-weight="{rw}"'
                    if ls:
                        a += f' letter-spacing="{_f(ls, 3)}em"'
                    uses.append(f"<text {a}>{escape(words[w])}</text>")
                    continue
                for gid, gx, gy in mapped:
                    ys = f' y="{_f(gy, 1)}"' if abs(gy) > 0.05 else ""
                    uses.append(f'<use href="#{gid}" x="{_f(start + gx, 1)}"{ys}/>')
            if not uses:
                continue
            if rf != fill:
                out.append(f'<g fill="{rf}">' + "".join(uses) + "</g>")
            else:
                out.append("".join(uses))
        out.append("</g>")
        return "".join(out)

    def defs_svg(self):
        return "".join(self.defs)
