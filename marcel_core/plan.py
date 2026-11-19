"""Lecture du plan coté : le modèle LIT les cotes écrites sur la photo du plan, le code les CONTRÔLE.

L'artisan photographie son croquis ; Marcel pré-remplit longueur, largeur, hauteur, portes et fenêtres.
Rien n'est enregistré sans que l'artisan confirme : les valeurs reviennent avec « a_confirmer ».
Le modèle ne mesure rien et ne devine rien : une cote qui n'est pas écrite reste vide.
"""
from typing import Optional

from . import hf

PROMPT_PLAN = """Voici la photo d'un plan de pièce coté, dessiné par un artisan (vue de dessus).
Lis UNIQUEMENT les nombres écrits sur le plan. Ne mesure rien, ne devine rien : si une cote n'est pas écrite, mets null.
Recopie chaque nombre dans l'unité écrite et indique cette unité. Réponds UNIQUEMENT avec un objet JSON :
{
  "unite": "m | cm | mm",
  "cote_horizontale": nombre,          // longueur totale des murs du haut et du bas du dessin
  "cote_verticale": nombre,            // longueur totale des murs de gauche et de droite du dessin
  "hauteur_sous_plafond": nombre ou null,   // souvent notée HSP ou H
  "surface_ecrite_m2": nombre ou null,
  "piece": "nom de la pièce écrit sur le plan, ou null",
  "ouvertures": [
    {"type": "porte | fenetre",
     "mur": "haut | bas | gauche | droite",       // côté du dessin où elle se trouve
     "largeur": nombre ou null, "hauteur": nombre ou null, "allege": nombre ou null,
     "debut": nombre ou null}                       // cote écrite entre le coin GAUCHE du mur (murs haut et bas) ou le coin du HAUT (murs gauche et droite) et le début de l'ouverture
  ],
  "cotes_lues": ["toutes les cotes écrites, telles quelles"],
  "doutes": ["nombre illisible, cote ambiguë, cotes qui ne s'additionnent pas…"]
}"""

EN_METRES = {"m": 1.0, "cm": 0.01, "mm": 0.001}
MUR = {"haut": "fond", "bas": "avant", "gauche": "gauche", "droite": "droit"}   # noms des murs du rendu 3D


def _n(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", ".").replace("m", "").strip())
    except (TypeError, ValueError):
        return None


def controler(lu: dict) -> dict:
    """Transforme ce que le modèle a lu en valeurs de fiche, en mètres, avec les alertes. Aucun appel réseau."""
    alertes = [str(d) for d in lu.get("doutes") or [] if d]
    k = EN_METRES.get(str(lu.get("unite") or "m").strip().lower(), 1.0)

    def m(v, maxi=30.0):
        x = _n(v)
        if x is None or x <= 0:
            return None
        x *= k
        if x > maxi:   # 420 lu comme des mètres : c'étaient des centimètres (ou des millimètres)
            x = x / 100 if x / 100 <= maxi else x / 1000
        return round(x, 3)

    h_, v_ = m(lu.get("cote_horizontale")), m(lu.get("cote_verticale"))
    hsp = m(lu.get("hauteur_sous_plafond"), 6.0)
    if h_ is None or v_ is None:
        alertes.append("les deux dimensions de la pièce ne sont pas lisibles sur le plan : à saisir à la main")
    for nom, x in (("longueur", h_), ("largeur", v_)):
        if x is not None and not 1.0 <= x <= 15.0:
            alertes.append(f"{nom} de {x:g} m : inhabituel pour une pièce, à vérifier")
    if hsp is None:
        alertes.append("hauteur sous plafond absente du plan : à saisir")
    elif not 2.0 <= hsp <= 4.0:
        alertes.append(f"hauteur sous plafond de {hsp:g} m : à vérifier")
    surface = _n(lu.get("surface_ecrite_m2"))
    if h_ and v_ and surface and abs(h_ * v_ - surface) > max(0.6, 0.06 * surface):
        alertes.append(f"surface écrite {surface:g} m² ≠ {h_:g} × {v_:g} = {h_ * v_:.1f} m² : une cote est peut-être fausse")

    ouvertures = []
    for o in lu.get("ouvertures") or []:
        genre = "porte" if "port" in str(o.get("type", "")).lower() else "fenetre"
        cote = str(o.get("mur") or "").strip().lower()
        long_mur = h_ if cote in ("haut", "bas") else v_ if cote in ("gauche", "droite") else None
        larg, debut = m(o.get("largeur"), 6.0), m(o.get("debut"))
        ligne = {"type": genre, "mur": MUR.get(cote), "largeur_m": larg, "hauteur_m": m(o.get("hauteur"), 4.0),
                 "allege_m": m(o.get("allege"), 3.0) if genre == "fenetre" else None, "position_m": None}
        if larg is None:
            alertes.append(f"largeur de la {genre} non écrite : taille standard utilisée")
        if long_mur and larg and debut is not None:
            if debut + larg > long_mur + 0.02:
                alertes.append(f"{genre} : {debut:g} + {larg:g} m dépasse le mur de {long_mur:g} m, position ignorée")
            else:  # le rendu compte depuis le coin gauche du mur VU DE L'INTÉRIEUR
                ligne["position_m"] = round(debut if cote in ("haut", "droite") else long_mur - debut - larg, 3)
        ouvertures.append(ligne)

    longueur, largeur = (max(h_, v_), min(h_, v_)) if h_ and v_ else (h_, v_)
    if h_ and v_ and v_ > h_:   # la fiche veut longueur ≥ largeur : les murs du dessin sont alors tournés d'un quart
        for o in ouvertures:
            o["position_m"] = None
        alertes.append("plan dessiné en hauteur : emplacement des ouvertures à confirmer")
    return {"longueur_m": longueur, "largeur_m": largeur, "hauteur_m": hsp,
            "surface_m2": round(longueur * largeur, 2) if longueur and largeur else None,
            "nb_portes": sum(o["type"] == "porte" for o in ouvertures),
            "nb_fenetres": sum(o["type"] == "fenetre" for o in ouvertures),
            "ouvertures": ouvertures, "piece": lu.get("piece"), "cotes_lues": lu.get("cotes_lues") or [],
            "alertes": alertes, "a_confirmer": True}


def lire_plan(plan_data_url: str) -> dict:
    """Photo du plan (data URL) → valeurs à proposer dans la fiche. L'artisan confirme avant tout enregistrement."""
    r = hf.chat([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": plan_data_url}},
                                              {"type": "text", "text": PROMPT_PLAN}]}], 900)
    lu = hf._json(r["texte"])
    if not isinstance(lu, dict):
        raise ValueError("le plan n'a pas pu être lu : photo floue ou sans cotes ?")
    return {**controler(lu), "modele": hf.MODELE, "duree_s": r["duree_s"]}
