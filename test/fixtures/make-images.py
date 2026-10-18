"""Render the fixture images the eye is driven with (BUILD-PLAN.md, "Tests are cheap").

  python test/fixtures/make-images.py <out dir>      (npm run fixtures)

Six images with known fields, drawn with Pillow so the printed text is exactly
the FIXTURES table below; fields.json beside them records the same table so a
binding can name what each image prints. Deterministic: the same Pillow draws
the same bytes, so a cassette keyed on the image's hash stays valid.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
DESK = (92, 74, 60)

FIXTURES: dict[str, dict] = {
    "la-ticket.png": {
        "kind": "ticket",
        "fields": {
            "city": "Los Angeles",
            "citation": "4512087733",
            "plate": "8ABC123",
            "issued": "2026-10-12",
            "due": "2026-11-02",
            "amount": "73.00",
            "violation": "Meter expired",
        },
    },
    "ladwp-bill.png": {
        "kind": "bill",
        "fields": {
            "biller": "LADWP",
            "account": "1234567890",
            "amount": "148.22",
            "due": "2026-11-05",
            "phone": "1-800-342-5397",
        },
    },
    "cholula-32oz.png": {
        "kind": "product",
        "fields": {"name": "Cholula Original hot sauce", "size": "32 oz"},
    },
    "ticket-blurred.png": {
        "kind": "unknown",
        "fields": {},
        "note": "la-ticket at arm's length: shrunk and blurred until the digits cannot be read",
    },
    "blank-sheet.png": {"kind": "unknown", "fields": {}, "note": "a blank sheet of paper"},
    "mug.png": {"kind": "unknown", "fields": {}, "note": "a coffee mug with no label"},
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def ticket() -> Image.Image:
    f = FIXTURES["la-ticket.png"]["fields"]
    img = Image.new("RGB", (W, H), DESK)
    d = ImageDraw.Draw(img)
    d.rectangle((340, 40, 940, 680), fill=(252, 250, 240), outline=(40, 40, 40), width=3)
    d.text((370, 60), "CITY OF LOS ANGELES", font=font(34), fill=(0, 0, 0))
    d.text((370, 104), "NOTICE OF PARKING VIOLATION", font=font(26), fill=(160, 0, 0))
    rows = [
        ("CITATION NO.", f["citation"]),
        ("LICENSE PLATE", f["plate"]),
        ("ISSUE DATE", f["issued"]),
        ("VIOLATION", f["violation"]),
        ("AMOUNT DUE", f"${f['amount']}"),
        ("DUE DATE", f["due"]),
    ]
    y = 170
    for label, value in rows:
        d.text((370, y), label, font=font(20), fill=(80, 80, 80))
        d.text((370, y + 24), value, font=font(36), fill=(0, 0, 0))
        y += 80
    return img


def bill() -> Image.Image:
    f = FIXTURES["ladwp-bill.png"]["fields"]
    img = Image.new("RGB", (W, H), DESK)
    d = ImageDraw.Draw(img)
    d.rectangle((300, 30, 980, 690), fill=(255, 255, 255), outline=(40, 40, 40), width=3)
    d.text((330, 50), f["biller"], font=font(56), fill=(0, 70, 140))
    d.text((330, 120), "Los Angeles Department of Water and Power", font=font(24), fill=(0, 0, 0))
    rows = [
        ("ACCOUNT NUMBER", f["account"]),
        ("AMOUNT DUE", f"${f['amount']}"),
        ("PAYMENT DUE BY", f["due"]),
        ("QUESTIONS? CALL", f["phone"]),
    ]
    y = 200
    for label, value in rows:
        d.text((330, y), label, font=font(22), fill=(80, 80, 80))
        d.text((330, y + 28), value, font=font(40), fill=(0, 0, 0))
        y += 110
    return img


def cholula() -> Image.Image:
    img = Image.new("RGB", (W, H), DESK)
    d = ImageDraw.Draw(img)
    d.rectangle((600, 40, 680, 150), fill=(30, 20, 15))  # the wooden cap
    d.rounded_rectangle((520, 150, 760, 680), radius=40, fill=(150, 20, 10))  # the bottle
    d.rectangle((530, 300, 750, 560), fill=(245, 225, 170))  # the label
    d.text((548, 320), "Cholula", font=font(48), fill=(120, 20, 0))
    d.text((548, 385), "ORIGINAL", font=font(30), fill=(0, 0, 0))
    d.text((548, 425), "HOT SAUCE", font=font(30), fill=(0, 0, 0))
    d.text((548, 490), "32 FL OZ", font=font(34), fill=(0, 0, 0))
    return img


def blurred_ticket() -> Image.Image:
    # Arm's length: the ticket a quarter of its size in the frame, then blurred.
    small = ticket().resize((W // 4, H // 4), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(3))
    img = Image.new("RGB", (W, H), DESK)
    img.paste(small, ((W - small.width) // 2, (H - small.height) // 2))
    return img.filter(ImageFilter.GaussianBlur(2))


def blank_sheet() -> Image.Image:
    img = Image.new("RGB", (W, H), DESK)
    ImageDraw.Draw(img).rectangle((340, 40, 940, 680), fill=(252, 252, 252))
    return img


def mug() -> Image.Image:
    img = Image.new("RGB", (W, H), DESK)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((470, 200, 760, 600), radius=30, fill=(235, 235, 230))
    d.ellipse((730, 290, 870, 480), outline=(235, 235, 230), width=28)
    d.ellipse((470, 180, 760, 230), fill=(60, 35, 20))  # the coffee
    return img


DRAW = {
    "la-ticket.png": ticket,
    "ladwp-bill.png": bill,
    "cholula-32oz.png": cholula,
    "ticket-blurred.png": blurred_ticket,
    "blank-sheet.png": blank_sheet,
    "mug.png": mug,
}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: make-images.py <out dir>", file=sys.stderr)
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    for name, draw in DRAW.items():
        draw().save(out / name, format="PNG", optimize=False)
    (out / "fields.json").write_text(json.dumps(FIXTURES, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(DRAW)} images and fields.json to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
