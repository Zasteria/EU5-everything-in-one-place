#!/usr/bin/env python3
"""Draw `.metadata/thumbnail.png`, the Workshop page picture (512x512).

Three maintenance sliders: a faded wartime knob at the top, an arrow, and the
knob where the mod puts it after peace; beside them a coin with a falling
arrow for inflation.  Drawn at 4x and scaled down for smooth edges.

Usage:  python3 mods/war_sliders/tools/make_thumbnail.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MOD = Path(__file__).resolve().parent.parent
OUT = MOD / ".metadata/thumbnail.png"
S = 4                      # supersampling
SIZE = 512
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

BG_TOP = (44, 36, 28)
BG_BOTTOM = (18, 15, 12)
GOLD = (214, 176, 98)
GOLD_DARK = (150, 116, 56)
TRACK = (70, 60, 48)
RED = (168, 58, 46)
TEXT = (232, 214, 170)


def px(v):
    return int(v * S)


def main() -> None:
    img = Image.new("RGB", (px(SIZE), px(SIZE)))
    d = ImageDraw.Draw(img)
    for y in range(px(SIZE)):
        t = y / px(SIZE)
        d.line([(0, y), (px(SIZE), y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    # frame
    d.rounded_rectangle([px(10), px(10), px(502), px(502)], radius=px(18),
                        outline=GOLD_DARK, width=px(4))

    title = ImageFont.truetype(FONT, px(54))
    d.text((px(256), px(66)), "WAR SLIDERS", font=title, fill=TEXT, anchor="mm")

    # three sliders
    top, bottom = px(140), px(420)
    for x in (110, 185, 260):
        cx = px(x)
        d.rounded_rectangle([cx - px(9), top, cx + px(9), bottom], radius=px(9), fill=TRACK)
        d.rounded_rectangle([cx - px(9), px(300), cx + px(9), bottom], radius=px(9), fill=GOLD_DARK)
        # wartime knob, faded red
        d.rounded_rectangle([cx - px(30), px(150), cx + px(30), px(180)], radius=px(8),
                            outline=RED, width=px(4))
        # arrow down
        d.line([(cx, px(190)), (cx, px(262))], fill=RED, width=px(5))
        d.polygon([(cx - px(13), px(258)), (cx + px(13), px(258)), (cx, px(278))], fill=RED)
        # peacetime knob
        d.rounded_rectangle([cx - px(30), px(285), cx + px(30), px(315)], radius=px(8),
                            fill=GOLD, outline=(90, 70, 36), width=px(3))

    # coin with a falling arrow
    ccx, ccy, r = px(392), px(250), px(62)
    d.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], fill=GOLD, outline=(110, 84, 40), width=px(5))
    d.ellipse([ccx - r + px(12), ccy - r + px(12), ccx + r - px(12), ccy + r - px(12)],
              outline=GOLD_DARK, width=px(3))
    d.text((ccx, ccy), "%", font=ImageFont.truetype(FONT, px(64)), fill=(96, 70, 30), anchor="mm")
    ax = ccx
    d.line([(ax, px(330)), (ax, px(398))], fill=RED, width=px(8))
    d.polygon([(ax - px(22), px(392)), (ax + px(22), px(392)), (ax, px(424))], fill=RED)

    sub = ImageFont.truetype(FONT, px(26))
    d.text((px(256), px(462)), "back to peace in one step", font=sub, fill=GOLD, anchor="mm")

    img.resize((SIZE, SIZE), Image.LANCZOS).save(OUT, optimize=True)
    print(f"{OUT.relative_to(MOD.parent.parent)}: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
