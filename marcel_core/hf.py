"""Hugging Face : comprendre la demande (photo + texte) et rédiger le guide de travaux.

Le modèle comprend et rédige. Les CHIFFRES viennent de l'utilisateur (formulaire)
ou du code (vérification) — jamais du modèle.
"""
import json
import math
import os
import re
import time
from typing import Optional

from .modeles import Besoin, Emplacement, Projet

MODELE = os.environ.get("HF_MODELE", "Qwen/Qwen3.8-27B")
MAX_BESOINS = 4  # chaque besoin coûte des étapes d'agent : on plafonne
HORS_PERIMETRE = ("plomberie", "plombier", "robinet", "évier", "lavabo", "chauffe-eau", "ballon d'eau", "wc", "toilette",
                  "douche", "baignoire", "tuyau", "canalisation", "électricité", "électrique", "tableau électrique",
                  "disjoncteur", "câblage", "gaz", "chaudière", "radiateur")


def chat(messages: list, max_tokens: int = 1500) -> dict:
    from huggingface_hub import InferenceClient
    t0 = time.monotonic()
    r = InferenceClient(bill_to=os.environ.get("HF_BILL_TO") or None).chat_completion(
        model=MODELE, messages=messages, max_tokens=max_tokens, temperature=0.2,
        extra_body={"reasoning_effort": "none"})  # sinon Qwen3 « réfléchit » et épuise max_tokens
    texte = re.sub(r"<think>.*?(</think>|$)", "", r.choices[0].message.content or "", flags=re.S).strip()
    u = getattr(r, "usage", None)
    return {"texte": texte, "duree_s": round(time.monotonic() - t0, 1),
            "tokens_in": getattr(u, "prompt_tokens", None), "tokens_out": getattr(u, "completion_tokens", None)}


