"""Shrink outlined SVGs: rewrite every path `d` as relative commands rounded to 0.1 px.

Usage: python3 compact.py file.svg  (in place)
Rounding happens on absolute coordinates first, so relative steps never drift.
"""
import re
import sys

TOK = re.compile(r"[MLHVQCZmlhvqcz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")
NARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6, "Z": 0}


def fmt(v):
    v = round(v, 1)
    if v == int(v):
        s = str(int(v))
    else:
        s = f"{v:.1f}"
        if s.startswith("0."):
            s = s[1:]
        elif s.startswith("-0."):
            s = "-" + s[2:]
    return s


def join(nums):
    out = ""
    for n in nums:
        if out and not n.startswith("-"):
            out += " "
        out += n
    return out


def compact(d):
    toks = TOK.findall(d)
    i, cmd = 0, None
    cx = cy = sx = sy = 0.0
    res, last = [], None
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                res.append("z")
                cx, cy = sx, sy
                last = "z"
                continue
        if cmd is None or cmd.islower():
            raise ValueError("unexpected path data: " + d[:80])
        n = NARGS[cmd]
        vals = [round(float(v), 1) for v in toks[i:i + n]]
        i += n
        if cmd == "M":
            rel = [vals[0] - cx, vals[1] - cy]
            cx, cy = vals
            sx, sy = cx, cy
            c = "m"
            cmd = "L"  # extra coordinate pairs after M are implicit linetos
        elif cmd == "L":
            rel = [vals[0] - cx, vals[1] - cy]
            cx, cy = vals
            c = "l"
        elif cmd == "H":
            rel = [vals[0] - cx]
            cx = vals[0]
            c = "h"
        elif cmd == "V":
            rel = [vals[0] - cy]
            cy = vals[0]
            c = "v"
        elif cmd == "Q":
            rel = [vals[0] - cx, vals[1] - cy, vals[2] - cx, vals[3] - cy]
            cx, cy = vals[2], vals[3]
            c = "q"
        elif cmd == "C":
            rel = [vals[0] - cx, vals[1] - cy, vals[2] - cx, vals[3] - cy, vals[4] - cx, vals[5] - cy]
            cx, cy = vals[4], vals[5]
            c = "c"
        nums = [fmt(v) for v in rel]
        body = join(nums)
        if c == last and c != "m":
            res.append(("" if body.startswith("-") else " ") + body)
        else:
            res.append(c + body)
        last = c
    return "".join(res)


def main():
    path = sys.argv[1]
    s = open(path).read()
    before = len(s)
    s = re.sub(r'(<path[^>]*?\sd=")([^"]*)(")', lambda m: m.group(1) + compact(m.group(2)) + m.group(3), s)
    open(path, "w").write(s)
    print(f"compact {path}: {before} -> {len(s)} bytes")


if __name__ == "__main__":
    main()
