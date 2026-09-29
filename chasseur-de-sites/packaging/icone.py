"""Dessine l'icône de Chasseur de sites et l'écran de démarrage (Pillow). Lancé avant PyInstaller :

    python packaging/icone.py

Écrit dans packaging/genere/ : icone.ico (Windows), icone.png (fenêtre), icone-1024.png (Mac),
demarrage.png (écran affiché pendant le démarrage de l'exécutable Windows).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SORTIE = Path(__file__).resolve().parent / "genere"
T = 1024  # dessiné en grand puis réduit : bords lisses
HAUT, BAS = (47, 125, 225), (23, 74, 150)  # bleu de l'interface (#1f5fbf) en dégradé
ORANGE = (249, 115, 22)


def degrade(taille: int) -> Image.Image:
    fond = Image.new("RGB", (taille, taille))
    px = fond.load()
    for y in range(taille):
        for x in range(taille):
            t = (x + y) / (2 * taille - 2)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(HAUT, BAS))
    return fond


def dessiner() -> Image.Image:
    masque = Image.new("L", (T, T), 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, T - 1, T - 1), radius=230, fill=255)
    img = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    img.paste(degrade(T), (0, 0), masque)
    d = ImageDraw.Draw(img)
    # Page web (fenêtre de navigateur) derrière la loupe
    d.rounded_rectangle((170, 200, 760, 700), radius=48, fill=(255, 255, 255, 235))
    d.rounded_rectangle((170, 200, 760, 290), radius=48, fill=(255, 255, 255))
    d.rectangle((170, 250, 760, 290), fill=(255, 255, 255))
    for i, x in enumerate((225, 280, 335)):
        d.ellipse((x - 18, 227, x + 18, 263), fill=(ORANGE if i == 0 else (203, 213, 225)))
    for y, fin in ((360, 640), (430, 560), (500, 610)):
        d.rounded_rectangle((230, y, fin, y + 34), radius=17, fill=(203, 213, 225))
    # Fissure orange : le site cassé
    d.line((715, 310, 655, 375, 710, 425, 650, 490), fill=ORANGE, width=30, joint="curve")
    # Loupe
    cx, cy, r = 600, 665, 150
    marine = (15, 42, 92)
    d.line((cx + 110, cy + 110, 860, 925), fill=marine, width=122)  # manche, avec un contour foncé
    d.ellipse((860 - 61, 925 - 61, 860 + 61, 925 + 61), fill=marine)
    d.line((cx + 110, cy + 110, 860, 925), fill="white", width=90)
    d.ellipse((860 - 45, 925 - 45, 860 + 45, 925 + 45), fill="white")
    d.ellipse((cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16), fill=marine)  # verre bordé de foncé
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(214, 229, 250), outline="white", width=56)
    return img


def police(taille: int):
    for nom in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            continue
    return ImageFont.load_default(size=taille)


def ecran_de_demarrage(icone: Image.Image) -> Image.Image:
    ecran = Image.new("RGB", (600, 200), (245, 247, 251))
    ecran.paste(icone.resize((136, 136), Image.LANCZOS), (32, 32), icone.resize((136, 136), Image.LANCZOS))
    d = ImageDraw.Draw(ecran)
    d.text((196, 46), "Chasseur de sites", fill=(27, 36, 51), font=police(34))
    d.text((198, 92), "by ptabountchikoff", fill=(31, 95, 191), font=police(18))
    d.text((198, 132), "Démarrage en cours…", fill=(91, 101, 118), font=police(18))
    return ecran


def main() -> None:
    SORTIE.mkdir(exist_ok=True)
    icone = dessiner()
    icone.save(SORTIE / "icone.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icone.save(SORTIE / "icone-1024.png")
    icone.resize((256, 256), Image.LANCZOS).save(SORTIE / "icone.png")
    ecran_de_demarrage(icone).save(SORTIE / "demarrage.png")
    print(f"Icônes écrites dans {SORTIE}")


if __name__ == "__main__":
    main()
