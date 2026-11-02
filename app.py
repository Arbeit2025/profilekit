"""
profilekit - アカウント開設キット
==================================
新しいアカウントを作るときの「名前候補＋アイコン画像＋自己紹介文」を
1画面でセット生成する単一ファイル Flask アプリ。

accountnamemaker（名前候補生成）と accountimagemaker（seed 式アイコン生成）
の合体版。各候補のアイコンは、その名前文字列から決定的に導いた seed で
生成するので、同じ名前＋同じスタイルでは必ず同じ画像になる。

目次
----
1. 単語リストと自己紹介テンプレ
2. 名前生成ロジック
3. アイコン生成（identicon / geometric / pixel）
4. 画面（HTML）とルーティング

依存は Flask と Pillow のみ。DB は使わない。
"""

from __future__ import annotations

import colorsys
import hashlib
import io
import os
import random
import re

from flask import Flask, jsonify, render_template_string, request, send_file
from PIL import Image, ImageDraw

# ============================
# 1. 単語リストと自己紹介テンプレ
# ============================

THEMES = {
    "cute": [
        "mochi", "pudding", "sakura", "honey", "milky", "peach",
        "cocoa", "mimi", "lulu", "maru", "fuwa", "poko",
        "chibi", "usagi", "neko", "panda", "ringo", "ichigo",
    ],
    "cool": [
        "shadow", "blade", "nova", "vortex", "onyx", "raven",
        "zero", "storm", "wolf", "phantom", "eclipse", "drift",
        "falcon", "venom", "axis", "rogue", "night", "crimson",
    ],
    "nature": [
        "sora", "umi", "hoshi", "tsuki", "kaze", "hana",
        "mori", "kawa", "ame", "yuki", "taiyo", "kumo",
        "leaf", "river", "ocean", "forest", "meadow", "stone",
    ],
    "stylish": [
        "lumi", "astra", "velo", "noir", "ciel", "aura",
        "bijou", "eclat", "muse", "opal", "serene", "vivid",
        "gloss", "prism", "silk", "azure", "ivory", "pearl",
    ],
    "game": [
        "quest", "pixel", "mana", "loot", "boss", "combo",
        "level", "sword", "shield", "magic", "dragon", "hero",
        "respawn", "guild", "arcade", "dungeon", "potion", "critical",
    ],
    "food": [
        "cocoa", "mocha", "chai", "latte", "soda", "ramen",
        "sushi", "curry", "pasta", "waffle", "donut", "cookie",
        "melon", "lemon", "mint", "butter", "cream", "miso",
    ],
    "space": [
        "astro", "cosmo", "luna", "solar", "orbit", "comet",
        "nebula", "galaxy", "meteor", "star", "moon", "planet",
        "rocket", "saturn", "vega", "altair", "polaris", "zenith",
    ],
}

THEME_LABELS = {
    "cute": "かわいい",
    "cool": "かっこいい",
    "nature": "自然・和風",
    "stylish": "おしゃれ",
    "game": "ゲーム風",
    "food": "食べ物・カフェ",
    "space": "宇宙・星",
    "random": "おまかせ",
}
THEME_ORDER = ["cute", "cool", "nature", "stylish", "game", "food", "space", "random"]

PREFIXES = ["the", "its", "hello", "just", "mr", "ms"]

