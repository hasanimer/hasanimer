#!/usr/bin/env python3
"""System index card and principles card for the profile README.

Usage: python3 cards.py OUTDIR
Writes OUTDIR/system.svg, system-mobile.svg, principles.svg, principles-mobile.svg
as SVG sources with <text> (build.sh outlines and compacts them into ../assets/).

All content, every <title> and every aria-label come from data.json; the only
strings kept here are the eyebrow words and the system card's header note.
Text is measured with the vendored outline.py (same shaper and fonts as the
build), so wrapping and alignment are exact. Type is set through _cards_glyphs
(each distinct glyph is one <text> in <defs>, reused with <use>), which keeps the
outlined cards far under the 140 KB budget. Importing this module has no side
effects: readme.py may call system_alt() / principles_alt() for the README alt text.
"""
import functools
import json
import os
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outline  # noqa: E402
from _cards_glyphs import Setter  # noqa: E402

with open(os.path.join(HERE, "data.json"), encoding="utf-8") as fh:
    DATA = json.load(fh)

# ---------------------------------------------------------------- tokens (shared card system)
BG = "#070a12"
LINE = "#1c2436"
TEXT = "#e8ecf4"
TEXT2 = "#c3cad8"
MUTED = "#8d97ab"
SEP = "#525d74"          # item separators: present, but quieter than any text
CORE = "#f2b35b"
CORE_HI = "#ffe2a8"
CORE_MID = "#ffd27d"
LAYER = {"core": CORE, "infra": "#f0866a", "product": "#5fd0c5", "bridge": "#b58cff", "source": "#7c8aa5"}
SANS, MONO = "Geist", "Geist Mono"

EYEBROW_SYSTEM = ("Sistem", "The system")
EYEBROW_PRINCIPLES = ("İlkeler", "Principles")
SYSTEM_NOTE = ("{hub} haritasındaki katmanlar", "Layers of the {hub} map")

# per-variant metrics: desktop viewBox 1200, mobile viewBox 600
DESK = dict(W=1200, PAD=56, eyebrow=14, rule_gap=24)
MOB = dict(W=600, PAD=32, eyebrow=17, rule_gap=21)


# ---------------------------------------------------------------- helpers
def tr_upper(s):
    """Turkish uppercase: i -> İ, ı -> I."""
    return s.replace("i", "İ").replace("ı", "I").upper()


def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


@functools.lru_cache(maxsize=None)
def tw(text, size, weight=400, family=SANS, ls=0.0):
    """Advance width of a run exactly as outline.py lays it out (ls in em)."""
    if not text:
        return 0.0
    _, x = outline.shape_run(text, {"font-family": family, "font-size": str(size),
                                    "font-weight": str(weight), "letter-spacing": f"{ls}em"}, 0, 0)
    return x


def runs_width(runs, size, weight=400, family=SANS, ls=0.0):
    w = 0.0
    for r in runs:
        w += r.get("dx", 0.0)
        w += tw(r["t"], r.get("size", size), r.get("weight", weight), family, ls)
    return w


def wrap(text, width, size, weight=400, family=SANS):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and tw(trial, size, weight, family) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def wrap_bal(text, width, size, weight=400, family=SANS):
    """Fewest lines (greedy count), but with the line lengths evened out."""
    n = len(wrap(text, width, size, weight, family))
    if n <= 1:
        return wrap(text, width, size, weight, family)
    lo, hi = width * 0.3, width
    for _ in range(30):
        mid = (lo + hi) / 2
        if len(wrap(text, mid, size, weight, family)) <= n:
            hi = mid
        else:
            lo = mid
    return wrap(text, hi + 0.01, size, weight, family)


def wrap_nice(text, width, size, weight=400, family=SANS):
    """Greedy at full measure; balanced only if the last line would be a single word."""
    lines = wrap(text, width, size, weight, family)
    if len(lines) > 1 and " " not in lines[-1]:
        return wrap_bal(text, width, size, weight, family)
    return lines


def item_runs(it, fill, size, first, gap):
    """Runs for one list item: name, optional muted '(note)', preceded by a separator."""
    runs = []
    if not first:
        runs.append({"t": "·", "fill": SEP, "dx": gap})
        runs.append({"t": it["name"], "fill": fill, "dx": gap})
    else:
        runs.append({"t": it["name"], "fill": fill})
    if it.get("note"):
        runs.append({"t": f" ({it['note']})", "fill": MUTED})
    return runs


