"""Agents H Company : consigne générique, lancement, suivi, récupération du résultat.

Pensé pour un back sans état : on lance (→ session_id + lien live), le front suit
le statut, puis on récupère le résultat à partir du session_id.
"""
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

from .modeles import Besoin, Projet, Rapport

AGENT = "h/web-surfer-flash"
LOG = Path(__file__).resolve().parent.parent / "logs" / "runs.jsonl"

REGLES = """RÈGLES : ne crée pas de compte, ne te connecte pas. Tu peux ajouter au panier et saisir le code postal pour voir le délai de livraison, mais ne va JAMAIS jusqu'au formulaire d'adresse ou au paiement : arrête-toi au panier.
Si tu tombes sur un CAPTCHA ou une page "accès refusé", ne le contourne pas : arrête-toi et réponds avec acces_site = bloque."""


def _ligne_besoin(b: Besoin) -> str:
    if b.famille == "objet":
        lim = [f"{nom} ≤ {v:.0f} mm" for nom, v in (("largeur", b.largeur_max_mm), ("profondeur", b.profondeur_max_mm),
                                                    ("hauteur", b.hauteur_max_mm)) if v]
        t = f"- {b.id} : {b.description} (catégorie : {b.categorie}"
        t += f", style : {b.style})" if b.style else ")"
        if lim:
            t += (f". TAILLE MAXIMUM (place disponible, jeu de pose compris) : {', '.join(lim)}. "
                  "Ignore les produits plus grands et cherche des tailles plus petites si besoin.")
        return t + f" Quantité : {b.quantite}."
    if b.famille == "surface":
        t = f"- {b.id} : {b.categorie}"
        t += f" {b.couleur}" if b.couleur else ""
        t += f" pour {b.surface_m2:g} m²" if b.surface_m2 else ""
        t += f" en {b.couches} couches" if b.couches else ""
        return t + (f" ({b.description}). Relève la contenance d'une unité vendue (litres par pot, ou m² par paquet/rouleau) "
                    "dans contenance + unite_contenance, et pour la peinture le rendement en m²/L.")
    return f"- {b.id} : {b.description} ({b.categorie}), quantité {b.quantite}."


def consigne(projet: Projet, url: str, jour: Optional[date] = None) -> str:
    besoins = "\n".join(_ligne_besoin(b) for b in projet.besoins)
    return f"""Tu es l'assistant d'achat de Marcel sur {url}. Date du jour : {(jour or date.today()).isoformat()}. Code postal : {projet.code_postal}.

{REGLES}

BESOINS (renvoie besoin_id = l'identifiant en début de ligne) :
{besoins}

Pour chaque besoin, trouve jusqu'à 2 produits candidats vendus par l'enseigne. Ouvre chaque fiche produit et relève, tels qu'affichés : nom, URL de la fiche, URL de la photo principale (image_url), prix, dimensions converties en millimètres (1 cm = 10 mm ; onglet Caractéristiques / Fiche technique).
Sélectionne le magasin le plus proche de {projet.code_postal} et relève la disponibilité de chaque candidat dans ce magasin.
en_stock_magasin = true UNIQUEMENT si la page affiche explicitement un stock disponible dans ce magasin ; recopie ce texte dans stock_texte.
Ajoute ensuite au panier le meilleur candidat de chaque besoin, relève le délai de livraison pour {projet.code_postal} et convertis-le en nombre de jours à partir d'aujourd'hui (si c'est une plage de dates, prends la date la plus tardive).
Si l'enseigne ne vend pas un des besoins, ne renvoie aucun produit pour ce besoin et dis-le dans commentaire.
Ne devine jamais une valeur : si une information n'est pas affichée, laisse le champ vide."""


def limites(projet: Projet):
    n = len(projet.besoins)
    return min(50 + 30 * n, 150), min(600 + 240 * n, 1500)  # max_steps, max_time_s


