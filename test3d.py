#!/usr/bin/env python3
"""Marcel — test 3D Hugging Face (gratuit : Spaces ZeroGPU).

1. Envoie la photo produit à un modèle « image → 3D » hébergé sur un Space HF.
2. Remet l'objet à l'échelle EXACTE avec les dimensions vérifiées (le modèle
   ne connaît pas les vraies mesures : c'est le code qui les impose).
3. Le place dans la niche et produit une page HTML de visualisation.

Usage :
    uv run test3d.py test3d/etagere.jpg                 # Stable Fast 3D
    uv run test3d.py test3d/etagere.jpg --modele hunyuan
"""
import argparse
import base64
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

ICI = Path(__file__).parent
SORTIE = ICI / "test3d"
LOG = ICI / "logs" / "hf.jsonl"


def generer(image: str, modele: str) -> Path:
    from gradio_client import Client, handle_file
    tok = os.environ.get("HF_TOKEN")
    if modele == "sf3d":
        c = Client("stabilityai/stable-fast-3d", token=tok)
        _, glb = c.predict(handle_file(image), 0.85, "None", -1, 1024, api_name="/run_button")
    elif modele == "hunyuan":
        c = Client("tencent/Hunyuan3D-2", token=tok)
        res = c.predict(caption=None, image=handle_file(image), mv_image_front=None, mv_image_back=None,
                        mv_image_left=None, mv_image_right=None, steps=30, guidance_scale=5.0, seed=1234,
                        octree_resolution=256, check_box_rembg=True, num_chunks=8000, randomize_seed=False,
                        api_name="/shape_generation")  # /generation_all (texture) est en panne sur ce Space
        glb = res[0] if isinstance(res, (list, tuple)) else res
        if isinstance(glb, dict):
            glb = glb.get("value") or glb.get("path")
    elif modele == "trellis":
        c = Client("microsoft/TRELLIS.2", token=tok)
        c.predict(api_name="/start_session")
        pre = c.predict(handle_file(image), api_name="/preprocess_image")
        c.predict(image=handle_file(pre), seed=0, resolution="512", api_name="/image_to_3d")
        res = c.predict(decimation_target=100000, texture_size=1024, api_name="/extract_glb")
        glb = res[0] if isinstance(res, (list, tuple)) else res
        if isinstance(glb, dict):
            glb = glb.get("value") or glb.get("path")
    else:
        raise SystemExit(f"modèle inconnu : {modele}")
    dest = SORTIE / f"{modele}_brut.glb"
    shutil.copy(glb, dest)
    return dest


def mettre_a_echelle(glb: Path, L: float, P: float, H: float):
    """glTF : Y = haut. On impose largeur (X) = L, hauteur (Y) = H, profondeur (Z) = P, en mètres."""
    scene = trimesh.load(glb, force="scene")
    mesh = scene.to_geometry() if hasattr(scene, "to_geometry") else scene.dump(concatenate=True)
    ext = mesh.bounding_box.extents
    # si le modèle a sorti l'objet tourné de 90° (profondeur plus grande que largeur), on le remet
    if ext[2] > ext[0]:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        ext = mesh.bounding_box.extents
    proportions_brutes = {"L": 1.0, "P": round(ext[2] / ext[0], 3), "H": round(ext[1] / ext[0], 3)}
    proportions_reelles = {"L": 1.0, "P": round(P / L, 3), "H": round(H / L, 3)}
    mesh.apply_translation(-mesh.bounding_box.centroid)
    mesh.apply_scale([L / 1000 / ext[0], H / 1000 / ext[1], P / 1000 / ext[2]])
    if not getattr(mesh.visual, "material", None) or mesh.visual.kind != "texture":
        mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=[190, 150, 100, 255])  # chêne
    return mesh, proportions_brutes, proportions_reelles


