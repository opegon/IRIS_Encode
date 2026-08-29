"""make_icon.py — Génère l'icône du raccourci Bureau.

Un iris d'œil : anneau strié turquoise sur fond ardoise, pupille sombre,
reflet. Le rendu est déterministe (graine fixe) : relancer le script
reproduit l'icône à l'identique, elle est donc vérifiable depuis le source.

Écrit deux fichiers : iris.ico (le binaire, jamais versionné) et
iris.ico.b64 (le même, en base64 — c'est lui qui est versionné : le dépôt
ne porte aucun binaire, et build.bat le décode avec certutil, livré avec
Windows).

Nécessite Pillow (absent de requirements.txt : outil de développement,
pas une dépendance de l'application) :

    python -m pip install pillow
    python launcher/make_icon.py
"""

import base64
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024  # rendu suréchantillonné, réduit ensuite pour chaque taille
CX = CY = S // 2

FOND_HAUT = (23, 33, 54)
FOND_BAS = (10, 15, 26)
IRIS_BORD = (13, 84, 93)
IRIS_COEUR = (45, 212, 191)
PUPILLE = (2, 6, 23)


def _fond(img: Image.Image) -> None:
    """Carré arrondi, dégradé vertical ardoise."""
    grad = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        grad.putpixel(
            (0, y),
            tuple(round(h + (b - h) * t) for h, b in zip(FOND_HAUT, FOND_BAS)),
        )
    grad = grad.resize((S, S))
    masque = Image.new("L", (S, S), 0)
    ImageDraw.Draw(masque).rounded_rectangle(
        (0, 0, S - 1, S - 1), radius=round(S * 0.22), fill=255
    )
    img.paste(grad, (0, 0), masque)


def _iris(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    r_iris = round(S * 0.365)
    r_pupille = round(S * 0.155)

    # Dégradé radial : cœur turquoise vers bord profond.
    for r in range(r_iris, r_pupille, -1):
        t = (r - r_pupille) / (r_iris - r_pupille)
        c = tuple(
            round(co + (bo - co) * t) for co, bo in zip(IRIS_COEUR, IRIS_BORD)
        )
        d.ellipse((CX - r, CY - r, CX + r, CY + r), fill=c)

    # Striations : rayons d'opacité irrégulière, comme un iris réel.
    rnd = random.Random(20260829)
    voile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dv = ImageDraw.Draw(voile)
    for i in range(160):
        a = 2 * math.pi * i / 160 + rnd.uniform(-0.012, 0.012)
        r0 = r_pupille * 1.02
        r1 = r_iris * rnd.uniform(0.86, 0.99)
        clair = rnd.random() < 0.5
        couleur = (170, 255, 240, rnd.randint(28, 80)) if clair else (
            4, 36, 48, rnd.randint(30, 85)
        )
        dv.line(
            (
                CX + r0 * math.cos(a),
                CY + r0 * math.sin(a),
                CX + r1 * math.cos(a),
                CY + r1 * math.sin(a),
            ),
            fill=couleur,
            width=rnd.choice((6, 8, 10)),
        )
    img.alpha_composite(voile)

    # Anneau limbique, pupille, reflet.
    d = ImageDraw.Draw(img)
    d.ellipse(
        (CX - r_iris, CY - r_iris, CX + r_iris, CY + r_iris),
        outline=(6, 24, 34, 255),
        width=round(S * 0.018),
    )
    d.ellipse(
        (CX - r_pupille, CY - r_pupille, CX + r_pupille, CY + r_pupille),
        fill=PUPILLE,
    )
    rh = round(S * 0.075)
    d.ellipse(
        (
            CX - r_pupille * 0.62 - rh,
            CY - r_pupille * 0.62 - rh,
            CX - r_pupille * 0.62 + rh,
            CY - r_pupille * 0.62 + rh,
        ),
        fill=(236, 254, 252, 215),
    )


def main() -> None:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _fond(img)
    _iris(img)
    dest = Path(__file__).with_name("iris.ico")
    # 256 d'abord : c'est l'image de base, les autres en sont réduites.
    img.resize((256, 256), Image.LANCZOS).save(
        dest,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)],
    )
    print(f"écrit : {dest}")

    b64 = base64.encodebytes(dest.read_bytes()).decode("ascii")
    dest_b64 = dest.with_suffix(".ico.b64")
    dest_b64.write_text(b64, newline="\n")
    print(f"écrit : {dest_b64}")


if __name__ == "__main__":
    main()
