"""Saari scene images ek sheet par (naam ke saath) taaki jaldi jaanch ho sake.
python contact_sheet.py <assets_dir> <out.jpg> [cols]"""
import sys, glob, os
from PIL import Image, ImageDraw
d, out = sys.argv[1], sys.argv[2]; cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
files = sorted(glob.glob(os.path.join(d, "*.jpg")))
w, h = 360, 203; rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), "black")
for i, f in enumerate(files):
    im = Image.open(f).convert("RGB"); im.thumbnail((w, h))
    dr = ImageDraw.Draw(im); name = os.path.splitext(os.path.basename(f))[0]
    dr.rectangle((0, 0, 8 * len(name) + 10, 18), fill="black"); dr.text((5, 3), name, fill="yellow")
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out, quality=85); print(out, len(files), "images")
