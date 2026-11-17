#!/usr/bin/env python3
"""Marcel — test d'insertion d'un produit dans la photo de l'utilisateur.

A (contrôlée) : le code colle le vrai produit à la taille calculée, l'IA harmonise
                (ombres, lumière) sans toucher à la taille ni à la position.
B (libre)     : on demande à l'IA d'ajouter l'étagère elle-même (pour comparer).

Payé avec les crédits Inference Providers (pas de quota ZeroGPU).
    uv run insertion.py
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from huggingface_hub import InferenceClient
from PIL import Image, ImageDraw

ICI = Path(__file__).parent
D = ICI / "test3d"
OUT = D / "insertion"
LOG = ICI / "logs" / "hf.jsonl"

# --- Calibration (photo test3d/piece.jpg, 1200×1600) ---
PORTE_H_PX, PORTE_H_CM = 505, 204          # hauteur du vantail mesurée sur la photo / porte standard
PX_PAR_CM = PORTE_H_PX / PORTE_H_CM         # ≈ 2,48 px/cm
ZONE = (430, 598)                           # mur libre entre le coin et le cadre de porte (x en px)
ETAGERE_CM = (60, 20)                       # largeur, hauteur (fiche produit vérifiée)
HAUT_Y = 480                                # hauteur de pose (px)

MODELES = ["Qwen/Qwen-Image-Edit-2511", "black-forest-labs/FLUX.1-Kontext-dev"]

PROMPT_A = ("This photo shows a solid oak wall shelf that was pasted onto the white wall. Make it look like a real "
            "photo of this exact shelf mounted on the wall: add realistic contact shadows and lighting matching the "
            "room, consistent with the camera perspective. Keep the shelf exactly the same size, shape, colour and "
            "position. Do not change anything else in the image.")
PROMPT_B = ("Add a small solid oak wall shelf (60 cm wide, a flat board held by two vertical wooden side brackets) "
            "mounted on the white wall between the left corner and the door frame, at chest height. Photorealistic. "
            "Keep everything else unchanged.")


def decoupe_produit(chemin: Path) -> Image.Image:
    """Photo produit fond blanc → étagère seule sur fond transparent, recadrée."""
    im = Image.open(chemin).convert("RGB")
    a = np.asarray(im).astype(int)
    blanc = (a.min(axis=2) > 235)
    alpha = np.where(blanc, 0, 255).astype(np.uint8)
    rgba = np.dstack([np.asarray(im), alpha])
    ys, xs = np.where(~blanc)
    return Image.fromarray(rgba, "RGBA").crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def composite():
    piece = Image.open(D / "piece.jpg").convert("RGB")
    prod = decoupe_produit(D / "etagere.jpg")
    w = round(ETAGERE_CM[0] * PX_PAR_CM)
    h = round(prod.height * w / prod.width)    # garde les proportions de la photo produit (vue de 3/4)
    prod = prod.resize((w, h), Image.LANCZOS)
    x0 = round((ZONE[0] + ZONE[1]) / 2 - w / 2)
    piece.paste(prod, (x0, HAUT_Y), prod)
    out = OUT / "A0_colle_par_le_code.jpg"
    piece.save(out, quality=92)
    zone_cm = (ZONE[1] - ZONE[0]) / PX_PAR_CM
    print(f"Échelle {PX_PAR_CM:.2f} px/cm · zone libre {zone_cm:.0f} cm · étagère {w} px = {ETAGERE_CM[0]} cm "
          f"· jeu ≈ {(zone_cm - ETAGERE_CM[0]) / 2:.1f} cm de chaque côté")
    return out


def editer(img: Path, prompt: str, modele: str, nom: str):
    client = InferenceClient(bill_to=os.environ.get("HF_BILL_TO") or None)
    ligne = {"ts": datetime.now(timezone.utc).isoformat(), "tache": f"insertion-{nom}", "modele": modele}
    t0 = time.monotonic()
    try:
        res = client.image_to_image(img, prompt=prompt, model=modele)
        dest = OUT / f"{nom}_{modele.split('/')[1]}.jpg"
        res.convert("RGB").save(dest, quality=92)
        ligne.update(succes=True, fichier=dest.name, taille=list(res.size))
    except Exception as e:
        ligne.update(succes=False, erreur=f"{type(e).__name__}: {e}"[:400])
    ligne["duree_s"] = round(time.monotonic() - t0, 1)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    print(f"[{nom}] {modele} — {ligne['duree_s']} s — {ligne.get('fichier') or ligne.get('erreur')}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a0 = composite()
    for m in MODELES:
        editer(a0, PROMPT_A, m, "A_controlee")
        editer(D / "piece.jpg", PROMPT_B, m, "B_libre")


if __name__ == "__main__":
    main()
