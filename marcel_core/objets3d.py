"""Meubles en 3D : une photo de meuble → un objet 3D à la bonne taille, prêt pour Blender ou le navigateur.

Le modèle (TRELLIS, sur un Space Hugging Face) donne la FORME et la texture.
Les DIMENSIONS viennent de l'artisan ou de la fiche produit : c'est le code qui les impose.

Ce module ne tourne pas sur Vercel : une génération prend 30 à 40 s et consomme du quota GPU.
On l'appelle hors parcours (script `meuble3d.py`, ou le programme de rendu), et le résultat est mis en cache :
une même photo ne repasse jamais dans le modèle.

Dépendances du groupe « outils » (`uv sync --group outils`) : gradio-client, trimesh.
"""
import hashlib
import json
import os
import shutil
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

RACINE = Path(__file__).resolve().parent.parent
CACHE = RACINE / "objets3d"
LOG = RACINE / "logs" / "hf.jsonl"

# Écart de proportions au-delà duquel on prévient : le modèle a peut-être mal compris l'objet.
SEUIL_ECART_PCT = 25.0


class QuotaGPU(RuntimeError):
    """Le quota GPU du compte Hugging Face est épuisé : inutile de réessayer tout de suite."""


def _chemin(x):
    """Retrouve le fichier 3D dans la réponse d'un Space (les formats de réponse varient)."""
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
    if isinstance(x, str) and x.lower().endswith(".glb") and os.path.exists(x):
        return x
    return None


# ---------------------------------------------------------------- les modèles
def _trellis2(image: str, tok: Optional[str]):
    """TRELLIS.2 (Microsoft) : forme + texture, environ 100 000 faces, ~37 s."""
    from gradio_client import Client, handle_file
    c = Client("microsoft/TRELLIS.2", token=tok, verbose=False)
    c.predict(api_name="/start_session")
    pre = c.predict(handle_file(image), api_name="/preprocess_image")
    c.predict(image=handle_file(_image_pretraitee(pre)), seed=0, resolution="512", api_name="/image_to_3d")
    return _chemin(c.predict(decimation_target=100000, texture_size=1024, api_name="/extract_glb"))


def _trellis1(image: str, tok: Optional[str]):
    """TRELLIS v1 (Space de la communauté) : forme + texture, fichier très léger, ~27 s. Sert de secours."""
    from gradio_client import Client, handle_file
    c = Client("trellis-community/TRELLIS", token=tok, verbose=False)
    try:
        c.predict(api_name="/start_session")
    except Exception:
        pass
    pre = c.predict(handle_file(image), api_name="/preprocess_image")
    r = c.predict(image=handle_file(_image_pretraitee(pre)), multiimages=[], seed=0, ss_guidance_strength=7.5,
                  ss_sampling_steps=12, slat_guidance_strength=3.0, slat_sampling_steps=12,
                  multiimage_algo="stochastic", mesh_simplify=0.95, texture_size=1024,
                  api_name="/generate_and_extract_glb")
    return _chemin(r)


def _image_pretraitee(pre):
    if isinstance(pre, dict):
        return pre.get("path") or pre.get("value") or pre.get("url")
    if isinstance(pre, (list, tuple)):
        return _image_pretraitee(pre[0])
    return pre


MODELES = {
    "trellis2": ("TRELLIS.2 (Microsoft)", _trellis2),
    "trellis1": ("TRELLIS v1 (Microsoft)", _trellis1),
}
SECOURS = {"trellis2": "trellis1"}


def _journal(ligne: dict):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


def generer(image: str, modele: str = "trellis2", secours: bool = True):
    """Envoie la photo au modèle. Renvoie (fichier .glb brut, modèle réellement utilisé, durée en secondes).

    Si le modèle demandé échoue pour une autre raison que le quota, on essaie le modèle de secours.
    """
    if modele not in MODELES:
        raise ValueError(f"modèle inconnu : {modele} (choix : {', '.join(MODELES)})")
    tok = os.environ.get("HF_TOKEN")
    essais = [modele] + ([SECOURS[modele]] if secours and modele in SECOURS else [])
    derniere = None
    for m in essais:
        t0 = time.monotonic()
        ligne = {"ts": datetime.now(timezone.utc).isoformat(), "tache": "3d", "modele": m, "usage": "meuble"}
        try:
            glb = MODELES[m][1](image, tok)
            if not glb:
                raise RuntimeError("le Space n'a renvoyé aucun fichier .glb")
            duree = round(time.monotonic() - t0, 1)
            _journal({**ligne, "succes": True, "duree_s": duree})
            return Path(glb), m, duree
        except Exception as e:
            duree = round(time.monotonic() - t0, 1)
            _journal({**ligne, "succes": False, "duree_s": duree, "erreur": f"{type(e).__name__}: {e}"[:500]})
            if "quota" in str(e).lower():
                raise QuotaGPU(f"quota GPU Hugging Face épuisé ({MODELES[m][0]}) : {str(e)[:200]}") from e
            derniere = e
    raise RuntimeError(f"génération 3D impossible ({', '.join(essais)}) : {derniere}")


