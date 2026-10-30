#!/usr/bin/env python3
"""Art for Asgard's own Tools entries (Terminal, Moonlight, Files), in Firefox's entry style: a 1024² cover (gradient,
rings, glyph, name), a 629x140 marquee (the name in white) and a 1920x1080 screenshot card. Run from this folder;
needs rsvg-convert and Pillow. The glyphs are our own drawings."""
import os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(__file__), "../../qml/fonts/Nunito-Black.ttf")

GLYPHS = {   # 24x24 viewBox, white strokes
    "Terminal": '<rect x="2.5" y="4" width="19" height="16" rx="3"/><path d="m7 9.5 3 2.5-3 2.5M12.5 15h4.5"/>',
    "Moonlight": '<rect x="2.5" y="4" width="19" height="12.5" rx="2.5"/><path d="M8.5 20h7M12 16.5V20"/>'
                 '<path d="m10.5 8 4 2.3-4 2.3z" fill="#fff"/>',
    "Files": '<path d="M2.8 6.5A2 2 0 0 1 4.8 4.5h4.4l2 2.3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4.8a2 2 0 0 1-2-2z"/>'
             '<path d="M2.8 10h18.4"/>',
}
COLORS = {"Terminal": ((22, 28, 48), (48, 92, 110)), "Moonlight": ((24, 30, 86), (64, 98, 220)),
          "Files": ((52, 26, 84), (196, 112, 64))}


def gradient(size, a, b):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w + (h - y) / h) / 2   # dark bottom-left, light top-right
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return img


def glyph(name, px):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" '
           f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[name]}</svg>')
    with tempfile.TemporaryDirectory() as d:
        src, out = os.path.join(d, "g.svg"), os.path.join(d, "g.png")
        open(src, "w").write(svg)
        subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px), src, "-o", out], check=True)
        return Image.open(out).convert("RGBA")


def card(name, size, glyph_px, text_px):
    w, h = size
    img = gradient((w // 4, h // 4), *COLORS[name]).resize(size, Image.BICUBIC).convert("RGBA")
    rings = Image.new("RGBA", size)
    d = ImageDraw.Draw(rings)
    cx, cy = w // 2, int(h * 0.41)
    for r in (int(h * 0.37), int(h * 0.25)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 40), width=4)
    img.alpha_composite(rings)
    g = glyph(name, glyph_px)
    img.alpha_composite(g, (cx - glyph_px // 2, cy - glyph_px // 2))
    font = ImageFont.truetype(FONT, text_px)
    d = ImageDraw.Draw(img)
    d.text((cx, int(h * 0.86)), name, font=font, fill="white", anchor="mm")
    return img.convert("RGB")


def marquee(name):
    img = Image.new("RGBA", (629, 140))
    ImageDraw.Draw(img).text((314, 70), name, font=ImageFont.truetype(FONT, 110), fill="white", anchor="mm")
    return img.crop(img.getbbox()) if img.getbbox() else img


for name in GLYPHS:
    card(name, (1024, 1024), 420, 150).save(f"covers/{name}.png")
    card(name, (1920, 1080), 440, 150).save(f"screenshots/{name}.png")
    marquee(name).save(f"marquees/{name}.png")
    print(name)
