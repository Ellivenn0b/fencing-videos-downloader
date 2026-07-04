"""Génère l'icône de l'application (épées croisées) aux formats .ico, .icns et .png.

Lancer depuis la racine du dépôt :  python assets/make_icon.py
Ne dépend que de Pillow. Le résultat est versionné, donc à ne relancer
que si l'on veut retoucher le dessin.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent
SIZE = 1024  # résolution de travail (rééchantillonnée ensuite)

# Palette accordée au thème « blue » de CustomTkinter.
BG_TOP = (34, 118, 199)
BG_BOTTOM = (20, 74, 140)
BLADE = (238, 242, 248)
BLADE_EDGE = (196, 206, 220)
GUARD = (222, 228, 236)
POMMEL = (170, 180, 194)


def _vertical_gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        gradient.putpixel(
            (0, y),
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return gradient.resize((size, size))


def _rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * radius_ratio)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _draw_sword(size: int) -> Image.Image:
    """Dessine une épée verticale (pointe en haut) sur un calque transparent."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = size // 2
    blade_w = size * 0.05
    tip_y = size * 0.12
    guard_y = size * 0.66

    # Lame : polygone effilé vers la pointe.
    d.polygon(
        [
            (cx, tip_y),
            (cx + blade_w / 2, tip_y + size * 0.05),
            (cx + blade_w / 2, guard_y),
            (cx - blade_w / 2, guard_y),
            (cx - blade_w / 2, tip_y + size * 0.05),
        ],
        fill=BLADE,
    )
    # Arête centrale, pour un peu de relief.
    d.line([(cx, tip_y + size * 0.04), (cx, guard_y)], fill=BLADE_EDGE, width=max(2, int(size * 0.006)))

    # Garde (coquille) : ellipse transversale.
    d.ellipse(
        [cx - size * 0.13, guard_y - size * 0.02, cx + size * 0.13, guard_y + size * 0.05],
        fill=GUARD,
    )
    # Poignée.
    d.rounded_rectangle(
        [cx - blade_w * 0.6, guard_y + size * 0.04, cx + blade_w * 0.6, size * 0.86],
        radius=int(blade_w),
        fill=GUARD,
    )
    # Pommeau.
    d.ellipse(
        [cx - blade_w, size * 0.85, cx + blade_w, size * 0.85 + blade_w * 2],
        fill=POMMEL,
    )
    return layer


def build_master() -> Image.Image:
    # Fond dégradé + coins arrondis.
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    background = _vertical_gradient(SIZE, BG_TOP, BG_BOTTOM).convert("RGBA")
    icon.paste(background, (0, 0), _rounded_mask(SIZE))

    # Deux épées croisées en X.
    sword = _draw_sword(SIZE)
    for angle in (34, -34):
        rotated = sword.rotate(angle, resample=Image.BICUBIC, center=(SIZE / 2, SIZE / 2))
        icon.alpha_composite(rotated)

    return icon


def main() -> None:
    master = build_master()

    png_path = ASSETS / "icon.png"
    master.save(png_path)

    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    master.save(ASSETS / "icon.ico", sizes=[(s, s) for s in ico_sizes])

    # .icns pour macOS (Pillow gère l'écriture ; il faut des tailles carrées).
    icns_source = master.resize((1024, 1024), Image.LANCZOS)
    icns_source.save(ASSETS / "icon.icns")

    print("Icônes générées :", [p.name for p in ASSETS.glob("icon.*")])


if __name__ == "__main__":
    main()