# ---------------------------------------------------------------- mise à l'échelle
def mettre_a_echelle(glb: Path, sortie: Path, largeur_mm: float, profondeur_mm: Optional[float] = None,
                     hauteur_mm: Optional[float] = None) -> dict:
    """Impose les vraies dimensions à l'objet et l'enregistre dans `sortie`.

    Repère glTF : X = largeur, Y = hauteur (vers le haut), Z = profondeur. L'objet sort centré, posé sur Y = 0,
    en mètres. Blender et <model-viewer> lisent ce fichier tel quel.

    - Les trois dimensions sont données : mise à l'échelle exacte sur chaque axe.
    - Seule la largeur est donnée : mise à l'échelle uniforme, les proportions du modèle sont gardées.
    """
    import numpy as np
    import trimesh
    from trimesh.transformations import rotation_matrix, translation_matrix

    scene = trimesh.load(glb, force="scene")
    lo, hi = scene.bounds
    ext = hi - lo
    transfo = translation_matrix(-(lo + hi) / 2)  # 1. centrer
    tourne = False
    if profondeur_mm and largeur_mm >= profondeur_mm and ext[2] > ext[0] * 1.05:
        # Le modèle a sorti l'objet tourné d'un quart de tour (plus profond que large) : on le remet de face.
        transfo = rotation_matrix(np.pi / 2, [0, 1, 0]) @ transfo
        ext = np.array([ext[2], ext[1], ext[0]])
        tourne = True
    brutes = {"profondeur_sur_largeur": round(float(ext[2] / ext[0]), 3), "hauteur_sur_largeur": round(float(ext[1] / ext[0]), 3)}
    L = largeur_mm / 1000
    if profondeur_mm and hauteur_mm:
        P, H = profondeur_mm / 1000, hauteur_mm / 1000
        echelle = np.diag([L / ext[0], H / ext[1], P / ext[2], 1.0])
        reelles = {"profondeur_sur_largeur": round(P / L, 3), "hauteur_sur_largeur": round(H / L, 3)}
        ecart = round(100 * (abs(brutes["profondeur_sur_largeur"] / reelles["profondeur_sur_largeur"] - 1)
                             + abs(brutes["hauteur_sur_largeur"] / reelles["hauteur_sur_largeur"] - 1)) / 2, 1)
        mode = "exacte"
    else:
        s = L / ext[0]
        echelle = np.diag([s, s, s, 1.0])
        P, H = float(ext[2] * s), float(ext[1] * s)
        reelles, ecart, mode = None, None, "uniforme (proportions du modèle)"
    transfo = translation_matrix([0, H / 2, 0]) @ echelle @ transfo  # 2. dimensionner, 3. poser sur le sol
    scene.apply_transform(transfo)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    scene.export(sortie)
    faces = int(sum(len(g.faces) for g in scene.geometry.values() if hasattr(g, "faces")))
    alertes = []
    if ecart is not None and ecart > SEUIL_ECART_PCT:
        alertes.append(f"les proportions sorties par le modèle s'écartent de {ecart} % des vraies dimensions : "
                       "vérifier que l'objet 3D ressemble bien au meuble")
    if mode != "exacte":
        alertes.append("profondeur et hauteur déduites du modèle : donner les trois dimensions pour un objet exact")
    return {"fichier": str(sortie), "dimensions_mm": {"largeur": round(L * 1000), "profondeur": round(P * 1000), "hauteur": round(H * 1000)},
            "mise_a_echelle": mode, "remis_de_face": tourne, "proportions_modele": brutes, "proportions_reelles": reelles,
            "ecart_proportions_pct": ecart, "faces": faces, "taille_mo": round(sortie.stat().st_size / 1e6, 2), "alertes": alertes}