def wrap_items(items, width, size, fill, gap):
    """Break a list only between items (a name is never split). Returns a list of run lists."""
    lines, cur = [], []
    for it in items:
        trial = cur + [it]
        runs = [r for k, x in enumerate(trial) for r in item_runs(x, fill, size, k == 0, gap)]
        if cur and runs_width(runs, size) > width:
            lines.append(cur)
            cur = [it]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def wrap_items_bal(items, width, size, fill, gap):
    n = len(wrap_items(items, width, size, fill, gap))
    if n > 1:
        lo, hi = width * 0.3, width
        for _ in range(30):
            mid = (lo + hi) / 2
            if len(wrap_items(items, mid, size, fill, gap)) <= n:
                hi = mid
            else:
                lo = mid
        width = hi + 0.01
    return [[r for k, x in enumerate(line) for r in item_runs(x, fill, size, k == 0, gap)]
            for line in wrap_items(items, width, size, fill, gap)]


def doc(w, h, title, label, body, style=""):
    q = {'"': "&quot;"}
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(label, q)}" fill="none">\n'
            f"<title>{escape(title)}</title>\n{style}{body}\n</svg>\n")


def card_rect(w, h):
    return f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="16" fill="{BG}" stroke="{LINE}"/>'


def rule(x1, x2, y):
    return f'<path d="M{f(x1)} {f(y + .5)}H{f(x2)}" stroke="{LINE}"/>'


def header(T, V, tr, en, right=None):
    """Amber mono eyebrow at the top-left; optional right-aligned note; hairline under the row.
    Returns (svg, y of the hairline)."""
    W, PAD, s = V["W"], V["PAD"], V["eyebrow"]
    base = PAD + round(s * 0.72)          # cap top sits on the padding line
    out = [T(PAD, base, f"{tr_upper(tr)} · {en.upper()}", s, CORE, family=MONO, ls=0.14)]
    if right:
        out.append(T(W - PAD, base, right, 15, MUTED, anchor="end"))
    y = base + V["rule_gap"]
    out.append(rule(PAD, W - PAD, y))
    return "\n".join(out), y


def sphere_defs(prefix):
    out = []
    for name, c in LAYER.items():
        out.append(f'<radialGradient id="{prefix}s-{name}" cx=".34" cy=".3" r=".78">'
                   f'<stop offset="0" stop-color="{mix(c, "#ffffff", .5)}"/><stop offset=".45" stop-color="{c}"/>'
                   f'<stop offset="1" stop-color="{mix(c, BG, .62)}"/></radialGradient>')
    out.append(f'<radialGradient id="{prefix}corona"><stop offset="0" stop-color="{CORE_HI}"/>'
               f'<stop offset=".34" stop-color="{CORE_MID}" stop-opacity=".9"/>'
               f'<stop offset=".62" stop-color="{CORE}" stop-opacity=".28"/>'
               f'<stop offset="1" stop-color="{CORE}" stop-opacity="0"/></radialGradient>')
    out.append(f'<radialGradient id="{prefix}disk" cx=".42" cy=".38" r=".7"><stop offset="0" stop-color="#fffaf0"/>'
               f'<stop offset=".55" stop-color="{CORE_HI}"/><stop offset="1" stop-color="{CORE_MID}"/></radialGradient>')
    return "".join(out)


def layer_dot(prefix, layer, x, y, s=1.0):
    """The layer's body, as on the map: sun, planet sphere, or a cluster of belt rocks."""
    if layer == "core":
        return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(10 * s)}" fill="url(#{prefix}corona)"/>'
                f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(4.6 * s)}" fill="url(#{prefix}disk)"/>')
    if layer == "source":
        pts = [(-4.3, 1.9, 1.7), (0.4, -2.6, 2.1), (4.6, 1.2, 1.6), (-0.5, 3.8, 1.2), (3.2, -4.6, .9)]
        return "".join(f'<circle cx="{f(x + dx * s)}" cy="{f(y + dy * s)}" r="{f(r * s)}" fill="url(#{prefix}s-source)"/>'
                       for dx, dy, r in pts)
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(8.5 * s)}" fill="{LAYER[layer]}" fill-opacity=".12"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(5 * s)}" fill="url(#{prefix}s-{layer})"/>')


