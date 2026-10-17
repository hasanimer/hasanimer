#!/usr/bin/env python3
"""Metric card ("ÖLÇEK · SCALE"): the four figures shown on imer.app, each with its source.

Usage: python3 metrics.py OUT_DIR   -> OUT_DIR/metrics.svg (1200 wide), metrics-mobile.svg (600 wide)

Each cell: a mono body tag with a dot in the body's layer colour, the big number (unit set smaller),
the TR label, the EN label (muted) and the mono source line. On desktop the source blocks are
bottom-aligned on one shared baseline across the four cells. All strings come from data.json.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _orbit_lib import (BG, CAP, CORE, CORE_HI, CORE_MID, EYEBROW_DESKTOP, EYEBROW_LS, EYEBROW_MOBILE, LAYER,  # noqa: E402
                        LINE, MIN_DESKTOP, MIN_MOBILE, MONO, MUTED, PAD_DESKTOP, PAD_MOBILE, PRODUCT, SANS, TEXT, TEXT2,
                        T, card_base, card_border, f, fail, ink_box, load_data, mix, style_block, svg_open, tw,
                        tw_vis, upper_tr, wrap, wrap_bal, write)

WHERE = "metrics.py"
EYEBROW = ("Ölçek", "Scale")          # card eyebrow from final-spec ("ÖLÇEK · SCALE")
SEP = "#525d74"                       # separator dot in the header note (same as cards.py)

DESK = dict(W=1200, PAD=PAD_DESKTOP, eyebrow=EYEBROW_DESKTOP, rule_gap=24, note=15,
            tag=14, tag_ls=0.1, dot=1.0, num=54, unit=27, tr=18, tr_lh=25, en=16, en_lh=22, src=13, src_lh=19,
            live_r=5.0, live_clear=10)
MOB = dict(W=600, PAD=PAD_MOBILE, eyebrow=EYEBROW_MOBILE, rule_gap=21,
           tag=17, tag_ls=0.08, dot=1.25, num=64, unit=32, tr=20, tr_lh=28, en=18, en_lh=25, src=16, src_lh=23,
           live_r=6.5, live_clear=13)


def check_sizes(V, minimum, src_minimum):
    for key in ("eyebrow", "tag", "tr", "en", "unit"):
        if V[key] < minimum:
            fail(WHERE, f"{key} text is {V[key]}px, below the {minimum}px minimum")
    if V["src"] < src_minimum:
        fail(WHERE, f"source lines are {V['src']}px, below the {src_minimum}px minimum")


# ---------------------------------------------------------------- shared pieces
def defs(p):
    out = []
    for name, c in LAYER.items():
        out.append(f'<radialGradient id="{p}s-{name}" cx=".34" cy=".3" r=".78">'
                   f'<stop offset="0" stop-color="{mix(c, "#ffffff", .5)}"/><stop offset=".45" stop-color="{c}"/>'
                   f'<stop offset="1" stop-color="{mix(c, BG, .62)}"/></radialGradient>')
    out.append(f'<radialGradient id="{p}corona"><stop offset="0" stop-color="{CORE_HI}"/>'
               f'<stop offset=".34" stop-color="{CORE_MID}" stop-opacity=".95"/>'
               f'<stop offset=".6" stop-color="{CORE}" stop-opacity=".35"/>'
               f'<stop offset="1" stop-color="{CORE}" stop-opacity="0"/></radialGradient>')
    out.append(f'<radialGradient id="{p}disk" cx=".42" cy=".38" r=".7"><stop offset="0" stop-color="#fffaf0"/>'
               f'<stop offset=".55" stop-color="{CORE_HI}"/><stop offset="1" stop-color="{CORE_MID}"/></radialGradient>')
    return "".join(out)


def layer_dot(p, layer, x, y, s=1.0):
    """The measured body as it appears on the map: the sun for the core, a planet sphere otherwise."""
    if layer == "core":
        return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(10 * s)}" fill="url(#{p}corona)"/>'
                f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(4.6 * s)}" fill="url(#{p}disk)"/>')
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(8.5 * s)}" fill="{LAYER[layer]}" fill-opacity=".12"/>'
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(5 * s)}" fill="url(#{p}s-{layer})"/>')


def header(V, note=None):
    """Amber mono eyebrow top-left, optional right-aligned note, hairline under the row (as cards.py)."""
    W, PAD, s = V["W"], V["PAD"], V["eyebrow"]
    base = PAD + round(s * 0.72)
    eyebrow = f"{upper_tr(EYEBROW[0])} · {EYEBROW[1].upper()}"
    out = [T(PAD, base, eyebrow, s, 400, CORE, MONO, ls=s * EYEBROW_LS)]
    if note:
        tr, en = note
        sz = V["note"]
        w_en, w_dot, w_tr = tw(en, sz), tw("·", sz), tw(tr, sz)
        if PAD + tw(eyebrow, s, 400, MONO, s * EYEBROW_LS) + 32 + w_tr + w_dot + w_en + 16 > W - PAD:
            fail(WHERE, "header note does not fit beside the eyebrow")
        x = W - PAD
        out.append(T(x, base, en, sz, 400, MUTED, anchor="end"))
        x -= w_en + 8
        out.append(T(x, base, "·", sz, 400, SEP, anchor="end"))
        x -= w_dot + 8
        out.append(T(x, base, tr, sz, 400, TEXT2, anchor="end"))
    y = base + V["rule_gap"]
    out.append(f'<path d="M{f(PAD)} {f(y + .5)}H{f(W - PAD)}" stroke="{LINE}"/>')
    return "\n".join(out), y


def first_clause(s):
    return s.split(";")[0].strip().rstrip(".")


def aria(d):
    M = d["metrics"]
    parts = []
    for it in M["items"]:
        v = it["value"] + (f" {it['unit']}" if it["unit"] else "")
        parts.append(f"{v} {it['label_tr']} ({it['label_en']}; kaynak: {it['source']}).")
    label = f"{EYEBROW[0]} · {EYEBROW[1]}. {M['note_tr']} " + " ".join(parts)
    title = f"{EYEBROW[0]} · {EYEBROW[1]}: {first_clause(M['note_tr'])}"
    return label, title


def value_block(V, p, x, y, it, css):
    """Big number, optional smaller unit, and the live dot (kept >= 8px clear of the last glyph)."""
    size = V["num"]
    ls = -size * 0.02
    out = [T(x, y, it["value"], size, 600, TEXT, SANS, ls=ls)]
    adv = tw_vis(it["value"], size, 600, SANS, ls)
    right = x + adv
    if it["unit"]:
        ux = x + adv + size * 0.17
        out.append(T(ux, y, it["unit"], V["unit"], 500, TEXT2, SANS, ls=-V["unit"] * 0.01))
        right = ux + tw_vis(it["unit"], V["unit"], 500, SANS, -V["unit"] * 0.01)
    if it.get("live"):
        ink = ink_box(it["value"], size, 600, SANS, ls, x, y)
        r = V["live_r"]
        halo_max = r * 2.2                            # largest extent the halo reaches while it breathes
        cx = ink[2] + V["live_clear"] + halo_max      # spec minimum is 8px; a little more reads calmer
        cy = y - size * CAP / 2
        gap = cx - halo_max - ink[2]
        if gap < 8:
            fail(WHERE, f"live dot halo is only {gap:.1f}px from the '{it['value']}' glyph")
        out.append(f'<circle class="{p}live" cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 2)}" fill="{PRODUCT}" fill-opacity=".22"/>')
        out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{PRODUCT}"/>')
        css.append(f"@keyframes {p}live{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.35;transform:scale(1.1)}}}}"
                   f".{p}live{{transform-origin:{f(cx)}px {f(cy)}px;animation:{p}live 3.2s ease-in-out infinite}}")
        right = cx + halo_max
        print(f"[{WHERE}] live dot: halo edge {gap:.1f}px clear of the '{it['value']}' ink")
    return "\n".join(out), right


def tag(V, p, x, y, it):
    s = V["dot"]
    dx = x + 8.5 * s
    text = upper_tr(it["body"])
    return (layer_dot(p, it["layer"], dx, y - V["tag"] * CAP / 2, s)
            + T(x + 17 * s + 10, y, text, V["tag"], 400, MUTED, MONO, ls=V["tag"] * V["tag_ls"])), \
        x + 17 * s + 10 + tw_vis(text, V["tag"], 400, MONO, V["tag"] * V["tag_ls"])


# ---------------------------------------------------------------- desktop: four columns
def metrics_desktop(d, out_dir):
    V = DESK
    check_sizes(V, MIN_DESKTOP, 13)
    W, PAD = V["W"], V["PAD"]
    items = d["metrics"]["items"]
    n = len(items)
    G = 56                                          # gutter; the divider runs down its middle
    CW = (W - 2 * PAD - (n - 1) * G) / n
    p = "q"
    M = d["metrics"]
    head, hy = header(V, (first_clause(M["note_tr"]), first_clause(M["note_en"])))

    y_tag = hy + 46
    y_num = y_tag + 70
    y_tr = y_num + 40
    cells = []
    for it in items:
        tr = wrap_bal(it["label_tr"], CW, V["tr"])
        en = wrap_bal(it["label_en"], CW, V["en"])
        src = wrap(it["source"], CW, V["src"], 400, MONO)
        y_en = y_tr + (len(tr) - 1) * V["tr_lh"] + V["en_lh"] + 4
        y_text_end = y_en + (len(en) - 1) * V["en_lh"]
        cells.append((it, tr, en, src, y_en, y_text_end))
    # sources: bottom-aligned on one shared last baseline, at least 34px under the longest label block
    y_src_last = max(c[5] + 34 + (len(c[3]) - 1) * V["src_lh"] for c in cells)
    H = round(y_src_last + PAD - 8)

    css = []
    body = [card_base(W, H), head]
    for i in range(1, n):
        x = PAD + i * (CW + G) - G / 2
        body.append(f'<path d="M{f(x + .5)} {f(hy + 1)}V{f(y_src_last + 14)}" stroke="{LINE}"/>')
    for i, (it, tr, en, src, y_en, _) in enumerate(cells):
        x = PAD + i * (CW + G)
        tg, tag_right = tag(V, p, x, y_tag, it)
        vb, num_right = value_block(V, p, x, y_num, it, css)
        for right, what in ((tag_right, "body tag"), (num_right, "number")):
            if right > x + CW + 0.5:
                fail(WHERE, f"desktop {what} of '{it['value']}' overflows its column by {right - x - CW:.1f}px")
        body += [tg, vb]
        for j, line in enumerate(tr):
            body.append(T(x, y_tr + j * V["tr_lh"], line, V["tr"], 400, TEXT2))
        for j, line in enumerate(en):
            body.append(T(x, y_en + j * V["en_lh"], line, V["en"], 400, MUTED))
        y0 = y_src_last - (len(src) - 1) * V["src_lh"]
        for j, line in enumerate(src):
            body.append(T(x, y0 + j * V["src_lh"], line, V["src"], 400, MUTED, MONO))
    body.append(card_border(W, H))
    label, title = aria(d)
    svg = (svg_open(W, H, label, title) + f"<defs>{defs(p)}</defs>\n" + style_block(css) + "\n"
           + "\n".join(body) + "\n</svg>\n")
    write(out_dir, "metrics.svg", svg)
    print(f"[{WHERE}] desktop H={H}, column {CW:.0f}px, lines tr/en/src:",
          [(len(c[1]), len(c[2]), len(c[3])) for c in cells])


# ---------------------------------------------------------------- mobile: one column
def metrics_mobile(d, out_dir):
    V = MOB
    check_sizes(V, MIN_MOBILE, 16)
    W, PAD = V["W"], V["PAD"]
    CW = W - 2 * PAD
    p = "r"
    head, hy = header(V)
    css = []
    rows = []
    top = hy
    for it in d["metrics"]["items"]:
        tr = wrap_bal(it["label_tr"], CW, V["tr"])
        en = wrap_bal(it["label_en"], CW, V["en"])
        src = wrap(it["source"], CW, V["src"], 400, MONO)
        y_tag = top + 46
        y_num = y_tag + 74
        y_tr = y_num + 44
        y_en = y_tr + (len(tr) - 1) * V["tr_lh"] + V["en_lh"] + 4
        y_src = y_en + (len(en) - 1) * V["en_lh"] + 36
        bottom = y_src + (len(src) - 1) * V["src_lh"] + 36
        rows.append((it, tr, en, src, top, y_tag, y_num, y_tr, y_en, y_src, bottom))
        top = bottom
    H = round(top + PAD - 36 + 6)
    body = [card_base(W, H), head]
    for k, (it, tr, en, src, top, y_tag, y_num, y_tr, y_en, y_src, bottom) in enumerate(rows):
        if k:
            body.append(f'<path d="M{f(PAD)} {f(top + .5)}H{f(W - PAD)}" stroke="{LINE}"/>')
        tg, tag_right = tag(V, p, PAD, y_tag, it)
        vb, num_right = value_block(V, p, PAD, y_num, it, css)
        for right, what in ((tag_right, "body tag"), (num_right, "number")):
            if right > W - PAD:
                fail(WHERE, f"mobile {what} of '{it['value']}' overflows the card")
        body += [tg, vb]
        for j, line in enumerate(tr):
            body.append(T(PAD, y_tr + j * V["tr_lh"], line, V["tr"], 400, TEXT2))
        for j, line in enumerate(en):
            body.append(T(PAD, y_en + j * V["en_lh"], line, V["en"], 400, MUTED))
        for j, line in enumerate(src):
            body.append(T(PAD, y_src + j * V["src_lh"], line, V["src"], 400, MUTED, MONO))
    body.append(card_border(W, H))
    label, title = aria(d)
    svg = (svg_open(W, H, label, title) + f"<defs>{defs(p)}</defs>\n" + style_block(css) + "\n"
           + "\n".join(body) + "\n</svg>\n")
    write(out_dir, "metrics-mobile.svg", svg)
    print(f"[{WHERE}] mobile H={H}, lines tr/en/src:", [(len(r[1]), len(r[2]), len(r[3])) for r in rows])


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 metrics.py OUT_DIR")
    d = load_data()
    metrics_desktop(d, sys.argv[1])
    metrics_mobile(d, sys.argv[1])


if __name__ == "__main__":
    main()
