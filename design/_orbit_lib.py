"""Shared helpers for hero.py and metrics.py (the "orbit" cards).

Brand tokens, data.json loading, exact text measurement through the vendored
outline.py (the same shaper the build uses to outline the text), and small SVG
writers. Nothing here hard-codes content: every visible string comes from
data.json or from the card-system constants in final-spec.
"""
import json
import os
import re
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outline  # noqa: E402

# ---------------------------------------------------------------- tokens (imer.app CSS)
BG = "#070a12"
RAISED = "#0d1220"
LINE = "#1c2436"
TEXT = "#e8ecf4"
TEXT2 = "#c3cad8"
MUTED = "#8d97ab"
CORE = "#f2b35b"
CORE_HI = "#ffe2a8"
CORE_MID = "#ffd27d"
INFRA = "#f0866a"
PRODUCT = "#5fd0c5"
BRIDGE = "#b58cff"
SOURCE = "#7c8aa5"
LAYER = {"core": CORE, "infra": INFRA, "product": PRODUCT, "bridge": BRIDGE, "source": SOURCE}

SANS = "Geist"
MONO = "Geist Mono"
CAP = 0.71           # Geist / Geist Mono cap height (OS/2 sCapHeight / unitsPerEm)
XH = 0.53            # x-height

# ---------------------------------------------------------------- card system (final-spec.md)
CARD_RX = 16
PAD_DESKTOP = 56
PAD_MOBILE = 32
EYEBROW_DESKTOP = 14
EYEBROW_MOBILE = 17
EYEBROW_LS = 0.14    # em
MIN_DESKTOP = 14     # readable text, 1200-wide viewBox (13 only for mono source lines)
MIN_MOBILE = 17      # readable text, 600-wide viewBox (16 only for mono source lines)


class BuildError(SystemExit):
    pass


def fail(where, msg):
    raise BuildError(f"{where}: ERROR: {msg}")


def load_data():
    with open(os.path.join(HERE, "data.json"), encoding="utf-8") as fh:
        return json.load(fh)


