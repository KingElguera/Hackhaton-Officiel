#!/usr/bin/env python3
"""Marcel — test d'accès des enseignes.

Lance UNE session H Company par enseigne (max 3 en parallèle) avec la même
tâche : chercher un produit, ouvrir la fiche, relever prix / dimensions /
stock magasin / délai de livraison. Chaque run est loggué dans
logs/runs.jsonl (durée, statut, coût, étapes, lien de replay).

Usage :
    uv run test_enseignes.py                      # les 4 enseignes
    uv run test_enseignes.py ikea                 # une seule
    uv run test_enseignes.py ikea castorama --agent h/web-surfer-pro
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from hai_agents import Client

ENSEIGNES = {
    "leroymerlin": "https://www.leroymerlin.fr",
    "castorama": "https://www.castorama.fr",
    "manomano": "https://www.manomano.fr",
    "ikea": "https://www.ikea.com/fr/fr/",
    "bricorama": "https://www.bricorama.fr",
}
PRODUIT = "étagère murale"
CODE_POSTAL = "75011"
MAX_STEPS = 40      # plafond d'actions par session (protège les crédits)
MAX_TIME_S = 600    # plafond de durée par session
LOG = Path(__file__).parent / "logs" / "runs.jsonl"
CHAMPS_CLES = ["prix_eur", "dimensions", "stock_magasin", "delai_livraison"]


class Rapport(BaseModel):
    acces_site: Literal["ok", "bloque", "partiel"] = Field(
        description="ok = tout relevé ; partiel = site accessible mais infos manquantes ; bloque = captcha / accès refusé / page vide")
    obstacle: Optional[str] = Field(None, description="Ce qui a bloqué ou gêné (captcha, accès refusé, bandeau, sélection magasin...)")
    produit: Optional[str] = None
    url_produit: Optional[str] = None
    prix_eur: Optional[float] = None
    dimensions: Optional[str] = Field(None, description="Largeur x profondeur x hauteur avec unités, telles qu'affichées")
    magasin: Optional[str] = None
    stock_magasin: Optional[str] = Field(None, description="Disponibilité dans le magasin choisi, telle qu'affichée")
    delai_livraison: Optional[str] = Field(None, description="Délai ou date de livraison pour le code postal")
    commentaire: str = Field(description="Une ou deux phrases sur le déroulé")


TACHE = """Tu testes si le site {url} est utilisable. Ne crée pas de compte, ne te connecte pas, ne paie rien, n'ajoute rien au panier.
1. Ouvre {url}. Gère le bandeau cookies s'il y en a un.
2. Cherche "{produit}" et ouvre la fiche du premier produit vendu par l'enseigne.
3. Relève le prix et les dimensions exactes (souvent dans l'onglet Caractéristiques ou Fiche technique).
4. Relève le délai ou la date de livraison pour le code postal {cp}.
5. Sélectionne le magasin le plus proche de {cp} et relève la disponibilité en stock dans ce magasin.
Si tu tombes sur un CAPTCHA, une page "accès refusé" ou une page qui ne se charge pas, n'essaie pas de le contourner : arrête-toi et indique-le (acces_site = bloque).
Si une information est introuvable, laisse le champ vide et explique pourquoi dans commentaire."""


def _trouver_metrics(events):
    """Dernier bloc de métriques (coût, étapes) présent dans les événements."""
    dernier = None

    def walk(o):
        nonlocal dernier
        if isinstance(o, dict):
            if "total_cost" in o and "steps" in o:
                dernier = o
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for ev in events or []:
        try:
            walk(ev.model_dump() if hasattr(ev, "model_dump") else ev)
        except Exception:
            pass
    return dernier


def tester(nom: str, agent: str) -> dict:
    client = Client()  # lit HAI_API_KEY
    url = ENSEIGNES[nom]
    ligne = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "enseigne": nom,
        "agent": agent,
        "produit": PRODUIT,
    }
    t0 = time.monotonic()
    try:
        handle = client.start_session(
            agent=agent,
            messages=TACHE.format(url=url, produit=PRODUIT, cp=CODE_POSTAL),
            answer_schema=Rapport,
            max_steps=MAX_STEPS,
            max_time_s=MAX_TIME_S,
            timezone="Europe/Paris",
        )
        ligne["session_id"] = handle.id
        print(f"[{nom}] session lancée : {handle.id}", flush=True)
        try:
            ligne["replay_url"] = handle.get().agent_view_url
        except Exception:
            pass
        res = handle.wait_for_completion()
        ligne.update(
            statut=res.status,
            outcome=res.outcome,
            erreur=res.error,
            erreur_code=res.error_code,
            rapport=res.answer.model_dump() if isinstance(res.answer, BaseModel) else res.answer,
        )
        # Verdict calculé par le code, pas auto-déclaré par l'agent
        rap = ligne["rapport"] if isinstance(ligne["rapport"], dict) else {}
        manquants = [c for c in CHAMPS_CLES if rap.get(c) in (None, "")]
        ligne["champs_manquants"] = manquants
        if res.status not in ("completed", "idle") or rap.get("acces_site") == "bloque":
            ligne["verdict"] = "bloque"
        else:
            ligne["verdict"] = "ok" if not manquants else "partiel"
        m = _trouver_metrics(res.events)
        if m:
            ligne["etapes"] = m.get("steps")
            ligne["cout_total"] = m.get("total_cost")
    except Exception as e:  # AnswerValidationError, quota, réseau...
        ligne.update(statut="exception", erreur=f"{type(e).__name__}: {e}")
        raw = getattr(e, "raw", None)
        if raw is not None:
            ligne["rapport_brut"] = raw
    ligne["duree_s"] = round(time.monotonic() - t0, 1)

    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
    return ligne


def main():
    p = argparse.ArgumentParser()
    p.add_argument("enseignes", nargs="*", default=list(ENSEIGNES), choices=list(ENSEIGNES))
    p.add_argument("--agent", default="h/web-surfer-flash")
    p.add_argument("--parallele", type=int, default=1,
                   help="sessions en parallèle (Free : 5 requêtes/min par clé, donc 1 conseillé)")
    p.add_argument("-y", action="store_true", help="ne pas demander confirmation")
    a = p.parse_args()

    print(f"{len(a.enseignes)} session(s) vont être consommées ({', '.join(a.enseignes)}) avec {a.agent}.")
    if not a.y and input("On y va ? [o/N] ").strip().lower() not in ("o", "oui", "y"):
        return

    with ThreadPoolExecutor(max_workers=max(1, min(3, a.parallele))) as ex:
        resultats = list(ex.map(lambda n: tester(n, a.agent), a.enseignes))

    print("\n=== Résumé ===")
    for r in resultats:
        rap = r.get("rapport") if isinstance(r.get("rapport"), dict) else {}
        print(f"- {r['enseigne']:12} VERDICT={r.get('verdict', 'bloque')} manquants={r.get('champs_manquants')} "
              f"statut={r.get('statut')} acces_selon_agent={rap.get('acces_site')} "
              f"duree={r['duree_s']}s cout={r.get('cout_total')} etapes={r.get('etapes')}")
        print(f"    prix={rap.get('prix_eur')} dim={rap.get('dimensions')} stock={rap.get('stock_magasin')} "
              f"livraison={rap.get('delai_livraison')}")
        if rap.get("obstacle") or r.get("erreur"):
            print(f"    obstacle={rap.get('obstacle')} erreur={r.get('erreur')}")
        if r.get("replay_url"):
            print(f"    replay : {r['replay_url']}")
    print(f"\nLog complet : {LOG}")


if __name__ == "__main__":
    main()
