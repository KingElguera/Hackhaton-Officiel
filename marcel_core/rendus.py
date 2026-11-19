"""Rendus 3D : de la demande du site aux images de la pièce.

Le chemin complet :
  site ──POST /api/rendu──► table Supabase « rendus » (a_faire)
                               │
  atelier.py (poste avec Blender) prend la ligne ──► TRELLIS pour chaque photo de meuble ──► Blender
                               │
  images déposées dans le stockage ──► ligne « fait » ──► le site affiche (GET /api/rendu)

Ce fichier contient :
- le format de la demande (`DemandeRendu`), en centimètres, tel que le site l'envoie ;
- l'accès à Supabase (file d'attente et stockage), avec la clé de service ;
- la préparation du fichier de chantier lu par Blender, et le lancement de Blender.

Variables d'environnement (jamais dans le dépôt) : SUPABASE_URL, SUPABASE_SERVICE_KEY.
Pour l'atelier seulement : HF_TOKEN (TRELLIS), BLENDER (chemin du programme, facultatif), N8N_WEBHOOK_RENDU (facultatif).
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import re
import unicodedata
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

RACINE = Path(__file__).resolve().parent.parent
SCRIPT_BLENDER = RACINE / "rendu" / "marcel_rendu.py"
Mur = Literal["fond", "avant", "gauche", "droit"]

# Quelques noms de teintes courants. Le site peut aussi envoyer directement un code « #RRGGBB ».
TEINTES = {"blanc": "#F4F1EA", "blanc cassé": "#EFE9DD", "beige": "#E6D8C3", "lin": "#DDD2C0", "gris clair": "#D9D9D6",
           "gris": "#BDBDBD", "gris anthracite": "#4A4D52", "noir": "#2B2B2B", "vert sauge": "#A9B8A2", "vert": "#8FAE8B",
           "vert foncé": "#3F5B4C", "bleu": "#8DB8E0", "bleu nuit": "#27344F", "bleu canard": "#2F6F7E", "terracotta": "#C9764F",
           "jaune": "#E8C76A", "ocre": "#C99A4B", "rose": "#E8B7B0", "rose poudré": "#E5C6C0", "taupe": "#A89B8C",
           "rouge": "#B23A32", "rouge brique": "#9E4A35", "bordeaux": "#6E2433", "orange": "#E08A3C", "corail": "#E57F6B",
           "violet": "#7B5E8C", "lilas": "#B9A6CB", "marron": "#6B4A35", "chocolat": "#4E3428", "kaki": "#7D7A4E",
           "moutarde": "#C9A13B", "crème": "#F1E7D2", "sable": "#D9C6A5", "bleu ciel": "#B7D3E8", "bleu marine": "#22304A",
           "bleu pétrole": "#24505A", "turquoise": "#4FA9A6", "vert olive": "#7A7C45", "vert émeraude": "#2E7D5B",
           "vert d'eau": "#B9D8C9", "gris perle": "#CFCFCB", "anthracite": "#4A4D52"}


def _assombrir(hx: str, k: float = 0.85) -> str:
    c = [int(hx.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(v * k):02X}" for v in c)


# ---------------------------------------------------------------- la demande envoyée par le site
class PieceRendu(BaseModel):
    largeur_cm: float = Field(..., gt=50, lt=3000, description="largeur de la pièce (mur du fond)")
    profondeur_cm: float = Field(..., gt=50, lt=3000, description="profondeur de la pièce")
    hauteur_cm: float = Field(250, gt=150, lt=600)


class OuvertureRendu(BaseModel):
    type: Literal["fenetre", "porte"]
    mur: Mur
    position_cm: float = Field(..., ge=0, description="du coin gauche du mur au bord gauche, vu de l'intérieur")
    largeur_cm: float = Field(..., gt=0)
    hauteur_cm: float = Field(..., gt=0)
    allege_cm: Optional[float] = Field(None, description="fenêtre : hauteur du bas de la fenêtre (90 par défaut)")


class SolRendu(BaseModel):
    image: Optional[str] = Field(None, description="photo du revêtement : lien, ou data URL")
    taille_cm: float = Field(200, gt=0, description="taille réelle couverte par la photo")
    teintes: Optional[List[str]] = Field(None, description="sans photo : deux couleurs de lames, en #RRGGBB")


class MeubleRendu(BaseModel):
    nom: Optional[str] = None
    photo: Optional[str] = Field(None, description="photo du meuble (lien ou data URL) : il sera modélisé par TRELLIS")
    largeur_cm: float = Field(..., gt=0, description="largeur réelle, obligatoire")
    profondeur_cm: Optional[float] = None
    hauteur_cm: Optional[float] = None
    mur: Mur = "fond"
    position_cm: Optional[float] = Field(None, description="vide = centré sur le mur")
    pose_cm: float = Field(0, description="hauteur de pose (élément mural)")
    couleur: Optional[str] = Field(None, description="volume simple : couleur en #RRGGBB")


class DemandeRendu(BaseModel):
    projet_id: Optional[str] = None
    piece: PieceRendu
    peinture: str = Field("blanc", description="nom de teinte courant, code #RRGGBB, ou phrase (« blanc cassé sur 3 murs, vert sauge sur le mur gauche »)")
    murs: Dict[Mur, str] = Field(default_factory=dict, description="teinte propre à un mur (mur d'accent), ex. {'gauche': 'vert sauge'}")
    sol: SolRendu = Field(default_factory=SolRendu)
    ouvertures: List[OuvertureRendu] = Field(default_factory=list)
    meubles: List[MeubleRendu] = Field(default_factory=list, max_length=6)
    vues: List[Literal["photo1", "photo2", "dessus", "panorama", "maquette"]] = Field(
        default_factory=lambda: ["photo1", "photo2", "dessus", "maquette"])
    qualite: Literal["rapide", "finale"] = "rapide"


def verifier(d: DemandeRendu) -> List[str]:
    """Contrôles que le format seul ne fait pas : une ouverture ou un meuble doit tenir sur son mur."""
    pb = []
    longueur = {"fond": d.piece.largeur_cm, "avant": d.piece.largeur_cm, "gauche": d.piece.profondeur_cm, "droit": d.piece.profondeur_cm}
    for o in d.ouvertures:
        if o.position_cm + o.largeur_cm > longueur[o.mur] + 0.1:
            pb.append(f"{o.type} sur le mur {o.mur} : dépasse du mur ({o.position_cm:g} + {o.largeur_cm:g} cm pour {longueur[o.mur]:g} cm)")
        if (o.allege_cm or 0) + o.hauteur_cm > d.piece.hauteur_cm + 0.1:
            pb.append(f"{o.type} sur le mur {o.mur} : plus haute que la pièce")
    for m in d.meubles:
        if m.largeur_cm > longueur[m.mur] + 0.1:
            pb.append(f"meuble « {m.nom or 'sans nom'} » : plus large que le mur {m.mur}")
        elif m.position_cm is not None and m.position_cm + m.largeur_cm > longueur[m.mur] + 0.1:
            pb.append(f"meuble « {m.nom or 'sans nom'} » : dépasse du mur {m.mur}")
        if not m.photo and not (m.profondeur_cm and m.hauteur_cm):
            pb.append(f"meuble « {m.nom or 'sans nom'} » : sans photo, il faut la profondeur et la hauteur")
    return pb


# ---------------------------------------------------------------- Supabase (file d'attente + stockage)
class SupabaseAbsent(RuntimeError):
    pass


def _config():
    url, cle = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not cle:
        raise SupabaseAbsent("SUPABASE_URL et SUPABASE_SERVICE_KEY ne sont pas configurées")
    return url.rstrip("/"), cle


def _appel(methode: str, chemin: str, corps=None, params: Optional[dict] = None, entetes: Optional[dict] = None, brut: bool = False):
    url, cle = _config()
    adresse = url + chemin + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"apikey": cle}
    if cle.startswith("eyJ"):  # ancienne clé JWT : aussi en Authorization ; les clés sb_secret_ passent par apikey (comme base.py)
        h["Authorization"] = "Bearer " + cle
    donnees = None
    if corps is not None:
        if brut:
            donnees = corps
        else:
            donnees, h["Content-Type"] = json.dumps(corps).encode(), "application/json"
    h.update(entetes or {})
    req = urllib.request.Request(adresse, data=donnees, method=methode, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            texte = r.read().decode() or "null"
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {methode} {chemin} : {e.code} {e.read().decode()[:300]}") from e
    try:
        return json.loads(texte)
    except json.JSONDecodeError:
        return texte


def creer(demande: DemandeRendu) -> dict:
    """Ajoute une demande à la file. Appelé par l'API."""
    ligne = {"demande": demande.model_dump(), "etat": "a_faire"}
    if demande.projet_id:
        ligne["projet_id"] = demande.projet_id
    r = _appel("POST", "/rest/v1/rendus", ligne, entetes={"Prefer": "return=representation"})
    return r[0]


