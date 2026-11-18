"""Marcel — API pour le front (Vercel, fonctions Python).

Sans état : le front garde le `projet` et les `sessions` et les renvoie à chaque appel.

  GET  /api/sante                       → le back répond-il, les clés sont-elles configurées ?
  POST /api/comprendre                  → photo + texte + mesures → projet structuré (à faire valider)
  POST /api/parcours                    → lance un agent H par enseigne → sessions + liens live
  GET  /api/statut?ids=<id1>,<id2>      → avancement des agents (appeler toutes les 30 s max)
  POST /api/resultat                    → vérification, choix, planning, budget (+ guide)
"""
import os
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Les clés collées dans Vercel peuvent garder un retour à la ligne invisible : on les nettoie une fois pour toutes.
for _cle in ("HAI_API_KEY", "HF_TOKEN", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "HF_BILL_TO", "HF_MODELE"):
    if os.environ.get(_cle) is not None:
        os.environ[_cle] = os.environ[_cle].strip()

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from marcel_core import Projet  # noqa: E402
from marcel_core import agents  # noqa: E402
from marcel_core.verif import normaliser, synthese  # noqa: E402

app = FastAPI(title="Marcel API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("FRONT_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


class DemandeComprendre(BaseModel):
    texte: str = Field(..., min_length=3, description="ce que l'utilisateur veut faire")
    code_postal: str
    photo: Optional[str] = Field(None, description="data URL JPEG (data:image/jpeg;base64,...) ≤ 1600 px")
    budget_eur: Optional[float] = None
    largeur_cm: Optional[float] = None
    profondeur_cm: Optional[float] = None
    hauteur_cm: Optional[float] = None
    surface_murs_m2: Optional[float] = None
    surface_sol_m2: Optional[float] = None
    niveau: str = "débutant"


class SessionRef(BaseModel):
    enseigne: str
    session_id: str
    live_url: Optional[str] = None
    lance_le: Optional[str] = None


class DemandeParcours(BaseModel):
    projet: Projet
    enseignes: Optional[List[str]] = None


class DemandeResultat(BaseModel):
    projet: Projet
    sessions: List[SessionRef]
    guide: bool = True


def _erreur(e: Exception, quoi: str):
    msg = f"{type(e).__name__}: {e}"[:400]
    code = 429 if "429" in msg or "rate" in msg.lower() else 502
    raise HTTPException(status_code=code, detail=f"{quoi} : {msg}")


@app.get("/api/sante")
def sante():
    from marcel_core import base as _base
    supa = "absente"
    if _base.actif():
        try:
            _base.lire("fournisseurs")
            supa = "ok"
        except Exception as e:
            supa = f"erreur : {type(e).__name__}"[:80]
    return {"ok": True, "h_company": bool(os.environ.get("HAI_API_KEY")), "hugging_face": bool(os.environ.get("HF_TOKEN")),
            "supabase": supa}


@app.post("/api/comprendre")
def api_comprendre(d: DemandeComprendre):
    from marcel_core.hf import comprendre
    try:
        return comprendre(d.texte, d.code_postal, d.photo, d.budget_eur, d.largeur_cm, d.profondeur_cm,
                          d.hauteur_cm, d.surface_murs_m2, d.surface_sol_m2, d.niveau)
    except Exception as e:
        _erreur(e, "compréhension (Hugging Face)")


@app.post("/api/parcours")
def api_parcours(d: DemandeParcours):
    projet = normaliser(d.projet)  # le code recalcule toujours les contraintes chiffrées
    if not projet.besoins:
        raise HTTPException(400, "aucun besoin à chercher")
    enseignes = d.enseignes or list(projet.enseignes)
    inconnues = [e for e in enseignes if e not in projet.enseignes]
    if inconnues:
        raise HTTPException(400, f"enseigne(s) inconnue(s) : {inconnues}")
    sessions = []
    for e in enseignes:
        try:
            sessions.append(agents.demarrer(projet, e))
        except Exception as ex:
            sessions.append({"enseigne": e, "erreur": f"{type(ex).__name__}: {ex}"[:300]})
    return {"projet": projet.model_dump(), "sessions": sessions}


@app.get("/api/statut")
def api_statut(ids: str = Query(..., description="session_id séparés par des virgules")):
    out = []
    for sid in [i for i in ids.split(",") if i]:
        try:
            out.append(agents.statut(sid))
        except Exception as e:
            out.append({"session_id": sid, "statut": "inconnu", "termine": False, "erreur": f"{type(e).__name__}: {e}"[:200]})
    return {"sessions": out, "tous_termines": all(s.get("termine") for s in out)}


@app.post("/api/resultat")
def api_resultat(d: DemandeResultat):
    projet = normaliser(d.projet)
    sessions = []
    for s in d.sessions:
        try:
            sessions.append(agents.recuperer(s.enseigne, s.session_id, s.lance_le))
        except Exception as e:
            sessions.append({"enseigne": s.enseigne, "session_id": s.session_id, "statut": "exception",
                             "erreur": f"{type(e).__name__}: {e}"[:300]})
    res = synthese(projet, sessions)
    if d.guide and res["achats"]:
        from marcel_core.hf import guide
        try:
            res["guide"] = guide(res)
        except Exception as e:
            res["guide"] = {"erreur": f"{type(e).__name__}: {e}"[:300]}
    return res


# ====================================================================== Marcel Pro (parcours artisan)
# Contrat : docs/prompt_v0.md (lib/types.ts du front). L'état du chantier vit dans Supabase (table projets).
from datetime import datetime, timezone  # noqa: E402

from fastapi import Response  # noqa: E402

from marcel_core import base  # noqa: E402
from marcel_core import chantier as ch  # noqa: E402
from marcel_core.chiffrage import Chantier, ReleveFournisseur, consigne, evaluer, synthese  # noqa: E402

PAUSE_SUIVI_S = 45   # entre deux interrogations de H (clé Free : 5 requêtes/min)
BUDGET_REQ = 3       # requêtes H au maximum par passage


class Artisan(BaseModel):
    prenom: Optional[str] = None
    email: Optional[str] = None


class DemandeChantier(BaseModel):
    fiche: dict
    artisan: Optional[Artisan] = None


class DemandeReponses(BaseModel):
    reponses: List[dict] = []
    fournisseurs: Optional[List[str]] = None


class DemandeDevisPdf(BaseModel):
    client: dict = {}
    artisan: dict = {}
    decennale: Optional[str] = None
    conditions_paiement: Optional[str] = None
    validite_jours: Optional[int] = 30
    mediateur: Optional[str] = None
    adresse_chantier: Optional[str] = None
    lignes: Optional[List[dict]] = None
    taux_tva: Optional[float] = None


class DemandeChoix(BaseModel):
    id: str
    valeur: str


class DemandeConseil(BaseModel):
    conseil_id: str
    decision: str  # "garder" | "changer"


def _projet(cid: str) -> dict:
    if not base.actif():
        raise HTTPException(503, "Supabase n'est pas configuré sur le back")
    lignes = base.lire("projets", id=cid)
    if not lignes:
        raise HTTPException(404, "chantier introuvable")
    return lignes[0]


def _maj(cid: str, valeurs: dict) -> dict:
    return base.modifier("projets", {"id": cid}, valeurs)[0]


@app.get("/api/chantiers")
def lister_chantiers():
    if not base.actif():
        raise HTTPException(503, "Supabase n'est pas configuré sur le back")
    with base._client() as c:
        r = c.get("/projets", params={"select": "id,nom,created_at,statut,fiche", "fiche": "not.is.null",
                                      "order": "created_at.desc", "limit": 50})
        r.raise_for_status()
    return [{"id": p["id"], "nom": p.get("nom") or "Chantier", "piece": (p.get("fiche") or {}).get("piece"),
             "cree_le": p["created_at"], "etat": ch.ETAT_FRONT.get(p.get("statut"), "brouillon")} for p in r.json()]


@app.post("/api/chantiers")
def creer_chantier(d: DemandeChantier):
    f = dict(d.fiche)
    for k in ("longueur_m", "largeur_m"):
        if not f.get(k):
            raise HTTPException(400, f"{k} manquant : les dimensions ne peuvent pas être déléguées")
    photos, plan = f.pop("photos", []) or [], f.pop("plan", None)
    for k in ("photos_inspiration", "photos_meubles"):
        f[k] = len(f.get(k) or [])
    f["nb_photos"], f["plan_fourni"] = len(photos), bool(plan)
    try:
        analyse = __import__("marcel_core.hf", fromlist=["lire_chantier"]).lire_chantier(f, photos, plan)
    except Exception as e:  # la lecture des photos n'est jamais bloquante
        analyse = {"erreur": f"{type(e).__name__}: {e}"[:200]}
    if analyse.get("etat_murs") in ("a_reprendre", "abime") and not f.get("etat_murs"):
        f["etat_murs"] = analyse["etat_murs"]
    questions = ch.generer_questions({**f, "photos": photos, "plan": plan})
    p = base.inserer("projets", {
        "nom": f.get("nom"), "texte": f"Chantier — {f.get('nom')}", "code_postal": f.get("code_postal"),
        "budget_eur": f.get("budget_client_eur"), "niveau": "confirmé", "fiche": f, "analyse_photos": analyse,
        "questions": questions, "statut": "questions" if questions else "valide",
        "email_artisan": d.artisan.email if d.artisan else None, "prenom_artisan": d.artisan.prenom if d.artisan else None})[0]
    return {"id": p["id"], "questions": questions, "surfaces": ch.surfaces(f), "analyse_photos": analyse}


@app.get("/api/chantiers/{cid}/questions")
def questions_du_chantier(cid: str):
    return _projet(cid).get("questions") or []


@app.post("/api/chantiers/{cid}/reponses")
def envoyer_reponses(cid: str, d: DemandeReponses):
    p = _projet(cid)
    if p.get("sessions"):
        return ch.avancement(p)  # déjà lancé : on ne relance jamais deux fois (quota H)
    fiche, choix, delegues = ch.appliquer_reponses(dict(p.get("fiche") or {}), p.get("questions") or [], d.reponses)
    fours = {k: v for k, v in ch.FOURNISSEURS_DEFAUT.items() if not d.fournisseurs or k in d.fournisseurs}
    chantier = ch.chantier_chiffrage(cid, fiche, choix, fours, p.get("email_artisan"))
    n = len(chantier.produits)
    sessions = []
    for f in list(fours)[:3]:
        try:
            l = agents.lancer(consigne(chantier, fours[f]), ReleveFournisseur, min(40 + 14 * n, 200),
                              min(600 + 150 * n, 2400), fournisseur=f, chantier=cid)
            sessions.append({**l, "etat_agent": "en_cours", "etapes": 0})
        except Exception as e:
            sessions.append({"fournisseur": f, "etat_agent": "erreur", "erreur": f"{type(e).__name__}: {e}"[:200]})
    p = _maj(cid, {"fiche": fiche, "reponses": d.reponses, "choix_delegues": delegues,
                   "besoins": [x.model_dump() for x in chantier.produits], "sessions": sessions,
                   "statut": "en_recherche", "dernier_suivi": datetime.now(timezone.utc).isoformat()})
    return ch.avancement(p)


def _finaliser(p: dict) -> dict:
    fiche = p.get("fiche") or {}
    _, choix, _ = ch.appliquer_reponses(dict(fiche), p.get("questions") or [], p.get("reponses") or [])
    chantier = Chantier(nom=p.get("nom") or "Chantier", code_postal=p.get("code_postal") or "",
                        produits=p.get("besoins") or [], fournisseurs=ch.FOURNISSEURS_DEFAUT)
    sessions = [{**s, "reponse": s.get("rapport")} for s in p.get("sessions") or []]
    synth = synthese(chantier, sessions)
    dv = ch.devis(fiche, choix, synth)
    resultat = {"synthese": synth, "planning": ch.planning(fiche, choix, synth), "conseils": ch.conseils(fiche, choix, synth, dv),
                "releve_le": max((s.get("fini_le") or "" for s in sessions), default=None) or ch.maintenant(),
                "visuel": {"avant_url": None, "apres_url": None}}
    try:  # trace dans executions / releves (grille des agents)
        from chiffrage import enregistrer_session
        skill = base.skill_id("releve_prix")
        for s in sessions:
            if s.get("session_id"):
                enregistrer_session({**s, **evaluer(chantier, s.get("reponse"))}, chantier, p["id"], skill)
    except Exception as e:
        print(f"journal executions impossible : {e}", flush=True)
    return _maj(p["id"], {"resultat": resultat, "devis": dv, "total_eur": ch.totaux(dv)["total_ttc"],
                          "statut": "termine"})  # → webhook Supabase → n8n → mail


@app.get("/api/chantiers/{cid}/etat")
def etat_du_chantier(cid: str):
    p = _projet(cid)
    if p.get("statut") != "en_recherche":
        return ch.avancement(p)
    dernier = p.get("dernier_suivi")
    if dernier and (datetime.now(timezone.utc) - datetime.fromisoformat(dernier)).total_seconds() < PAUSE_SUIVI_S:
        return ch.avancement(p)
    sessions, budget = p.get("sessions") or [], BUDGET_REQ
    for s in sessions:
        if budget <= 0 or s.get("etat_agent") != "en_cours" or not s.get("session_id"):
            continue
        try:
            st = agents.statut(s["session_id"])
            budget -= 1
            s["etapes"] = st.get("etapes")
            if st["termine"] and budget > 0:
                r = agents.recuperer(s["fournisseur"], s["session_id"], s.get("lance_le"), schema=ReleveFournisseur)
                budget -= 2
                rep = r.get("rapport") or {}
                s.update(rapport=rep, statut=r.get("statut"), duree_s=r.get("duree_s"), cout_total=r.get("cout_total"),
                         replay_url=r.get("replay_url"), fini_le=ch.maintenant(),
                         etat_agent="bloque" if rep.get("acces_site") == "bloque" else "fini")
        except Exception as e:
            print(f"suivi {s.get('session_id')} : {type(e).__name__}: {e}", flush=True)
            if "429" in str(e):
                break
    p = _maj(cid, {"sessions": sessions, "dernier_suivi": datetime.now(timezone.utc).isoformat()})
    if all(s.get("etat_agent") != "en_cours" for s in sessions):
        p = _finaliser(p)
    return ch.avancement(p)


@app.get("/api/chantiers/{cid}/resultat")
def resultat_du_chantier(cid: str):
    p = _projet(cid)
    if p.get("statut") not in ("termine", "envoye"):
        raise HTTPException(409, "le chantier n'est pas encore prêt")
    return ch.resultat_front(p)


@app.post("/api/chantiers/{cid}/choix")
def changer_un_choix(cid: str, d: DemandeChoix):
    p = _projet(cid)
    delegues = [dict(c, valeur=d.valeur, raison="Choisi par toi.") if c["id"] == d.id else c for c in p.get("choix_delegues") or []]
    return ch.resultat_front(_maj(cid, {"choix_delegues": delegues}))


@app.post("/api/chantiers/{cid}/conseils")
def repondre_au_conseil(cid: str, d: DemandeConseil):
    p = _projet(cid)
    r = p.get("resultat") or {}
    r["conseils"] = [dict(c, decision=d.decision) if c["id"] == d.conseil_id else c for c in r.get("conseils") or []]
    return ch.resultat_front(_maj(cid, {"resultat": r}))


@app.post("/api/chantiers/{cid}/devis.pdf")
def exporter_devis_pdf(cid: str, d: DemandeDevisPdf):
    from marcel_core.devis_pdf import generer
    p = _projet(cid)
    dv = p.get("devis") or {"lignes": [], "taux_tva": 20}
    infos = d.model_dump()
    plan = (p.get("resultat") or {}).get("planning") or []
    if plan:
        infos.setdefault("debut_travaux", plan[0]["debut"])
        infos["debut_travaux"] = infos.get("debut_travaux") or plan[0]["debut"]
        infos["duree_jours"] = sum(t["duree_j"] for t in plan)
    infos["releve_le"] = ((p.get("resultat") or {}).get("releve_le") or "")[:10]
    if d.lignes is not None or d.taux_tva is not None:  # le devis corrigé par l'artisan est enregistré
        _maj(cid, {"devis": {"lignes": d.lignes or dv["lignes"], "taux_tva": d.taux_tva or dv["taux_tva"]}})
    numero = f"DEV-{datetime.now().strftime('%Y%m%d')}-{cid[:4].upper()}"
    pdf = generer(dv, infos, {**(p.get("fiche") or {}), "code_postal": p.get("code_postal")}, numero)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{numero}.pdf"'})


@app.post("/api/chantiers/{cid}/envoye")
def marquer_envoye(cid: str):
    return ch.avancement(_maj(cid, {"statut": "envoye"}))
