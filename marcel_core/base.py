"""Supabase : enregistrement des sessions, relevés et chantiers (API REST, clé service_role).

Variables d'environnement : SUPABASE_URL, SUPABASE_SERVICE_KEY. Sans elles, rien n'est écrit
(le reste de Marcel fonctionne quand même) : actif() renvoie False.
"""
import os
from typing import Optional

import httpx


def actif() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _client() -> httpx.Client:
    cle = os.environ["SUPABASE_SERVICE_KEY"]
    entetes = {"apikey": cle, "Content-Type": "application/json"}
    if cle.startswith("eyJ"):  # ancienne clé JWT : aussi en Authorization ; les clés sb_secret_ passent par apikey
        entetes["Authorization"] = f"Bearer {cle}"
    return httpx.Client(base_url=os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1", headers=entetes, timeout=20)


def inserer(table: str, lignes, conflit: Optional[str] = None, ignorer_doublons: bool = False) -> list:
    lignes = lignes if isinstance(lignes, list) else [lignes]
    if not lignes:
        return []
    prefer = ["return=representation"]
    if conflit:
        prefer.append("resolution=ignore-duplicates" if ignorer_doublons else "resolution=merge-duplicates")
    with _client() as c:
        r = c.post(f"/{table}", json=lignes, params={"on_conflict": conflit} if conflit else None,
                   headers={"Prefer": ",".join(prefer)})
        r.raise_for_status()
        return r.json()


def modifier(table: str, filtre: dict, valeurs: dict) -> list:
    with _client() as c:
        r = c.patch(f"/{table}", params={k: f"eq.{v}" for k, v in filtre.items()}, json=valeurs,
                    headers={"Prefer": "return=representation"})
        r.raise_for_status()
        return r.json()


def lire(table: str, **filtre) -> list:
    with _client() as c:
        r = c.get(f"/{table}", params={"select": "*", **{k: f"eq.{v}" for k, v in filtre.items()}})
        r.raise_for_status()
        return r.json()


def skill_id(nom: str) -> Optional[str]:
    lignes = lire("skills", nom=nom)
    return lignes[0]["id"] if lignes else None