def lire(rendu_id: str) -> Optional[dict]:
    r = _appel("GET", "/rest/v1/rendus", params={"id": "eq." + rendu_id, "select": "id,etat,resultat,erreur,created_at,pris_le,termine_le"})
    return r[0] if r else None


def prendre() -> Optional[dict]:
    """Prend la plus ancienne demande à faire. Si deux ateliers tournent, un seul l'obtient."""
    a_faire = _appel("GET", "/rest/v1/rendus", params={"etat": "eq.a_faire", "order": "created_at.asc", "limit": "1", "select": "id,tentatives"})
    if not a_faire:
        return None
    r = _appel("PATCH", "/rest/v1/rendus", {"etat": "en_cours", "pris_le": _maintenant(), "tentatives": a_faire[0]["tentatives"] + 1},
               params={"id": "eq." + a_faire[0]["id"], "etat": "eq.a_faire"}, entetes={"Prefer": "return=representation"})
    return r[0] if r else None


def terminer(rendu_id: str, resultat: dict):
    _appel("PATCH", "/rest/v1/rendus", {"etat": "fait", "resultat": resultat, "erreur": None, "termine_le": _maintenant()}, params={"id": "eq." + rendu_id})


def echouer(rendu_id: str, erreur: str):
    _appel("PATCH", "/rest/v1/rendus", {"etat": "echec", "erreur": erreur[:1000], "termine_le": _maintenant()}, params={"id": "eq." + rendu_id})


