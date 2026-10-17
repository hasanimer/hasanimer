#!/usr/bin/env python3
"""Hero card (desktop + mobile) and the imer.app sign-off mark.

Usage: python3 hero.py OUT_DIR   -> OUT_DIR/hero.svg, hero-mobile.svg, mark.svg (text still as <text>;
build.sh outlines and compacts them into ../assets/).

The map is drawn by _orbit_map.OrbitMap; every string comes from data.json. The build stops
with an error if a label would cover a body, a link, the comet or a drifting planet.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _orbit_lib import (BG, CORE, EYEBROW_DESKTOP, EYEBROW_LS, EYEBROW_MOBILE, LAYER, LINE, MIN_DESKTOP,  # noqa: E402
                        MIN_MOBILE, MUTED, PAD_DESKTOP, PAD_MOBILE, TEXT, TEXT2, MONO, T, card_base, card_border,
                        card_clip, f, f1, fail, load_data, style_block, svg_open, text_box, tw, write)
from _orbit_map import OrbitMap  # noqa: E402

WHERE = "hero.py"

# Map layout (presentation only; names are checked against data.json).
# name, layer, orbit rx, theta (90 = front, 270 = back), radius; drift arcs are solved in list order
BODIES = [
    ("Legaluga", "infra", 66, 162, 9.0),
    ("Legaluga Araştırma", "product", 104, 290, 5.6),
    ("Legaluga Araçları", "product", 104, 248, 4.8),
    ("Legaluga MCP", "bridge", 142, 322, 8.2),
    ("İmer İmza Köprüsü", "bridge", 142, 228, 4.8),
    ("Atıf Denetimi", "product", 182, 112, 8.8),
    ("Legaluga UDF Editor", "product", 182, 296, 5.0),
    ("Legaluga Mobil", "product", 262, 78, 5.6),        # listed before Skill so it claims its drift arc first
    ("Skill Kütüphanesi", "bridge", 222, 62, 5.6),
    ("Legaluga Yaptırım Aynası", "bridge", 222, 236, 5.0),
    ("Karar Kütüphanesi", "product", 262, 235, 8.4),
    ("Legaluga UYAP Asistanı", "product", 262, 286, 5.2),
]
BELT_BODIES = [  # name, rx, theta, radius
    ("Yargıtay", 318, 258, 3.8),
    ("Yapay zekâ asistanları", 318, 310, 3.8),
    ("Mevzuat ve Resmî Gazete", 322, 224, 3.4),
    ("UYAP", 316, 20, 3.2),
    ("Bedesten", 320, 150, 3.2),
]
LINKS = [  # inferred data flow (judged plausible): sources -> Legaluga -> products, MCP -> AI assistants
    ("Yargıtay", "Legaluga"),
    ("Mevzuat ve Resmî Gazete", "Legaluga"),
    ("Legaluga", "Atıf Denetimi"),
    ("Legaluga", "Karar Kütüphanesi"),
    ("Legaluga MCP", "Yapay zekâ asistanları"),
]
LIGHT_PATH = ["Yargıtay", "Legaluga", "Atıf Denetimi"]
# first-frame spots that differ on the narrower mobile map (keeps its larger labels clear)
MOBILE_THETA = {"Yargıtay": 272, "Yapay zekâ asistanları": 342, "Legaluga UDF Editor": 250, "Legaluga UYAP Asistanı": 332, "Legaluga Araçları": 236}
SUN_SIDES = ["r", ("below", .14), ("below", .04), ("above", .14)]


def aria(d):
    idn = d["identity"]
    parts = []
    for L in d["system"]:          # one sentence per layer ("Gezegenler: ürünler. Atıf Denetimi, ...")
        if "title" in L:
            parts.append(f"{L['label_tr']}: {L['title']} ({L['domain']}).")
        else:
            names = ", ".join(it["name"] + (f" ({it['note']})" if it.get("note") else "") for it in L["items"])
            parts.append(f"{L['label_tr']}. {names}.")
    label = (f"{idn['name']}, {idn['role_tr']} ({idn['role_en']}). {idn['hub']}: {idn['tagline_tr']} "
             f"Güneş sistemi haritası. " + " ".join(parts) + f" {d['caption_tr']}")
    title = f"{idn['name']} · {idn['hub']}: {idn['tagline_tr']}"
    return label, title


def stars(w, h, n, seed, avoid):
    """Sparse starfield kept out of every text and label box, so no star reads as a diacritic."""
    rnd = random.Random(seed)
    out = ['<g fill="#c3cad8">']
    placed = tw_i = 0
    while placed < n:
        x, y = rnd.uniform(8, w - 8), rnd.uniform(8, h - 8)
        r = 0.35 + rnd.random() ** 3 * 0.9
        op = 0.12 + rnd.random() ** 2 * 0.5
        twinkle = rnd.random() < 0.06
        if any(b[0] - 4 <= x <= b[2] + 4 and b[1] - 4 <= y <= b[3] + 4 for b in avoid):
            continue
        placed += 1
        cls = ""
        if twinkle:
            cls = f' class="tw{tw_i % 3}"'
            tw_i += 1
        out.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{f(r)}" fill-opacity="{op:.2f}"{cls}/>')
    out.append("</g>")
    css = ["@keyframes tw{0%,100%{opacity:1}50%{opacity:.25}}"]
    css += [f".tw{k}{{animation:tw {dur}s ease-in-out {delay}s infinite}}" for k, (dur, delay) in
            enumerate([(5, 0), (7, 2), (9, 4)])]
    return "\n".join(out), css


def legend_items(d):
    return [(it["layer"], it["text"]) for it in d["legend"]]


def legend_dot(cx, cy, r, layer):
    return f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{LAYER[layer]}"/>'


def check_sizes(where, items, minimum):
    for what, size in items:
        if size < minimum:
            fail(WHERE, f"{where}: {what} is {size}px, below the {minimum}px minimum")


# ---------------------------------------------------------------- desktop
def hero_desktop(d, out_dir):
    W, H = 1200, 420
    X = PAD_DESKTOP
    idn = d["identity"]
    sizes = dict(eyebrow=EYEBROW_DESKTOP, name=72, tagline=24, role=18, role_en=16, legend=16, label=16)
    check_sizes("desktop", sizes.items(), MIN_DESKTOP)

    copy = [  # (y, text, size, weight, fill, family, letter-spacing)
        (104, idn["eyebrow"], sizes["eyebrow"], 400, CORE, MONO, sizes["eyebrow"] * EYEBROW_LS),
        (182, idn["name"], sizes["name"], 600, TEXT, "Geist", -sizes["name"] * 0.02),
        (224, idn["tagline_tr"], sizes["tagline"], 400, TEXT2, "Geist", 0),
        (278, idn["role_tr"], sizes["role"], 500, TEXT, "Geist", 0),
        (305, idn["role_en"], sizes["role_en"], 400, MUTED, "Geist", 0),
    ]
    boxes = [text_box(X, y, t, sz, wt, fam, ls) for y, t, sz, wt, fill, fam, ls in copy]

    # legend row along the bottom, aligned with the copy column
    ly, ls_ = 382, sizes["legend"]
    leg, cx = [], X
    for layer, text in legend_items(d):
        leg.append(legend_dot(cx + 4.5, ly - ls_ * 0.35, 4.5, layer))
        leg.append(T(cx + 16, ly, text, ls_, 400, MUTED))
        cx += 16 + tw(text, ls_) + 26
    legend_box = (X, ly - ls_ * 0.92, cx - 26, ly + ls_ * 0.22)
    boxes.append(legend_box)

    m = OrbitMap(f"{WHERE} desktop", d, 880, 210, 1.1, bodies=BODIES, belt_bodies=BELT_BODIES,
                 labels=[("sun", SUN_SIDES), ("Legaluga", ["l", "al", "bl", "a"]), ("Legaluga MCP", ["b", "br", "r"]),
                         ("Atıf Denetimi", ["b", "bl", "br"]), ("Karar Kütüphanesi", ["a", "al", "ar"]),
                         ("Yargıtay", ["a", "ar", "al"]), ("Yapay zekâ asistanları", ["a", "al", "ar"])],
                 links=LINKS, light_path=LIGHT_PATH, label_size=sizes["label"], min_label=MIN_DESKTOP,
                 prefix="m", avoid=boxes, bounds=(X, 12, W - 12, H - 12), belt_n=330, seed=7)

    st, stcss = stars(W, H, 140, 3, boxes + [b for b, _ in m.pills])
    label, title = aria(d)
    defs = [m.defs(), card_clip("card", W, H),
            '<linearGradient id="scrim" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{BG}" stop-opacity=".96"/><stop offset=".62" stop-color="{BG}" stop-opacity=".82"/>'
            f'<stop offset="1" stop-color="{BG}" stop-opacity="0"/></linearGradient>']
    body = [card_base(W, H), st, m.haze(), m.orbits(), m.belt(), m.links_svg(), m.sun(), m.planets(), m.light(),
            f'<rect width="640" height="{H}" fill="url(#scrim)"/>', m.labels(), "<g>"]
    for y, t, sz, wt, fill, fam, ls in copy:
        body.append(T(X, y, t, sz, wt, fill, fam, ls=ls))
    body.append("</g>")
    body += leg
    svg = (svg_open(W, H, label, title) + "<defs>" + "\n".join(defs) + "</defs>\n" + style_block(stcss + m.css) + "\n"
           + '<g clip-path="url(#card)">' + "\n".join(body) + "</g>\n" + card_border(W, H) + "\n</svg>\n")
    write(out_dir, "hero.svg", svg)
    print(m.report())
    print(f"[{WHERE} desktop] legend ends at x={cx - 26:.0f}; comet head at {[round(v) for v in m.comet_head0]}")


# ---------------------------------------------------------------- mobile
def hero_mobile(d, out_dir):
    W = 600
    X = PAD_MOBILE
    idn = d["identity"]
    sizes = dict(eyebrow=EYEBROW_MOBILE, name=66, tagline=27, role=20, role_en=18, legend=18, label=17)
    check_sizes("mobile", sizes.items(), MIN_MOBILE)
    copy = [
        (72, idn["eyebrow"], sizes["eyebrow"], 400, CORE, MONO, sizes["eyebrow"] * EYEBROW_LS),
        (144, idn["name"], sizes["name"], 600, TEXT, "Geist", -sizes["name"] * 0.02),
        (190, idn["tagline_tr"], sizes["tagline"], 400, TEXT2, "Geist", 0),
        (238, idn["role_tr"], sizes["role"], 500, TEXT, "Geist", 0),
        (266, idn["role_en"], sizes["role_en"], 400, MUTED, "Geist", 0),
    ]
    for y, t, sz, wt, fill, fam, ls in copy:
        if X + tw(t, sz, wt, fam, ls) > W - X:
            fail(WHERE, f"mobile: '{t}' is wider than the card")
    boxes = [text_box(X, y, t, sz, wt, fam, ls) for y, t, sz, wt, fill, fam, ls in copy]

    lsize = sizes["legend"]
    items = legend_items(d)
    rows = [items[i:i + 2] for i in range(0, len(items), 2)]
    col2 = X + 300
    ly0 = 640
    lh = 32
    H = ly0 + (len(rows) - 1) * lh + 44
    leg = []
    for ri, row in enumerate(rows):
        for ci, (layer, text) in enumerate(row):
            x = X if ci == 0 else col2
            y = ly0 + ri * lh
            if x + 19 + tw(text, lsize) > (col2 - 16 if ci == 0 else W - X):
                fail(WHERE, f"mobile legend item '{text}' does not fit its column")
            leg.append(legend_dot(x + 5.5, y - lsize * 0.35, 5.5, layer))
            leg.append(T(x + 19, y, text, lsize, 400, MUTED))
    boxes.append((X, ly0 - lsize * 0.92, W - X, ly0 + (len(rows) - 1) * lh + lsize * 0.22))

    bodies = [(n, L, rx, MOBILE_THETA.get(n, th), r) for n, L, rx, th, r in BODIES]
    belt = [(n, rx, MOBILE_THETA.get(n, th), r) for n, rx, th, r in BELT_BODIES]
    m = OrbitMap(f"{WHERE} mobile", d, 300, 460, 0.94, k=0.40, bodies=bodies, belt_bodies=belt,
                 labels=[("sun", SUN_SIDES), ("Legaluga", ["l", "al", "bl"]), ("Legaluga MCP", ["a", "ar", "al", "b"]),
                         ("Atıf Denetimi", ["b", "bl", "br"]), ("Karar Kütüphanesi", ["a", "al", "ar"])],
                 links=LINKS, light_path=LIGHT_PATH, label_size=sizes["label"], min_label=MIN_MOBILE,
                 prefix="n", avoid=boxes, bounds=(12, 290, W - 12, ly0 - 34), belt_n=270, seed=11)

    st, stcss = stars(W, H, 100, 5, boxes + [b for b, _ in m.pills])
    label, title = aria(d)
    defs = [m.defs(), card_clip("card", W, H)]
    body = [card_base(W, H), st, m.haze(), m.orbits(), m.belt(), m.links_svg(), m.sun(), m.planets(), m.light(),
            m.labels(), "<g>"]
    for y, t, sz, wt, fill, fam, ls in copy:
        body.append(T(X, y, t, sz, wt, fill, fam, ls=ls))
    body.append("</g>")
    body += leg
    svg = (svg_open(W, H, label, title) + "<defs>" + "\n".join(defs) + "</defs>\n" + style_block(stcss + m.css) + "\n"
           + '<g clip-path="url(#card)">' + "\n".join(body) + "</g>\n" + card_border(W, H) + "\n</svg>\n")
    write(out_dir, "hero-mobile.svg", svg)
    print(m.report())
    print(f"[{WHERE} mobile] H={H}; comet head at {[round(v) for v in m.comet_head0]}")


# ---------------------------------------------------------------- sign-off mark (the imer.app favicon)
def mark(d, out_dir):
    idn = d["identity"]
    label = f"{idn['hub']}: {idn['tagline_tr'].rstrip('.')}"
    svg = (svg_open(64, 64, label, label)
           + '<defs><radialGradient id="g" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffe2a8"/>'
             '<stop offset=".55" stop-color="#f2b35b"/><stop offset="1" stop-color="#f2b35b" stop-opacity="0"/>'
             '</radialGradient></defs>'
           + f'<rect width="64" height="64" rx="14" fill="{BG}"/>'
             '<rect x=".5" y=".5" width="63" height="63" rx="13.5" stroke="' + LINE + '"/>'
             '<ellipse cx="32" cy="34" rx="25" ry="11" stroke="#5fd0c5" stroke-opacity=".55" stroke-width="1.6" '
             'transform="rotate(-14 32 34)"/>'
             '<circle cx="32" cy="33" r="14" fill="url(#g)"/><circle cx="32" cy="33" r="7.5" fill="#ffd27d"/>'
             '<circle cx="54" cy="27" r="3.4" fill="#5fd0c5"/></svg>\n')
    write(out_dir, "mark.svg", svg)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 hero.py OUT_DIR")
    out_dir = sys.argv[1]
    d = load_data()
    hero_desktop(d, out_dir)
    hero_mobile(d, out_dir)
    mark(d, out_dir)


if __name__ == "__main__":
    main()
