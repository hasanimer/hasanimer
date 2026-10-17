"""The tilted solar-system map used by hero.py (desktop and mobile variants).

Everything is computed: orbit projection, label pills (placed by a collision
search), the drift of unlabelled planets (restricted to arcs that never meet a
pill, a labelled body or another drifting planet) and the comet light. The
build fails with an error if any pill would cover a body, a link, the comet
path, or a drifting planet in any frame of its animation.
"""
import math
import os
import random

from _orbit_lib import (BG, CAP, CORE, CORE_HI, CORE_MID, LAYER, LINE, MUTED, TEXT, TEXT2, T, boxes_overlap,
                        circle_box_dist, f, f1, fail, mix, seg_box_dist, tw)

PILL_FILL = "#0a0e18"          # opaque: nothing shows through a label
PILL_STROKE = "#232c40"
CORE_PILL_FILL = mix(CORE, BG, 0.92)


class OrbitMap:
    TILT = -10.0
    K = 0.36                     # ellipse squash (view inclination)
    ORBITS = [(66, "infra"), (104, "product"), (142, "bridge"), (182, "product"), (222, "bridge"), (262, "product")]
    FAINT = (84, 123, 162, 202, 242)
    BELT = (292, 344)
    SUN_R = 19                   # disc radius (map units)
    CORONA_R = 52
    PULSE = 1.07                 # corona breathing scale

    def __init__(self, where, data, cx, cy, s, *, bodies, belt_bodies, labels, links, light_path,
                 label_size, min_label, prefix, avoid=(), bounds=None, belt_n=300, seed=7, k=None):
        self.where = where
        if k is not None:
            self.K = k
        self.cx, self.cy, self.s = cx, cy, s
        self.bodies = bodies              # [(name, layer, rx, theta, r)]
        self.belt_bodies = belt_bodies    # [(name, rx, theta, r)]
        self.labels_spec = labels         # [(name or "sun", [sides...])] in placement order
        self.links = links
        self.light_path = light_path
        self.label_size = label_size
        self.min_label = min_label
        self.p = prefix
        self.avoid = list(avoid)
        self.bounds = bounds
        self.belt_n = belt_n
        self.seed = seed
        self.css = []
        self.pills = []                   # (box, name)
        self._validate(data)
        self._layout()

    # ------------------------------------------------------------ data checks
    def _validate(self, data):
        known = {}
        for layer in data["system"]:
            if "title" in layer:
                known[layer["title"]] = layer["layer"]
            for it in layer.get("items", []):
                known[it["name"]] = layer["layer"]
        self.sun_name = next(L["title"] for L in data["system"] if L["layer"] == "core")
        for name, layer, *_ in self.bodies:
            if known.get(name) != layer:
                fail(self.where, f"map body '{name}' ({layer}) is not a {layer} item in data.json")
        for name, *_ in self.belt_bodies:
            if known.get(name) != "source":
                fail(self.where, f"belt body '{name}' is not an external system in data.json")

    # ------------------------------------------------------------ projection
    def P(self, rx, th):
        t = math.radians(th)
        x0, y0 = rx * math.cos(t), self.K * rx * math.sin(t)
        a = math.radians(self.TILT)
        x = x0 * math.cos(a) - y0 * math.sin(a)
        y = x0 * math.sin(a) + y0 * math.cos(a)
        return self.cx + self.s * x, self.cy + self.s * y

    @staticmethod
    def depth(th):
        return (math.sin(math.radians(th)) + 1) / 2   # 0 back .. 1 front (theta 90 = nearest)

    def dscale(self, th):
        return 0.84 + 0.28 * self.depth(th)

    def glow_clear(self):
        """Radius around the sun that labels keep clear of: the visible corona at its largest pulse, plus air."""
        return self.CORONA_R * self.s * self.PULSE * 0.86 + 7 * self.s

    # ------------------------------------------------------------ layout
    def _layout(self):
        s = self.s
        self.pos = {}
        self.static = []                  # (x, y, r, name): circles labels and drift must avoid
        self.static.append((self.cx, self.cy, self.SUN_R * s + 3, "sun"))
        self.planet_r = {}
        labelled = {n for n, _ in self.labels_spec}
        for name, layer, rx, th, r in self.bodies:
            x, y = self.P(rx, th)
            self.pos[name] = (x, y)
            rv = r * s * self.dscale(th)
            self.planet_r[name] = rv
            if name in labelled:
                self.static.append((x, y, rv * 1.8, name))
        for name, rx, th, r in self.belt_bodies:
            x, y = self.P(rx, th)
            self.pos[name] = (x, y)
            rv = r * s * self.dscale(th)
            self.planet_r[name] = rv
            self.static.append((x, y, rv + 1.5, name))
        self.light_pts = [self.pos[n] for n in self.light_path]
        self.link_segs = [(self.pos[a], self.pos[b], a, b) for a, b in self.links]
        for (p1, p2, a, b) in self.link_segs:
            vx, vy = p2[0] - p1[0], p2[1] - p1[1]
            t = max(0, min(1, ((self.cx - p1[0]) * vx + (self.cy - p1[1]) * vy) / (vx * vx + vy * vy)))
            dd = math.dist((self.cx, self.cy), (p1[0] + t * vx, p1[1] + t * vy))
            if dd < self.SUN_R * s + 12:
                fail(self.where, f"link {a} -> {b} passes {dd:.0f}px from the sun centre")
        self._place_labels()
        self._solve_drift()
        self._comet_setup()

    # ------------------------------------------------------------ labels
    def pill_style(self, kind):
        if kind == "core":
            size = self.label_size + 2
            return dict(size=size, weight=600, fill=CORE, h=size * 1.7, padx=size * 0.66)
        if kind == "source":
            size = max(self.label_size - 1, self.min_label)
            return dict(size=size, weight=500, fill=TEXT2, h=size * 1.66, padx=size * 0.64)
        size = self.label_size
        return dict(size=size, weight=500, fill=TEXT, h=size * 1.66, padx=size * 0.64)

    def _candidates(self, x, y, r, w, h, sides, gap):
        d = r + gap
        dd = (r + gap) * 0.72
        for side in sides:
            if side == "b":
                yield side, (x - w / 2, y + d)
            elif side == "a":
                yield side, (x - w / 2, y - d - h)
            elif side == "l":
                yield side, (x - d - w, y - h / 2)
            elif side == "r":
                yield side, (x + d, y - h / 2)
            elif side == "br":
                yield side, (x + dd, y + dd)
            elif side == "bl":
                yield side, (x - dd - w, y + dd)
            elif side == "ar":
                yield side, (x + dd, y - dd - h)
            elif side == "al":
                yield side, (x - dd - w, y - dd - h)
            elif isinstance(side, tuple):      # ("sun", fraction of the pill left of the sun centre)
                yield side, (x - w * side[1], y + d) if side[0] == "below" else (x - w * side[1], y - d - h)

    def _pill_ok(self, box, owner, kind):
        why = []
        if self.bounds and not (box[0] >= self.bounds[0] and box[1] >= self.bounds[1]
                                and box[2] <= self.bounds[2] and box[3] <= self.bounds[3]):
            why.append("outside the map bounds")
        for ab in self.avoid:
            if boxes_overlap(box, ab, 10):
                why.append(f"overlaps text box {[round(v) for v in ab]}")
        for ob, on in self.pills:
            if boxes_overlap(box, ob, 6):
                why.append(f"overlaps label '{on}'")
        for (x, y, r, name) in self.static:
            if name == owner:
                continue
            if name == "sun":
                if circle_box_dist(x, y, box) < self.glow_clear():
                    why.append("sits on the sun's corona")
            elif circle_box_dist(x, y, box) < r + 3:
                why.append(f"covers body '{name}'")
        for name, layer, rx, th, r in self.bodies:      # unlabelled planets at their first-frame spot
            if name == owner or any(name == n for n, _ in self.labels_spec):
                continue
            x, y = self.pos[name]
            if circle_box_dist(x, y, box) < self.drift_extent(self.planet_r[name]) + 3:
                why.append(f"covers drifting planet '{name}' in frame 0")
        for (p1, p2, a, b) in self.link_segs:
            if owner in (a, b):
                # the link may touch its own body, but not run under that body's pill
                pass
            if seg_box_dist(p1, p2, box) < 2.5:
                why.append(f"covers link {a} -> {b}")
        for i in range(len(self.light_pts) - 1):
            if seg_box_dist(self.light_pts[i], self.light_pts[i + 1], box) < self.comet_halfwidth() + 2:
                why.append("covers the comet path")
        return why

    def _place_labels(self):
        s = self.s
        self.pill_svgs = []
        for name, sides in self.labels_spec:
            if name == "sun":
                kind, x, y, r, text = "core", self.cx, self.cy, 0.0, self.sun_name
                gap = self.glow_clear()
            elif name in self.planet_r and any(n == name for n, *_ in self.belt_bodies):
                kind, (x, y), r, text = "source", self.pos[name], self.planet_r[name], name
                gap = 6 * s
            else:
                layer = next(L for n, L, *_ in self.bodies if n == name)
                kind, (x, y), r, text = layer, self.pos[name], self.planet_r[name] * 1.8, name
                gap = 6 * s
            st = self.pill_style(kind)
            w = tw(text, st["size"], st["weight"]) + 2 * st["padx"]
            h = st["h"]
            tried = []
            for side, (bx, by) in self._candidates(x, y, r, w, h, sides, gap):
                box = (bx, by, bx + w, by + h)
                why = self._pill_ok(box, name if name != "sun" else "sun", kind)
                if not why:
                    if tried and os.environ.get("ORBIT_DEBUG") == "1":
                        print("DEBUG", self.where, f"'{text}' placed {side} after:\n    " + "\n    ".join(tried))
                    break
                tried.append(f"{side}: {'; '.join(sorted(set(why)))}")
            else:
                msg = f"no collision-free spot for the '{text}' label:\n    " + "\n    ".join(tried)
                if os.environ.get("ORBIT_DEBUG") != "1":       # layout-debug aid only; never set in build.sh
                    fail(self.where, msg)
                print("DEBUG", self.where, msg)
                side, (bx, by) = next(self._candidates(x, y, r, w, h, sides, gap))
                box = (bx, by, bx + w, by + h)
            self.pills.append((box, text))
            ty = by + h / 2 + st["size"] * CAP / 2
            stroke = (f' stroke="{CORE}" stroke-opacity=".38"' if kind == "core" else f' stroke="{PILL_STROKE}"')
            fill = CORE_PILL_FILL if kind == "core" else PILL_FILL
            self.pill_svgs.append(
                f'<rect x="{f(bx)}" y="{f(by)}" width="{f(w)}" height="{f(h)}" rx="{f(h / 2)}" fill="{fill}"{stroke}/>'
                + T(bx + w / 2, ty, text, st["size"], st["weight"], st["fill"], anchor="middle"))

    # ------------------------------------------------------------ drift
    @staticmethod
    def drift_extent(rv):
        """Visible radius of a drifting planet: its disc plus the brighter part of its halo."""
        return max(rv + 3, rv * 1.6)

    def _blocked(self, x, y, ext, owner, sweeps):
        """Reason a drifting planet may not be at (x, y), or '' if the spot is free."""
        for box, label in self.pills:
            if circle_box_dist(x, y, box) < ext + 4:
                return f"the '{label}' label"
        for (sx, sy, sr, name) in self.static:
            if name != owner and math.dist((x, y), (sx, sy)) < ext + sr + 3:
                return f"body '{name}'"
        for (sx, sy, sr, name) in sweeps:
            if name != owner and math.dist((x, y), (sx, sy)) < ext + sr + 2:
                return f"the drift path of '{name}'"
        return ""

    def _solve_drift(self):
        """Each unlabelled planet librates slowly along the largest pill-free arc around its spot."""
        labelled = {n for n, _ in self.labels_spec}
        self.drift = {}
        A_MAX = 16.0
        # every other planet's first-frame spot is an obstacle from the start, so an earlier
        # planet's arc never reaches a later planet's spot; solved arcs are added as they come
        sweeps = [(*self.pos[n], self.drift_extent(r * self.s * self.dscale(th)), n)
                  for n, _, rx, th, r in self.bodies if n not in labelled]
        for name, layer, rx, th0, r in self.bodies:
            if name in labelled:
                continue
            rr = r * self.s

            def ext(th):
                return self.drift_extent(rr * self.dscale(th))

            x0, y0 = self.P(rx, th0)
            why = self._blocked(x0, y0, ext(th0), name, sweeps)
            if why:
                fail(self.where, f"drifting planet '{name}' starts on {why}; move it (theta) or that label")
            lo = hi = th0
            step = 0.25
            while hi - th0 < 2 * A_MAX + 4 and not self._blocked(*self.P(rx, hi + step), ext(hi + step), name, sweeps):
                hi += step
            while th0 - lo < 2 * A_MAX + 4 and not self._blocked(*self.P(rx, lo - step), ext(lo - step), name, sweeps):
                lo -= step
            lo, hi = lo + 2.0, hi - 2.0                     # safety margin inside the free arc
            lo, hi = max(lo, th0 - 2 * A_MAX), min(hi, th0 + 2 * A_MAX)
            if hi - lo < 4 or not (lo <= th0 <= hi):
                self.drift[name] = None                       # no room: this planet stays still
                sweeps.append((x0, y0, ext(th0), name))
                continue
            c, A = (lo + hi) / 2, min((hi - lo) / 2, A_MAX)
            lo, hi = c - A, c + A
            if not (lo <= th0 <= hi):                         # keep frame 0 on the planet's spot
                c = min(max(c, th0 - A), th0 + A)
            phase = math.asin(max(-1, min(1, (th0 - c) / A)))
            period = 110 * (rx / 180) ** 0.5
            N = 24
            frames = []
            for j in range(N + 1):
                th = c + A * math.sin(2 * math.pi * j / N + phase)
                x, y = self.P(rx, th)
                frames.append((100 * j / N, x, y, self.dscale(th)))
            self.drift[name] = (period, frames, rr)
            for j in range(N):
                for k in range(4):
                    t = k / 4
                    (_, xa, ya, sa), (_, xb, yb, sb) = frames[j], frames[j + 1]
                    sweeps.append((xa + (xb - xa) * t, ya + (yb - ya) * t,
                                   self.drift_extent(rr * (sa + (sb - sa) * t)), name))
        self._verify_drift()

    def _verify_drift(self):
        """Replay every keyframe segment the way CSS interpolates it and assert no pill is ever touched."""
        for name, spec in self.drift.items():
            if not spec:
                continue
            period, frames, rr = spec
            for j in range(len(frames) - 1):
                (_, xa, ya, sa), (_, xb, yb, sb) = frames[j], frames[j + 1]
                for k in range(21):
                    t = k / 20
                    x, y, sc = xa + (xb - xa) * t, ya + (yb - ya) * t, sa + (sb - sa) * t
                    e = self.drift_extent(rr * sc)
                    for box, label in self.pills:
                        if circle_box_dist(x, y, box) < e + 1:
                            fail(self.where, f"drifting planet '{name}' passes under the '{label}' label "
                                             f"at {frames[j][0]:.0f}%+ of its {period:.0f}s cycle")

    # ------------------------------------------------------------ svg pieces
    def defs(self):
        p, cx, cy, s = self.p, self.cx, self.cy, self.s
        out = []
        for name, c in LAYER.items():
            out.append(f'<radialGradient id="{p}s-{name}" cx=".36" cy=".32" r=".78">'
                       f'<stop offset="0" stop-color="{mix(c, "#ffffff", .45)}"/><stop offset=".48" stop-color="{c}"/>'
                       f'<stop offset="1" stop-color="{mix(c, BG, .6)}"/></radialGradient>')
            out.append(f'<radialGradient id="{p}b-{name}" cx=".38" cy=".3" r=".82">'
                       f'<stop offset="0" stop-color="{mix(c, "#ffffff", .3)}"/><stop offset=".5" stop-color="{mix(c, BG, .1)}"/>'
                       f'<stop offset="1" stop-color="{mix(c, BG, .58)}"/></radialGradient>')
            out.append(f'<radialGradient id="{p}h-{name}"><stop offset="0" stop-color="{c}" stop-opacity=".36"/>'
                       f'<stop offset=".45" stop-color="{c}" stop-opacity=".1"/>'
                       f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
        out.append(f'<radialGradient id="{p}limb" cx=".4" cy=".34" r=".72"><stop offset=".5" stop-color="{BG}" stop-opacity="0"/>'
                   f'<stop offset="1" stop-color="{BG}" stop-opacity=".5"/></radialGradient>')
        out.append(
            f'<radialGradient id="{p}haze" cx="{f(cx)}" cy="{f(cy)}" r="{f(230 * s)}" gradientUnits="userSpaceOnUse" '
            f'gradientTransform="translate({f(cx)} {f(cy)}) scale(1 .62) translate({f(-cx)} {f(-cy)})">'
            f'<stop offset="0" stop-color="{CORE}" stop-opacity=".38"/><stop offset=".2" stop-color="#d9893a" stop-opacity=".2"/>'
            f'<stop offset=".5" stop-color="#a5571f" stop-opacity=".08"/><stop offset="1" stop-color="#a5571f" stop-opacity="0"/>'
            f'</radialGradient>')
        out.append(f'<radialGradient id="{p}corona"><stop offset="0" stop-color="{CORE_HI}"/>'
                   f'<stop offset=".34" stop-color="{CORE_MID}" stop-opacity=".95"/>'
                   f'<stop offset=".6" stop-color="{CORE}" stop-opacity=".35"/>'
                   f'<stop offset="1" stop-color="{CORE}" stop-opacity="0"/></radialGradient>')
        out.append(f'<radialGradient id="{p}disk" cx=".42" cy=".38" r=".7"><stop offset="0" stop-color="#fffaf0"/>'
                   f'<stop offset=".55" stop-color="{CORE_HI}"/><stop offset="1" stop-color="{CORE_MID}"/></radialGradient>')
        top, bot = cy - 150 * s, cy + 150 * s
        for name in ("infra", "product", "bridge"):
            c = LAYER[name]
            o1, o2 = (0.16, 0.5) if name != "infra" else (0.3, 0.7)
            out.append(f'<linearGradient id="{p}o-{name}" x1="0" y1="{f(top)}" x2="0" y2="{f(bot)}" gradientUnits="userSpaceOnUse">'
                       f'<stop offset="0" stop-color="{c}" stop-opacity="{o1 * .55:.2f}"/>'
                       f'<stop offset=".5" stop-color="{c}" stop-opacity="{o1:.2f}"/>'
                       f'<stop offset="1" stop-color="{c}" stop-opacity="{o2:.2f}"/></linearGradient>')
        out.append(f'<filter id="{p}glow" x="-200%" y="-200%" width="500%" height="500%">'
                   f'<feGaussianBlur stdDeviation="{f(2.6 * s)}"/></filter>')
        return "\n".join(out)

    def haze(self):
        s = self.s
        return (f'<rect x="{f(self.cx - 260 * s)}" y="{f(self.cy - 200 * s)}" width="{f(520 * s)}" '
                f'height="{f(400 * s)}" fill="url(#{self.p}haze)"/>')

    def orbits(self):
        cx, cy, s = self.cx, self.cy, self.s
        rot = f'transform="rotate({f(self.TILT)} {f(cx)} {f(cy)})"'
        out = ['<g stroke-width="1">']
        for rx, layer in self.ORBITS:
            out.append(f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx * s)}" ry="{f(rx * self.K * s)}" {rot} '
                       f'stroke="url(#{self.p}o-{layer})"/>')
        for rx in self.FAINT:
            out.append(f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx * s)}" ry="{f(rx * self.K * s)}" {rot} '
                       f'stroke="{LINE}" stroke-opacity=".55"/>')
        out.append("</g>")
        return "\n".join(out)

    def belt(self):
        rnd = random.Random(self.seed)
        lo, hi = self.BELT
        keep_out = [b for b, _ in self.pills] + self.avoid
        out = ['<g>']
        for _ in range(self.belt_n):
            th = rnd.uniform(0, 360)
            u = (rnd.random() + rnd.random() + rnd.random()) / 3
            rx = lo + (hi - lo) * u
            x, y = self.P(rx, th)
            y += rnd.uniform(-3.2, 3.2) * self.s
            d = self.depth(th)
            r = (0.45 + rnd.random() ** 2.2 * 1.9) * (0.75 + 0.45 * d) * self.s
            op = 0.22 + 0.5 * d * rnd.uniform(0.6, 1.0) + rnd.uniform(0, 0.18)
            col = "#7c8aa5" if rnd.random() < 0.7 else "#a7b2c7"
            if any(circle_box_dist(x, y, b) < r + 2.5 for b in keep_out):
                continue
            if any(math.dist((x, y), (sx, sy)) < r + sr + 1.5 for sx, sy, sr, n in self.static if n != "sun"):
                continue
            out.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{f1(max(r, .5))}" fill="{col}" fill-opacity="{op:.2f}"/>')
        out.append("</g>")
        return "\n".join(out)

    def links_svg(self):
        hot = {tuple(self.light_path[i:i + 2]) for i in range(len(self.light_path) - 1)}
        out = [f'<g stroke="{MUTED}" stroke-width="{f(max(.9, self.s))}" stroke-dasharray="3 4" stroke-linecap="round">']
        for (p1, p2, a, b) in self.link_segs:
            op = ".36" if (a, b) in hot else ".24"
            out.append(f'<path d="M{f(p1[0])} {f(p1[1])}L{f(p2[0])} {f(p2[1])}" stroke-opacity="{op}"/>')
        out.append("</g>")
        return "\n".join(out)

    def sun(self):
        p, cx, cy, s = self.p, self.cx, self.cy, self.s
        self.css.append(f"@keyframes {p}pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale({self.PULSE})}}}}"
                        f".{p}pulse{{transform-origin:{f(cx)}px {f(cy)}px;animation:{p}pulse 7s ease-in-out infinite}}")
        return (f'<g><circle class="{p}pulse" cx="{f(cx)}" cy="{f(cy)}" r="{f(self.CORONA_R * s)}" fill="url(#{p}corona)"/>'
                f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(self.SUN_R * s)}" fill="url(#{p}disk)"/></g>')

    # banded gas-giant body, drawn around (0, 0) in the planet's own coordinates
    BANDS = (  # (centre y, half height, light?, opacity, wave amplitude, phase) as fractions of r
        (-0.62, 0.09, False, .42, .05, 0.0),
        (-0.30, 0.07, True, .30, .06, 1.3),
        (-0.04, 0.13, False, .36, .07, 2.1),
        (0.27, 0.06, True, .26, .05, .4),
        (0.52, 0.10, False, .40, .06, 2.8),
    )

    def _band_path(self, R, yc, hh, amp, ph):
        n = 7
        top, bot = [], []
        for i in range(n + 1):
            x = -1.15 * R + 2.3 * R * i / n
            top.append((x, R * (yc - hh + amp * math.sin(2.6 * x / R + ph))))
            bot.append((x, R * (yc + hh + amp * math.sin(2.6 * x / R + ph + .9))))
        pts = top + bot[::-1]
        return "M" + "L".join(f"{f1(x)} {f1(y)}" for x, y in pts) + "Z"

    def planet_body(self, uid, layer, R, strength=1.0):
        c = LAYER[layer]
        dark, light = mix(c, BG, .62), mix(c, "#ffffff", .45)
        bands = "".join(
            f'<path d="{self._band_path(R, yc, hh, amp, ph)}" fill="{light if lt else dark}" fill-opacity="{op * strength:.2f}"/>'
            for yc, hh, lt, op, amp, ph in self.BANDS)
        return (f'<clipPath id="{uid}"><circle r="{f(R)}"/></clipPath>'
                f'<circle r="{f(R)}" fill="url(#{self.p}b-{layer})"/>'
                f'<g clip-path="url(#{uid})"><g transform="rotate({f(self.TILT)})">{bands}</g>'
                f'<circle r="{f(R)}" fill="url(#{self.p}limb)"/></g>'
                f'<circle r="{f(R - .4)}" stroke="{mix(c, "#ffffff", .2)}" stroke-opacity=".5" stroke-width=".8"/>')

    def planets(self):
        p = self.p
        labelled = {n for n, _ in self.labels_spec}
        out = []
        for i, (name, layer, rx, th, r) in enumerate(self.bodies):
            x, y = self.pos[name]
            sc = self.dscale(th)
            rr = r * self.s
            halo = f'<circle r="{f(rr * 2.7)}" fill="url(#{p}h-{layer})"/>'
            if name in labelled:
                out.append(f'<g transform="translate({f(x)} {f(y)}) scale({sc:.3f})">'
                           f'<circle r="{f(rr * 1.8)}" stroke="{LAYER[layer]}" stroke-opacity=".3" stroke-width="{f(1 / sc)}"/>'
                           f'{halo}{self.planet_body(f"{p}c{i}", layer, rr)}</g>')
                continue
            spec = self.drift.get(name)
            body = f'{halo}{self.planet_body(f"{p}c{i}", layer, rr, .8)}'
            if spec:
                period, frames, _ = spec
                kf = "".join(f"{f(t)}%{{transform:translate({f1(fx)}px,{f1(fy)}px) scale({fs:.3f})}}"
                             for t, fx, fy, fs in frames)
                self.css.append(f"@keyframes {p}d{i}{{{kf}}}.{p}d{i}{{animation:{p}d{i} {f(period)}s linear infinite}}")
                t0, fx, fy, fs = frames[0]
                out.append(f'<g class="{p}d{i}" transform="translate({f1(fx)} {f1(fy)}) scale({fs:.3f})">{body}</g>')
            else:
                out.append(f'<g transform="translate({f(x)} {f(y)}) scale({sc:.3f})">{body}</g>')
        for name, rx, th, r in self.belt_bodies:
            x, y = self.pos[name]
            out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(self.planet_r[name])}" fill="url(#{p}s-source)"/>')
        return "\n".join(out)

    # ------------------------------------------------------------ the comet (a data light)
    def comet_halfwidth(self):
        return 5.2 * self.s

    def _comet_setup(self):
        """Where the comet sits in frame 0, checked so its head and tail touch no body in that frame."""
        pts = self.light_pts
        segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        s = self.s
        self.c_tail, self.c_head, self.c_len = 46 * s, .6 * s, sum(segs)
        r_first = self.planet_r.get(self.light_path[0], 3)
        s0 = min(segs[0] * 0.78, max(self.c_tail + r_first + 8 * s, segs[0] * 0.5))
        if s0 - self.c_tail < r_first + 2:
            fail(self.where, "comet tail would start inside its source body; lengthen the first link")
        self.c_s0 = s0
        frame0 = []
        for name, layer, rx, th, r in self.bodies:
            spec = self.drift.get(name)
            x, y = (spec[1][0][1], spec[1][0][2]) if spec else self.pos[name]
            frame0.append((name, x, y, self.drift_extent(self.planet_r[name]) if name not in self.light_path
                           else 0))
        for name, rx, th, r in self.belt_bodies:
            if name not in self.light_path:
                frame0.append((name, *self.pos[name], self.planet_r[name] + 2))
        for (p1, p2, a, b) in self.link_segs:           # no body may look attached to a link it is not on
            for name, bx, by, e in frame0:
                if e and name not in (a, b) and seg_box_dist(p1, p2, (bx, by, bx, by)) < e + 1.5:
                    fail(self.where, f"in frame 0 '{name}' sits on the {a} -> {b} link; move it (theta)")
        n = 40
        for i in range(n + 1):
            x, y = self._point_at(pts, s0 - self.c_tail + (self.c_tail + 6 * s) * i / n)
            for name, bx, by, e in frame0:
                if e and math.dist((x, y), (bx, by)) < e + self.comet_halfwidth() * .7:
                    fail(self.where, f"in frame 0 the comet sits on '{name}'; move that body (theta)")

    def light(self):
        """A data light running source -> Legaluga -> product: a glowing head and a tapered,
        fading tail (stacked dashes that share the head's position). Frame 0 shows it in flight."""
        pts = self.light_pts
        L = self.c_len
        s = self.s
        p = self.p
        tail, head, s0 = self.c_tail, self.c_head, self.c_s0
        lo, hi = -head, L + tail + head
        travel = 0.6
        dur = 10
        a = travel * (hi - s0) / (hi - lo) * 100
        b = a + (1 - travel) * 100
        gap = L + 2 * tail + 40
        d = "M" + "L".join(f"{f(x)} {f(y)}" for x, y in pts)

        def kf(name, length):
            def off(x):
                return f(length - x)
            return (f"@keyframes {name}{{0%{{stroke-dashoffset:{off(s0)}}}{f(a)}%{{stroke-dashoffset:{off(hi)}}}"
                    f"{f(a + .01)}%{{stroke-dashoffset:{off(lo)}}}{f(b)}%{{stroke-dashoffset:{off(lo)}}}"
                    f"100%{{stroke-dashoffset:{off(s0)}}}}}.{name}{{animation:{name} {dur}s linear infinite}}")

        layers = []
        K = 7
        for k in range(1, K + 1):            # k = 1 shortest (at the head) .. K longest (tail end)
            ln = tail * k / K
            w = s * (3.0 - 2.2 * (k - 1) / (K - 1))
            col = mix(CORE_MID, CORE, (k - 1) / (K - 1))
            self.css.append(kf(f"{p}t{k}", ln))
            layers.append(f'<path class="{p}t{k}" d="{d}" stroke="{col}" stroke-opacity=".2" stroke-width="{f(w)}" '
                          f'stroke-dasharray="{f(ln)} {f(gap)}" stroke-dashoffset="{f(ln - s0)}"/>')
        self.css.append(kf(f"{p}hd", head))
        cls = f'class="{p}hd" d="{d}" stroke-dasharray="{f(head)} {f(gap)}" stroke-dashoffset="{f(head - s0)}"'
        layers.append(f'<path {cls} stroke="{CORE}" stroke-opacity=".9" stroke-width="{f(13 * s)}" filter="url(#{p}glow)"/>')
        layers.append(f'<path {cls} stroke="#fff3d6" stroke-width="{f(3.8 * s)}"/>')
        self.comet_head0 = self._point_at(pts, s0)
        return '<g stroke-linecap="round" stroke-linejoin="round" fill="none">' + "".join(layers) + "</g>"

    @staticmethod
    def _point_at(pts, dist):
        for i in range(len(pts) - 1):
            seg = math.dist(pts[i], pts[i + 1])
            if dist <= seg:
                t = dist / seg
                return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
            dist -= seg
        return pts[-1]

    def labels(self):
        return "\n".join(self.pill_svgs)

    def report(self):
        out = [f"[{self.where}] pills: " + ", ".join(f"{n} {[round(v) for v in b]}" for b, n in self.pills)]
        moving = {n: v for n, v in self.drift.items() if v}
        still = [n for n, v in self.drift.items() if not v]
        out.append(f"[{self.where}] drifting: " + ", ".join(
            f"{n} ±{(max(fr[1] for fr in v[1]) - min(fr[1] for fr in v[1])) / 2:.0f}px/{v[0]:.0f}s" for n, v in moving.items())
            + (f"; still: {', '.join(still)}" if still else ""))
        return "\n".join(out)
