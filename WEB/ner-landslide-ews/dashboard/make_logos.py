from PIL import Image, ImageDraw
import os
here = os.path.dirname(os.path.abspath(__file__))
for src, out in [("logo_low.png","low.png"),("logo_medium.png","medium.png"),("logo_high.png","high.png")]:
    p = os.path.join(here, src)
    if not os.path.exists(p): print("missing:", src); continue
    img = Image.open(p).convert("RGBA")
    for c in [(0,0),(img.width-1,0),(0,img.height-1),(img.width-1,img.height-1)]:
        ImageDraw.floodfill(img, c, (0,0,0,0), thresh=80)   # background → transparent
    img.thumbnail((96,96), Image.LANCZOS)
    img.save(os.path.join(here, out))
    print("saved", out)