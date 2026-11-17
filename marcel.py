#!/usr/bin/env python3
"""Marcel — parcours complet sur une pièce.

1. Un agent H Company par enseigne cherche les produits du cas, relève prix,
   dimensions (mm), stock magasin, délai de livraison (panier, sans payer).
2. Le CODE (pas l'agent) vérifie : l'étagère rentre-t-elle dans la niche ?
   combien de pots de peinture ? budget tenu ?
3. Le code choisit le meilleur produit vérifié par besoin et construit l'ordre
   des travaux contraint par les dates de disponibilité.

Usage :
    uv run marcel.py                         # lance les agents (2 sessions)
    uv run marcel.py --enseignes castorama   # une seule enseigne (1 session)
    uv run marcel.py --rejouer out/<dossier> # recalcule sans consommer de session
"""
import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ICI = Path(__file__).parent
LOG = ICI / "logs" / "runs.jsonl"
SORTIE = ICI / "out"
MAX_STEPS = 90
MAX_TIME_S = 900
JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
POLL_S = 30  # 1 requête de suivi par session toutes les 30 s (clé Free : 5 req/min)


# ---------------------------------------------------------------- schéma agent
class Produit(BaseModel):
    besoin: Literal["etagere", "peinture"]
    nom: str
    url: Optional[str] = None
    prix_eur: Optional[float] = Field(None, description="Prix unitaire TTC affiché")
    largeur_mm: Optional[float] = Field(None, description="Largeur/longueur en millimètres (1 cm = 10 mm)")
    profondeur_mm: Optional[float] = Field(None, description="Profondeur en millimètres")
    hauteur_mm: Optional[float] = Field(None, description="Hauteur ou épaisseur en millimètres")
    volume_l: Optional[float] = Field(None, description="Peinture : contenance du pot en litres")
    rendement_m2_par_l: Optional[float] = Field(None, description="Peinture : rendement affiché en m² par litre")
    magasin: Optional[str] = None
    en_stock_magasin: Optional[bool] = Field(None, description="True si disponible en retrait dans le magasin choisi")
    stock_texte: Optional[str] = Field(None, description="Disponibilité telle qu'affichée")
    delai_livraison_texte: Optional[str] = Field(None, description="Délai/date de livraison tel qu'affiché")
    delai_livraison_jours: Optional[int] = Field(None, description="Nombre de jours entre aujourd'hui et la livraison")
    ajoute_au_panier: bool = False


class Rapport(BaseModel):
    acces_site: Literal["ok", "partiel", "bloque"]
    obstacle: Optional[str] = None
    produits: List[Produit] = Field(default_factory=list)
    commentaire: str


TACHE = """Tu es l'assistant d'achat de Marcel sur {url}. Date du jour : {jour}. Code postal : {cp}.

RÈGLES : ne crée pas de compte, ne te connecte pas. Tu peux ajouter au panier et saisir le code postal pour voir le délai de livraison, mais ne va JAMAIS jusqu'au formulaire d'adresse ou au paiement : arrête-toi au panier.
Si tu tombes sur un CAPTCHA ou une page "accès refusé", ne le contourne pas : arrête-toi et réponds avec acces_site = bloque.

BESOINS :
1. etagere : une étagère murale pour une niche de {L} mm de large et {P} mm de profondeur. Elle doit faire AU MAXIMUM {Lmax} mm de large et {Pmax} mm de profondeur (jeu de pose compris). Ignore les produits plus grands et cherche des tailles plus petites si besoin (ex. 60 cm). Trouve jusqu'à 2 produits candidats.
2. peinture : peinture murale {couleur} pour l'intérieur, pour {S} m² en {couches} couches. Trouve jusqu'à 2 produits candidats.

Pour chaque candidat, ouvre la fiche produit et relève, tels qu'affichés : nom, URL, prix, dimensions converties en millimètres (onglet Caractéristiques / Fiche technique), et pour la peinture le volume en litres et le rendement en m²/L.
Sélectionne le magasin le plus proche de {cp} et relève la disponibilité de chaque candidat dans ce magasin.
en_stock_magasin = true UNIQUEMENT si la page affiche explicitement un stock disponible dans ce magasin ; recopie ce texte dans stock_texte.
Ajoute ensuite au panier le meilleur candidat de chaque besoin, relève le délai de livraison pour {cp} et convertis-le en nombre de jours à partir d'aujourd'hui (si c'est une plage de dates, prends la date la plus tardive).
Si l'enseigne ne vend pas un des besoins, ne renvoie aucun produit pour ce besoin et dis-le dans commentaire.
Ne devine jamais une valeur : si une information n'est pas affichée, laisse le champ vide."""


