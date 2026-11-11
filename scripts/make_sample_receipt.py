"""Draw the demo receipt (frontend/public/sample-receipt.png): a slightly tilted, paper-looking restaurant bill."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample-receipt.png"
ITEMS = [("Margherita Pizza", 1, 16.50), ("Truffle Pasta", 1, 21.00), ("Ribeye Steak", 1, 34.00),
         ("Caesar Salad", 1, 12.50), ("Garlic Bread", 2, 13.00), ("House Red Wine (btl)", 1, 38.00),
         ("Sparkling Water", 3, 13.50), ("Tiramisu", 2, 18.00)]
TAX_RATE = 0.0875


def font(size, bold=False):
    for name in (("consolab.ttf" if bold else "consola.ttf"), "cour.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


subtotal = sum(price for _, _, price in ITEMS)
tax = round(subtotal * TAX_RATE, 2)
total = subtotal + tax
width, line = 620, 34
lines = [("center", "LA PICCOLA TRATTORIA", 34, True), ("center", "88 Market Street, San Francisco CA", 22, False),
         ("center", "Table 12   Server: Gianna   11/11/2026 8:42 PM", 20, False), ("rule",)]
lines += [("item", f"{qty} {name}", f"{price:.2f}") for name, qty, price in ITEMS]
lines += [("rule",), ("item", "Subtotal", f"{subtotal:.2f}"), ("item", "Sales Tax 8.75%", f"{tax:.2f}"),
          ("total", "TOTAL", f"${total:.2f}"), ("rule",), ("item", "VISA ****4417", f"{total:.2f}"),
          ("center", "Gratuity not included", 22, False), ("center", "Grazie mille!", 26, True)]

paper = Image.new("RGB", (width, 120 + line * len(lines)), (252, 250, 243))
draw = ImageDraw.Draw(paper)
y = 50
for entry in lines:
    if entry[0] == "center":
        _, text, size, bold = entry
        f = font(size, bold)
        draw.text(((width - draw.textlength(text, font=f)) / 2, y), text, font=f, fill=(35, 35, 40))
    elif entry[0] == "rule":
        draw.text((40, y), "-" * 44, font=font(22), fill=(120, 120, 120))
    else:
        _, left, right = entry
        f = font(30 if entry[0] == "total" else 24, entry[0] == "total")
        draw.text((40, y), left, font=f, fill=(35, 35, 40))
        draw.text((width - 40 - draw.textlength(right, font=f), y), right, font=f, fill=(35, 35, 40))
    y += line

canvas = Image.new("RGB", (paper.width + 160, paper.height + 160), (196, 186, 170))
shadow = Image.new("RGB", paper.size, (120, 110, 95))
canvas.paste(shadow, (90, 92))
canvas = canvas.filter(ImageFilter.GaussianBlur(8))
canvas.paste(paper, (80, 80))
canvas = canvas.rotate(-2.5, resample=Image.BICUBIC, fillcolor=(196, 186, 170))
OUT.parent.mkdir(parents=True, exist_ok=True)
canvas.save(OUT)
print(OUT, f"subtotal {subtotal:.2f} tax {tax:.2f} total {total:.2f}")