def deposer(fichier: Path, chemin: str, seau: str = "rendus") -> str:
    """Dépose un fichier dans le stockage et renvoie son adresse publique."""
    types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".glb": "model/gltf-binary"}
    _appel("POST", f"/storage/v1/object/{seau}/{urllib.parse.quote(chemin)}", fichier.read_bytes(), brut=True,
           entetes={"Content-Type": types.get(fichier.suffix.lower(), "application/octet-stream"), "x-upsert": "true"})
    return f"{_config()[0]}/storage/v1/object/public/{seau}/{urllib.parse.quote(chemin)}"


# ---------------------------------------------------------------- du parcours artisan au rendu
SOLS = [(("chêne clair", "chene clair", "clair", "blanchi", "hêtre", "bouleau", "érable"), ["#C9A77A", "#B8935F"]),
        (("chêne foncé", "chene fonce", "noyer", "wengé", "foncé", "fonce"), ["#7A5637", "#5E4129"]),
        (("gris", "béton", "beton", "anthracite"), ["#B9B6B0", "#A29F99"]),
        (("blanc",), ["#E6E1D8", "#D8D2C7"]),
        (("chêne", "chene", "naturel", "miel"), ["#B98A5A", "#A47747"])]
PORTE_CM, FENETRE_CM, ALLEGE_CM = (83, 204), (120, 135), 90   # tailles standard, les mêmes que marcel_core/chantier.py