# ---------------------------------------------------------------- agents
def _metrics(events):
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
    return dernier or {}


def lancer_agent(nom: str, url: str, cas: dict, agent: str) -> dict:
    from hai_agents import Client, is_settled_session_status

    client = Client()
    ligne = {"ts": datetime.now(timezone.utc).isoformat(), "type": "parcours",
             "cas": cas["nom"], "enseigne": nom, "agent": agent}
    t0 = time.monotonic()
    try:
        msg = TACHE.format(
            url=url, jour=date.today().isoformat(), cp=cas["code_postal"],
            L=cas["niche"]["largeur_mm"], P=cas["niche"]["profondeur_mm"],
            Lmax=cas["niche"]["largeur_mm"] - cas["niche"]["marge_mm"],
            Pmax=cas["niche"]["profondeur_mm"] - cas["niche"]["marge_mm"],
            couleur=cas["peinture"]["couleur"], S=cas["peinture"]["surface_m2"],
            couches=cas["peinture"]["couches"])
        h = client.start_session(agent=agent, messages=msg, answer_schema=Rapport,
                                 max_steps=MAX_STEPS, max_time_s=MAX_TIME_S, timezone="Europe/Paris")
        ligne["session_id"] = h.id
        try:
            ligne["replay_url"] = h.get().agent_view_url
        except Exception:
            pass
        print(f"[{nom}] session lancée : {ligne.get('replay_url') or h.id}", flush=True)

        while True:
            time.sleep(POLL_S)
            try:
                st = h.status()
            except Exception as e:  # 429 ou réseau : on retente au prochain tour
                print(f"[{nom}] suivi indisponible ({type(e).__name__}), on retente", flush=True)
                continue
            statut = str(getattr(st.status, "value", st.status))
            print(f"[{nom}] {statut} — {st.steps} étapes — {round(time.monotonic() - t0)} s", flush=True)
            if is_settled_session_status(statut):
                break
            if time.monotonic() - t0 > MAX_TIME_S + 180:
                h.cancel()
                break

        res = h.wait_for_completion()
        ligne.update(statut=res.status, erreur=res.error, erreur_code=res.error_code,
                     rapport=res.answer.model_dump() if isinstance(res.answer, BaseModel) else res.answer)
        m = _metrics(res.events)
        ligne["etapes"], ligne["cout_total"] = m.get("steps"), m.get("total_cost")
    except Exception as e:
        ligne.update(statut="exception", erreur=f"{type(e).__name__}: {e}")
        if getattr(e, "raw", None) is not None:
            ligne["rapport_brut"] = e.raw
    ligne["duree_s"] = round(time.monotonic() - t0, 1)
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
    return ligne


