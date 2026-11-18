#!/usr/bin/env python3
"""Marcel — l'atelier : le programme qui déclenche TRELLIS puis Blender dès qu'un rendu est demandé.

Il tourne sur un poste où Blender est installé (pas sur Vercel). Il va chercher lui-même le travail
dans Supabase : personne n'a besoin de joindre ce poste depuis internet.

    # En continu : surveille la file « rendus » de Supabase
    uv run --group outils atelier.py

    # Une seule demande de la file, puis s'arrête
    uv run --group outils atelier.py --une-fois

    # Sans Supabase : traite un fichier de demande et range les images dans out/atelier/
    uv run --group outils atelier.py --fichier cas/rendu_chambre.json

Variables d'environnement : SUPABASE_URL, SUPABASE_SERVICE_KEY, HF_TOKEN.
Facultatif : BLENDER (chemin du programme), N8N_WEBHOOK_RENDU (prévenu quand un rendu est fini).
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from marcel_core import rendus

ICI = Path(__file__).parent
TRAVAIL = ICI / "out" / "atelier"


def prevenir(charge: dict):
    """Prévient n8n qu'un rendu est terminé (c'est lui qui envoie le mail). Un échec ici n'arrête rien."""
    url = os.environ.get("N8N_WEBHOOK_RENDU")
    if not url:
        return
    try:
        req = urllib.request.Request(url, data=json.dumps(charge).encode(), method="POST", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"[atelier] n8n non prévenu : {type(e).__name__}: {e}", flush=True)


def traiter_ligne(ligne: dict, modele: str) -> bool:
    rid = ligne["id"]
    dossier = TRAVAIL / rid
    print(f"[atelier] rendu {rid} : début", flush=True)
    try:
        demande = rendus.DemandeRendu.model_validate(ligne["demande"])
        res = rendus.traiter(demande, dossier, modele)
        for img in res["images"]:
            img["url"] = rendus.deposer(dossier / img["fichier"], f"{rid}/{img['fichier']}")
        for m in res["meubles_3d"]:
            if m.get("fichier"):
                m["url"] = rendus.deposer(Path(m["fichier"]), Path(m["fichier"]).name, seau="objets3d")
                m.pop("fichier")
        res.pop("dossier", None)
        rendus.terminer(rid, res)
        if ligne.get("projet_id"):  # le site lit les images dans le résultat du chantier
            try:
                rendus.noter_visuel(ligne["projet_id"], rid, "fait", res["images"], res["alertes"])
            except Exception as e:
                print(f"[atelier] visuel non rangé dans le chantier : {type(e).__name__}: {e}", flush=True)
        print(f"[atelier] rendu {rid} : fait en {res['total_secondes']} s — {len(res['images'])} image(s), {len(res['alertes'])} alerte(s)", flush=True)
        prevenir({"rendu_id": rid, "projet_id": ligne.get("projet_id"), "etat": "fait", "images": res["images"]})
        return True
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        print(f"[atelier] rendu {rid} : échec — {msg[:300]}", flush=True)
        try:
            rendus.echouer(rid, msg)
        except Exception as e2:
            print(f"[atelier] impossible de noter l'échec : {e2}", flush=True)
        prevenir({"rendu_id": rid, "projet_id": ligne.get("projet_id"), "etat": "echec", "erreur": msg[:300]})
        return False


def main():
    a = argparse.ArgumentParser(description="Atelier Marcel : déclenche TRELLIS et Blender")
    a.add_argument("--fichier", help="traite ce fichier de demande, sans Supabase")
    a.add_argument("--une-fois", action="store_true", help="traite une demande de la file puis s'arrête")
    a.add_argument("--pause", type=float, default=5, help="secondes entre deux regards sur la file")
    a.add_argument("--modele", default="trellis2", choices=["trellis2", "trellis1"])
    args = a.parse_args()

    try:
        print(f"[atelier] Blender : {rendus.blender()}", flush=True)
    except FileNotFoundError as e:
        raise SystemExit(f"[atelier] {e}")

    if args.fichier:
        demande = rendus.DemandeRendu.model_validate(json.loads(Path(args.fichier).read_text(encoding="utf-8")))
        dossier = TRAVAIL / ("local-" + time.strftime("%Y%m%d-%H%M%S"))
        try:
            res = rendus.traiter(demande, dossier, args.modele)
        except ValueError as e:
            raise SystemExit(f"[atelier] {e}")
        (dossier / "resultat.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    try:
        rendus._config()
    except rendus.SupabaseAbsent as e:
        raise SystemExit(f"[atelier] {e}. Pour essayer sans Supabase : --fichier cas/rendu_chambre.json")
    print("[atelier] en attente de rendus (Ctrl+C pour arrêter)…", flush=True)
    while True:
        try:
            ligne = rendus.prendre()
        except Exception as e:
            print(f"[atelier] file illisible : {type(e).__name__}: {e}", flush=True)
            ligne = None
        if ligne:
            traiter_ligne(ligne, args.modele)
            if args.une_fois:
                return
        elif args.une_fois:
            print("[atelier] rien à faire", flush=True)
            return
        else:
            time.sleep(args.pause)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
