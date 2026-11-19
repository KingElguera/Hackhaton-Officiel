"""Dictée : l'artisan décrit son chantier à voix haute, Marcel remplit la fiche et dit ce qu'il manque.

Deux étapes : un modèle transcrit la voix en texte, puis le modèle de texte range ce qui a été DIT dans les
champs de la fiche. Rien n'est inventé : un champ non dicté reste vide et apparaît dans « manquants ».
Rien n'est enregistré : le site pré-remplit, l'artisan relit et valide.
"""
import base64
import os
import re
import time
from typing import Optional

from . import hf

MODELE_VOIX = os.environ.get("HF_MODELE_VOIX", "openai/whisper-large-v3")
POSTES = ("murs", "plafond", "sol", "plinthes", "eclairage")
ETATS = ("bon", "a_reprendre", "abime")
MAX_OCTETS = 4_000_000   # ≈ 2 min de voix ; Vercel refuse les envois plus lourds

PROMPT = """Un artisan rénovateur vient de dicter les informations d'un chantier. Voici la transcription :
« {texte} »

Range UNIQUEMENT ce qui est dit dans cet objet JSON. Ce qui n'est pas dit vaut null (ou liste vide). N'invente rien.
Les dimensions sont en mètres (« quatre mètres vingt » = 4.2, « 420 » = 4.2, « 2 mètres 50 » = 2.5).
{{
  "nom": "nom du client ou du chantier, ou null",
  "piece": "chambre | salon | cuisine | salle de bain | couloir | bureau | autre, ou null",
  "code_postal": "5 chiffres, ou null",
  "longueur_m": nombre ou null,
  "largeur_m": nombre ou null,
  "hauteur_m": nombre ou null,
  "nb_portes": "portes qui EXISTENT déjà dans la pièce : entier ou null",
  "nb_fenetres": "fenêtres qui EXISTENT déjà : entier ou null",
  "nb_portes_a_creer": "portes à CRÉER (percer, ajouter) : entier ou null",
  "nb_fenetres_a_creer": "fenêtres à CRÉER : entier ou null",
  "teinte_murs": "la ou les couleurs des murs, mot pour mot (ex. « gris clair, mur du fond bleu canard »), ou null",
  "teinte_sol": "la couleur ou l'essence du sol (ex. « chêne clair »), ou null",
  "etat_murs": "bon | a_reprendre | abime, ou null",
  "postes": [{{"poste": "murs | plafond | sol | plinthes | eclairage", "gamme_ou_produit": "gamme (entrée / milieu / haut de gamme), marque ou type de produit (ex. « parquet stratifié »), JAMAIS une couleur ; ou null"}}],
  "budget_client_eur": nombre ou null,
  "date_debut_souhaitee": "AAAA-MM-JJ si une date précise est dite, sinon null",
  "notes": "tout le reste d'utile pour le chantier, en une ou deux phrases, ou null"
}}"""

QUESTIONS = {"piece": "Quelle pièce ?", "longueur_m": "Quelle longueur ?", "largeur_m": "Quelle largeur ?",
             "hauteur_m": "Quelle hauteur sous plafond ?", "nb_portes": "Combien de portes ?",
             "nb_fenetres": "Combien de fenêtres ?", "postes": "Quels travaux : murs, plafond, sol, plinthes ?",
             "code_postal": "Quel code postal ?"}


def transcrire(audio: bytes) -> dict:
    """Voix → texte. Accepte ce que le navigateur enregistre (webm, mp4/m4a, wav, mp3)."""
    from huggingface_hub import InferenceClient
    if len(audio) > MAX_OCTETS:
        raise ValueError("enregistrement trop long : 2 minutes maximum")
    t0 = time.monotonic()
    r = InferenceClient(bill_to=os.environ.get("HF_BILL_TO") or None).automatic_speech_recognition(audio, model=MODELE_VOIX)
    texte = re.sub(r"\s+", " ", (r.text or "")).strip()
    if len(texte) < 3:
        raise ValueError("rien n'a été entendu : réessaie plus près du micro")
    return {"texte": texte, "duree_s": round(time.monotonic() - t0, 1), "modele": MODELE_VOIX}


def _nombre(v, mini, maxi, entier=False):
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not entier and x > maxi and mini <= x / 100 <= maxi:   # « 420 » dicté en centimètres
        x /= 100
    if not mini <= x <= maxi:
        return None
    return int(x) if entier else round(x, 2)