# ---------------------------------------------------------------- vérification (code)
def verifier(cas: dict, sessions: List[dict]) -> List[dict]:
    niche, pein = cas["niche"], cas["peinture"]
    lmax = niche["largeur_mm"] - niche["marge_mm"]
    pmax = niche["profondeur_mm"] - niche["marge_mm"]
    candidats = []
    for s in sessions:
        rap = s.get("rapport") if isinstance(s.get("rapport"), dict) else {}
        for p in rap.get("produits") or []:
            c = dict(p, enseigne=s["enseigne"], raisons=[], valide=True)
            if p.get("prix_eur") is None:
                c["valide"] = False
                c["raisons"].append("prix non relevé")
            if p["besoin"] == "etagere":
                L, P = p.get("largeur_mm"), p.get("profondeur_mm")
                if L is None or P is None:
                    c["valide"] = False
                    c["raisons"].append("dimensions non relevées : impossible de vérifier la niche")
                else:
                    if L > lmax:
                        c["valide"] = False
                        c["raisons"].append(f"trop large : {L:.0f} mm > {lmax} mm")
                    if P > pmax:
                        c["valide"] = False
                        c["raisons"].append(f"trop profonde : {P:.0f} mm > {pmax} mm")
                    if c["valide"]:
                        c["raisons"].append(f"rentre dans la niche ({L:.0f}×{P:.0f} mm ≤ {lmax}×{pmax} mm)")
                c["quantite"] = 1
            else:
                vol = p.get("volume_l")
                rend = p.get("rendement_m2_par_l")
                if not rend:
                    rend = pein["rendement_par_defaut_m2_par_l"]
                    c["raisons"].append(f"rendement non affiché : {rend} m²/L supposé")
                if not vol:
                    c["valide"] = False
                    c["raisons"].append("volume du pot non relevé")
                    c["quantite"] = None
                else:
                    litres = pein["surface_m2"] * pein["couches"] / rend
                    c["quantite"] = math.ceil(litres / vol)
                    c["raisons"].append(f"{litres:.1f} L nécessaires → {c['quantite']} pot(s) de {vol:g} L")
            c["cout_eur"] = round(c["quantite"] * p["prix_eur"], 2) if c.get("quantite") and p.get("prix_eur") else None
            if p.get("en_stock_magasin") and p.get("stock_texte"):
                c["dispo_jours"], c["dispo_mode"] = 0, f"retrait magasin ({p.get('magasin') or '?'})"
            elif p.get("delai_livraison_jours") is not None:
                c["dispo_jours"], c["dispo_mode"] = p["delai_livraison_jours"], "livraison"
            else:
                c["dispo_jours"], c["dispo_mode"] = None, "disponibilité inconnue"
            if p.get("en_stock_magasin") and not p.get("stock_texte"):
                c["raisons"].append("stock magasin annoncé par l'agent sans texte affiché : non retenu")
            candidats.append(c)
    return candidats


def choisir(candidats: List[dict]) -> dict:
    choix = {}
    for besoin in ("etagere", "peinture"):
        ok = [c for c in candidats if c["besoin"] == besoin and c["valide"]]
        ok.sort(key=lambda c: (c["dispo_jours"] is None,
                               c["cout_eur"] if c["cout_eur"] is not None else 1e9,
                               c["dispo_jours"] if c["dispo_jours"] is not None else 99))
        choix[besoin] = ok[0] if ok else None
    return choix


def planifier(cas: dict, choix: dict) -> List[dict]:
    debutant = cas["niveau"].startswith("d")
    j0 = date.today()
    taches = []
    pein = choix.get("peinture")
    eta = choix.get("etagere")
    d_pein = pein["dispo_jours"] if pein and pein["dispo_jours"] is not None else None
    duree_pein = 3 if debutant else 2  # préparation + 2 couches + séchage
    if d_pein is not None:
        taches.append({"tache": "Préparer les murs et peindre (2 couches + séchage)",
                       "debut": j0 + timedelta(days=d_pein), "duree_j": duree_pein,
                       "attend": f"peinture ({pein['dispo_mode']})"})
    fin_pein = (j0 + timedelta(days=d_pein + duree_pein)) if d_pein is not None else None
    d_eta = eta["dispo_jours"] if eta and eta["dispo_jours"] is not None else None
    if d_eta is not None and fin_pein is not None:
        debut = max(j0 + timedelta(days=d_eta), fin_pein)
        taches.append({"tache": "Poser l'étagère dans la niche (perçage + chevilles)",
                       "debut": debut, "duree_j": 1,
                       "attend": f"étagère ({eta['dispo_mode']}) et fin de la peinture"})
    return taches


