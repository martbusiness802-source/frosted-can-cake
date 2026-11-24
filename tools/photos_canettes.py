#!/usr/bin/env python3
"""Transforme une photo de canette (vue de face) en texture qui s'enroule autour de la canette 3D.

Utilisation :
    python3 tools/photos_canettes.py PHOTO SAVEUR GAUCHE HAUT DROITE BAS

    PHOTO   : la photo de la canette, vue de face
    SAVEUR  : speculos, pistache, oreo ou bueno
    GAUCHE HAUT DROITE BAS : le rectangle du corps de la canette dans la photo, en pixels
              (du bord gauche au bord droit du verre, du dessous du couvercle au-dessus du fond)

Exemple :
    python3 tools/photos_canettes.py ~/Images/pistache.png pistache 222 200 806 1330

Crée assets/canette-SAVEUR.jpg (ordinateurs) et assets/canette-SAVEUR-lo.jpg (téléphones).
De face, la canette 3D montre exactement la photo ; l'arrière montre une seconde copie
pour que le texte reste lisible quand la canette tourne.
Nécessite : pip install pillow numpy
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SAVEURS = ("speculos", "pistache", "oreo", "bueno")
SORTIES = [(1536, 768, "", 80), (1024, 512, "-lo", 78)]
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def derouler(photo, saveur, gauche, haut, droite, bas):
    im = Image.open(photo).convert("RGB")
    marge = int((droite - gauche) * 0.03)  # évite d'attraper le fond de la photo sur les bords
    corps = im.crop((gauche + marge, haut, droite - marge, bas))
    for largeur, hauteur, suffixe, qualite in SORTIES:
        a = np.asarray(corps.resize((corps.width * 2, hauteur), Image.LANCZOS))
        cw = a.shape[1]
        angle = ((np.arange(largeur) + 0.5) / largeur - 0.5) * 2 * math.pi
        # deux faces : -90°..90° (devant) et 90°..270° (derrière), chacune = la photo
        local = np.where(np.abs(angle) <= math.pi / 2, angle,
                         np.where(angle > 0, angle - math.pi, angle + math.pi))
        colonnes = np.clip(((np.sin(local) + 1) / 2 * (cw - 1)).round().astype(int), 0, cw - 1)
        sortie = ASSETS / "canette-{}{}.jpg".format(saveur, suffixe)
        Image.fromarray(a[:, colonnes, :]).save(sortie, quality=qualite, optimize=True, progressive=True)
        print("créé :", sortie.relative_to(ASSETS.parent))


def main():
    if len(sys.argv) != 7 or sys.argv[2] not in SAVEURS:
        sys.exit(__doc__)
    derouler(sys.argv[1], sys.argv[2], *map(int, sys.argv[3:]))


if __name__ == "__main__":
    main()
