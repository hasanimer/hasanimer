#!/usr/bin/env python3
"""Regenerate the generated blocks of README.md.

Usage: python3 readme.py ../README.md

Blocks live between HTML comment markers, e.g. <!-- gen:hero --> ... <!-- /gen:hero -->.
Alt text is the aria-label of the built desktop SVG (itself generated from data.json),
so the picture, its description and the README never drift apart. The metrics block
also lists every figure with its source as real text. Text outside markers is left alone.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))


def aria(name):
    svg = open(os.path.join(ROOT, "assets", f"{name}.svg"), encoding="utf-8").read()
    m = re.search(r'<svg[^>]*\saria-label="([^"]*)"', svg)
    if not m:
        sys.exit(f"readme.py: assets/{name}.svg has no aria-label")
    return m.group(1)


def picture(name, indent=""):
    return "\n".join([
        f"{indent}<picture>",
        f'{indent}  <source media="(max-width: 600px)" srcset="assets/{name}-mobile.svg">',
        f'{indent}  <img src="assets/{name}.svg" width="100%" alt="{aria(name)}">',
        f"{indent}</picture>",
    ])


def hero():
    url = DATA["identity"]["hub_url"]
    return f'<p>\n  <a href="{url}">\n{picture("hero", "    ")}\n  </a>\n</p>'


def metrics():
    m = DATA["metrics"]
    rows = []
    for it in m["items"]:
        value = f'{it["value"]} {it["unit"]}'.strip()
        rows.append(f'- **{value}** {it["label_tr"]} · {it["label_en"]}<br>'
                    f'<sub>Kaynak / source: <code>{it["source"]}</code></sub>')
    return "\n".join([
        f'<p>\n  <a href="{DATA["identity"]["hub_url"]}">\n{picture("metrics", "    ")}\n  </a>\n</p>',
        "",
        "<details>",
        "<summary>Rakamlar ve kaynakları · Figures and sources</summary>",
        "",
        *rows,
        "",
        f'<sub>{m["note_tr"]} {m["note_en"]}</sub>',
        "",
        "</details>",
    ])


def card(name):
    return f"<p>\n{picture(name, '  ')}\n</p>"


BLOCKS = {
    "hero": hero,
    "metrics": metrics,
    "system": lambda: card("system"),
    "principles": lambda: card("principles"),
}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "README.md")
    text = open(path, encoding="utf-8").read()
    for key, build in BLOCKS.items():
        pat = re.compile(rf"(<!-- gen:{key} -->)\n(?:.*?\n)?(<!-- /gen:{key} -->)", re.S)
        if not pat.search(text):
            sys.exit(f"readme.py: marker gen:{key} not found in {path}")
        body = build()
        text = pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)
    open(path, "w", encoding="utf-8").write(text)
    print(f"readme.py: updated {', '.join(BLOCKS)} in {path}")


if __name__ == "__main__":
    main()