def _json(texte: str):
    m = re.search(r"\{.*\}", texte, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- comprendre
PROMPT_COMPRENDRE = """Tu es Marcel, assistant de rénovation pour particuliers. Un utilisateur décrit son projet{avec_photo}.
Demande de l'utilisateur : « {texte} »
Mesures et infos données par l'utilisateur (fiables, NE LES MODIFIE PAS) : {infos}

Transforme la demande en liste de besoins d'achat. Familles :
- "objet" : un article qui doit éventuellement tenir dans une place (meuble, étagère, canapé, armoire, table, lit, luminaire, miroir…)
- "surface" : un matériau qui couvre une surface (peinture, papier peint, parquet, carrelage, lambris, sol vinyle…)
- "fourniture" : un petit article compté à l'unité, UNIQUEMENT si l'utilisateur le demande (vis, chevilles, colle…)
Marcel NE FAIT PAS la plomberie, l'électricité, le gaz ni le chauffage : mets ces demandes dans "hors_perimetre".
"dans_emplacement" = true seulement pour l'objet destiné à la place mesurée par l'utilisateur.
"categorie" = le type précis d'article (ex. "canapé 3 places", "étagère murale", "peinture murale"), jamais un mot vague comme "meuble".
N'invente AUCUN chiffre : ne mets surface_m2 ou couches que si l'utilisateur les a écrits. Pas de prix, pas de marque imposée.
"questions" : seulement pour une info indispensable ABSENTE des mesures ci-dessus ; ne redemande jamais une mesure déjà fournie.
{consigne_photo}
Réponds UNIQUEMENT avec un objet JSON :
{{
  "nom": "titre court du projet",
  "piece": "type de pièce",
  "besoins": [{{"id": "snake_case_court", "famille": "objet|surface|fourniture", "categorie": "...", "description": "...",
               "quantite": 1, "dans_emplacement": false, "surface_m2": null, "couches": null, "couleur": null, "style": null}}],
  "hors_perimetre": ["..."],
  "questions": ["question à poser à l'utilisateur s'il manque une info indispensable"]{schema_photo}
}}"""

CONSIGNE_PHOTO = """La photo sert à comprendre la pièce, PAS à mesurer. Décris seulement ce qui est visible ; si la photo ne correspond pas à la demande (autre pièce, emplacement absent), dis-le dans points_attention."""
SCHEMA_PHOTO = """,
  "photo": {"type_piece": "...", "elements_visibles": ["..."], "etat_murs": "bon | à reboucher | à poncer | inconnu",
            "couleur_murs_actuelle": "...", "emplacement_visible": true, "points_attention": ["..."], "confiance": "haute | moyenne | basse"}"""


def _cm(v) -> Optional[float]:
    try:
        return float(v) * 10 if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _num(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def comprendre(texte: str, code_postal: str, photo_data_url: Optional[str] = None, budget_eur=None,
               largeur_cm=None, profondeur_cm=None, hauteur_cm=None, surface_murs_m2=None,
               surface_sol_m2=None, niveau: str = "débutant") -> dict:
    infos = {k: v for k, v in {"code_postal": code_postal, "budget_eur": budget_eur,
                               "largeur_place_cm": largeur_cm, "profondeur_place_cm": profondeur_cm,
                               "hauteur_place_cm": hauteur_cm, "surface_murs_m2": surface_murs_m2,
                               "surface_sol_m2": surface_sol_m2, "niveau": niveau}.items() if v not in (None, "")}
    prompt = PROMPT_COMPRENDRE.format(
        texte=texte, infos=json.dumps(infos, ensure_ascii=False),
        avec_photo=" et envoie une photo de sa pièce" if photo_data_url else "",
        consigne_photo=CONSIGNE_PHOTO if photo_data_url else "", schema_photo=SCHEMA_PHOTO if photo_data_url else "")
    contenu = [{"type": "text", "text": prompt}]
    if photo_data_url:
        contenu.insert(0, {"type": "image_url", "image_url": {"url": photo_data_url}})
    r = chat([{"role": "user", "content": contenu}], 1500)
    brut = _json(r["texte"])
    if not brut:
        raise ValueError(f"réponse illisible du modèle : {r['texte'][:200]}")

    # ---- le CODE reprend la main sur tout ce qui est chiffré ou risqué
    alertes, hors = [], list(brut.get("hors_perimetre") or [])
    besoins, vus = [], set()
    for b in brut.get("besoins") or []:
        txt = f"{b.get('categorie', '')} {b.get('description', '')}".lower()
        if any(m in txt for m in HORS_PERIMETRE):
            hors.append(b.get("description") or b.get("categorie"))
            continue
        if b.get("famille") not in ("objet", "surface", "fourniture"):
            continue
        bid = re.sub(r"[^a-z0-9_]", "_", (b.get("id") or b.get("categorie") or "besoin").lower())[:30] or "besoin"
        while bid in vus:
            bid += "_2"
        vus.add(bid)
        b["id"] = bid
        b["quantite"] = max(1, int(_num(b.get("quantite")) or 1))
        # surface : on ne garde que la valeur saisie par l'utilisateur, sinon estimation signalée
        if b["famille"] == "surface":
            sol = any(m in txt for m in ("parquet", "carrelage", "sol", "moquette", "stratifié", "vinyle"))
            saisie = _num(surface_sol_m2) if sol else _num(surface_murs_m2)
            ecrite = _num(b.get("surface_m2"))
            if saisie:
                b["surface_m2"], b["surface_source"] = saisie, "formulaire"
            elif ecrite and re.search(rf"\b{ecrite:g}\b", texte.replace(",", ".")):
                b["surface_m2"], b["surface_source"] = ecrite, "texte de l'utilisateur"
            elif not sol and _num(surface_sol_m2):
                # murs ≈ périmètre d'une pièce carrée × 2,5 m de hauteur − 2 m² d'ouvertures
                a = _num(surface_sol_m2)
                b["surface_m2"] = round(4 * math.sqrt(a) * 2.5 - 2, 1)
                b["surface_source"] = "estimation (pièce carrée, 2,5 m sous plafond)"
                alertes.append(f"{b['categorie']} : surface des murs estimée à {b['surface_m2']} m² — à confirmer")
            else:
                b["surface_m2"], b["surface_source"] = None, None
        else:
            b["surface_m2"] = None
        besoins.append(Besoin.model_validate({k: v for k, v in b.items() if k in Besoin.model_fields}))
    if len(besoins) > MAX_BESOINS:
        alertes.append(f"{len(besoins)} besoins demandés : Marcel traite les {MAX_BESOINS} premiers")
        besoins = besoins[:MAX_BESOINS]
    if not besoins:
        alertes.append("aucun besoin d'achat compris : reformulez la demande")

    projet = Projet(
        nom=brut.get("nom") or "Projet", piece=brut.get("piece") or "pièce", code_postal=str(code_postal),
        budget_eur=_num(budget_eur), niveau=niveau if niveau in ("débutant", "intermédiaire", "confirmé") else "débutant",
        emplacement=Emplacement(largeur_mm=_cm(largeur_cm), profondeur_mm=_cm(profondeur_cm), hauteur_mm=_cm(hauteur_cm)),
        besoins=besoins, hors_perimetre=[h for h in hors if h], photo=brut.get("photo"), alertes=alertes)
    from .verif import normaliser
    projet = normaliser(projet)
    return {"projet": projet.model_dump(), "questions": brut.get("questions") or [],
            "modele": MODELE, "duree_s": r["duree_s"]}


# ---------------------------------------------------------------- guide
PROMPT_GUIDE = """Tu es Marcel, assistant de rénovation pour bricoleurs de niveau {niveau}. Rédige en français un guide de travaux
clair et concret, à partir UNIQUEMENT des données vérifiées ci-dessous (n'invente aucun produit, prix, quantité ni date).

Structure :
1. Résumé en 2 phrases (ce qu'on fait, total des achats comparé au budget, date de fin).
2. Liste d'achats (produit, enseigne, quantité, prix) — reprends exactement les données.
3. Outils nécessaires non inclus dans la liste (« à prévoir si vous ne l'avez pas »).
4. Planning jour par jour en suivant l'ordre des travaux fourni, avec les étapes concrètes pour un {niveau}.
5. 3 conseils de sécurité.
N'ajoute aucune surface, pièce, produit ou tâche qui n'est pas dans les données.

DONNÉES VÉRIFIÉES :
{donnees}"""


def guide(resultat: dict) -> dict:
    p = resultat["projet"]
    donnees = {
        "piece": p["piece"], "emplacement_mm": p["emplacement"], "photo": p.get("photo"),
        "besoins": [{k: b.get(k) for k in ("id", "categorie", "description", "surface_m2", "couches", "couleur")}
                    for b in p["besoins"]],
        "achats": [{k: a.get(k) for k in ("besoin_id", "nom", "enseigne", "quantite", "prix_eur", "cout_eur", "dispo_mode")}
                   for a in resultat["achats"]],
        "total_achats_eur": resultat["total_eur"], "budget_max_eur": resultat["budget_eur"],
        "ordre_travaux": resultat["taches"], "fin_travaux": resultat["fin_travaux"],
    }
    r = chat([{"role": "user", "content": PROMPT_GUIDE.format(
        niveau=p["niveau"], donnees=json.dumps(donnees, ensure_ascii=False, default=str))}], 3000)
    if not r["texte"]:
        raise ValueError("guide vide")
    return {"guide_md": r["texte"], "modele": MODELE, "duree_s": r["duree_s"]}