def depuis_fiche(fiche: dict, choix: Optional[dict] = None, projet_id: Optional[str] = None):
    """Fabrique la demande de rendu à partir de la fiche du chantier et des choix. Renvoie (demande, alertes).

    La fiche donne les dimensions et le NOMBRE de portes et de fenêtres, pas leur position :
    elles sont placées à des endroits plausibles, et une alerte le dit.
    """
    choix, alertes = choix or {}, []
    if not fiche.get("longueur_m") or not fiche.get("largeur_m"):
        raise ValueError("la fiche n'a pas les dimensions de la pièce : pas de rendu possible")
    L, l = float(fiche["longueur_m"]) * 100, float(fiche["largeur_m"]) * 100
    H = float(fiche.get("hauteur_m") or 0) * 100
    if not H:
        H = 250
        alertes.append("hauteur sous plafond absente de la fiche : 2,50 m par défaut")
    postes = {p.get("poste") for p in fiche.get("postes") or []}
    peinture = str(choix.get("teinte_murs") or "blanc") if ("murs" in postes or not postes) else "blanc"
    teinte_sol = str(choix.get("teinte_sol") or "").lower() + " " + str(choix.get("revetement_sol") or "").lower()
    teintes = next((t for mots, t in SOLS if any(m in teinte_sol for m in mots)), None)
    if teintes is None:  # une couleur franche (« bleu », « rouge »…) : on l'applique telle quelle aux lames
        connues = _teintes_dans(teinte_sol)
        if connues:
            hx = TEINTES[connues[0]]
            teintes = [hx, _assombrir(hx)]
        else:
            teintes = ["#B98A5A", "#8E6238"]
            if str(choix.get("teinte_sol") or "").strip():
                alertes.append(f"teinte de sol « {choix['teinte_sol']} » inconnue : parquet chêne par défaut")
    longueur = {"fond": L, "avant": L, "gauche": l, "droit": l}
    ouvertures = []
    nb_portes = int(fiche.get("nb_portes") or 0) + int(fiche.get("nb_portes_a_creer") or 0)        # la pièce APRÈS travaux
    nb_fenetres = int(fiche.get("nb_fenetres") or 0) + int(fiche.get("nb_fenetres_a_creer") or 0)
    # Emplacements lus sur le plan coté (POST /api/plan, confirmés par l'artisan) : on les respecte pour les ouvertures existantes,
    # et seules les ouvertures à créer sont placées par Marcel.
    lues = [o for o in fiche.get("ouvertures") or [] if o.get("mur") in longueur and o.get("position_m") is not None]
    plan_ok = bool(lues) and len(lues) == len(fiche.get("ouvertures") or [])
    if plan_ok:
        for o in lues:
            porte = o.get("type") == "porte"
            larg = float(o.get("largeur_m") or 0) * 100 or (PORTE_CM[0] if porte else FENETRE_CM[0])
            haut = float(o.get("hauteur_m") or 0) * 100 or (PORTE_CM[1] if porte else FENETRE_CM[1])
            ligne = {"type": "porte" if porte else "fenetre", "mur": o["mur"], "position_cm": float(o["position_m"]) * 100,
                     "largeur_cm": larg, "hauteur_cm": min(haut, H - 10)}
            if not porte:
                ligne["allege_cm"] = float(o.get("allege_m") or 0) * 100 or ALLEGE_CM
            ouvertures.append(ligne)
        nb_portes = int(fiche.get("nb_portes_a_creer") or 0)
        nb_fenetres = int(fiche.get("nb_fenetres_a_creer") or 0)
        deja = len(ouvertures)

    def libre(mur, larg, x):
        return all(o["mur"] != mur or x + larg + 20 <= o["position_cm"] or x >= o["position_cm"] + o["largeur_cm"] + 20
                   for o in ouvertures)
    for i, mur in enumerate(["fond", "avant", "droit", "gauche"][:nb_portes] if plan_ok else ["fond", "avant", "droit"][:nb_portes]):
        if plan_ok:   # porte à créer : près du coin droit d'un mur, sinon au premier endroit libre
            x = next((x for x in range(int(longueur[mur] - PORTE_CM[0] - 30), 29, -10) if libre(mur, PORTE_CM[0], x)), None)
            if x is not None:
                ouvertures.append({"type": "porte", "mur": mur, "position_cm": float(x), "largeur_cm": PORTE_CM[0],
                                   "hauteur_cm": min(PORTE_CM[1], H - 10)})
            continue
        if longueur[mur] >= PORTE_CM[0] + 60:   # une porte près du coin droit du mur
            ouvertures.append({"type": "porte", "mur": mur, "position_cm": longueur[mur] - PORTE_CM[0] - 30,
                               "largeur_cm": PORTE_CM[0], "hauteur_cm": min(PORTE_CM[1], H - 10)})
    for i, mur in enumerate(["gauche", "droit", "fond", "avant"][:nb_fenetres]):
        if plan_ok:   # fenêtre à créer : au premier endroit libre du mur
            x = next((x for x in range(40, int(longueur[mur] - FENETRE_CM[0] - 39), 10) if libre(mur, FENETRE_CM[0], x)), None)
            if x is not None and H >= ALLEGE_CM + FENETRE_CM[1] + 10:
                ouvertures.append({"type": "fenetre", "mur": mur, "position_cm": float(x), "largeur_cm": FENETRE_CM[0],
                                   "hauteur_cm": FENETRE_CM[1], "allege_cm": ALLEGE_CM})
            continue
        libre = longueur[mur] - (PORTE_CM[0] + 60 if any(o["mur"] == mur for o in ouvertures) else 0)
        if libre >= FENETRE_CM[0] + 40 and H >= ALLEGE_CM + FENETRE_CM[1] + 10:   # une fenêtre centrée sur la partie libre du mur
            ouvertures.append({"type": "fenetre", "mur": mur, "position_cm": round((libre - FENETRE_CM[0]) / 2),
                               "largeur_cm": FENETRE_CM[0], "hauteur_cm": FENETRE_CM[1], "allege_cm": ALLEGE_CM})
    demandees = nb_portes + nb_fenetres + (deja if plan_ok else 0)
    if plan_ok and (nb_portes or nb_fenetres):
        alertes.append("portes et fenêtres existantes placées d'après le plan ; celles à créer, placées par Marcel")
    elif demandees and not plan_ok:
        alertes.append("emplacement des portes et des fenêtres estimé : la fiche donne leur nombre, pas leur position")
    if len(ouvertures) < demandees:
        alertes.append(f"{demandees - len(ouvertures)} ouverture(s) non affichée(s) : pas assez de place sur les murs")
    meubles = placer_meubles(fiche.get("meubles") or [], longueur, ouvertures, alertes)
    d = DemandeRendu(projet_id=projet_id, piece={"largeur_cm": L, "profondeur_cm": l, "hauteur_cm": H}, peinture=peinture,
                     sol={"teintes": teintes}, ouvertures=ouvertures, meubles=meubles)
    return d, alertes