def upper_tr(s):
    """Uppercase with the Turkish dotted/dotless i mapping (i -> İ, ı -> I)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def f1(v):
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def props(size, weight=400, family=SANS, ls=0.0):
    return {"font-family": family, "font-size": str(size), "font-weight": str(weight),
            "letter-spacing": str(ls)}


def tw(text, size, weight=400, family=SANS, ls=0.0):
    """Advance width exactly as outline.py lays the run out (trailing letter-spacing included)."""
    _, x = outline.shape_run(text, props(size, weight, family, ls), 0, 0)
    return x


def tw_vis(text, size, weight=400, family=SANS, ls=0.0):
    """Visible advance (without the trailing letter-spacing browsers add after the last glyph)."""
    return tw(text, size, weight, family, ls) - (ls if text else 0.0)


_NUM = re.compile(r"[MLHVQCZ]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")


def ink_box(text, size, weight=400, family=SANS, ls=0.0, x=0.0, y=0.0):
    """Bounding box of the outlined glyphs (control points included, so slightly generous)."""
    d, _ = outline.shape_run(text, props(size, weight, family, ls), x, y)
    toks = _NUM.findall(d)
    xs, ys = [], []
    i, cmd = 0, None
    cx = cy = 0.0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            continue
        if cmd in ("M", "L", "Q", "C"):
            cx, cy = float(toks[i]), float(toks[i + 1])
            i += 2
        elif cmd == "H":
            cx = float(t)
            i += 1
        elif cmd == "V":
            cy = float(t)
            i += 1
        else:
            i += 1
            continue
        xs.append(cx)
        ys.append(cy)
    if not xs:
        return (x, y, x, y)
    return (min(xs), min(ys), max(xs), max(ys))


def T(x, y, text, size, weight=400, fill=TEXT, family=SANS, ls=None, anchor=None, extra=""):
    a = [f'x="{f(x)}"', f'y="{f(y)}"', f'font-family="{family}"', f'font-size="{f(size)}"',
         f'font-weight="{weight}"', f'fill="{fill}"']
    if ls:
        a.append(f'letter-spacing="{f(ls)}"')
    if anchor:
        a.append(f'text-anchor="{anchor}"')
    if extra:
        a.append(extra)
    return f"<text {' '.join(a)}>{escape(text)}</text>"


def text_box(x, y, text, size, weight=400, family=SANS, ls=0.0, anchor=None):
    """Layout box of a text line (advance width x [baseline - ascent, baseline + descent])."""
    w = tw(text, size, weight, family, ls)
    x0 = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
    return (x0, y - 0.92 * size, x0 + w, y + 0.22 * size)


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def wrap(text, width, size, weight=400, family=SANS, ls=0.0, break_after="/"):
    """Greedy word wrap; a single word wider than the line may break after `break_after`."""
    pieces = []
    for w in text.split(" "):
        if break_after and tw_vis(w, size, weight, family, ls) > width and break_after in w:
            bits = w.split(break_after)
            for k, bt in enumerate(bits):
                t = bt + (break_after if k < len(bits) - 1 else "")
                if t:
                    pieces.append((t, " " if k == 0 else ""))
        else:
            pieces.append((w, " "))
    lines, cur = [], ""
    for t, sep in pieces:
        cand = cur + sep + t if cur else t
        if not cur or tw_vis(cand, size, weight, family, ls) <= width:
            cur = cand
        else:
            lines.append(cur)
            cur = t
    if cur:
        lines.append(cur)
    return lines


def wrap_bal(text, width, size, weight=400, family=SANS, ls=0.0):
    """Same number of lines as a greedy wrap, with the line lengths evened out (no orphans)."""
    lines = wrap(text, width, size, weight, family, ls, break_after=None)
    if len(lines) <= 1:
        return lines
    n, lo, hi = len(lines), width * 0.3, width
    for _ in range(30):
        mid = (lo + hi) / 2
        if len(wrap(text, mid, size, weight, family, ls, break_after=None)) <= n:
            hi = mid
        else:
            lo = mid
    return wrap(text, hi + 0.01, size, weight, family, ls, break_after=None)


def attr(s):
    return escape(s, {'"': "&quot;"})


def svg_open(w, h, label, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}" height="{f(h)}" viewBox="0 0 {f(w)} {f(h)}" '
            f'role="img" aria-label="{attr(label)}" fill="none">\n'
            f"<title>{escape(title)}</title>\n")


def card_base(w, h):
    """Card fill (drawn first)."""
    return f'<rect x=".5" y=".5" width="{f(w - 1)}" height="{f(h - 1)}" rx="{CARD_RX}" fill="{BG}"/>'


def card_border(w, h):
    """Card hairline border (drawn last, above any clipped artwork)."""
    return f'<rect x=".5" y=".5" width="{f(w - 1)}" height="{f(h - 1)}" rx="{CARD_RX}" stroke="{LINE}"/>'


def card_clip(cid, w, h):
    return f'<clipPath id="{cid}"><rect x=".5" y=".5" width="{f(w - 1)}" height="{f(h - 1)}" rx="{CARD_RX}"/></clipPath>'


def style_block(css):
    """All motion is opt-in: nothing animates for prefers-reduced-motion: reduce."""
    if not css:
        return ""
    return "<style>@media (prefers-reduced-motion: no-preference){" + "".join(css) + "}</style>"


def boxes_overlap(a, b, pad=0.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def circle_box_dist(cx, cy, b):
    nx = min(max(cx, b[0]), b[2])
    ny = min(max(cy, b[1]), b[3])
    return ((cx - nx) ** 2 + (cy - ny) ** 2) ** 0.5


def seg_box_dist(p, q, b, steps=None):
    """Smallest distance between segment pq and box b (sampled; exact enough at 0.5px steps)."""
    (x1, y1), (x2, y2) = p, q
    L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    n = steps or max(2, int(L / 0.5))
    best = 1e9
    for i in range(n + 1):
        t = i / n
        best = min(best, circle_box_dist(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, b))
        if best == 0:
            break
    return best


def write(out_dir, name, svg):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return path
