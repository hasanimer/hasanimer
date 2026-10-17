# Profil tasarımı · Profile design

`assets/*.svg` ve README'deki görsel blokları bu klasörden üretilir. Rakamlar ve metinler tek yerde durur: `data.json`.
The images in `assets/` and the generated blocks in `README.md` are built from this folder; all figures and copy live in `data.json`.

## Güncelleme · Updating

1. `data.json` içinde rakamı, kaynağını veya tarihini değiştir. / Edit a figure, its source or date in `data.json`.
2. `design/build.sh` çalıştır. / Run `design/build.sh`.

`build.sh` şunları yapar / does:

- `hero.py`, `metrics.py` ve `cards.py` SVG kaynaklarını üretir (yazılar `<text>` olarak).
- `outline.py` yazıları Geist / Geist Mono ile vektöre çevirir; GitHub'da yazı tipi yüklenmeden aynı görünür.
- `compact.py` yol verisini küçültür.
- `readme.py`, README'deki `<!-- gen:... -->` bloklarını yeniler (görsel, alt metin, kaynak listesi). Blok dışındaki metne dokunmaz.

Proje eklemek için yalnızca README'deki tabloya bir satır eklemek yeter. / To add a project, add a row to the table in `README.md`; no rebuild needed.

## Gereksinimler · Requirements

```sh
pip install fonttools uharfbuzz
npm pack geist && tar xzf geist-*.tgz   # statik TTF'ler: package/dist/fonts/geist-sans, geist-mono
export GEIST_DIR=/yol/geist-ttf          # Geist-*.ttf ve GeistMono-*.ttf aynı klasörde
design/build.sh
```

Geist yazı tipleri SIL Open Font License ile dağıtılır: https://github.com/vercel/geist-font