def placer_meubles(liste: list, longueur: dict, ouvertures: list, alertes: list) -> List[MeubleRendu]:
    """Range les meubles de la fiche contre les murs, sans boucher une porte ni une fenêtre et sans se chevaucher.

    Chaque meuble : {photo, nom, largeur_cm (obligatoire), profondeur_cm, hauteur_cm, mur (facultatif)}.
    Sans mur imposé, Marcel choisit le mur qui a le plus de place libre.
    """
    marge = 10
    # (début, fin, hauteur libre en dessous) : sous une fenêtre, un meuble bas passe (lit, commode basse)
    occupe = {m: [(o["position_cm"] - marge, o["position_cm"] + o["largeur_cm"] + marge, (o.get("allege_cm") or 0) - 5)
                  for o in ouvertures if o["mur"] == m] for m in longueur}

    def place_libre(mur, larg, haut=None):
        """Premier espace libre assez large ; le meuble y est centré."""
        genes = [(a, b) for a, b, dessous in occupe[mur] if not (haut and haut <= dessous)]
        x = marge
        for a, b in sorted(genes) + [(longueur[mur] - marge, longueur[mur])]:
            if a - x >= larg:
                return x + (a - x - larg) / 2
            x = max(x, b)
        return None

    def libre_total(mur):
        return longueur[mur] - sum(b - a for a, b, _ in occupe[mur])

    out = []
    for i, m in enumerate(liste[:6]):
        nom = (m.get("nom") or f"meuble {i + 1}").strip()
        try:
            larg = float(m.get("largeur_cm") or 0)
        except (TypeError, ValueError):
            larg = 0
        if larg <= 0:
            alertes.append(f"{nom} : largeur non renseignée — meuble non affiché")
            continue
        if not m.get("photo") and not (m.get("profondeur_cm") and m.get("hauteur_cm")):
            alertes.append(f"{nom} : ni photo ni profondeur/hauteur — meuble non affiché")
            continue
        def nombre(k):
            try:
                return float(m[k]) if m.get(k) else None
            except (TypeError, ValueError):
                return None
        voulu = m.get("mur") if m.get("mur") in longueur else None
        murs = [voulu] if voulu else sorted(longueur, key=lambda w: (-libre_total(w), w))
        for mur in murs:
            x = place_libre(mur, larg, nombre("hauteur_cm"))
            if x is not None:
                break
        else:
            alertes.append(f"{nom} : pas assez de place libre sur {'le mur ' + voulu if voulu else 'les murs'} — non affiché")
            continue
        occupe[mur].append((x, x + larg, 0))
        out.append(MeubleRendu(nom=nom, photo=m.get("photo"), largeur_cm=larg, profondeur_cm=nombre("profondeur_cm"),
                               hauteur_cm=nombre("hauteur_cm"), mur=mur, position_cm=x))
    if out:
        alertes.append("meubles placés par Marcel le long des murs libres : leur emplacement est indicatif")
    return out


