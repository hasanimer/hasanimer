#!/usr/bin/env python3
"""Convert <text> elements in an SVG to outlined <path>s using Geist / Geist Mono.

Usage: python3 outline.py in.svg out.svg

Why: SVGs embedded in a GitHub README are rendered as <img>, which cannot load
web fonts reliably. Outlining makes the typography identical on every viewer.

Supported on <text>/<tspan> (as presentation attributes, inherited from <g>
ancestors too): x, y, dx, font-family (Geist | Geist Mono), font-size (px/num),
font-weight (100-900 | normal | bold), letter-spacing (num | em), text-anchor
(start | middle | end), fill. <tspan> runs flow inline after the previous run;
only <text> may carry x/y. Other attributes on <text> (class, style, opacity,
transform, id, ...) are moved to a wrapper <g> so CSS/animations keep working.
The original string is kept in a data-text attribute on the wrapper <g>.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

# Static Geist / Geist Mono TTFs (OFL). Get them with `npm pack geist` (dist/fonts)
# or from https://github.com/vercel/geist-font/releases, then point GEIST_DIR at them.
FONT_DIR = os.environ.get("GEIST_DIR", os.path.expanduser("~/.fonts"))
WEIGHTS = {100: "Thin", 200: "UltraLight", 300: "Light", 400: "Regular", 500: "Medium",
           600: "SemiBold", 700: "Bold", 800: "Black", 900: "UltraBlack"}
INHERITED = ["font-family", "font-size", "font-weight", "letter-spacing", "text-anchor", "fill"]
TEXT_ATTRS = set(INHERITED) | {"x", "y", "dx", "dy", "font-style", "dominant-baseline", "xml:space"}

_fonts = {}


def tag(el):
    return el.tag.split("}")[-1]


def load_font(family, weight):
    mono = "mono" in family.lower()
    w = min(WEIGHTS, key=lambda k: abs(k - weight))
    name = f"{'GeistMono' if mono else 'Geist'}-{WEIGHTS[w]}.ttf"
    if name not in _fonts:
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            sys.exit(f"outline.py: {path} not found; set GEIST_DIR to a folder with static Geist TTFs")
        blob = hb.Blob.from_file_path(path)
        face = hb.Face(blob)
        font = hb.Font(face)
        tt = TTFont(path)
        _fonts[name] = (font, tt, tt["head"].unitsPerEm, tt.getGlyphSet(), tt.getGlyphOrder())
    return _fonts[name]


def num(v, default=0.0):
    if v is None:
        return default
    m = re.match(r"\s*(-?[\d.]+)", str(v))
    return float(m.group(1)) if m else default


def parse_weight(v):
    if v is None or v == "normal":
        return 400
    if v == "bold":
        return 700
    return int(num(v, 400))


def parse_style(el):
    """Fold text-related properties from a style="" attribute into attributes."""
    style = el.get("style")
    if not style:
        return
    keep = []
    for decl in style.split(";"):
        if ":" not in decl:
            continue
        k, v = [s.strip() for s in decl.split(":", 1)]
        if k in INHERITED and el.get(k) is None:
            el.set(k, v)
        else:
            keep.append(f"{k}:{v}")
    if keep:
        el.set("style", ";".join(keep))
    else:
        del el.attrib["style"]


def shape_run(text, props, pen_x, y):
    family = props.get("font-family", "Geist")
    size = num(props.get("font-size"), 16)
    weight = parse_weight(props.get("font-weight"))
    ls_raw = props.get("letter-spacing", "0")
    ls = num(ls_raw) * size if str(ls_raw).strip().endswith("em") else num(ls_raw)
    font, tt, upem, glyphset, order = load_font(family, weight)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    buf.language = "tr"
    hb.shape(font, buf, {"kern": True, "liga": True})
    scale = size / upem
    d_parts = []
    x = pen_x
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gname = order[info.codepoint]
        gx = x + pos.x_offset * scale
        gy = y - pos.y_offset * scale
        sp = SVGPathPen(glyphset, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        glyphset[gname].draw(TransformPen(sp, (scale, 0, 0, -scale, gx, gy)))
        cmd = sp.getCommands()
        if cmd:
            d_parts.append(cmd)
        x += pos.x_advance * scale + ls
    # browsers apply letter-spacing after every glyph, the last one included
    return "".join(d_parts), x


def effective(el, parents, key):
    node = el
    while node is not None:
        if node.get(key) is not None:
            return node.get(key)
        node = parents.get(node)
    return None


def convert(root):
    parents = {c: p for p in root.iter() for c in p}
    for el in root.iter():
        parse_style(el)
    texts = [el for el in root.iter() if tag(el) == "text"]
    for t in texts:
        base = {k: effective(t, parents, k) for k in INHERITED}
        base = {k: v for k, v in base.items() if v is not None}
        x0, y0 = num(t.get("x")), num(t.get("y"))
        x0 += num(t.get("dx"))
        y0 += num(t.get("dy"))
        runs = []
        if t.text and t.text.strip("\n"):
            runs.append((t.text, dict(base), None))
        for child in list(t):
            if tag(child) == "tspan":
                cprops = dict(base)
                for k in INHERITED:
                    if child.get(k) is not None:
                        cprops[k] = child.get(k)
                if child.get("dx"):
                    runs.append(("", {"__dx": num(child.get("dx"))}, None))
                runs.append((child.text or "", cprops, child.get("fill")))
            if child.tail and child.tail.strip("\n"):
                runs.append((child.tail, dict(base), None))
        # collapse whitespace like default SVG (xml:space default)
        norm = []
        for i, (s, p, f) in enumerate(runs):
            if "__dx" in p:
                norm.append((s, p, f))
                continue
            s = re.sub(r"\s+", " ", s.replace("\n", " "))
            norm.append((s, p, f))
        if norm:
            first = next((i for i, r in enumerate(norm) if "__dx" not in r[1]), None)
            last = max((i for i, r in enumerate(norm) if "__dx" not in r[1]), default=None)
            if first is not None:
                s, p, f = norm[first]
                norm[first] = (s.lstrip(), p, f)
            if last is not None:
                s, p, f = norm[last]
                norm[last] = (s.rstrip(), p, f)
        # first pass: measure
        pen = 0.0
        shaped = []
        for s, p, f in norm:
            if "__dx" in p:
                pen += p["__dx"]
                continue
            d, nx = shape_run(s, p, pen, 0.0)
            shaped.append((s, p, f, pen))
            pen = nx
        width = pen
        anchor = base.get("text-anchor", "start")
        off = {"start": 0.0, "middle": -width / 2, "end": -width}.get(anchor, 0.0)
        g = ET.Element(f"{{{SVG_NS}}}g")
        label = "".join(s for s, p, f in norm if "__dx" not in p)
        for k, v in t.attrib.items():
            if k not in TEXT_ATTRS:
                g.set(k, v)
        if t.get("fill") is not None:
            g.set("fill", t.get("fill"))
        elif "fill" in base and parents.get(t) is not None and effective(parents[t], parents, "fill") != base["fill"]:
            g.set("fill", base["fill"])
        g.set("data-text", label)
        for s, p, f, px in shaped:
            d, _ = shape_run(s, p, x0 + off + px, y0)
            if not d:
                continue
            path = ET.SubElement(g, f"{{{SVG_NS}}}path")
            path.set("d", d)
            if f is not None:
                path.set("fill", f)
        parent = parents[t]
        idx = list(parent).index(t)
        g.tail = t.tail
        parent.remove(t)
        parent.insert(idx, g)
    return root


def main():
    src, dst = sys.argv[1], sys.argv[2]
    tree = ET.parse(src)
    convert(tree.getroot())
    tree.write(dst, encoding="unicode", xml_declaration=False)
    print(f"outlined {src} -> {dst}")


if __name__ == "__main__":
    main()
