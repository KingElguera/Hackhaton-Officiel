#!/usr/bin/env python3
"""Génère supabase/donnees_tests.sql : tous nos résultats de tests, prêts à coller dans Supabase.

Sources : logs/runs.jsonl (sessions H), out/20261117-132747/ (parcours n°1), essais Hugging Face (RETOURS.md).
    uv run supabase/generer_donnees.py
"""
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent.parent
REPO = "https://github.com/KingElguera/Hackhaton-Officiel/blob/main"
RAW = "https://raw.githubusercontent.com/KingElguera/Hackhaton-Officiel/main"
PROJET_ID = "a1b2c3d4-0000-4000-8000-000000017001"   # projet « chambre » du 17/11
CHAMPS_TEST = ["prix_eur", "dimensions", "stock_magasin", "delai_livraison"]


def q(v):
    """Valeur SQL sûre (dollar-quoting pour le texte et le JSON)."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (dict, list)):
        return f"$j${json.dumps(v, ensure_ascii=False, default=str)}$j$::jsonb"
    return f"$t${v}$t$"


def insert(table, rows, conflit):
    if not rows:
        return ""
    cols = list(rows[0])
    vals = ",\n".join("  (" + ", ".join(r[c] if isinstance(r[c], str) and r[c].startswith("(select") else q(r[c])
                                        for c in cols) + ")" for r in rows)
    if conflit is None:
        return f"insert into public.{table} ({', '.join(cols)}) values\n{vals}"
    return f"insert into public.{table} ({', '.join(cols)}) values\n{vals}\non conflict {conflit} do nothing;\n\n"


def une_seule_fois(condition_existe, insertion):
    """Insertion protégée : ne s'exécute pas si les lignes sont déjà là (tables sans clé naturelle)."""
    return f"do $do$ begin\nif not exists ({condition_existe}) then\n{insertion};\nend if;\nend $do$;\n\n"


def skill(nom):
    return f"(select id from public.skills where nom = '{nom}')"


def exec_id(session_id):
    return f"(select id from public.executions where session_id = '{session_id}')"