# 自己紹介文テンプレ（テーマ別・各3パターン以上）。{name} に名前が入る。
BIO_TEMPLATES = {
    "cute": [
        "{name} です。かわいいものと甘いものが大好き。のんびり更新していきます。",
        "{name} と申します。ふわふわした日常をつぶやくアカウントです。よろしくお願いします。",
        "{name} です。小さな幸せを集めるのが趣味。仲良くしてください。",
    ],
    "cool": [
        "{name} です。静かに、でも確実に。気になったことをつぶやきます。",
        "{name} と言います。硬派なものと夜の静けさが好き。フォロー歓迎。",
        "{name} です。多くは語りません。たまに本音を置いていきます。",
    ],
    "nature": [
        "{name} です。空と緑と、季節の移ろいを眺めるのが好きなアカウントです。",
        "{name} と申します。散歩と写真と、ゆるい日常の記録。よろしくどうぞ。",
        "{name} です。自然の小さな変化を拾って投稿しています。",
    ],
    "stylish": [
        "{name} です。美しいもの、洗練されたものを集めるアカウント。よろしくお願いします。",
        "{name} と申します。デザインと色と余白が好き。気ままに更新します。",
        "{name} です。日常を少しだけおしゃれに切り取る練習中。",
    ],
    "game": [
        "{name} です。ゲーム大好きアカウント。プレイ記録と攻略メモを置いていきます。",
        "{name} と言います。RPGとパズルが主食。レベル上げは計画的に。",
        "{name} です。新作チェックと積みゲー消化が日課です。対戦も歓迎。",
    ],
    "food": [
        "{name} です。カフェ巡りとおいしいものの記録アカウント。飯テロ注意。",
        "{name} と申します。甘いものとコーヒーで生きています。おすすめ募集中。",
        "{name} です。作ったもの・食べたものを気ままに投稿します。",
    ],
    "space": [
        "{name} です。星空と宇宙の話題が好き。夜更かし気味のアカウントです。",
        "{name} と申します。月と星と、少しのロマンを投稿しています。",
        "{name} です。天体観測と宇宙ニュースの感想置き場。",
    ],
    "random": [
        "{name} です。気ままに始めた新しいアカウント。よろしくお願いします。",
        "{name} と申します。好きなことを好きなときに投稿します。",
        "{name} です。日常の記録と小さな発見を置いていく場所。",
    ],
}

STYLES = {
    "identicon": "Identicon（5×5ブロック）",
    "geometric": "Geometric（幾何学模様）",
    "pixel": "Pixel（ドット絵フェイス）",
}
STYLE_ORDER = ["identicon", "geometric", "pixel"]
ICON_SIZE = 256
CANDIDATE_COUNT = 6

app = Flask(__name__)


# ============================
# 2. 名前生成ロジック
# ============================


def sanitize_keyword(raw: str) -> str:
    """キーワードをアカウント名に使える形（小文字英数と _ .）へ整える。"""
    word = (raw or "").strip().lower()
    word = re.sub(r"[^a-z0-9_.]", "", word)
    return word.strip("._")


def _one_name(theme: str, keyword: str, use_numbers: bool,
              rng: random.Random) -> str:
    theme_name = theme
    if theme_name == "random":
        theme_name = rng.choice(sorted(THEMES))
    words = THEMES[theme_name]
    sep = rng.choice(["", "_", "."])

    if keyword:
        pattern = rng.choice(["kw_word", "word_kw", "kw_only", "kw_word"])
        if pattern == "kw_word":
            base = keyword + sep + rng.choice(words)
        elif pattern == "word_kw":
            base = rng.choice(words) + sep + keyword
        else:
            base = keyword
    else:
        pattern = rng.choice(["two", "two", "one", "prefix_one"])
        if pattern == "two":
            a, b = rng.sample(words, 2)
            base = a + sep + b if sep else a + b
        elif pattern == "prefix_one":
            base = rng.choice(PREFIXES) + sep + rng.choice(words)
        else:
            base = rng.choice(words)

    if use_numbers and rng.random() < 0.4:
        base = base + str(rng.choice([rng.randint(2, 99),
                                       rng.randint(100, 999),
                                       rng.randint(2000, 2026)]))
    return base


def generate_names(theme: str = "random", keyword: str = "",
                   count: int = CANDIDATE_COUNT, use_numbers: bool = True,
                   max_length: int = 30, seed=None) -> list:
    """名前候補を count 件、重複なしで生成する。"""
    if theme != "random" and theme not in THEMES:
        raise ValueError(f"unknown theme: {theme}")
    if not isinstance(count, int) or count < 1 or count > 50:
        raise ValueError("count must be 1..50")
    if max_length < 4 or max_length > 64:
        raise ValueError("max_length must be 4..64")

    kw = sanitize_keyword(keyword)
    if keyword and keyword.strip() and not kw:
        raise ValueError("keyword has no usable characters")

    rng = random.Random(seed)
    names, seen = [], set()
    for _ in range(count * 60):
        if len(names) >= count:
            break
        name = _one_name(theme, kw, use_numbers, rng)
        if len(name) > max_length or name in seen:
            continue
        if not use_numbers and any(c.isdigit() for c in name):
            continue
        seen.add(name)
        names.append(name)
    return names


