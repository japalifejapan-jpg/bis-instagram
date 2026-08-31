#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIS / D'sTs Instagram カルーセル画像ジェネレーター v2
- 出力 1031 x 1373 (横1031 / 縦1373)。投稿用は 4:5 に満たないため左右をクリームで詰めて 1099x1373 を別途出力。
- 1枚目は必ず商品画像を全面に敷く（商品紹介の場合）
- 中面も生成背景写真をベースに敷き、文字だけの質素さを避ける
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1031, 1373

CREAM      = (250, 246, 239)
CREAM_DEEP = (243, 234, 219)
BEIGE      = (236, 222, 199)
BROWN      = (58, 42, 31)
GOLD       = (183, 142, 42)
GOLD_LT    = (206, 172, 88)
SUB        = (118, 101, 86)
WHITE      = (255, 255, 255)

F_SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
F_SANS_R  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F_SANS_B  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
F_SANS_M  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"

def font(p, s): return ImageFont.truetype(p, s, index=0)

NO_HEAD = "、。）」』】〉》”’!?！？・…ー"

def wrap_jp(d, text, f, mw):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if d.textlength(cur + ch, font=f) <= mw:
            cur += ch
        elif ch in NO_HEAD and cur:
            lines.append(cur + ch); cur = ""
        else:
            lines.append(cur); cur = ch
    if cur: lines.append(cur)
    return lines

def draw_block(d, text, f, fill, x, y, mw, leading=1.55, align="center", shadow=None):
    lines = wrap_jp(d, text, f, mw)
    lh = int(f.size * leading)
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        lx = x + (mw - tw) / 2 if align == "center" else (x + mw - tw if align == "right" else x)
        if shadow:
            d.text((lx + 2, y + i * lh + 2), ln, font=f, fill=shadow)
        d.text((lx, y + i * lh), ln, font=f, fill=fill)
    return y + len(lines) * lh

def block_h(d, text, f, mw, leading=1.55):
    return len(wrap_jp(d, text, f, mw)) * int(f.size * leading)

# ---------- 素材 ----------
def load_cover(path, w=W, h=H):
    """全面カバー用に縦横比を保ってセンタークロップ"""
    im = Image.open(path).convert("RGB")
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = int((im.height - h) * 0.35)
    return im.crop((left, top, left + w, top + h))

def cream_base(bg=None, strength=0.90):
    """クリーム地。bg があれば大きくぼかして薄く敷き、質感を出す。"""
    base = Image.new("RGB", (W, H), CREAM)
    if bg and os.path.exists(bg):
        im = load_cover(bg).filter(ImageFilter.GaussianBlur(46))
        im = ImageEnhance.Color(im).enhance(0.55)
        im = ImageEnhance.Brightness(im).enhance(1.18)
        base = Image.blend(im, base, strength)
    # 上下のやわらかい光
    ov = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(ov)
    d.ellipse((-W * 0.3, -H * 0.75, W * 1.3, H * 0.55), fill=40)
    ov = ov.filter(ImageFilter.GaussianBlur(200))
    return Image.composite(Image.new("RGB", (W, H), WHITE), base, ov)

def scrim(img, frac=0.62, color=CREAM, side="bottom"):
    """写真の上に、下(または右)からクリーム色のグラデーションを重ねる"""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    if side == "bottom":
        top = int(H * (1 - frac))
        for y in range(top, H):
            t = (y - top) / max(1, H - top)
            d.line([(0, y), (W, y)], fill=int(255 * min(1.0, t ** 0.78 * 1.12)))
    else:
        left = int(W * (1 - frac))
        for x in range(left, W):
            t = (x - left) / max(1, W - left)
            d.line([(x, 0), (x, H)], fill=int(255 * min(1.0, t ** 0.78 * 1.12)))
    return Image.composite(Image.new("RGB", (W, H), color), img, m)

def wave_edge(img, base, y0, amp=26):
    """img の下辺を波形にして base の上に置く"""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    edge = [(x, y0 - amp + amp * math.sin(2 * math.pi * x / W)) for x in range(W + 1)]
    d.polygon([(0, 0), (W, 0)] + list(reversed(edge)), fill=255)
    out = base.copy(); out.paste(img, (0, 0), m); return out

def logo(d, x, y, size=42, fill=GOLD):
    d.text((x, y), "BiS", font=font(F_SERIF_B, size), fill=fill)

def rule(d, cx, y, half=150, col=GOLD_LT, wpx=2):
    d.line([(cx - half, y), (cx + half, y)], fill=col, width=wpx)