def _log(ligne: dict):
    try:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
    except OSError:  # système de fichiers en lecture seule (Vercel) : on logue sur la sortie standard
        print(json.dumps(ligne, ensure_ascii=False, default=str), flush=True)


def demarrer(projet: Projet, enseigne: str, agent: str = AGENT) -> dict:
    from hai_agents import Client
    url = projet.enseignes[enseigne]
    max_steps, max_time = limites(projet)
    h = Client().start_session(agent=agent, messages=consigne(projet, url), answer_schema=Rapport,
                               max_steps=max_steps, max_time_s=max_time, timezone="Europe/Paris")
    live = None
    try:
        live = h.get().agent_view_url
    except Exception:
        pass
    _log({"ts": datetime.now(timezone.utc).isoformat(), "type": "lancement", "projet": projet.nom,
          "enseigne": enseigne, "agent": agent, "session_id": h.id, "replay_url": live})
    return {"enseigne": enseigne, "session_id": h.id, "live_url": live, "agent": agent,
            "lance_le": datetime.now(timezone.utc).isoformat()}


def statut(session_id: str) -> dict:
    from hai_agents import Client, is_settled_session_status
    st = Client().session(session_id).status()
    s = str(getattr(st.status, "value", st.status))
    return {"session_id": session_id, "statut": s, "etapes": getattr(st, "steps", None),
            "termine": bool(is_settled_session_status(s))}


def _metrics(events):
    dernier = {}

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


def recuperer(enseigne: str, session_id: str, lance_le: Optional[str] = None) -> dict:
    """Résultat d'une session terminée, normalisé avec le schéma Rapport."""
    from hai_agents import Client
    h = Client().session(session_id)
    res = h.wait_for_completion()
    ans = res.answer
    if isinstance(ans, BaseModel):
        ans = ans.model_dump()
    elif isinstance(ans, str):
        try:
            ans = json.loads(ans)
        except json.JSONDecodeError:
            ans = {"acces_site": "partiel", "commentaire": ans[:500], "produits": []}
    try:
        ans = Rapport.model_validate(ans).model_dump()
    except Exception:
        pass
    m = _metrics(res.events)
    ligne = {"ts": datetime.now(timezone.utc).isoformat(), "type": "parcours", "enseigne": enseigne,
             "session_id": session_id, "statut": str(res.status), "erreur": res.error, "erreur_code": res.error_code,
             "rapport": ans, "etapes": m.get("steps"), "cout_total": m.get("total_cost")}
    try:
        ligne["replay_url"] = h.get().agent_view_url
    except Exception:
        pass
    if lance_le:
        try:
            ligne["duree_s"] = round((datetime.now(timezone.utc) - datetime.fromisoformat(lance_le)).total_seconds(), 1)
        except ValueError:
            pass
    _log(ligne)
    return ligne


def executer(projet: Projet, enseignes: List[str], agent: str = AGENT, poll_s: int = 30) -> List[dict]:
    """Mode ligne de commande : lance, suit toutes les 30 s (clé Free : 5 req/min), récupère."""
    lances = [demarrer(projet, e, agent) for e in enseignes]
    for l in lances:
        print(f"[{l['enseigne']}] session lancée : {l['live_url'] or l['session_id']}", flush=True)
    t0, en_cours = time.monotonic(), {l["session_id"] for l in lances}
    _, max_time = limites(projet)
    while en_cours and time.monotonic() - t0 < max_time + 180:
        time.sleep(poll_s)
        for sid in list(en_cours):
            try:
                st = statut(sid)
            except Exception as e:
                print(f"suivi indisponible ({type(e).__name__}), on retente", flush=True)
                continue
            print(f"[{sid[:8]}] {st['statut']} — {st['etapes']} étapes — {round(time.monotonic() - t0)} s", flush=True)
            if st["termine"]:
                en_cours.discard(sid)
    return [recuperer(l["enseigne"], l["session_id"], l["lance_le"]) for l in lances]