def seed_from_name(name: str) -> int:
    """名前文字列から決定的に seed（32bit 整数）を導く。"""
    digest = hashlib.sha256((name or "").encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def make_bio(name: str, theme: str) -> str:
    """テーマ別テンプレから、名前で決定的に1つ選んで自己紹介文を作る。"""
    templates = BIO_TEMPLATES.get(theme, BIO_TEMPLATES["random"])
    index = seed_from_name(name) % len(templates)
    return templates[index].format(name=name)


def build_kit(theme: str = "random", keyword: str = "", style: str = "identicon",
              use_numbers: bool = True, seed=None) -> list:
    """名前・アイコン種別・自己紹介文をまとめた候補リストを作る。"""
    names = generate_names(theme=theme, keyword=keyword,
                           count=CANDIDATE_COUNT, use_numbers=use_numbers,
                           seed=seed)
    return [
        {"name": name, "style": style, "bio": make_bio(name, theme)}
        for name in names
    ]


# ============================
# 3. アイコン生成
# ============================


def _hsl_to_rgb(h: float, s: float, lightness: float) -> tuple:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, lightness, s)
    return (int(r * 255), int(g * 255), int(b * 255))


def make_palette(rng: random.Random) -> dict:
    """背景・前景・アクセントの3色。明度差でコントラストを確保する。"""
    hue = rng.random()
    accent_shift = rng.choice([0.08, -0.08, 0.5])
    if rng.random() < 0.35:
        bg = _hsl_to_rgb(hue, rng.uniform(0.25, 0.45), rng.uniform(0.08, 0.16))
        fg = _hsl_to_rgb(hue, rng.uniform(0.45, 0.70), rng.uniform(0.62, 0.80))
        accent = _hsl_to_rgb(hue + accent_shift,
                             rng.uniform(0.50, 0.75), rng.uniform(0.55, 0.72))
    else:
        bg = _hsl_to_rgb(hue, rng.uniform(0.30, 0.55), rng.uniform(0.84, 0.92))
        fg = _hsl_to_rgb(hue, rng.uniform(0.50, 0.75), rng.uniform(0.22, 0.40))
        accent = _hsl_to_rgb(hue + accent_shift,
                             rng.uniform(0.50, 0.80), rng.uniform(0.30, 0.48))
    return {"bg": bg, "fg": fg, "accent": accent}


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _draw_identicon(rng: random.Random, palette: dict, size: int) -> Image.Image:
    """5×5 左右対称ブロック。"""
    cells = 5
    unit = 40
    img = Image.new("RGB", (cells * unit, cells * unit), palette["bg"])
    draw = ImageDraw.Draw(img)
    half = (cells + 1) // 2
    for y in range(cells):
        for x in range(half):
            if rng.random() < 0.52:
                color = palette["accent"] if rng.random() < 0.22 else palette["fg"]
                for xx in {x, cells - 1 - x}:
                    draw.rectangle(
                        [xx * unit, y * unit,
                         (xx + 1) * unit - 1, (y + 1) * unit - 1],
                        fill=color,
                    )
    return img.resize((size, size), Image.NEAREST)


def _draw_geometric(rng: random.Random, palette: dict, size: int) -> Image.Image:
    """グラデーション背景＋円・三角形・線。2倍で描いて縮小する。"""
    ss = 2
    w = size * ss
    top = _lerp_color(palette["bg"], palette["accent"], 0.35)
    bottom = palette["bg"]
    img = Image.new("RGB", (w, w), bottom)
    draw = ImageDraw.Draw(img)
    for yy in range(w):
        draw.line([(0, yy), (w, yy)],
                  fill=_lerp_color(top, bottom, yy / max(w - 1, 1)))

    overlay = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    def rgba(color, alpha):
        return (color[0], color[1], color[2], alpha)

    for _ in range(rng.randint(3, 6)):
        cx, cy = rng.uniform(0, w), rng.uniform(0, w)
        r = rng.uniform(0.07, 0.34) * w
        color = palette["fg"] if rng.random() < 0.6 else palette["accent"]
        if rng.random() < 0.35:
            od.ellipse([cx - r, cy - r, cx + r, cy + r],
                       outline=rgba(color, rng.randint(140, 220)),
                       width=max(2, int(w * 0.012)))
        else:
            od.ellipse([cx - r, cy - r, cx + r, cy + r],
                       fill=rgba(color, rng.randint(70, 170)))
    for _ in range(rng.randint(1, 3)):
        pts = [(rng.uniform(0, w), rng.uniform(0, w)) for _ in range(3)]
        color = palette["accent"] if rng.random() < 0.5 else palette["fg"]
        od.polygon(pts, fill=rgba(color, rng.randint(60, 150)))
    for _ in range(rng.randint(2, 4)):
        x1, y1 = rng.uniform(0, w), rng.uniform(0, w)
        x2, y2 = rng.uniform(0, w), rng.uniform(0, w)
        color = palette["fg"] if rng.random() < 0.5 else palette["accent"]
        od.line([(x1, y1), (x2, y2)],
                fill=rgba(color, rng.randint(120, 210)),
                width=max(2, int(w * rng.uniform(0.006, 0.02))))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return img.resize((size, size), Image.LANCZOS)


