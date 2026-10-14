"""Turn the source portrait into the two crops the page needs.

  hero.webp     tall crop, sits in the 23vw plate on the right of the hero
  profile.webp  head-and-shoulders crop for section 09

Greyscale, contrast 1.15, gamma 1.1 to pull the highlights down so the plate
does not glare against the off-white paper background.
"""
import pathlib

from PIL import Image, ImageEnhance

SRC = pathlib.Path(r"C:\Users\82108\Desktop\meeee\증명사진_여권.jpg")
OUT = pathlib.Path(__file__).parent / "assets"
CONTRAST = 1.15
GAMMA = 1.1


def grade(im):
    im = im.convert("L")
    im = ImageEnhance.Contrast(im).enhance(CONTRAST)
    # gamma > 1 darkens midtones and compresses the top end
    lut = [round(255 * ((i / 255) ** GAMMA)) for i in range(256)]
    return im.point(lut)


def main():
    OUT.mkdir(exist_ok=True)
    src = Image.open(SRC)
    w, h = src.size

    # hero: narrow the frame to ~0.66 so the plate reads as a tall panel
    target = 0.66
    cw = round(h * target)
    x = (w - cw) // 2
    hero = grade(src.crop((x, 0, x + cw, h)))
    hero.save(OUT / "hero.webp", "WEBP", quality=88, method=6)

    # profile: head and shoulders, 4:5
    pw, ph = 340, 425
    cx, cy = w // 2, 230
    box = (cx - pw // 2, max(0, cy - ph // 2), cx + pw // 2, min(h, cy + ph // 2))
    profile = grade(src.crop(box))
    profile.save(OUT / "profile.webp", "WEBP", quality=88, method=6)

    for f in ("hero.webp", "profile.webp"):
        p = OUT / f
        print(f"{f:14} {Image.open(p).size}  {p.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
