"""Vérification, choix, planning et budget — calculés par le CODE, jamais par un modèle.

L'agent H et Hugging Face extraient des informations ; ce module décide :
- un objet rentre-t-il dans l'emplacement (marge comprise) ?
- combien d'unités d'un matériau acheter pour la surface (perte comprise) ?
- quel produit retenir par besoin, dans quel ordre faire les travaux, budget tenu ?
"""
import math
from datetime import date, timedelta
from typing import List, Optional

from .modeles import Projet

JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
RENDEMENT_PEINTURE_DEFAUT = 10.0  # m²/L, valeur courante quand la fiche ne l'affiche pas

# perte (chutes, raccords) par type de matériau — valeurs usuelles du métier
PERTES = [("peinture", 0), ("papier peint", 15), ("lambris", 10), ("parquet", 10), ("stratifié", 10),
          ("carrelage", 10), ("faïence", 10), ("vinyle", 10), ("moquette", 10), ("enduit", 10)]
# phase (ordre des travaux) et durée en jours (débutant, confirmé)
PHASES = [("enduit", "murs", (2, 1), "Reboucher / enduire les murs (séchage compris)"),
          ("peinture", "murs", (3, 2), "Préparer les murs et peindre ({couches} couches + séchage)"),
          ("papier peint", "murs", (2, 1), "Poser le papier peint"),
          ("lambris", "murs", (2, 1), "Poser le lambris"),
          ("faïence", "murs", (3, 2), "Poser la faïence (joints + séchage)"),
          ("carrelage", "sols", (3, 2), "Poser le carrelage (joints + séchage)"),
          ("parquet", "sols", (2, 1), "Poser le parquet"),
          ("stratifié", "sols", (2, 1), "Poser le sol stratifié"),
          ("vinyle", "sols", (1, 1), "Poser le sol vinyle"),
          ("moquette", "sols", (1, 1), "Poser la moquette")]
ORDRE_PHASES = {"murs": 0, "sols": 1, "objets": 2}


def _phase(categorie: str, famille: str):
    c = categorie.lower()
    for mot, phase, durees, libelle in PHASES:
        if mot in c:
            return phase, durees, libelle
    if famille == "surface":
        return "murs", (2, 1), f"Poser / appliquer : {categorie}"
    if any(m in c for m in ("étagère", "etagere", "miroir", "meuble mural", "applique", "tringle", "cadre")):
        return "objets", (1, 1), f"Fixer au mur : {categorie} (perçage + chevilles)"
    if any(m in c for m in ("canapé", "canape", "fauteuil", "tapis", "chaise", "lampe", "pouf")):
        return "objets", (1, 1), f"Installer : {categorie}"
    return "objets", (1, 1), f"Monter et installer : {categorie}"


# ---------------------------------------------------------------- 1. normaliser la demande
def normaliser(projet: Projet) -> Projet:
    """Le code fixe les contraintes chiffrées (jamais le modèle) : tailles max, pertes, couches."""
    e = projet.emplacement
    for b in projet.besoins:
        if b.famille == "objet" and b.dans_emplacement:
            if e.largeur_mm:
                b.largeur_max_mm = e.largeur_mm - e.marge_mm
            if e.profondeur_mm:
                b.profondeur_max_mm = e.profondeur_mm - e.marge_mm
            if e.hauteur_mm:
                b.hauteur_max_mm = e.hauteur_mm - e.marge_mm
            if not (e.largeur_mm or e.profondeur_mm or e.hauteur_mm):
                projet.alertes.append(f"{b.categorie} : aucune mesure d'emplacement fournie, impossible de vérifier qu'il rentre")
        if b.famille == "surface":
            if b.perte_pct is None:
                b.perte_pct = next((p for mot, p in PERTES if mot in b.categorie.lower()), 10)
            if "peinture" in b.categorie.lower() and not b.couches:
                b.couches = 2
            if not b.surface_m2:
                projet.alertes.append(f"{b.categorie} : surface inconnue, quantité impossible à calculer")
    return projet


# ---------------------------------------------------------------- 2. vérifier chaque produit
def _legacy(p: dict) -> dict:
    """Compatibilité avec le premier parcours (champs besoin / volume_l)."""
    p = dict(p)
    if "besoin_id" not in p and "besoin" in p:
        p["besoin_id"] = p["besoin"]
    if p.get("volume_l") and not p.get("contenance"):
        p["contenance"], p["unite_contenance"] = p["volume_l"], "L"
    return p