# ---------------------------------------------------------------- rapport
def rapport_md(cas, sessions, candidats, choix, taches) -> str:
    L = [f"# Marcel — {cas['nom']}", "",
         f"Pièce : {cas['piece']} · Niche : {cas['niche']['largeur_mm']}×{cas['niche']['profondeur_mm']} mm · "
         f"Peinture : {cas['peinture']['surface_m2']} m² × {cas['peinture']['couches']} couches · "
         f"Budget : {cas['budget_eur']} € · Niveau : {cas['niveau']} · CP {cas['code_postal']}", "",
         "## Liste d'achats vérifiée", ""]
    total = 0.0
    for besoin, c in choix.items():
        if not c:
            L.append(f"- **{besoin}** : aucun produit vérifié ✗")
            continue
        total += c["cout_eur"] or 0
        L.append(f"- **{besoin}** — {c['nom']} ({c['enseigne']}) : {c['quantite']} × {c['prix_eur']:.2f} € = "
                 f"**{c['cout_eur']:.2f} €** · {c['dispo_mode']}"
                 + (f" (J+{c['dispo_jours']})" if c["dispo_jours"] else "")
                 + f"\n  - {'; '.join(c['raisons'])}"
                 + (f"\n  - {c['url']}" if c.get("url") else ""))
    ok_budget = total <= cas["budget_eur"]
    L += ["", f"**Total : {total:.2f} €** / budget {cas['budget_eur']} € → "
          + ("✅ dans le budget" if ok_budget else "❌ dépassement"), "",
          "## Ordre des travaux", ""]
    for i, t in enumerate(taches, 1):
        L.append(f"{i}. {JOURS[t['debut'].weekday()]} {t['debut'].strftime('%d/%m')} — {t['tache']} ({t['duree_j']} j) · attend : {t['attend']}")
    if not taches:
        L.append("Impossible à planifier : disponibilité inconnue pour au moins un produit.")
    L += ["", "## Tous les candidats vus par les agents", "",
          "| Enseigne | Besoin | Produit | Prix | Dimensions (mm) | Dispo | Vérifié | Raison |", "|---|---|---|---|---|---|---|---|"]
    for c in candidats:
        dims = "×".join(f"{c[k]:.0f}" for k in ("largeur_mm", "profondeur_mm", "hauteur_mm") if c.get(k)) or "—"
        L.append(f"| {c['enseigne']} | {c['besoin']} | {c['nom']} | {c.get('prix_eur') or '—'} | {dims} | "
                 f"{c['dispo_mode']} | {'✅' if c['valide'] else '❌'} | {'; '.join(c['raisons'])} |")
    L += ["", "## Métriques des agents", "", "| Enseigne | Statut | Accès | Durée | Étapes | Coût | Replay |", "|---|---|---|---|---|---|---|"]
    for s in sessions:
        rap = s.get("rapport") if isinstance(s.get("rapport"), dict) else {}
        L.append(f"| {s['enseigne']} | {s.get('statut')} | {rap.get('acces_site', '—')} | {s.get('duree_s')} s | "
                 f"{s.get('etapes')} | {s.get('cout_total')} | {s.get('replay_url') or s.get('session_id', '')} |")
    L += ["", "_Marcel s'arrête avant le paiement : rien n'a été acheté._"]
    return "\n".join(L)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cas", default=str(ICI / "cas" / "chambre.json"))
    ap.add_argument("--enseignes", nargs="*")
    ap.add_argument("--agent", default="h/web-surfer-flash")
    ap.add_argument("--rejouer", help="dossier out/... dont on recalcule le résultat sans lancer d'agent")
    ap.add_argument("-y", action="store_true")
    a = ap.parse_args()
    cas = json.loads(Path(a.cas).read_text(encoding="utf-8"))

    if a.rejouer:
        dossier = Path(a.rejouer)
        sessions = json.loads((dossier / "sessions.json").read_text(encoding="utf-8"))
    else:
        ens = {k: v for k, v in cas["enseignes"].items() if not a.enseignes or k in a.enseignes}
        print(f"{len(ens)} session(s) vont être consommées ({', '.join(ens)}) avec {a.agent}.")
        if not a.y and input("On y va ? [o/N] ").strip().lower() not in ("o", "oui", "y"):
            return
        with ThreadPoolExecutor(max_workers=2) as ex:
            sessions = list(ex.map(lambda kv: lancer_agent(kv[0], kv[1], cas, a.agent), ens.items()))
        dossier = SORTIE / datetime.now().strftime("%Y%m%d-%H%M%S")
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "sessions.json").write_text(json.dumps(sessions, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    candidats = verifier(cas, sessions)
    choix = choisir(candidats)
    taches = planifier(cas, choix)
    md = rapport_md(cas, sessions, candidats, choix, taches)
    (dossier / "rapport.md").write_text(md, encoding="utf-8")
    (dossier / "resultat.json").write_text(json.dumps(
        {"cas": cas, "candidats": candidats, "choix": choix, "taches": taches},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n" + md)
    print(f"\nFichiers : {dossier}")


if __name__ == "__main__":
    main()
