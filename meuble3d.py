#!/usr/bin/env python3
"""Marcel — une photo de meuble → un objet 3D à l'échelle (TRELLIS, Space Hugging Face).

Le modèle donne la forme et la texture. Les dimensions sont celles que vous donnez, en centimètres.
Le résultat est mis en cache dans objets3d/ : relancer la commande sur la même photo ne consomme pas de quota.

    uv run --group outils meuble3d.py test3d/etagere.jpg --largeur 60 --profondeur 17 --hauteur 20
    uv run --group outils meuble3d.py canape.jpg --largeur 210                      # proportions du modèle
    uv run --group outils meuble3d.py canape.jpg --largeur 210 --mur fond --position 0.5
    uv run --group outils meuble3d.py test3d/etagere.jpg --largeur 60 --profondeur 17 --hauteur 20 \\
        --brut test3d/trellis_brut.glb                                               # sans appeler le modèle

Avec --mur, la commande affiche aussi la ligne à ajouter aux « meubles » du fichier de chantier
lu par rendu/marcel_rendu.py (Blender).
"""
import argparse
import json
import sys

from marcel_core import objets3d


def main():
    a = argparse.ArgumentParser(description="Photo de meuble → objet 3D à l'échelle")
    a.add_argument("photo", help="fichier image ou lien vers l'image")
    a.add_argument("--largeur", type=float, required=True, help="largeur réelle du meuble, en cm (obligatoire)")
    a.add_argument("--profondeur", type=float, help="profondeur réelle, en cm")
    a.add_argument("--hauteur", type=float, help="hauteur réelle, en cm")
    a.add_argument("--modele", default="trellis2", choices=list(objets3d.MODELES))
    a.add_argument("--brut", help="fichier .glb déjà sorti par le modèle : refait seulement la mise à l'échelle")
    a.add_argument("--regenerer", action="store_true", help="ignore le cache et relance le modèle")
    a.add_argument("--mur", choices=["fond", "avant", "gauche", "droit"], help="mur contre lequel poser le meuble")
    a.add_argument("--position", type=float, help="distance en m entre le coin gauche du mur et le meuble")
    a.add_argument("--pose", type=float, default=0.0, help="hauteur de pose en m (étagère murale : 1.2)")
    a.add_argument("--nom", help="nom du meuble dans le chantier")
    args = a.parse_args()

    def mm(cm):
        return cm * 10 if cm else None

    try:
        r = objets3d.objet_3d(args.photo, mm(args.largeur), mm(args.profondeur), mm(args.hauteur),
                              modele=args.modele, brut=args.brut, regenerer=args.regenerer)
    except (ValueError, FileNotFoundError) as e:
        print(f"[3d] {e}", file=sys.stderr)
        raise SystemExit(1)
    except objets3d.QuotaGPU as e:
        print(f"[3d] {e}\n     Réessayer plus tard, ou utiliser un compte Hugging Face avec plus de quota.", file=sys.stderr)
        raise SystemExit(2)
    d = r["dimensions_mm"]
    origine = "cache" if r["depuis_cache"] else (f"{r['duree_generation_s']} s" if r["duree_generation_s"] else "fichier fourni")
    print(f"[3d] {r['nom_modele']} — {origine} — {d['largeur'] / 10:g} × {d['profondeur'] / 10:g} × {d['hauteur'] / 10:g} cm "
          f"— {r['faces']} faces, {r['taille_mo']} Mo — mise à l'échelle {r['mise_a_echelle']}")
    if r["ecart_proportions_pct"] is not None:
        print(f"     écart de proportions modèle / réel : {r['ecart_proportions_pct']} %")
    for al in r["alertes"]:
        print(f"     ⚠ {al}")
    print(f"→ {r['fichier']}")
    if args.mur:
        print("À ajouter aux « meubles » du chantier :")
        print(json.dumps(objets3d.entree_chantier(r, args.mur, args.position, args.nom, args.pose), ensure_ascii=False))


if __name__ == "__main__":
    main()