def main():
    lignes = [json.loads(l) for l in (ICI / "logs" / "runs.jsonl").read_text().splitlines() if l.strip()]
    # fusion des doublons (le parcours n°1 a été relu par l'API le 18/11)
    sessions = {}
    for l in lignes:
        if not l.get("session_id"):
            continue
        prec = sessions.get(l["session_id"], {})
        sessions[l["session_id"]] = {**l, **{k: v for k, v in prec.items() if v is not None}}

    res1 = json.loads((ICI / "out" / "20261117-132747" / "resultat.json").read_text())
    verdicts = {(c["enseigne"], c["nom"]): c for c in res1["candidats"]}

    executions, releves = [], []
    for sid, l in sessions.items():
        rap = l.get("rapport") if isinstance(l.get("rapport"), dict) else {}
        parcours = l.get("type") == "parcours"
        e = {"created_at": l["ts"], "projet_id": PROJET_ID if parcours else None,
             "skill_id": skill("parcours_marcel" if parcours else "test_acces"),
             "fournisseur_id": l["enseigne"], "agent": l.get("agent") or "h/web-surfer-flash", "session_id": sid,
             "live_url": l.get("replay_url"), "statut": l.get("statut"), "acces_site": rap.get("acces_site"),
             "duree_s": l.get("duree_s"), "etapes": l.get("etapes"), "cout_credits": l.get("cout_total"),
             "erreur": l.get("erreur"), "reponse": rap or None, "format_respecte": bool(rap.get("acces_site"))}
        if parcours:
            prods = rap.get("produits") or []
            e["nb_produits_attendus"] = len(prods)
            e["nb_produits_corrects"] = sum(1 for p in prods if verdicts.get((l["enseigne"], p["nom"]), {}).get("valide"))
            for p in prods:
                v = verdicts.get((l["enseigne"], p["nom"]), {})
                releves.append({"execution_id": exec_id(sid), "besoin_id": p.get("besoin"), "produit_demande": p.get("besoin"),
                                "produit": p.get("nom"), "prix_eur": p.get("prix_eur"),
                                "unite": f"pot {p['volume_l']:g} L" if p.get("volume_l") else "pièce",
                                "stock": p.get("stock_texte"), "en_stock": p.get("en_stock_magasin"),
                                "delai_texte": p.get("delai_livraison_texte"), "delai_jours": p.get("delai_livraison_jours"),
                                "lien": p.get("url"), "largeur_mm": p.get("largeur_mm"), "profondeur_mm": p.get("profondeur_mm"),
                                "hauteur_mm": p.get("hauteur_mm"), "valide": v.get("valide"), "raisons": v.get("raisons")})
        else:
            manquants = [c for c in CHAMPS_TEST if rap.get(c) in (None, "")]
            bloque = rap.get("acces_site") == "bloque"
            e["nb_produits_attendus"] = 1
            e["nb_produits_corrects"] = 0 if bloque or manquants else 1
            e["reponse"] = dict(rap, champs_manquants=manquants,
                                verdict_code="bloque" if bloque else ("ok" if not manquants else "partiel"))
            if not bloque and rap.get("produit"):
                releves.append({"execution_id": exec_id(sid), "besoin_id": None, "produit_demande": "étagère murale",
                                "produit": rap.get("produit"), "prix_eur": rap.get("prix_eur"), "unite": "pièce",
                                "stock": rap.get("stock_magasin"), "en_stock": None, "delai_texte": rap.get("delai_livraison"),
                                "delai_jours": None, "lien": rap.get("url_produit"), "largeur_mm": None,
                                "profondeur_mm": None, "hauteur_mm": None, "valide": not manquants,
                                "raisons": [f"champs manquants : {', '.join(manquants)}"] if manquants else ["4 champs relevés"]})
        executions.append(e)

    cas = res1["cas"]
    projets = [{"id": PROJET_ID, "created_at": "2026-11-17T12:27:47+00:00",
                "texte": "Étagère dans la niche de la chambre (80 × 25 cm) + repeindre 30 m² de murs en blanc",
                "photo_url": None, "code_postal": cas["code_postal"], "budget_eur": cas["budget_eur"], "niveau": cas["niveau"],
                "emplacement": cas["niche"], "besoins": [{"id": "etagere", "famille": "objet"},
                                                         {"id": "peinture", "famille": "surface", **cas["peinture"]}],
                "hors_perimetre": [], "statut": "termine",
                "resultat": {"choix": res1["choix"], "taches": res1["taches"]}, "total_eur": 77.89, "fin_travaux": "2026-11-24"}]

    E = lambda tache, plateforme, modele, demande, utilisable, duree, cout, faux, capture, note, ts="2026-11-17T17:00:00+00:00": {
        "created_at": ts, "tache": tache, "plateforme": plateforme, "modele": modele, "demande": demande,
        "utilisable": utilisable, "duree_s": duree, "cout": cout, "ce_qui_est_faux": faux, "capture_url": capture,
        "note_sur_5": note, "details": {"source": "import_tests_17_18_11"}}
    HFI, HFS, H = "Hugging Face Inference Providers", "Hugging Face Spaces (ZeroGPU)", "H Company"
    photo_produit = "photo produit IKEA KLAVRESTRÖM (fond blanc)"
    essais = [
        E("relevé de prix (accès enseignes)", H, "h/web-surfer-flash", "1 produit, prix + dimensions + stock + délai, sur 5 enseignes",
          True, 68.2, "~0,17 crédit H (5 sessions)", "Leroy Merlin et ManoMano bloqués par CAPTCHA ; délai IKEA/Bricorama visible seulement au panier ; unité 18 cm au lieu de 18 mm (Castorama)",
          f"{REPO}/RETOURS.md", 4, "2026-11-17T09:00:00+00:00"),
        E("parcours complet", H, "h/web-surfer-flash", "étagère pour niche 800×250 mm + peinture 30 m², Castorama + IKEA",
          True, 303.3, "~0,29 crédit H (2 sessions)", "a proposé des étagères de 800 mm (rejetées par le code) ; stock IKEA annoncé sans texte affiché",
          f"{REPO}/out/20261117-132747/rapport.md", 4, "2026-11-17T12:30:00+00:00"),
        E("relevé de prix", H, "h/web-surfer-pro", "à faire le 18/11 : mêmes 5 produits que flash", None, None, None, None, None, None,
          "2026-11-18T09:00:00+00:00"),
        E("guide de travaux", HFI, "Qwen/Qwen3.8-27B", "rédiger le guide à partir des données vérifiées du parcours n°1",
          True, 3.7, "~1 700 tokens (quelques centimes)", "réponse vide tant que le mode réflexion est actif (corrigé : reasoning_effort=none) ; 1re version : « budget 150 € » au lieu de 77,89 € et plafond inventé (corrigé en lui donnant le total)",
          f"{REPO}/out/20261117-132747/guide.md", 4),
        E("lecture photo", HFI, "Qwen/Qwen3.8-27B", "décrire la photo (couloir) alors que la consigne annonce une chambre avec niche",
          True, 3.1, "quelques centimes", "oubli de la prise électrique ; conseil « sous-couche » générique. Pas influencé par la consigne : « couloir », « niche non visible »",
          f"{REPO}/test3d/piece.jpg", 4),
        E("comprendre la demande", HFI, "Qwen/Qwen3.8-27B", "photo + « canapé 3 places + peinture vert sauge + robinet » + mesures",
          True, 3.5, "quelques centimes", "catégorie vague (« meuble ») et question redondante (corrigés dans la consigne) ; robinet bien mis hors périmètre",
          None, 4, "2026-11-18T08:30:00+00:00"),
        E("image → 3D", HFS, "stabilityai/stable-fast-3d", photo_produit, False, 2.4, "quota gratuit", "erreur interne du Space", None, 0),
        E("image → 3D", HFS, "tencent/Hunyuan3D-2", photo_produit, True, 12.4, "quota gratuit",
          "pas de texture (module en panne) ; forme la plus fidèle (3,9 % d'écart)", f"{REPO}/test3d/bench/web/hunyuan2.glb", 4),
        E("image → 3D", HFS, "tencent/Hunyuan3D-2.1", photo_produit, False, 29.2, "quota gratuit",
          "plateau parasite collé à l'objet (138 % d'écart) ; texture refusée (quota)", f"{REPO}/test3d/bench/web/hunyuan21.glb", 1),
        E("image → 3D", HFS, "microsoft/TRELLIS.2", photo_produit, True, 37.3, "quota gratuit",
          "7,6 % d'écart de proportions (corrigé par la remise à l'échelle du code)", f"{REPO}/test3d/bench/web/trellis2.glb", 4),
        E("image → 3D", HFS, "trellis-community/TRELLIS (v1)", photo_produit, True, 26.5, "quota gratuit",
          "8,5 % d'écart de proportions ; très léger (0,2 Mo) : idéal web et réalité augmentée", f"{REPO}/test3d/bench/web/trellis1.glb", 4),
        E("image → 3D", HFS, "VAST-AI/TripoSG", photo_produit, False, 9.1, "quota gratuit", "erreur interne du Space", None, 0),
        E("image → 3D", HFS, "Wuvin/Unique3D", photo_produit, None, None, "quota gratuit", "non testé : quota ZeroGPU épuisé", None, None),
        E("insertion photo", "code (sans IA)", "collage à l'échelle + ombre calculée", "étagère 60 cm dans une zone de 68 cm (échelle par la porte)",
          True, 0.1, "0", "effet « collage » (photo produit vue de 3/4)", f"{REPO}/test3d/insertion/planche2.jpg", 3),
        E("insertion photo", HFI, "Qwen/Qwen-Image-Edit-2511", "harmoniser l'étagère collée par le code", False, 89.7, "quelques centimes",
          "photo recadrée en carré, rendu dessin, gros plan", f"{REPO}/test3d/insertion/planche.jpg", 0),
        E("insertion photo", HFI, "black-forest-labs/FLUX.1-Kontext-dev", "harmoniser l'étagère collée par le code", False, 18.6, "quelques centimes",
          "a remplacé l'étagère par un autre meuble (caisson)", f"{REPO}/test3d/insertion/planche.jpg", 2),
        E("insertion photo", HFI, "black-forest-labs/FLUX.1-Kontext-dev (consigne stricte)", "garder l'étagère identique, ajouter seulement l'ombre",
          False, 18.4, "quelques centimes", "bon produit mais ~2,5× trop grand", f"{REPO}/test3d/insertion/planche2.jpg", 2),
        E("insertion photo", HFI, "Qwen/Qwen-Image-Edit-2511 (libre)", "ajouter une étagère de 60 cm entre le coin et la porte", False, 15.1,
          "quelques centimes", "couleurs saturées vert/orange, étagère générique mal placée", f"{REPO}/test3d/insertion/planche.jpg", 0),
        E("insertion photo", HFI, "black-forest-labs/FLUX.1-Kontext-dev (libre)", "ajouter une étagère de 60 cm entre le coin et la porte", False, 18.1,
          "quelques centimes", "photo préservée mais étagère générique, trop grande et mal placée", f"{REPO}/test3d/insertion/planche.jpg", 1),
    ]
    modeles = [{"produit_lien": "https://www.ikea.com/fr/fr/p/klavrestroem-etagere-murale-chene-30601689/",
                "glb_url": f"{RAW}/test3d/bench/web/trellis1.glb", "modele": "TRELLIS v1", "duree_s": 26.5}]

    sql = ("-- Marcel — nos résultats de tests (17–18/11), généré par supabase/generer_donnees.py\n"
           "-- À coller dans Supabase → SQL Editor APRÈS schema.sql. Ré-exécutable sans doublons.\n\n"
           + insert("projets", projets, "(id)")
           + insert("executions", executions, "(session_id)")
           + "-- relevés et essais : insérés une seule fois (pas de doublons si on relance le fichier)\n"
           + une_seule_fois("select 1 from public.releves r join public.executions e on e.id = r.execution_id "
                            f"where e.session_id in ({', '.join(repr(s) for s in sessions)})",
                            insert("releves", releves, None))
           + insert("modeles_3d", modeles, "(produit_lien)")
           + une_seule_fois("select 1 from public.essais where details->>'source' = 'import_tests_17_18_11'",
                            insert("essais", essais, None)))
    out = ICI / "supabase" / "donnees_tests.sql"
    out.write_text(sql, encoding="utf-8")
    print(f"{out} : {len(projets)} projet, {len(executions)} exécutions, {len(releves)} relevés, "
          f"{len(modeles)} modèle 3D, {len(essais)} essais")


if __name__ == "__main__":
    main()