def verifier(projet: Projet, sessions: List[dict]) -> List[dict]:
    besoins = {b.id: b for b in projet.besoins}
    candidats = []
    for s in sessions:
        rap = s.get("rapport") if isinstance(s.get("rapport"), dict) else {}
        for p in rap.get("produits") or []:
            p = _legacy(p)
            b = besoins.get(p.get("besoin_id"))
            c = dict(p, enseigne=s.get("enseigne"), raisons=[], valide=True,
                     famille=b.famille if b else None, categorie=b.categorie if b else None)
            if not b:
                c["valide"] = False
                c["raisons"].append(f"besoin inconnu : {p.get('besoin_id')}")
                candidats.append(c)
                continue
            if p.get("prix_eur") is None:
                c["valide"] = False
                c["raisons"].append("prix non relevé")

            if b.famille == "objet":
                for champ, maxi, mot in (("largeur_mm", b.largeur_max_mm, "large"),
                                         ("profondeur_mm", b.profondeur_max_mm, "profond"),
                                         ("hauteur_mm", b.hauteur_max_mm, "haut")):
                    if maxi is None:
                        continue
                    v = p.get(champ)
                    if v is None:
                        c["valide"] = False
                        c["raisons"].append(f"{champ.split('_')[0]} non relevée : impossible de vérifier qu'il rentre")
                    elif v > maxi:
                        c["valide"] = False
                        c["raisons"].append(f"trop {mot} : {v:.0f} mm > {maxi:.0f} mm")
                if c["valide"] and b.dans_emplacement and any((b.largeur_max_mm, b.profondeur_max_mm, b.hauteur_max_mm)):
                    dims = "×".join(f"{p[k]:.0f}" for k in ("largeur_mm", "profondeur_mm", "hauteur_mm") if p.get(k))
                    c["raisons"].append(f"rentre dans l'emplacement ({dims} mm, marge {projet.emplacement.marge_mm:.0f} mm comprise)")
                c["quantite"] = b.quantite

            elif b.famille == "surface":
                cont, unite = p.get("contenance"), p.get("unite_contenance")
                if not b.surface_m2:
                    c["valide"], c["quantite"] = False, None
                    c["raisons"].append("surface à couvrir inconnue")
                elif not cont or unite not in ("L", "m2"):
                    c["valide"], c["quantite"] = False, None
                    c["raisons"].append("contenance (L ou m² par unité) non relevée")
                else:
                    perte = (b.perte_pct or 0) / 100
                    if unite == "L":
                        rend = p.get("rendement_m2_par_l")
                        if not rend:
                            rend = RENDEMENT_PEINTURE_DEFAUT
                            c["raisons"].append(f"rendement non affiché : {rend:g} m²/L supposé")
                        couches = b.couches or 1
                        besoin_u = b.surface_m2 * couches / rend * (1 + perte)
                        c["quantite"] = math.ceil(besoin_u / cont)
                        c["raisons"].append(f"{b.surface_m2:g} m² × {couches} couche(s) ÷ {rend:g} m²/L = {besoin_u:.1f} L "
                                            f"→ {c['quantite']} × {cont:g} L")
                    else:
                        besoin_u = b.surface_m2 * (1 + perte)
                        c["quantite"] = math.ceil(besoin_u / cont)
                        c["raisons"].append(f"{b.surface_m2:g} m² + {b.perte_pct:g} % de perte = {besoin_u:.1f} m² "
                                            f"→ {c['quantite']} × {cont:g} m²")
            else:  # fourniture
                c["quantite"] = b.quantite

            c["cout_eur"] = round(c["quantite"] * p["prix_eur"], 2) if c.get("quantite") and p.get("prix_eur") else None
            if p.get("en_stock_magasin") and p.get("stock_texte"):
                c["dispo_jours"], c["dispo_mode"] = 0, f"retrait magasin ({p.get('magasin') or '?'})"
            elif p.get("delai_livraison_jours") is not None:
                c["dispo_jours"], c["dispo_mode"] = p["delai_livraison_jours"], "livraison"
            else:
                c["dispo_jours"], c["dispo_mode"] = None, "disponibilité inconnue"
            if p.get("en_stock_magasin") and not p.get("stock_texte"):
                c["raisons"].append("stock magasin annoncé sans texte affiché : non retenu")
            candidats.append(c)
    return candidats