# ---------------------------------------------------------------- alt / aria text (from data.json)
def _items_text(items):
    return ", ".join(it["name"] + (f" ({it['note']})" if it.get("note") else "") for it in items)


def system_alt():
    hub = DATA["identity"]["hub"]
    parts = [f"{EYEBROW_SYSTEM[0]} · {EYEBROW_SYSTEM[1]}: {SYSTEM_NOTE[0].format(hub=hub)}."]
    for L in DATA["system"]:
        head = f"{L['label_tr']} ({L['label_en']})"
        if "title" in L:
            s = f"{head}: {L['title']}, {L['domain']}."
            if L.get("motto"):
                s += f" “{L['motto']}”"
            s += f" {L['desc_tr']} {L['desc_en']}"
        else:
            s = f"{head}: {_items_text(L['items'])}."
        parts.append(s)
    parts.append(f"{DATA['caption_tr']} {DATA['caption_en']}")
    return " ".join(parts)


def principles_alt():
    parts = [f"{EYEBROW_PRINCIPLES[0]} · {EYEBROW_PRINCIPLES[1]}:"]
    for i, p in enumerate(DATA["principles"], 1):
        parts.append(f"{i:02d}. {p['title_tr']} ({p['title_en']}) {p['body_tr']}")
    return " ".join(parts)


# ---------------------------------------------------------------- flow pictogram (caption illustration)
def flow_glyph(prefix, x0, x1, cy, s=1.0, anim=True):
    """A belt rock, Legaluga and a product joined by dashed connections, with one data
    light on the first leg: a picture of the caption it sits next to (lights = the
    direction data flows, dashes = the connections). Returns (svg, css)."""
    xa, xb, xc = x0 + 5 * s, (x0 + x1) / 2, x1 - 6 * s
    l1a, l1b = xa + 9 * s, xb - 11 * s          # first leg, clear of both bodies
    l2a, l2b = xb + 11 * s, xc - 10 * s
    out = [f'<g stroke="{MUTED}" stroke-opacity=".6" stroke-width="{f(1.1 * s)}" '
           f'stroke-dasharray="{f(3 * s)} {f(4 * s)}" stroke-linecap="round">'
           f'<path d="M{f(l1a)} {f(cy)}H{f(l1b)}"/><path d="M{f(l2a)} {f(cy)}H{f(l2b)}"/></g>']
    out.append(layer_dot(prefix, "source", xa, cy, 0.85 * s))
    out.append(layer_dot(prefix, "infra", xb, cy, s))
    out.append(layer_dot(prefix, "product", xc, cy, s))
    tail = 26 * s
    s0, e = l1a + tail * 0.35, l1b - 3 * s       # where the head appears / fades out
    hx = s0 + 0.5 * (e - s0)                    # static first frame: halfway along
    css, cls = "", ""
    if anim:
        L, m, fd = e - s0, 0.72, 6 * s          # m: share of the cycle spent moving
        pc = lambda d: m * d / L * 100          # noqa: E731  percent of cycle for distance d
        a = pc(e - hx)
        b = a + (1 - m) * 100
        k = [(0, 0, 1), (a - pc(fd), e - hx - fd, 1), (a, e - hx, 0), (a + .01, s0 - hx, 0),
             (b, s0 - hx, 0), (b + pc(fd), s0 - hx + fd, 1), (100, 0, 1)]
        css = (f"@keyframes {prefix}lt{{" + "".join(f"{f(t)}%{{transform:translateX({f(x)}px);opacity:{o}}}" for t, x, o in k)
               + f"}}.{prefix}lt{{animation:{prefix}lt 8s linear infinite}}")
        cls = f' class="{prefix}lt"'
    out.append(f'<defs><linearGradient id="{prefix}tail" x1="0" y1="0" x2="1" y2="0">'
               f'<stop offset="0" stop-color="{CORE}" stop-opacity="0"/><stop offset="1" stop-color="{CORE_MID}" stop-opacity=".9"/>'
               f'</linearGradient><radialGradient id="{prefix}head"><stop offset="0" stop-color="#fff6e0"/>'
               f'<stop offset=".3" stop-color="{CORE_MID}" stop-opacity=".85"/><stop offset="1" stop-color="{CORE}" stop-opacity="0"/>'
               f'</radialGradient></defs>')
    out.append(f'<g{cls}><rect x="{f(hx - tail)}" y="{f(cy - 0.95 * s)}" width="{f(tail)}" height="{f(1.9 * s)}" '
               f'rx="{f(.95 * s)}" fill="url(#{prefix}tail)"/>'
               f'<circle cx="{f(hx)}" cy="{f(cy)}" r="{f(6.5 * s)}" fill="url(#{prefix}head)"/>'
               f'<circle cx="{f(hx)}" cy="{f(cy)}" r="{f(1.8 * s)}" fill="#fff6e0"/></g>')
    return "".join(out), css