# ---------- スライド ----------
def product_card(img, prod_path, cx, cy, box_w, box_h):
    """商品画像を角丸＋やわらかい影のカードとして配置（中心 cx,cy）"""
    if not (prod_path and os.path.exists(prod_path)):
        return img
    pr = Image.open(prod_path).convert("RGB")
    r = min(box_w / pr.width, box_h / pr.height)
    pw, ph = int(pr.width * r), int(pr.height * r)
    pr = pr.resize((pw, ph), Image.LANCZOS)
    px, py = int(cx - pw / 2), int(cy - ph / 2)

    rad = 26
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph - 1), rad, fill=255)

    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle((px + 6, py + 16, px + pw + 6, py + ph + 16), rad, fill=100)
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    img = Image.composite(Image.new("RGB", (W, H), (118, 98, 76)), img, sh)
    img.paste(pr, (px, py), mask)
    return img


def slide_cover(sp, photo=None):
    """1枚目：商品画像が主役。上に商品カード、下にコピー（縦長レイアウト）。"""
    prod = sp.get("product_image")
    bg = sp.get("bg")
    photo_top = 0.58   # 上部にビジュアル、下 42% にコピー

    if prod and os.path.exists(prod):
        base = load_cover(bg) if (bg and os.path.exists(bg)) else cream_base(None)
    elif photo and os.path.exists(photo):
        base = load_cover(photo)
    else:
        base = cream_base(bg, 0.55)

    img = scrim(base, frac=1 - photo_top + 0.06)
    if prod and os.path.exists(prod):
        img = product_card(img, prod, W * 0.5, H * photo_top * 0.50,
                           int(W * 0.62), int(H * photo_top * 0.86))

    d = ImageDraw.Draw(img)
    logo(d, 74, 58, 44, GOLD)

    fh = font(F_SERIF_B, 56)
    fs = font(F_SANS_M, 26)
    mw = W - 150
    hh = block_h(d, sp["headline"], fh, mw, 1.44)
    sh_ = block_h(d, sp["subcopy"], fs, mw - 90, 1.82)
    total = hh + 30 + 36 + sh_
    y = H - 86 - total

    y = draw_block(d, sp["headline"], fh, BROWN, 75, y, mw, 1.44)
    y += 30
    rule(d, W // 2, y, 140)
    y += 36
    draw_block(d, sp["subcopy"], fs, SUB, 120, y, mw - 90, 1.82)
    return img


def to_instagram(path, out_path, min_ratio=0.8):
    """Instagram の下限 4:5 を満たすよう左右にクリームの余白を足す"""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    if w / h >= min_ratio:
        im.save(out_path, "JPEG", quality=92, optimize=True); return out_path
    nw = int(math.ceil(h * min_ratio))
    canvas = Image.new("RGB", (nw, h), CREAM)
    canvas.paste(im, ((nw - w) // 2, 0))
    canvas.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path

def _points(sp, s, dry, bg=None):
    img = None if dry else cream_base(bg or sp.get("bg"), 0.84)
    d = ImageDraw.Draw(img if img else Image.new("RGB", (W, H)))
    z = lambda v: max(14, int(v * s))
    lab = sp.get("label", "")
    if lab and not dry:
        fl = font(F_SANS_B, z(25))
        tw = d.textlength(lab, font=fl)
        d.rounded_rectangle((110, 86, 110 + tw + 46, 86 + 54), 27, fill=BEIGE)
        d.text((133, 99), lab, font=fl, fill=(142, 106, 28))

    y = 178 if lab else 120
    fh = font(F_SERIF_B, z(52))
    if not dry:
        draw_block(d, sp["heading"], fh, BROWN, 110, y, W - 300, 1.42, "left")
    y += block_h(d, sp["heading"], fh, W - 300, 1.42) + 20
    if not dry:
        d.line([(110, y), (272, y)], fill=GOLD_LT, width=2)
    y += z(46)

    fn = font(F_SERIF_B, z(32))
    ft = font(F_SANS_B, z(34))
    fb = font(F_SANS_R, z(26))
    r = z(52)
    x2 = 110 + r + 26
    w2 = W - x2 - 120
    for i, p in enumerate(sp["points"], 1):
        if not dry:
            d.ellipse((110, y - 4, 110 + r, y + r - 4), outline=GOLD_LT, width=2)
            num = str(i); nw = d.textlength(num, font=fn)
            d.text((110 + r / 2 - nw / 2, y + 1), num, font=fn, fill=GOLD)
            ty = draw_block(d, p["title"], ft, BROWN, x2, y - 2, w2, 1.38, "left")
            draw_block(d, p["body"], fb, SUB, x2, ty + 8, w2, 1.7, "left")
        y += block_h(d, p["title"], ft, w2, 1.38) + 8 + block_h(d, p["body"], fb, w2, 1.7) + z(34)
    if not dry:
        logo(d, W - 150, H - 88, 38)
    return y if dry else img

def slide_points(sp, photo=None):
    s = 1.0
    while s > 0.55 and _points(sp, s, True) > H - 110:
        s -= 0.04
    while s < 1.45 and _points(sp, s + 0.04, True) <= H - 130:
        s += 0.04
    return _points(sp, s, False, photo)

def slide_fact(sp, photo=None):
    img = cream_base(photo or sp.get("bg"), 0.84)
    d = ImageDraw.Draw(img)
    fh = font(F_SERIF_B, 54)
    y = 96
    y = draw_block(d, sp["heading"], fh, BROWN, 140, y, W - 280, 1.42)
    y += 26
    rule(d, W // 2, y, 150)
    y += 50

    ft = font(F_SANS_B, 33)
    fb = font(F_SANS_R, 25)
    cols, gap, pad = 2, 26, 78
    cw = (W - pad * 2 - gap) // cols
    avail = H - y - 100
    ch = max(180, min(330, (avail - gap) // 2))
    y += max(0, (avail - (ch * 2 + gap)) // 2)
    for i, f in enumerate(sp["facts"][:4]):
        cx = pad + (i % cols) * (cw + gap)
        cy = y + (i // cols) * (ch + gap)
        d.rounded_rectangle((cx, cy, cx + cw, cy + ch), 22, fill=(252, 250, 246))
        kh = block_h(d, f["k"], ft, cw - 40, 1.35)
        vh = block_h(d, f["v"], fb, cw - 48, 1.62)
        ty = cy + (ch - (kh + 18 + vh)) // 2
        ty = draw_block(d, f["k"], ft, GOLD, cx + 20, ty, cw - 40, 1.35)
        draw_block(d, f["v"], fb, BROWN, cx + 24, ty + 18, cw - 48, 1.62)
    logo(d, W - 150, H - 88, 38)
    return img

def slide_cta(sp, photo=None):
    p = photo or sp.get("bg")
    img = scrim(load_cover(p), frac=0.86) if p and os.path.exists(p) else cream_base(None)
    d = ImageDraw.Draw(img)
    fh = font(F_SERIF_B, 60)
    fs = font(F_SANS_M, 30)
    mw = W - 300
    hh = block_h(d, sp["cta_headline"], fh, mw, 1.46)
    sh = block_h(d, sp["cta_body"], fs, mw - 120, 1.8)
    total = hh + 32 + 38 + sh + 46 + 86 + 40
    y = (H - total) // 2

    y = draw_block(d, sp["cta_headline"], fh, BROWN, 150, y, mw, 1.46)
    y += 32
    rule(d, W // 2, y, 150)
    y += 38
    y = draw_block(d, sp["cta_body"], fs, SUB, 210, y, mw - 120, 1.8)

    y += 46
    btn = sp.get("cta_button", "プロフィールのリンクへ ▶")
    fb = font(F_SANS_B, 32)
    bw = d.textlength(btn, font=fb) + 100
    d.rounded_rectangle(((W - bw) / 2, y, (W + bw) / 2, y + 86), 43, fill=GOLD)
    d.text(((W - d.textlength(btn, font=fb)) / 2, y + 23), btn, font=fb, fill=WHITE)

    f2 = font(F_SERIF_B, 34)
    t = "BiS 株式会社  |  D'sTs"
    d.text(((W - d.textlength(t, font=f2)) / 2, H - 82), t, font=f2, fill=BROWN)
    return img

BUILDERS = {"cover": slide_cover, "points": slide_points,
            "fact": slide_fact, "cta": slide_cta}

def build(post, outdir):
    os.makedirs(outdir, exist_ok=True)
    ig = os.path.join(outdir, "instagram")
    os.makedirs(ig, exist_ok=True)
    paths = []
    for i, sp in enumerate(post["slides"], 1):
        img = BUILDERS[sp["type"]](sp, sp.get("photo"))
        p = os.path.join(outdir, f"{post['id']}_{i:02d}.jpg")
        img.save(p, "JPEG", quality=92, optimize=True)
        to_instagram(p, os.path.join(ig, f"{post['id']}_{i:02d}.jpg"))
        paths.append(p)
    with open(os.path.join(outdir, f"{post['id']}_caption.txt"), "w") as f:
        f.write(post["caption"] + "\n\n" + " ".join(post["hashtags"]))
    return paths

if __name__ == "__main__":
    post = json.load(open(sys.argv[1]))
    for p in build(post, sys.argv[2]):
        print(p)