# ---------------------------------------------------------------- 3. choisir
def choisir(projet: Projet, candidats: List[dict]) -> dict:
    """Par besoin : disponibilité connue d'abord, puis le moins cher, puis le plus tôt disponible."""
    choix = {}
    for b in projet.besoins:
        ok = [c for c in candidats if c.get("besoin_id") == b.id and c["valide"]]
        ok.sort(key=lambda c: (c["dispo_jours"] is None,
                               c["cout_eur"] if c["cout_eur"] is not None else 1e9,
                               c["dispo_jours"] if c["dispo_jours"] is not None else 99))
        choix[b.id] = ok[0] if ok else None
    return choix


# ---------------------------------------------------------------- 4. planifier
def planifier(projet: Projet, choix: dict, j0: Optional[date] = None):
    """Ordre : murs → sols → objets. Chaque tâche attend son produit ET la fin de la précédente."""
    j0 = j0 or date.today()
    debutant = projet.niveau == "débutant"
    besoins = {b.id: b for b in projet.besoins}
    fournitures = [c for bid, c in choix.items() if c and besoins[bid].famille == "fourniture"]
    d_fourn = max((c["dispo_jours"] for c in fournitures if c["dispo_jours"] is not None), default=0)

    items = []
    for bid, c in choix.items():
        b = besoins[bid]
        if b.famille == "fourniture":
            continue
        phase, durees, libelle = _phase(b.categorie, b.famille)
        items.append((ORDRE_PHASES[phase], bid, b, c, durees[0] if debutant else durees[1],
                      libelle.format(couches=b.couches or 2)))
    items.sort(key=lambda x: x[0])

    taches, non_planifiees, fin = [], [], j0 + timedelta(days=d_fourn)
    for _, bid, b, c, duree, libelle in items:
        if not c:
            non_planifiees.append({"besoin_id": bid, "raison": "aucun produit vérifié"})
            continue
        if c["dispo_jours"] is None:
            non_planifiees.append({"besoin_id": bid, "raison": "disponibilité inconnue"})
            continue
        debut = max(j0 + timedelta(days=c["dispo_jours"]), fin)
        attend = [f"{b.categorie} ({c['dispo_mode']})"]
        if debut == fin and taches:
            attend.append("fin de la tâche précédente")
        taches.append({"besoin_id": bid, "tache": libelle, "debut": debut.isoformat(),
                       "jour": f"{JOURS[debut.weekday()]} {debut.strftime('%d/%m')}", "duree_j": duree,
                       "attend": " et ".join(attend)})
        fin = debut + timedelta(days=duree)
    return taches, non_planifiees, (fin.isoformat() if taches else None)


# ---------------------------------------------------------------- 5. synthèse
def synthese(projet: Projet, sessions: List[dict], j0: Optional[date] = None) -> dict:
    candidats = verifier(projet, sessions)
    choix = choisir(projet, candidats)
    taches, non_planifiees, fin = planifier(projet, choix, j0)
    total = round(sum((c or {}).get("cout_eur") or 0 for c in choix.values()), 2)
    manquants = [bid for bid, c in choix.items() if not c]
    return {
        "projet": projet.model_dump(),
        "achats": [dict(c, besoin_id=bid) for bid, c in choix.items() if c],
        "besoins_sans_produit": manquants,
        "total_eur": total,
        "budget_eur": projet.budget_eur,
        "dans_budget": None if projet.budget_eur is None else total <= projet.budget_eur,
        "taches": taches,
        "taches_non_planifiees": non_planifiees,
        "fin_travaux": fin,
        "candidats": candidats,
        "agents": [{k: s.get(k) for k in ("enseigne", "session_id", "statut", "duree_s", "etapes", "cout_total", "replay_url")}
                   | {"acces_site": (s.get("rapport") or {}).get("acces_site") if isinstance(s.get("rapport"), dict) else None,
                      "commentaire": (s.get("rapport") or {}).get("commentaire") if isinstance(s.get("rapport"), dict) else None}
                   for s in sessions],
    }