def style_block(css):
    if not css:
        return ""
    return f"<style>@media (prefers-reduced-motion: no-preference){{{css}}}</style>\n"


# ---------------------------------------------------------------- system card (desktop)
def system_desktop():
    V = DESK
    W, PAD = V["W"], V["PAD"]
    RX = W - PAD
    hub = DATA["identity"]["hub"]
    P = "sd"
    S = Setter("g")
    T = S.line
    LBL, LBL_LS = 14, 0.1
    TITLE, MOTTO, DOM, DESC, DESC_EN, ITEM, CAP, CAP_EN = 24, 18, 16, 18, 16, 18, 17, 16
    LH_DESC, LH_EN, LH_ITEM, LH_CAP, LH_CAP_EN = 28, 25, 31, 26, 25
    DOT_X, LBL_X = PAD + 7, PAD + 28
    lw = max(max(tw(tr_upper(L["label_tr"]), LBL, 400, MONO, LBL_LS), tw(L["label_en"].upper(), LBL, 400, MONO, LBL_LS))
             for L in DATA["system"])
    MX = max(320, round(LBL_X + lw + 44))
    CW = RX - MX
    GAP = ITEM * 0.5

    note = [{"t": SYSTEM_NOTE[0].format(hub=hub), "fill": TEXT2},
            {"t": "·", "fill": SEP, "dx": 8}, {"t": SYSTEM_NOTE[1].format(hub=hub), "fill": MUTED, "dx": 8}]
    head, y = header(T, V, *EYEBROW_SYSTEM, right=note)
    out = [head]
    for L in DATA["system"]:
        layer = L["layer"]
        top = y + 44                       # first baseline of the row
        out.append(layer_dot(P, layer, DOT_X, top - 5))
        out.append(T(LBL_X, top, tr_upper(L["label_tr"]), LBL, LAYER[layer], family=MONO, ls=LBL_LS))
        out.append(T(LBL_X, top + 23, L["label_en"].upper(), LBL, MUTED, family=MONO, ls=LBL_LS))
        if "title" in L:
            runs = [{"t": L["title"], "fill": TEXT}]
            if L.get("motto"):
                runs.append({"t": L["motto"], "fill": LAYER[layer], "weight": 400, "size": MOTTO, "dx": 14})
            tw_title = runs_width(runs, TITLE, 600)
            dw = tw(L["domain"], DOM, 400, MONO)
            assert tw_title + 24 + dw <= CW, "title collides with domain"
            out.append(T(MX, top, runs, TITLE, TEXT, weight=600, ls=0))
            out.append(T(RX, top, L["domain"], DOM, TEXT2, family=MONO, anchor="end"))
            yy = top + 34
            for line in wrap_bal(L["desc_tr"], CW, DESC):
                out.append(T(MX, yy, line, DESC, TEXT2))
                yy += LH_DESC
            yy += LH_EN - LH_DESC
            for line in wrap_bal(L["desc_en"], CW, DESC_EN):
                out.append(T(MX, yy, line, DESC_EN, MUTED))
                yy += LH_EN
            last = yy - LH_EN
        else:
            fill = TEXT2 if layer == "source" else TEXT
            yy = top
            for runs in wrap_items_bal(L["items"], CW, ITEM, fill, GAP):
                out.append(T(MX, yy, runs, ITEM, fill))
                yy += LH_ITEM
            last = max(yy - LH_ITEM, top + 23)
        y = last + 30
        out.append(rule(PAD, RX, y))
    # footer: the map's caption, verbatim, with the flow pictogram in the label column
    top = y + 40
    tr_lines = wrap_bal(DATA["caption_tr"], CW, CAP)
    en_lines = wrap_bal(DATA["caption_en"], CW, CAP_EN)
    yy = top
    for line in tr_lines:
        out.append(T(MX, yy, line, CAP, TEXT2))
        yy += LH_CAP
    yy += LH_CAP_EN - LH_CAP
    for line in en_lines:
        out.append(T(MX, yy, line, CAP_EN, MUTED))
        yy += LH_CAP_EN
    last = yy - LH_CAP_EN
    mid = (top - CAP * 0.36 + last - CAP_EN * 0.36) / 2
    glyph, css = flow_glyph(P, PAD, LBL_X + lw, mid, 1.3)
    out.append(glyph)
    H = round(last + PAD - 6)
    body = f"<defs>{sphere_defs(P)}{S.defs_svg()}</defs>\n" + card_rect(W, H) + "\n" + "\n".join(out)
    label = system_alt()
    return doc(W, H, label, label, body, style_block(css)), H