def niche(Ln: float, Pn: float, Hn: float, ep: float = 0.05):
    """Niche = 2 murs latéraux + fond, en blanc (couleur de la peinture choisie)."""
    l, p, h = Ln / 1000, Pn / 1000, Hn / 1000
    murs = [
        trimesh.creation.box([ep, h, p + ep], trimesh.transformations.translation_matrix([-l / 2 - ep / 2, h / 2, 0])),
        trimesh.creation.box([ep, h, p + ep], trimesh.transformations.translation_matrix([l / 2 + ep / 2, h / 2, 0])),
        trimesh.creation.box([l + 2 * ep, h, ep], trimesh.transformations.translation_matrix([0, h / 2, -p / 2 - ep / 2])),
    ]
    for m in murs:
        m.visual.face_colors = [245, 245, 242, 255]
    return murs


def page_html(glb: Path, titre: str, infos: str) -> Path:
    b64 = base64.b64encode(glb.read_bytes()).decode()
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{titre}</title>
<script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
<style>body{{margin:0;font-family:system-ui;background:#f4f4f2}}model-viewer{{width:100vw;height:85vh}}p{{padding:0 16px}}</style>
</head><body><p><b>{titre}</b> — {infos}</p>
<model-viewer src="data:model/gltf-binary;base64,{b64}" camera-controls auto-rotate shadow-intensity="1" exposure="1.1"></model-viewer>
</body></html>"""
    out = glb.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument("image")
    a.add_argument("--modele", default="sf3d", choices=["sf3d", "hunyuan", "trellis"])
    a.add_argument("--reutiliser", action="store_true", help="réutilise test3d/<modele>_brut.glb sans regénérer")
    a.add_argument("--dims", default="600,170,200", help="largeur,profondeur,hauteur en mm (vérifiées)")
    a.add_argument("--niche", default="800,250,450", help="largeur,profondeur,hauteur de la niche en mm")
    args = a.parse_args()
    L, P, H = map(float, args.dims.split(","))
    Ln, Pn, Hn = map(float, args.niche.split(","))
    SORTIE.mkdir(exist_ok=True)

    if args.reutiliser:
        brut = SORTIE / f"{args.modele}_brut.glb"
        print(f"[3d] {args.modele} — réutilisation de {brut}")
        return finir(brut, args, L, P, H, Ln, Pn, Hn)
    ligne = {"ts": datetime.now(timezone.utc).isoformat(), "tache": "3d", "modele": args.modele}
    t0 = time.monotonic()
    try:
        brut = generer(args.image, args.modele)
        ligne.update(succes=True, duree_s=round(time.monotonic() - t0, 1))
    except Exception as e:
        ligne.update(succes=False, duree_s=round(time.monotonic() - t0, 1), erreur=f"{type(e).__name__}: {e}"[:500])
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    print(f"[3d] {args.modele} — {ligne['duree_s']} s — " + ("ok" if ligne["succes"] else ligne["erreur"]))
    if not ligne["succes"]:
        raise SystemExit(1)
    finir(brut, args, L, P, H, Ln, Pn, Hn)


def finir(brut, args, L, P, H, Ln, Pn, Hn):
    mesh, pb, pr = mettre_a_echelle(brut, L, P, H)
    pb = {k: float(v) for k, v in pb.items()}
    print(f"Proportions sorties par le modèle : {pb}  |  réelles (fiche produit) : {pr}")
    seul = SORTIE / f"{args.modele}_etagere.glb"
    mesh.export(seul)
    # étagère posée dans la niche, centrée, à mi-hauteur, collée au fond
    mesh.apply_translation([0, Hn / 1000 / 2, -Pn / 1000 / 2 + P / 1000 / 2])
    scene = trimesh.Scene(niche(Ln, Pn, Hn) + [mesh])
    dans_niche = SORTIE / f"{args.modele}_niche.glb"
    scene.export(dans_niche)
    jeu = (Ln - L) / 2
    for f, t in ((seul, "Étagère seule (à l'échelle réelle)"), (dans_niche, "Étagère dans la niche")):
        print("→", page_html(f, t, f"étagère {L:.0f}×{P:.0f}×{H:.0f} mm · niche {Ln:.0f}×{Pn:.0f} mm "
                                  f"· jeu {jeu:.0f} mm de chaque côté · modèle {args.modele}"))


if __name__ == "__main__":
    main()