# ---------------------------------------------------------------- fonction principale
def _photo_locale(image: str, cache: Path) -> Path:
    """La photo peut être un fichier ou un lien (par exemple l'image relevée par l'agent)."""
    if image.startswith(("http://", "https://")):
        cache.mkdir(parents=True, exist_ok=True)
        dest = cache / ("photo_" + hashlib.sha256(image.encode()).hexdigest()[:12] + ".jpg")
        if not dest.exists():
            req = urllib.request.Request(image, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r, dest.open("wb") as f:
                shutil.copyfileobj(r, f)
        return dest
    p = Path(image)
    if not p.exists():
        raise FileNotFoundError(f"photo introuvable : {image}")
    return p


def empreinte_visuelle(photo: Path) -> Optional[str]:
    """Empreinte qui ne change pas quand la photo est recompressée ou réduite par le site (moyenne sur 16 × 16 gris).
    Sert à retrouver en cache un meuble déjà modélisé à partir de la même photo produit."""
    try:
        from PIL import Image
        im = Image.open(photo).convert("L")
        im.thumbnail((256, 256))
        petit = im.resize((16, 16), Image.BILINEAR)
        px = list(petit.tobytes())   # niveaux de gris, un octet par point
        m = sum(px) / len(px)
        return "".join("1" if v > m else "0" for v in px)   # 256 bits
    except Exception:
        return None


def _meme_photo(cache: Path, bits: Optional[str], tolerance: int = 12) -> Optional[str]:
    """Clé d'un meuble déjà modélisé dont la photo ressemble à celle-ci (≤ 12 points différents sur 256), sinon None."""
    if not bits:
        return None
    try:
        connus = json.loads((cache / "empreintes.json").read_text())
    except Exception:
        return None
    meilleur = min(((sum(a != b for a, b in zip(bits, v)), k) for k, v in connus.items() if len(v) == len(bits)), default=None)
    return meilleur[1] if meilleur and meilleur[0] <= tolerance else None


def _retenir(cache: Path, cle: str, bits: Optional[str]):
    if not bits:
        return
    f = cache / "empreintes.json"
    try:
        connus = json.loads(f.read_text())
    except Exception:
        connus = {}
    if connus.get(cle) != bits:
        connus[cle] = bits
        f.write_text(json.dumps(connus))


def objet_3d(image: str, largeur_mm: float, profondeur_mm: Optional[float] = None, hauteur_mm: Optional[float] = None,
             modele: str = "trellis2", cache: Path = CACHE, brut: Optional[str] = None, regenerer: bool = False) -> dict:
    """Photo d'un meuble + ses dimensions → fichier .glb à l'échelle.

    `brut` : chemin d'un .glb déjà sorti par le modèle (pour refaire la mise à l'échelle sans consommer de quota).
    Le .glb brut est gardé en cache sous l'empreinte de la photo : changer les dimensions ne relance pas le modèle.
    """
    if not largeur_mm or largeur_mm <= 0:
        raise ValueError("la largeur du meuble est obligatoire : le modèle ne connaît pas les vraies mesures")
    photo = _photo_locale(image, cache)
    cle = hashlib.sha256(photo.read_bytes()).hexdigest()[:12]
    cache.mkdir(parents=True, exist_ok=True)
    duree, depuis_cache = None, False
    if brut:
        if not Path(brut).exists():
            raise FileNotFoundError(f"fichier brut introuvable : {brut}")
        # Un fichier déjà sorti par le modèle : on le range dans le cache, il ne sera plus jamais regénéré.
        glb_brut, utilise = cache / f"{cle}_{modele}_brut.glb", modele
        if Path(brut).resolve() != glb_brut.resolve():
            shutil.copy(brut, glb_brut)
        depuis_cache = True
    else:
        bits = empreinte_visuelle(photo)
        if not regenerer and not list(cache.glob(f"{cle}_*_brut.glb")):
            cle = _meme_photo(cache, bits) or cle   # même photo, recompressée par le site : le meuble est déjà modélisé
        existants = sorted(cache.glob(f"{cle}_*_brut.glb"))
        voulu = cache / f"{cle}_{modele}_brut.glb"
        if not regenerer and (voulu.exists() or existants):
            glb_brut = voulu if voulu.exists() else existants[0]
            utilise, depuis_cache = glb_brut.name.split("_")[1], True
        else:
            tmp, utilise, duree = generer(str(photo), modele)
            glb_brut = cache / f"{cle}_{utilise}_brut.glb"
            shutil.copy(tmp, glb_brut)
        _retenir(cache, cle, bits)
    dims = "x".join(str(int(round(v))) if v else "auto" for v in (largeur_mm, profondeur_mm, hauteur_mm))
    final = cache / f"{cle}_{dims}.glb"
    infos = mettre_a_echelle(glb_brut, final, largeur_mm, profondeur_mm, hauteur_mm)
    resultat = {"cle": cle, "photo": str(photo), "modele": utilise, "nom_modele": MODELES.get(utilise, (utilise,))[0],
                "duree_generation_s": duree, "depuis_cache": depuis_cache, "brut": str(glb_brut), **infos}
    (cache / f"{cle}.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultat


def entree_chantier(resultat: dict, mur: str = "fond", position_m: Optional[float] = None, nom: Optional[str] = None,
                    hauteur_pose_m: float = 0.0) -> dict:
    """Ce qu'il faut ajouter à la liste « meubles » du fichier de chantier lu par rendu/marcel_rendu.py."""
    if mur not in ("fond", "avant", "gauche", "droit"):
        raise ValueError("mur : fond, avant, gauche ou droit")
    fichier = Path(resultat["fichier"])
    try:  # chemin relatif à la racine du dépôt : le fichier de chantier reste valable sur une autre machine
        fichier = fichier.resolve().relative_to(RACINE)
    except ValueError:
        pass
    e = {"nom": nom or "meuble_" + resultat["cle"], "modele": fichier.as_posix(), "mur": mur,
         "largeur_m": resultat["dimensions_mm"]["largeur"] / 1000}
    if position_m is not None:
        e["position"] = position_m
    if hauteur_pose_m:
        e["hauteur_pose_m"] = hauteur_pose_m
    return e