# ---------------------------------------------------------------- system card (mobile)
def system_mobile():
    V = MOB
    W, PAD = V["W"], V["PAD"]
    RX = W - PAD
    CW = RX - PAD
    P = "sm"
    S = Setter("g")
    T = S.line
    LBL, LBL_LS = 17, 0.08
    TITLE, MOTTO, DOM, DESC, DESC_EN, ITEM, CAP, CAP_EN = 28, 20, 18, 20, 18, 20, 19, 18
    GAP = ITEM * 0.48
    head, y = header(T, V, *EYEBROW_SYSTEM)
    out = [head]
    for L in DATA["system"]:
        layer = L["layer"]
        top = y + 42
        out.append(layer_dot(P, layer, PAD + 8, top - 6, 1.2))
        trl, enl = tr_upper(L["label_tr"]), L["label_en"].upper()
        runs = [{"t": trl, "fill": LAYER[layer]}, {"t": "·", "fill": SEP, "dx": 6}, {"t": enl, "fill": MUTED, "dx": 6}]
        if PAD + 30 + runs_width(runs, LBL, 400, MONO, LBL_LS) <= RX:      # "GÜNEŞ · CORE" on one line
            out.append(T(PAD + 30, top, runs, LBL, LAYER[layer], family=MONO, ls=LBL_LS))
        else:
            out.append(T(PAD + 30, top, trl, LBL, LAYER[layer], family=MONO, ls=LBL_LS))
            top += 26
            out.append(T(PAD + 30, top, enl, LBL, MUTED, family=MONO, ls=LBL_LS))
        if "title" in L:
            yy = top + 46
            dw = tw(L["domain"], DOM, 400, MONO)
            assert tw(L["title"], TITLE, 600) + 20 + dw <= CW
            out.append(T(PAD, yy, L["title"], TITLE, TEXT, weight=600))
            out.append(T(RX, yy, L["domain"], DOM, TEXT2, family=MONO, anchor="end"))
            yy += 34
            if L.get("motto"):
                out.append(T(PAD, yy, L["motto"], MOTTO, LAYER[layer]))
                yy += 34
            for line in wrap_bal(L["desc_tr"], CW, DESC):
                out.append(T(PAD, yy, line, DESC, TEXT2))
                yy += 30
            yy += -30 + 28
            for line in wrap_bal(L["desc_en"], CW, DESC_EN):
                out.append(T(PAD, yy, line, DESC_EN, MUTED))
                yy += 27
            last = yy - 27
        else:
            fill = TEXT2 if layer == "source" else TEXT
            yy = top + 42
            for runs in wrap_items_bal(L["items"], CW, ITEM, fill, GAP):
                out.append(T(PAD, yy, runs, ITEM, fill))
                yy += 32
            last = yy - 32
        y = last + 32
        out.append(rule(PAD, RX, y))
    # footer caption with the pictogram on its own line above
    gy = y + 34
    glyph, css = flow_glyph(P, PAD, PAD + 270, gy, 1.5)
    out.append(glyph)
    yy = gy + 44
    for line in wrap_bal(DATA["caption_tr"], CW, CAP):
        out.append(T(PAD, yy, line, CAP, TEXT2))
        yy += 28
    yy += -28 + 28
    for line in wrap_bal(DATA["caption_en"], CW, CAP_EN):
        out.append(T(PAD, yy, line, CAP_EN, MUTED))
        yy += 27
    last = yy - 27
    H = round(last + PAD - 4)
    body = f"<defs>{sphere_defs(P)}{S.defs_svg()}</defs>\n" + card_rect(W, H) + "\n" + "\n".join(out)
    label = system_alt()
    return doc(W, H, label, label, body, style_block(css)), H