def _draw_pixel(rng: random.Random, palette: dict, size: int) -> Image.Image:
    """16×16 ドット絵の簡易フェイス。"""
    grid = 16
    unit = 10
    img = Image.new("RGB", (grid * unit, grid * unit), palette["bg"])
    draw = ImageDraw.Draw(img)

    def px(x, y, color):
        if 0 <= x < grid and 0 <= y < grid:
            draw.rectangle(
                [x * unit, y * unit, (x + 1) * unit - 1, (y + 1) * unit - 1],
                fill=color,
            )

    dark = (34, 32, 44)
    face = palette["fg"]

    cx, cy = 7.5, 8.0
    rx = rng.uniform(5.2, 6.0)
    ry = rng.uniform(5.8, 6.6)
    for y in range(grid):
        for x in range(grid):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                px(x, y, face)

    deco = rng.choice(["ears", "antenna", "none"])
    if deco == "ears":
        for dx, dy in [(2, 1), (3, 1), (3, 2), (12, 1), (13, 1), (12, 2)]:
            px(dx, dy, face)
    elif deco == "antenna":
        for dy in range(0, 3):
            px(8, dy, face)
        px(8, 0, palette["accent"])

    eye_y = rng.choice([6, 7])
    eye_h = rng.choice([1, 2])
    wink = rng.random() < 0.18
    for dy in range(eye_h):
        px(5, eye_y + dy, dark)
        if not wink:
            px(10, eye_y + dy, dark)
    if wink:
        px(10, eye_y, dark)

    mouth_y = rng.choice([10, 11])
    mouth = rng.choice(["smile", "flat", "open", "small"])
    if mouth == "smile":
        for dx, dy in [(6, 0), (9, 0), (7, 1), (8, 1)]:
            px(dx, mouth_y + dy, dark)
    elif mouth == "flat":
        for dx in range(6, 10):
            px(dx, mouth_y, dark)
    elif mouth == "open":
        for dx, dy in [(7, 0), (8, 0), (7, 1), (8, 1)]:
            px(dx, mouth_y + dy, palette["accent"])
    else:
        for dx in (7, 8):
            px(dx, mouth_y, dark)

    if rng.random() < 0.6:
        px(3, 9, palette["accent"])
        px(12, 9, palette["accent"])

    return img.resize((size, size), Image.NEAREST)


_GENERATORS = {
    "identicon": _draw_identicon,
    "geometric": _draw_geometric,
    "pixel": _draw_pixel,
}


def generate_icon(name: str, style: str) -> bytes:
    """名前と style から決定的にアイコンを生成し、PNG バイト列を返す。

    seed は名前文字列のハッシュから導くため、同じ名前＋同じスタイルでは
    必ず同じバイト列になる。
    """
    if style not in _GENERATORS:
        raise ValueError(f"unknown style: {style}")
    seed = seed_from_name(name)
    rng = random.Random(seed * 31 + STYLE_ORDER.index(style))
    palette = make_palette(rng)
    img = _GENERATORS[style](rng, palette, ICON_SIZE)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================
# 4. 画面（HTML）とルーティング
# ============================

INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>profilekit（アカウント開設キット）</title>
<style>
  body { font-family: sans-serif; margin: 2rem auto; max-width: 880px; padding: 0 1rem;
         background: #f4f7fb; color: #1d2b3a; }
  .card { background: #fff; border-radius: 12px; padding: 20px; margin: 16px 0;
          box-shadow: 0 2px 8px rgba(29,43,58,.10); }
  label { display: block; margin: 12px 0 4px; font-weight: bold; }
  input, select { padding: 10px; font-size: 1rem; width: 100%; box-sizing: border-box; }
  input[type="checkbox"] { width: auto; }
  button { padding: 12px 20px; font-size: 1.05rem; background: #1d4e79; color: #fff;
           border: 0; border-radius: 8px; cursor: pointer; width: 100%; margin-top: 16px; }
  .grid { display: flex; flex-wrap: wrap; gap: 1rem; }
  .kit { background: #fff; border-radius: 12px; padding: 16px; width: 240px;
         box-shadow: 0 2px 8px rgba(29,43,58,.10); }
  .kit img { width: 96px; height: 96px; border-radius: 12px; border: 1px solid #dbe4ee; }
  .kit .name { font-size: 1.15rem; font-weight: bold; margin: 10px 0 6px;
               word-break: break-all; }
  .kit .bio { font-size: .9rem; color: #40536a; }
  .hint { color: #5a7186; font-size: .9rem; }
</style>
</head>
<body>
<h1>profilekit（アカウント開設キット）</h1>
<p>新しいアカウントのための「名前候補＋アイコン＋自己紹介文」をセットで生成します。
アイコンは名前から決定的に作られるので、同じ名前ではいつも同じ絵になります。</p>
<p class="hint">※ 候補が各サービスで実際に使えるか（空き状況）は確認していません。</p>

<div class="card">
<form method="post" action="/generate">
  <label for="theme">テーマ</label>
  <select id="theme" name="theme">
    {% for key in theme_order %}
    <option value="{{ key }}"{% if key == theme %} selected{% endif %}>{{ theme_labels[key] }}</option>
    {% endfor %}
  </select>

  <label for="keyword">キーワード（任意・英数字）</label>
  <input id="keyword" name="keyword" value="{{ keyword | e }}" placeholder="例: cocoa">

  <label for="style">アイコンのスタイル</label>
  <select id="style" name="style">
    {% for key in style_order %}
    <option value="{{ key }}"{% if key == style %} selected{% endif %}>{{ styles[key] }}</option>
    {% endfor %}
  </select>

  <label><input type="checkbox" name="use_numbers" value="1"{% if use_numbers %} checked{% endif %}>
  数字をつける</label>

  <button type="submit">キットを生成</button>
</form>
</div>

{% if kits %}
<h2>候補キット（{{ kits | length }}件）</h2>
<div class="grid">
  {% for kit in kits %}
  <div class="kit">
    <img src="/icon?name={{ kit.name }}&style={{ kit.style }}" alt="{{ kit.name | e }} のアイコン">
    <div class="name">{{ kit.name | e }}</div>
    <div class="bio">{{ kit.bio | e }}</div>
  </div>
  {% endfor %}
</div>
{% endif %}
</body>
</html>
"""


def _parse_options(source):
    theme = source.get("theme", "random")
    if theme not in THEME_LABELS:
        theme = "random"
    style = source.get("style", "identicon")
    if style not in STYLES:
        style = "identicon"
    keyword = source.get("keyword", "")
    use_numbers = source.get("use_numbers") == "1"
    return theme, keyword, style, use_numbers


def _render(theme, keyword, style, use_numbers, kits):
    return render_template_string(
        INDEX_HTML,
        theme_labels=THEME_LABELS,
        theme_order=THEME_ORDER,
        styles=STYLES,
        style_order=STYLE_ORDER,
        theme=theme,
        keyword=keyword,
        style=style,
        use_numbers=use_numbers,
        kits=kits,
    )


@app.route("/", methods=["GET"])
def index():
    return _render("random", "", "identicon", True, [])


@app.route("/generate", methods=["GET", "POST"])
def generate():
    source = request.form if request.method == "POST" else request.args
    theme, keyword, style, use_numbers = _parse_options(source)
    try:
        kits = build_kit(theme=theme, keyword=keyword, style=style,
                         use_numbers=use_numbers)
    except ValueError:
        kits = build_kit(theme="random", keyword="", style=style,
                         use_numbers=use_numbers)
        theme, keyword = "random", ""
    return _render(theme, keyword, style, use_numbers, kits)


@app.route("/icon", methods=["GET"])
def icon():
    name = request.args.get("name")
    if not name:
        return ("name is required", 400)
    style = request.args.get("style", "identicon")
    if style not in STYLES:
        return (f"unknown style: {style}", 400)
    data = generate_icon(name, style)
    return send_file(io.BytesIO(data), mimetype="image/png")


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