def deposer_photo(source: str, chemin: str) -> str:
    """Range une photo envoyée par le site (data URL) dans le stockage et renvoie son lien public. Un lien reste un lien."""
    if not source.startswith("data:"):
        return source
    entete, _, donnees = source.partition(",")
    ext, typ = (".png", "image/png") if "png" in entete else (".jpg", "image/jpeg")
    _appel("POST", f"/storage/v1/object/rendus/{urllib.parse.quote(chemin + ext)}", base64.b64decode(donnees), brut=True,
           entetes={"Content-Type": typ, "x-upsert": "true"})
    return f"{_config()[0]}/storage/v1/object/public/rendus/{urllib.parse.quote(chemin + ext)}"


def demander_pour_projet(projet: dict, choix: Optional[dict] = None):
    """Met en file le rendu d'un chantier (ligne de la table projets). Renvoie (ligne de la file, alertes)."""
    if choix is None:  # sans les choix calculés, on reprend ceux que Marcel a notés
        choix = {c["id"]: c["valeur"] for c in projet.get("choix_delegues") or [] if c.get("id")}
        for r in projet.get("reponses") or []:
            if r.get("reponse") and not r.get("delegue"):
                choix[r["question_id"]] = str(r["reponse"])
    demande, alertes = depuis_fiche(projet.get("fiche") or {}, choix, projet.get("id"))
    problemes = verifier(demande)
    if problemes:
        raise ValueError("rendu impossible : " + " ; ".join(problemes))
    return creer(demande), alertes


def noter_visuel(projet_id: str, rendu_id: str, etat: str, images: Optional[list] = None, alertes: Optional[list] = None):
    """Range les images dans le résultat du chantier : le site les trouve dans resultat.visuel, sans autre appel."""
    lignes = _appel("GET", "/rest/v1/projets", params={"id": "eq." + projet_id, "select": "resultat"})
    if not lignes:
        return
    resultat = lignes[0].get("resultat") or {}
    visuel = dict(resultat.get("visuel") or {})
    urls = {i["fichier"]: i.get("url") for i in images or []}
    visuel.update(rendu_id=rendu_id, etat=etat, images=images or [], apres_url=urls.get("photo1.png") or visuel.get("apres_url"),
                  panorama_url=urls.get("panorama_360.jpg"), dessus_url=urls.get("dessus.png"),
                  maquette_url=urls.get("maquette.glb"))
    if alertes is not None:  # celles de la préparation (meubles, ouvertures estimées) + celles du rendu, sans doublon
        visuel["alertes"] = list(dict.fromkeys((visuel.get("alertes_demande") or []) + list(alertes)))
    resultat["visuel"] = visuel
    _appel("PATCH", "/rest/v1/projets", {"resultat": resultat}, params={"id": "eq." + projet_id})


