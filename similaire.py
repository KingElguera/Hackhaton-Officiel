#!/usr/bin/env python3
"""Marcel — « produit similaire » : retrouve dans un petit catalogue les revêtements les plus proches d'une photo d'inspiration.

ESSAI, pas encore branché au site. Le modèle (SigLIP 2, licence Apache) tourne sur ce poste : rien n'est envoyé ailleurs.

    # 1. Les mots à chercher chez le fournisseur (modèle déjà branché, aucun téléchargement)
    uv run --group outils similaire.py --mots inspiration.jpg

    # 2. Les 3 produits du catalogue les plus proches (télécharge le modèle la première fois, ~400 Mo)
    uv run --with torch --with transformers --with pillow --with numpy similaire.py catalogue/ inspiration.jpg

Le catalogue est un dossier d'images de produits. S'il contient catalogue.csv (colonnes : fichier,nom,prix,lien),
ces informations sont jointes au résultat. Les empreintes des images sont gardées dans catalogue/.index.npz.
"""
import argparse
import base64
import csv
import json
import sys
from pathlib import Path

MODELE = "google/siglip2-base-patch16-224"
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}

PROMPT_MOTS = """Voici une photo d'inspiration donnée par un client à un artisan. Décris le revêtement mural ou de sol principal
pour le retrouver chez un fournisseur. Réponds UNIQUEMENT avec un objet JSON :
{"type": "papier peint | peinture | carrelage | parquet | autre", "motif": "...", "couleurs": ["..."], "style": "...",
 "matiere": "...", "recherche": "3 à 6 mots à taper dans la recherche du site du fournisseur"}"""


def mots(image: Path) -> dict:
    from marcel_core import hf
    url = "data:image/jpeg;base64," + base64.b64encode(image.read_bytes()).decode()
    r = hf.chat([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}},
                                              {"type": "text", "text": PROMPT_MOTS}]}], 300)
    return {**(hf._json(r["texte"]) or {}), "duree_s": r["duree_s"]}


def _empreintes(chemins: list):
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    modele, prep = AutoModel.from_pretrained(MODELE).eval(), AutoProcessor.from_pretrained(MODELE)
    sorties = []
    for i in range(0, len(chemins), 16):
        lot = [Image.open(c).convert("RGB") for c in chemins[i:i + 16]]
        with torch.no_grad():
            v = modele.get_image_features(**prep(images=lot, return_tensors="pt"))
        v = getattr(v, "pooler_output", v)
        sorties.append(torch.nn.functional.normalize(v, dim=-1).numpy())
    return np.concatenate(sorties)


def proches(catalogue: Path, image: Path, combien: int = 3) -> list:
    import numpy as np
    fichiers = sorted(p for p in catalogue.iterdir() if p.suffix.lower() in IMAGES)
    if not fichiers:
        raise SystemExit(f"aucune image de produit dans {catalogue}")
    index = catalogue / ".index.npz"
    noms = [p.name for p in fichiers]
    if index.exists() and list(np.load(index)["noms"]) == noms:
        base = np.load(index)["vecteurs"]
    else:
        print(f"[similaire] calcul des empreintes de {len(fichiers)} produit(s)…", file=sys.stderr)
        base = _empreintes(fichiers)
        np.savez(index, noms=np.array(noms), vecteurs=base)
    scores = base @ _empreintes([image])[0]
    infos = {}
    if (catalogue / "catalogue.csv").exists():
        with open(catalogue / "catalogue.csv", encoding="utf-8") as f:
            infos = {l["fichier"]: l for l in csv.DictReader(f)}
    return [{"fichier": noms[i], "ressemblance": round(float(scores[i]), 3), **{k: v for k, v in infos.get(noms[i], {}).items() if k != "fichier"}}
            for i in np.argsort(-scores)[:combien]]


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Produits du catalogue les plus proches d'une photo d'inspiration")
    a.add_argument("--mots", help="photo d'inspiration : donne seulement les mots à chercher chez le fournisseur")
    a.add_argument("catalogue", nargs="?"); a.add_argument("image", nargs="?")
    a.add_argument("-n", type=int, default=3)
    args = a.parse_args()
    if args.mots:
        print(json.dumps(mots(Path(args.mots)), ensure_ascii=False, indent=2))
    elif args.catalogue and args.image:
        print(json.dumps(proches(Path(args.catalogue), Path(args.image), args.n), ensure_ascii=False, indent=2))
    else:
        a.error("donner --mots photo.jpg, ou bien : dossier_catalogue photo.jpg")
