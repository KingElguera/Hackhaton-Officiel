#!/usr/bin/env python3
"""Marcel — analyse des modèles 3D comparés + page de comparaison.

Lit test3d/bench/bilan.json (+ les 2 premiers tests TRELLIS.2 / Hunyuan3D-2),
mesure chaque objet, le remet à l'échelle exacte, et écrit
test3d/bench/index.html (rendus côte à côte + tableau).

    uv run analyse3d.py            puis    uv run analyse3d.py --serveur
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

ICI = Path(__file__).parent
B = ICI / "test3d" / "bench"
WEB = B / "web"
L, P, H = 600.0, 170.0, 200.0  # étagère KLAVRESTRÖM, fiche produit (mm)

ANCIENS = {
    "trellis2": ("TRELLIS.2 (Microsoft)", ICI / "test3d" / "trellis_brut.glb", 37.3, "forme + texture"),
    "hunyuan2": ("Hunyuan3D-2 (Tencent)", ICI / "test3d" / "hunyuan_brut.glb", 12.4, "forme seule (texture en panne)"),
}


def charger(p: Path):
    s = trimesh.load(p, force="scene")
    return s.to_geometry() if hasattr(s, "to_geometry") else s.dump(concatenate=True)


def analyser(cle, nom, fichier: Path, duree, sortie):
    m = charger(fichier)
    texture = getattr(m.visual, "kind", None) == "texture"
    couleurs = getattr(m.visual, "kind", None) == "vertex" and len(np.unique(m.visual.vertex_colors[:, :3], axis=0)) > 8
    ext = m.bounding_box.extents
    if ext[2] > ext[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        ext = m.bounding_box.extents
    p_ratio, h_ratio = ext[2] / ext[0], ext[1] / ext[0]
    err = (abs(p_ratio - P / L) / (P / L) + abs(h_ratio - H / L) / (H / L)) / 2 * 100
    m.apply_translation(-m.bounding_box.centroid)
    m.apply_scale([L / 1000 / ext[0], H / 1000 / ext[1], P / 1000 / ext[2]])
    if not texture and not couleurs:
        m.visual = trimesh.visual.ColorVisuals(m, face_colors=[190, 150, 100, 255])
    WEB.mkdir(parents=True, exist_ok=True)
    web = WEB / f"{cle}.glb"
    m.export(web)
    return {
        "cle": cle, "nom": nom, "duree_s": duree, "sortie": sortie,
        "texture": "oui" if texture else ("couleurs" if couleurs else "non"),
        "faces": int(len(m.faces)), "taille_mo": round(web.stat().st_size / 1e6, 1),
        "prop_brutes": f"{p_ratio:.3f} / {h_ratio:.3f}", "ecart_pct": round(float(err), 1),
    }


def page(lignes, echecs):
    cartes = "\n".join(
        f"""<figure><model-viewer src="web/{r['cle']}.glb" camera-controls auto-rotate shadow-intensity="1"
 camera-orbit="-30deg 70deg auto" loading="lazy"></model-viewer>
<figcaption><b>{r['nom']}</b><br>{r['duree_s']} s · texture : {r['texture']} · écart forme {r['ecart_pct']} %</figcaption></figure>"""
        for r in lignes)
    tab = "\n".join(
        f"<tr><td>{r['nom']}</td><td>{r['duree_s']} s</td><td>{r['texture']}</td><td>{r['ecart_pct']} %</td>"
        f"<td>{r['faces']:,}".replace(",", " ") + f"</td><td>{r['taille_mo']} Mo</td></tr>" for r in lignes)
    ech = "".join(f"<li><b>{n}</b> : {e}</li>" for n, e in echecs)
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Comparatif 3D</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
<style>body{{font-family:system-ui;margin:16px;background:#f6f5f2;color:#222}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}}
figure{{margin:0;background:#fff;border-radius:10px;padding:8px}}model-viewer{{width:100%;height:260px}}
figcaption{{font-size:13px;line-height:1.4}}table{{border-collapse:collapse;margin-top:16px;background:#fff}}
td,th{{border:1px solid #ddd;padding:6px 10px;font-size:14px}}</style></head><body>
<h2>Image → 3D : comparatif des modèles Hugging Face (Spaces gratuits)</h2>
<p>Même photo produit (étagère IKEA KLAVRESTRÖM). Chaque objet est remis à l'échelle exacte de la fiche produit
(600 × 170 × 200 mm) par notre code. <i>Écart forme</i> = écart moyen des proportions brutes du modèle par rapport à la fiche
(0 % = parfait). Classement par écart de forme.</p>
<div class="g">{cartes}</div>
<table><tr><th>Modèle</th><th>Durée</th><th>Texture</th><th>Écart forme</th><th>Faces</th><th>Fichier</th></tr>{tab}</table>
{"<h3>Échecs</h3><ul>" + ech + "</ul>" if ech else ""}
</body></html>"""
    (B / "index.html").write_text(html, encoding="utf-8")


def main():
    bilan = json.loads((B / "bilan.json").read_text())
    lignes, echecs = [], []
    for cle, (nom, f, d, s) in ANCIENS.items():
        if f.exists():
            lignes.append(analyser(cle, nom, f, d, s))
    for cle, r in bilan.items():
        if r.get("succes"):
            try:
                lignes.append(analyser(cle, r["nom"], B / r["fichier"], r["duree_s"], r["sortie"]))
            except Exception as e:
                echecs.append((r["nom"], f"fichier illisible : {type(e).__name__}: {e}"[:200]))
        else:
            echecs.append((r["nom"], r.get("erreur", "")[:200]))
    lignes.sort(key=lambda r: r["ecart_pct"])
    page(lignes, echecs)
    (B / "analyse.json").write_text(json.dumps({"ok": lignes, "echecs": echecs}, ensure_ascii=False, indent=2))
    for r in lignes:
        print(f"{r['nom']:42} {r['duree_s']:>6} s  texture={r['texture']:8} écart={r['ecart_pct']:>5} %  "
              f"faces={r['faces']:>7}  {r['taille_mo']} Mo")
    for n, e in echecs:
        print(f"ÉCHEC {n}: {e}")


if __name__ == "__main__":
    main()