def _maintenant() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------- préparation du chantier pour Blender
def _fichier_depuis(source: str, dossier: Path, nom: str) -> Path:
    """Une image peut arriver en lien, en data URL ou en chemin local : on la range toujours dans un fichier."""
    dossier.mkdir(parents=True, exist_ok=True)
    if source.startswith("data:"):
        entete, _, donnees = source.partition(",")
        ext = ".png" if "png" in entete else ".jpg"
        dest = dossier / (nom + ext)
        dest.write_bytes(base64.b64decode(donnees))
        return dest
    if source.startswith(("http://", "https://")):
        ext = os.path.splitext(urllib.parse.urlparse(source).path)[1].lower()
        dest = dossier / (nom + (ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"))
        req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r, dest.open("wb") as f:
            shutil.copyfileobj(r, f)
        return dest
    p = Path(source) if os.path.isabs(source) else RACINE / source
    if not p.exists():
        raise FileNotFoundError(f"image introuvable : {source}")
    return p


def _sans_accents(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


# Les mots qui désignent un mur, vus depuis l'intérieur de la pièce (même repère que les ouvertures).
MOTS_MURS = [("gauche", "gauche"), ("droite", "droit"), ("droit", "droit"), ("fond", "fond"), ("entree", "avant"), ("avant", "avant")]
MOTS_ACCENT = ("tete de lit", "mur d'accent", "un mur", "un seul mur", "pan de mur", "1 mur", "1 seul mur", "un des murs")


def _teintes_dans(texte: str) -> List[str]:
    """Les teintes connues citées dans un texte, dans l'ordre (« vert sauge » passe avant « vert »)."""
    t, trouvees = _sans_accents(texte), []
    for nom in sorted(TEINTES, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(_sans_accents(nom)) + r"(?:e?s)?\b", t):
            if not any(a <= m.start() < b for _, a, b in trouvees):
                trouvees.append((nom, m.start(), m.end()))
    return [nom for nom, _, _ in sorted(trouvees, key=lambda x: x[1])]


def lire_peinture(texte: str):
    """Comprend une phrase de couleur : renvoie (teinte de base, {mur: teinte}, alertes).

    « Blanc cassé mat sur 3 murs, vert sauge mat sur le mur gauche (tête de lit) »
      → base « blanc cassé », {"gauche": "vert sauge"}.
    """
    texte, alertes = (texte or "").strip(), []
    if not texte or texte.startswith("#") or texte.lower() in TEINTES:
        return texte or "blanc", {}, alertes
    base, murs, derniere = None, {}, None
    for morceau in re.split(r"[,;/+]|\bet\b|\bavec\b", texte, flags=re.I):
        t = _sans_accents(morceau)
        if not t.strip():
            continue
        teintes = _teintes_dans(morceau) or ([derniere] if derniere else [])
        cibles = [mur for mot, mur in MOTS_MURS if re.search(r"\b" + mot + r"\b", t)]
        if not cibles and any(m in t for m in MOTS_ACCENT):
            cibles = ["fond"]
            alertes.append("mur d'accent sans côté précisé : Marcel l'a mis sur le mur du fond")
        if not teintes:
            continue
        derniere = teintes[-1]
        if cibles:
            for mur in dict.fromkeys(cibles):
                murs[mur] = teintes[-1]
        elif base is None:
            base = teintes[0]
    if base is None and not murs:
        alertes.append(f"teinte « {texte} » inconnue : murs rendus en blanc")
    return base or "blanc", murs, alertes


def _teinte(nom: str, alertes: list) -> str:
    n = (nom or "").strip()
    if n.startswith("#") and len(n) == 7:
        return n
    if n.lower() in TEINTES:
        return TEINTES[n.lower()]
    alertes.append(f"teinte « {nom} » inconnue : murs rendus en blanc")
    return TEINTES["blanc"]


def vers_chantier(d: DemandeRendu, dossier: Path, modele_3d: str = "trellis2") -> dict:
    """Transforme la demande du site en fichier de chantier pour Blender.

    C'est ici que TRELLIS est déclenché : chaque meuble accompagné d'une photo devient un objet 3D à l'échelle.
    Si la génération échoue (quota, Space en panne), le meuble est rendu en volume simple et une alerte le dit.
    """
    from . import objets3d
    alertes, meubles, generations = [], [], []
    chantier = {"largeur": d.piece.largeur_cm / 100, "profondeur": d.piece.profondeur_cm / 100, "hauteur": d.piece.hauteur_cm / 100,
                "plinthe": "#F4F1EA", "qualite": d.qualite, "vues": list(d.vues)}
    base, murs, a = lire_peinture(d.peinture)
    alertes += a
    chantier["peinture"] = _teinte(base, alertes)
    murs.update(d.murs)
    if murs:
        chantier["peinture_murs"] = {mur: _teinte(t, alertes) for mur, t in murs.items()}
    if d.sol.image:
        try:
            chantier["sol_image"] = str(_fichier_depuis(d.sol.image, dossier, "sol").resolve())
            chantier["sol_image_taille_m"] = d.sol.taille_cm / 100
        except Exception as e:
            alertes.append(f"photo du sol illisible ({type(e).__name__}) : sol rendu en lames génériques")
    if "sol_image" not in chantier:
        chantier["sol"] = d.sol.teintes or ["#B98A5A", "#8E6238"]
    chantier["ouvertures"] = [{"type": o.type, "mur": o.mur, "position": o.position_cm / 100, "largeur": o.largeur_cm / 100,
                               "hauteur": o.hauteur_cm / 100, **({"allege": o.allege_cm / 100} if o.allege_cm is not None else {})}
                              for o in d.ouvertures]
    for i, m in enumerate(d.meubles):
        nom = m.nom or f"meuble_{i + 1}"
        place = {"nom": nom, "mur": m.mur, **({"position": m.position_cm / 100} if m.position_cm is not None else {}),
                 **({"hauteur_pose_m": m.pose_cm / 100} if m.pose_cm else {})}
        fait = False
        if m.photo:
            t0 = time.monotonic()
            try:
                photo = _fichier_depuis(m.photo, dossier, "meuble_" + hashlib.sha256(m.photo.encode()).hexdigest()[:10])
                r = objets3d.objet_3d(str(photo), m.largeur_cm * 10, (m.profondeur_cm or 0) * 10 or None,
                                      (m.hauteur_cm or 0) * 10 or None, modele=modele_3d)
                meubles.append({**place, "modele": r["fichier"], "largeur_m": m.largeur_cm / 100})
                generations.append({"nom": nom, "modele": r["nom_modele"], "depuis_cache": r["depuis_cache"],
                                    "duree_generation_s": r["duree_generation_s"], "dimensions_mm": r["dimensions_mm"],
                                    "ecart_proportions_pct": r["ecart_proportions_pct"], "fichier": r["fichier"]})
                alertes += [f"{nom} : {a}" for a in r["alertes"]]
                fait = True
            except Exception as e:
                generations.append({"nom": nom, "echec": f"{type(e).__name__}: {e}"[:300], "duree_s": round(time.monotonic() - t0, 1)})
                alertes.append(f"{nom} : objet 3D impossible ({type(e).__name__}) — affiché en volume simple")
        if not fait:
            if m.profondeur_cm and m.hauteur_cm:
                meubles.append({**place, "taille": [m.largeur_cm / 100, m.profondeur_cm / 100, m.hauteur_cm / 100],
                                **({"couleur": m.couleur} if m.couleur else {})})
            else:
                alertes.append(f"{nom} : ni objet 3D ni dimensions complètes — non affiché")
    chantier["meubles"] = meubles
    return {"chantier": chantier, "alertes": alertes, "meubles_3d": generations}


# ---------------------------------------------------------------- Blender
def blender() -> str:
    candidats = [os.environ.get("BLENDER"), shutil.which("blender"), "/Applications/Blender.app/Contents/MacOS/Blender"]
    for c in candidats:
        if c and os.path.exists(c):
            return c
    raise FileNotFoundError("Blender introuvable : l'installer, ou donner son chemin dans la variable BLENDER")


def lancer_blender(chantier: dict, dossier: Path, delai_s: int = 1200) -> dict:
    """Écrit le fichier de chantier, lance Blender sans interface et lit la ligne RESULTAT."""
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "chantier.json"
    fichier.write_text(json.dumps(chantier, ensure_ascii=False, indent=1), encoding="utf-8")
    p = subprocess.run([blender(), "--background", "--python", str(SCRIPT_BLENDER), "--", str(fichier), str(dossier)],
                       capture_output=True, text=True, timeout=delai_s)
    for ligne in reversed(p.stdout.splitlines()):
        if ligne.startswith("RESULTAT "):
            return json.loads(ligne[len("RESULTAT "):])
    fin = "\n".join((p.stdout + "\n" + p.stderr).strip().splitlines()[-8:])
    raise RuntimeError(f"Blender n'a pas rendu d'image (code {p.returncode}) :\n{fin}")


def traiter(d: DemandeRendu, dossier: Path, modele_3d: str = "trellis2") -> dict:
    """La chaîne complète, sur le poste : demande → meubles 3D → Blender → images. Ne touche pas à Supabase."""
    t0 = time.monotonic()
    problemes = verifier(d)
    if problemes:
        raise ValueError("demande incohérente : " + " ; ".join(problemes))
    prep = vers_chantier(d, dossier, modele_3d)
    rendu = lancer_blender(prep["chantier"], dossier)
    return {"images": rendu["images"], "meubles_poses": rendu.get("meubles", []), "meubles_3d": prep["meubles_3d"],
            "alertes": prep["alertes"], "blender_secondes": rendu.get("total_secondes"),
            "total_secondes": round(time.monotonic() - t0, 1), "dossier": str(dossier)}
