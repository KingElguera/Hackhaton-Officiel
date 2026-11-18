#!/usr/bin/env python3
"""Marcel — Brique 1 : chiffrage d'un chantier chez plusieurs fournisseurs.

Un agent H par fournisseur (et par agent si on compare flash/pro), 3 en parallèle au maximum.
Chaque session est enregistrée dans Supabase (executions + releves) si SUPABASE_URL et
SUPABASE_SERVICE_KEY sont définies ; le chantier passe à « termine » à la fin (déclencheur du mail n8n).

    uv run chiffrage.py chantiers/exemple.json
    uv run chiffrage.py chantiers/exemple.json --fournisseurs castorama --agents h/web-surfer-flash h/web-surfer-pro
    uv run chiffrage.py chantiers/exemple.json --rejouer out/chiffrage-<date>     # sans relancer d'agent
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from marcel_core import agents, base
from marcel_core.chiffrage import Chantier, ReleveFournisseur, consigne, evaluer, synthese, synthese_md

ICI = Path(__file__).parent
PARALLELE = 3  # plan H : 3 sessions simultanées


def enregistrer_session(s: dict, chantier: Chantier, projet_id, skill):
    """Une session terminée → 1 ligne executions + ses relevés."""
    rep = s.get("reponse") or {}
    ex = base.inserer("executions", {
        "projet_id": projet_id, "skill_id": skill, "fournisseur_id": s["fournisseur"], "agent": s["agent"],
        "session_id": s["session_id"], "live_url": s.get("replay_url") or s.get("live_url"), "statut": s.get("statut"),
        "acces_site": rep.get("acces_site"), "duree_s": s.get("duree_s"), "etapes": s.get("etapes"),
        "cout_credits": s.get("cout_total"), "erreur": s.get("erreur"), "reponse": rep or None,
        "nb_produits_attendus": s.get("nb_produits_attendus"), "nb_produits_corrects": s.get("nb_produits_corrects"),
        "format_respecte": s.get("format_respecte"), "termine_le": datetime.now(timezone.utc).isoformat()},
        conflit="session_id")
    if not ex:
        return
    designation = {p.ref: p.designation for p in chantier.produits}
    from marcel_core.chiffrage import complete
    base.inserer("releves", [{
        "execution_id": ex[0]["id"], "besoin_id": l.get("ref"), "produit_demande": designation.get(l.get("ref")),
        "produit": l.get("produit"), "prix_eur": l.get("prix_eur"), "unite": l.get("unite"), "stock": l.get("stock"),
        "en_stock": l.get("en_stock"), "delai_texte": l.get("delai_texte"), "delai_jours": l.get("delai_jours"),
        "lien": l.get("lien"), "image_url": l.get("image_url"), "valide": complete(l),
        "raisons": ["6 champs du format relevés"] if complete(l) else ["champ(s) manquant(s) dans le format fixe"]}
        for l in rep.get("lignes") or []])


def executer(chantier: Chantier, jobs, panier: bool, projet_id, skill) -> list:
    n = len(chantier.produits)
    max_steps, max_time = min(40 + 14 * n, 200), min(600 + 150 * n, 2400)
    sessions = []
    for i in range(0, len(jobs), PARALLELE):
        vague = []
        for f, agent in jobs[i:i + PARALLELE]:
            try:
                l = agents.lancer(consigne(chantier, chantier.fournisseurs[f], panier), ReleveFournisseur,
                                  max_steps, max_time, agent, fournisseur=f, chantier=chantier.nom)
                print(f"[{f} · {agent}] lancé — en direct : {l['live_url'] or l['session_id']}", flush=True)
                vague.append(l)
            except Exception as e:
                print(f"[{f} · {agent}] lancement impossible : {type(e).__name__}: {e}", flush=True)
                sessions.append({"fournisseur": f, "agent": agent, "statut": "exception", "erreur": str(e)[:300]})
        t0, en_cours = time.monotonic(), {l["session_id"] for l in vague}
        poll = max(30, 15 * len(vague))  # clé Free : 5 requêtes/min
        while en_cours and time.monotonic() - t0 < max_time + 180:
            time.sleep(poll)
            for sid in list(en_cours):
                try:
                    st = agents.statut(sid)
                except Exception as e:
                    print(f"  suivi indisponible ({type(e).__name__}), on retente", flush=True)
                    continue
                f = next(l["fournisseur"] for l in vague if l["session_id"] == sid)
                print(f"  [{f}] {st['statut']} — {st['etapes']} étapes — {round(time.monotonic() - t0)} s", flush=True)
                if st["termine"]:
                    en_cours.discard(sid)
        for l in vague:
            try:
                r = agents.recuperer(l["fournisseur"], l["session_id"], l["lance_le"], schema=ReleveFournisseur)
            except Exception as e:
                r = {"statut": "exception", "erreur": f"{type(e).__name__}: {e}"[:300], "session_id": l["session_id"]}
            s = {**l, **r, "reponse": r.get("rapport")}
            s.update(evaluer(chantier, s["reponse"]))
            sessions.append(s)
            print(f"[{l['fournisseur']} · {l['agent']}] fini : {s.get('statut')} — {s.get('duree_s')} s — "
                  f"{s['nb_produits_corrects']}/{s['nb_produits_attendus']} lignes complètes — format "
                  f"{'OK' if s['format_respecte'] else 'non respecté'} — coût {s.get('cout_total')}", flush=True)
            if projet_id:
                try:
                    enregistrer_session(s, chantier, projet_id, skill)
                except Exception as e:
                    print(f"  Supabase : écriture impossible ({type(e).__name__}: {e})", flush=True)
    return sessions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chantier")
    ap.add_argument("--fournisseurs", nargs="*")
    ap.add_argument("--agents", nargs="*", default=["h/web-surfer-flash"])
    ap.add_argument("--panier", action="store_true", help="ajouter au panier pour lire le délai (plus d'étapes)")
    ap.add_argument("--rejouer")
    ap.add_argument("-y", action="store_true")
    a = ap.parse_args()
    chantier = Chantier.model_validate_json(Path(a.chantier).read_text(encoding="utf-8"))
    projet_id = skill = None

    if a.rejouer:
        dossier = Path(a.rejouer)
        sessions = json.loads((dossier / "sessions.json").read_text(encoding="utf-8"))
    else:
        fours = [f for f in chantier.fournisseurs if not a.fournisseurs or f in a.fournisseurs]
        jobs = [(f, ag) for f in fours for ag in a.agents]
        print(f"{len(jobs)} session(s) H : {', '.join(f'{f}/{ag.split("/")[-1]}' for f, ag in jobs)} — "
              f"{len(chantier.produits)} produits. Supabase : {'oui' if base.actif() else 'non (clé absente)'}.")
        if not a.y and input("On y va ? [o/N] ").strip().lower() not in ("o", "oui", "y"):
            return
        if base.actif():
            try:
                base.inserer("fournisseurs", [{"id": f, "nom": f.capitalize(), "url": chantier.fournisseurs[f]} for f in fours],
                             conflit="id", ignorer_doublons=True)
                skill = base.skill_id("releve_prix")
                projet_id = base.inserer("projets", {"nom": chantier.nom, "email_artisan": chantier.email_artisan,
                                                     "texte": f"Chiffrage — {chantier.nom}", "code_postal": chantier.code_postal,
                                                     "besoins": [p.model_dump() for p in chantier.produits],
                                                     "statut": "en_recherche"})[0]["id"]
                print(f"Chantier enregistré dans Supabase : {projet_id}")
            except Exception as e:
                print(f"Supabase indisponible ({type(e).__name__}: {e}) : on continue sans.")
        sessions = executer(chantier, jobs, a.panier, projet_id, skill)
        dossier = ICI / "out" / f"chiffrage-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "sessions.json").write_text(json.dumps(sessions, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    s = synthese(chantier, sessions)
    md = synthese_md(s, sessions)
    (dossier / "synthese.md").write_text(md, encoding="utf-8")
    (dossier / "resultat.json").write_text(json.dumps(s, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if not a.rejouer and projet_id:
        try:
            base.modifier("projets", {"id": projet_id}, {"statut": "termine", "resultat": s,
                                                         "total_eur": s["total_meilleurs_prix_eur"]})
            print("Chantier passé à « termine » dans Supabase (déclencheur du mail).")
        except Exception as e:
            print(f"Supabase : mise à jour impossible ({type(e).__name__}: {e})")
    print("\n" + md + f"\n\nFichiers : {dossier}")


if __name__ == "__main__":
    main()
