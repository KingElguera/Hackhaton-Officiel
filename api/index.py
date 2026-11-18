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
    return {"ok": True, "h_company": bool(os.environ.get("HAI_API_KEY")), "hugging_face": bool(os.environ.get("HF_TOKEN"))}


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