def controler(lu: dict) -> dict:
    """Nettoie ce que le modèle a rangé : bornes, valeurs autorisées, champs manquants. Aucun appel réseau."""
    alertes = []
    f = {"nom": (lu.get("nom") or None), "piece": (str(lu["piece"]).lower() if lu.get("piece") else None),
         "longueur_m": _nombre(lu.get("longueur_m"), 1, 15), "largeur_m": _nombre(lu.get("largeur_m"), 1, 15),
         "hauteur_m": _nombre(lu.get("hauteur_m"), 2, 4),
         "nb_portes": _nombre(lu.get("nb_portes"), 0, 6, True), "nb_fenetres": _nombre(lu.get("nb_fenetres"), 0, 8, True),
         "nb_portes_a_creer": _nombre(lu.get("nb_portes_a_creer"), 1, 6, True),
         "nb_fenetres_a_creer": _nombre(lu.get("nb_fenetres_a_creer"), 1, 6, True),
         "teinte_murs": (str(lu["teinte_murs"]).strip() if lu.get("teinte_murs") else None),
         "teinte_sol": (str(lu["teinte_sol"]).strip() if lu.get("teinte_sol") else None),
         "etat_murs": lu.get("etat_murs") if lu.get("etat_murs") in ETATS else None,
         "budget_client_eur": _nombre(lu.get("budget_client_eur"), 50, 500000),
         "notes": lu.get("notes") or None}
    cp = re.sub(r"\D", "", str(lu.get("code_postal") or ""))
    f["code_postal"] = cp if len(cp) == 5 else None
    d = str(lu.get("date_debut_souhaitee") or "")
    f["date_debut_souhaitee"] = d if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else None
    for nom, brut in (("longueur", "longueur_m"), ("largeur", "largeur_m"), ("hauteur", "hauteur_m")):
        if lu.get(brut) is not None and f[brut] is None:
            alertes.append(f"{nom} dictée « {lu[brut]} » : valeur inhabituelle, à saisir à la main")
    if f["longueur_m"] and f["largeur_m"] and f["largeur_m"] > f["longueur_m"]:
        f["longueur_m"], f["largeur_m"] = f["largeur_m"], f["longueur_m"]
    vus, postes = set(), []
    for p in lu.get("postes") or []:
        nom = str((p or {}).get("poste") or "").lower()
        if nom in POSTES and nom not in vus:
            vus.add(nom)
            postes.append({"poste": nom, "gamme_ou_produit": (p.get("gamme_ou_produit") or None)})
    f["postes"] = postes
    manquants = [{"champ": c, "question": q} for c, q in QUESTIONS.items() if f.get(c) in (None, [], "")]
    return {"fiche": {k: v for k, v in f.items() if v not in (None, [], "")}, "manquants": manquants,
            "alertes": alertes, "a_confirmer": True}


def structurer(texte: str) -> dict:
    """Texte dicté → champs de la fiche + ce qu'il reste à demander."""
    r = hf.chat([{"role": "user", "content": PROMPT.format(texte=texte.strip()[:4000])}], 700)
    lu = hf._json(r["texte"])
    if not isinstance(lu, dict):
        raise ValueError("la dictée n'a pas pu être comprise : reformule en donnant la pièce et ses dimensions")
    return {**controler(lu), "duree_s": r["duree_s"]}


def dicter(audio_data_url: Optional[str] = None, texte: Optional[str] = None) -> dict:
    """Enregistrement (data URL audio) ou texte déjà transcrit → fiche pré-remplie à faire confirmer."""
    voix = None
    if audio_data_url:
        if "," not in audio_data_url or not audio_data_url.startswith("data:"):
            raise ValueError("l'enregistrement doit être une data URL audio")
        voix = transcrire(base64.b64decode(audio_data_url.split(",", 1)[1]))
        texte = voix["texte"]
    if not texte or len(texte.strip()) < 3:
        raise ValueError("rien à comprendre : envoie un enregistrement ou un texte")
    r = structurer(texte)
    return {"texte": texte.strip(), **r, "duree_s": round(r["duree_s"] + (voix["duree_s"] if voix else 0), 1),
            "modeles": {"voix": voix["modele"] if voix else None, "texte": hf.MODELE}}
