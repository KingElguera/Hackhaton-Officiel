#!/usr/bin/env python3
"""Marcel — comparaison de modèles image → 3D (Spaces Hugging Face gratuits).

Même photo, réglages par défaut de chaque Space. Pour chaque modèle :
durée, succès/erreur, fichier .glb brut dans test3d/bench/.
S'arrête dès qu'une erreur de quota GPU apparaît (pour garder du quota).

    uv run bench3d.py test3d/etagere.jpg               # tous
    uv run bench3d.py test3d/etagere.jpg tripo trellis1
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from gradio_client import Client, handle_file

ICI = Path(__file__).parent
OUT = ICI / "test3d" / "bench"
LOG = ICI / "logs" / "hf.jsonl"
TOK = os.environ.get("HF_TOKEN")


def _chemin(x):
    if isinstance(x, (list, tuple)):
        for v in x:
            p = _chemin(v)
            if p:
                return p
        return None
    if isinstance(x, dict):
        for k in ("value", "path", "model", "file"):
            if x.get(k):
                return _chemin(x[k])
        return None
    if isinstance(x, str) and x.lower().endswith((".glb", ".obj", ".ply")) and os.path.exists(x):
        return x
    return None


def hunyuan21(img):
    c = Client("tencent/Hunyuan3D-2.1", token=TOK, verbose=False)
    try:
        r = c.predict(image=handle_file(img), steps=30, guidance_scale=5.0, seed=1234, octree_resolution=256,
                      check_box_rembg=True, num_chunks=8000, randomize_seed=False, api_name="/generation_all")
        return r[1] if _chemin(r[1]) else _chemin(r), "forme + texture"
    except Exception as e:
        print(f"   (texture en échec : {str(e)[:120]} → forme seule)")
        r = c.predict(image=handle_file(img), steps=30, guidance_scale=5.0, seed=1234, octree_resolution=256,
                      check_box_rembg=True, num_chunks=8000, randomize_seed=False, api_name="/shape_generation")
        return _chemin(r), "forme seule (texture en panne)"


def tripo(img):
    c = Client("VAST-AI/TripoSG", token=TOK, verbose=False)
    seg = c.predict(handle_file(img), api_name="/run_segmentation")
    seg_p = _chemin(seg) or (seg.get("path") if isinstance(seg, dict) else seg)
    mesh = c.predict(handle_file(seg_p), 0, 50, 7.0, True, 100000, api_name="/image_to_3d")
    mesh_p = _chemin(mesh)
    try:
        tex = c.predict(handle_file(seg_p), handle_file(mesh_p), 0, api_name="/run_texture")
        return _chemin(tex), "forme + texture"
    except Exception as e:
        print(f"   (texture en échec : {str(e)[:120]})")
        return mesh_p, "forme seule"


def trellis1(img):
    c = Client("trellis-community/TRELLIS", token=TOK, verbose=False)
    try:
        c.predict(api_name="/start_session")
    except Exception:
        pass
    pre = c.predict(handle_file(img), api_name="/preprocess_image")
    r = c.predict(image=handle_file(_chemin(pre) or pre), multiimages=[], seed=0, ss_guidance_strength=7.5,
                  ss_sampling_steps=12, slat_guidance_strength=3.0, slat_sampling_steps=12,
                  multiimage_algo="stochastic", mesh_simplify=0.95, texture_size=1024,
                  api_name="/generate_and_extract_glb")
    return _chemin(r[1:]) or _chemin(r), "forme + texture"


def unique3d(img):
    c = Client("Wuvin/Unique3D", token=TOK, verbose=False)
    r = c.predict(handle_file(img), True, 0, False, True, 0.1, "std", api_name="/generate3dv2")
    return _chemin(r), "forme + couleurs"


def hi3dgen(img):
    c = Client("Stable-X/Hi3DGen", token=TOK, verbose=False)
    pre = c.predict(handle_file(img), api_name="/preprocess_image")
    r = c.predict(handle_file(_chemin(pre) or pre), 0, 3, 50, 3.0, 6, api_name="/generate_3d")
    p = _chemin(r)
    if p and not p.lower().endswith(".glb"):
        try:
            p = _chemin(c.predict(p, "glb", api_name="/update_download_button")) or p
        except Exception:
            pass
    return p, "forme seule (géométrie détaillée)"


def pixal3d(img):
    c = Client("TencentARC/Pixal3D", token=TOK, verbose=False)
    pre = c.predict(handle_file(img), api_name="/preprocess")
    st = c.predict(handle_file(_chemin(pre) or pre), 0, 512, 7.5, 0.7, 12, 5.0, 7.5, 0.5, 12, 3.0, 1.0, 0.0, 12,
                   3.0, -1.0, "deg", "", api_name="/generate_3d")
    state = st.get("state_path") if isinstance(st, dict) else None
    sid = st.get("session_id", "") if isinstance(st, dict) else ""
    if not state and isinstance(st, dict):
        state = next((v for v in st.values() if isinstance(v, str) and ("/" in v)), None)
    r = c.predict(state, 100000, 1024, sid, api_name="/extract_glb_api")
    return _chemin(r), "forme + texture"


def frogleo(img):
    c = Client("frogleo/Image-to-3D", token=TOK, verbose=False)
    r = c.predict(handle_file(img), 5, 5.5, 1234, 256, 8000, 10000, False, api_name="/gen_shape")
    return _chemin(r), "forme seule"


MODELES = {
    "hunyuan21": ("Hunyuan3D-2.1 (Tencent)", hunyuan21),
    "tripo": ("TripoSG (VAST)", tripo),
    "trellis1": ("TRELLIS v1 (Microsoft)", trellis1),
    "unique3d": ("Unique3D", unique3d),
    "hi3dgen": ("Hi3DGen (Stable-X)", hi3dgen),
    "pixal3d": ("Pixal3D (Tencent ARC)", pixal3d),
    "frogleo": ("Image-to-3D (frogleo, Hunyuan rapide)", frogleo),
}


def main():
    img = sys.argv[1]
    choix = sys.argv[2:] or list(MODELES)
    OUT.mkdir(parents=True, exist_ok=True)
    bilan = OUT / "bilan.json"
    res = json.loads(bilan.read_text()) if bilan.exists() else {}
    for cle in choix:
        nom, fn = MODELES[cle]
        print(f"→ {nom} …", flush=True)
        t0 = time.monotonic()
        ligne = {"ts": datetime.now(timezone.utc).isoformat(), "tache": "3d-bench", "modele": cle}
        try:
            chemin, sortie = fn(img)
            if not chemin:
                raise RuntimeError("aucun fichier 3D renvoyé")
            dest = OUT / f"{cle}{Path(chemin).suffix.lower()}"
            shutil.copy(chemin, dest)
            ligne.update(succes=True, sortie=sortie, fichier=dest.name)
        except Exception as e:
            ligne.update(succes=False, erreur=f"{type(e).__name__}: {e}"[:400])
        ligne["duree_s"] = round(time.monotonic() - t0, 1)
        print(f"   {'OK' if ligne['succes'] else 'ÉCHEC'} en {ligne['duree_s']} s — "
              f"{ligne.get('sortie') or ligne.get('erreur')}", flush=True)
        res[cle] = {"nom": nom, **ligne}
        bilan.write_text(json.dumps(res, ensure_ascii=False, indent=2))
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        if not ligne["succes"] and "quota" in ligne.get("erreur", "").lower():
            print("Quota GPU gratuit atteint : on s'arrête là pour en garder.")
            break


if __name__ == "__main__":
    main()