# ---------------------------------------------------------------- principles card (desktop)
def principles_desktop():
    V = DESK
    S = Setter("g")
    T = S.line
    W, PAD = V["W"], V["PAD"]
    NUM, TITLE, EN, BODY, LH = 14, 24, 17, 18, 28
    # gutter: the widest one (64 down to 40) that still gives the fewest body lines
    def depth(gap):
        cw = (W - 2 * PAD - 2 * gap) / 3
        return max(len(wrap_nice(p["body_tr"], cw, BODY)) for p in DATA["principles"])
    GAP = min(range(64, 39, -2), key=lambda g: (depth(g), -g))
    cw = (W - 2 * PAD - 2 * GAP) / 3
    head, y = header(T, V, *EYEBROW_PRINCIPLES)
    out = [head]
    ends = []
    for i, p in enumerate(DATA["principles"]):
        x = PAD + i * (cw + GAP)
        ny = y + 44
        out.append(T(x, ny, f"{i + 1:02d}", NUM, CORE, family=MONO, ls=0.1))
        ty = ny + 40
        out.append(T(x, ty, p["title_tr"], TITLE, TEXT, weight=600, ls=-0.01))
        ey = ty + 29
        out.append(T(x, ey, p["title_en"], EN, MUTED))
        by = ey + 37
        for line in wrap_nice(p["body_tr"], cw, BODY):
            out.append(T(x, by, line, BODY, TEXT2))
            by += LH
        ends.append(by - LH)
    H = round(max(ends) + PAD - 6)
    body = f"<defs>{S.defs_svg()}</defs>\n" + card_rect(W, H) + "\n" + "\n".join(out)
    label = principles_alt()
    return doc(W, H, label, label, body), H


# ---------------------------------------------------------------- principles card (mobile)
def principles_mobile():
    V = MOB
    S = Setter("g")
    T = S.line
    W, PAD = V["W"], V["PAD"]
    RX = W - PAD
    NUM, TITLE, EN, BODY, LH = 17, 27, 19, 20, 30
    IND = 50
    tx = PAD + IND
    cw = RX - tx
    head, y = header(T, V, *EYEBROW_PRINCIPLES)
    out = [head]
    n = len(DATA["principles"])
    for i, p in enumerate(DATA["principles"]):
        ty = y + 50
        out.append(T(PAD, ty, f"{i + 1:02d}", NUM, CORE, family=MONO, ls=0.08))
        out.append(T(tx, ty, p["title_tr"], TITLE, TEXT, weight=600, ls=-0.01))
        ey = ty + 32
        out.append(T(tx, ey, p["title_en"], EN, MUTED))
        by = ey + 38
        for line in wrap_nice(p["body_tr"], cw, BODY):
            out.append(T(tx, by, line, BODY, TEXT2))
            by += LH
        last = by - LH
        if i < n - 1:
            y = last + 32
            out.append(rule(PAD, RX, y))
    H = round(last + PAD - 4)
    body = f"<defs>{S.defs_svg()}</defs>\n" + card_rect(W, H) + "\n" + "\n".join(out)
    label = principles_alt()
    return doc(W, H, label, label, body), H


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 cards.py OUTDIR")
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    for name, fn in [("system.svg", system_desktop), ("system-mobile.svg", system_mobile),
                     ("principles.svg", principles_desktop), ("principles-mobile.svg", principles_mobile)]:
        svg, h = fn()
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"cards.py: {name} height {h}")


if __name__ == "__main__":
    main()
