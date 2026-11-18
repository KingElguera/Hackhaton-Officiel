#!/usr/bin/env python3
"""Marcel — vérifie en une commande que Hugging Face est prêt, et dit quoi faire sinon.

    uv run --group outils hf_verif.py

Quatre contrôles, en français, sans rien modifier :
  1. la clé HF_TOKEN est-elle là ?
  2. est-elle valide, et à quel compte appartient-elle ?
  3. le modèle de texte et d'image (Qwen) répond-il ? (un appel minuscule, moins d'un centime)
  4. les Spaces TRELLIS, qui fabriquent les meubles en 3D, sont-ils allumés ?
"""
import os
import sys
import time

OK, KO, INFO = "  ✓", "  ✗", "  ·"
PAGE_CLE = "https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained"
SPACES = {"TRELLIS.2": "microsoft/TRELLIS.2", "TRELLIS v1 (secours)": "trellis-community/TRELLIS"}


def main() -> int:
    pb = 0
    print("1. La clé Hugging Face")
    tok = os.environ.get("HF_TOKEN")
    if not tok:
        print(f"{KO} HF_TOKEN n'est pas définie.")
        print(f"{INFO} La créer ici (2 clics) : {PAGE_CLE}")
        print(f"{INFO} Puis lancer ./demarrer.sh : il la demande une fois et la range dans .env, hors du dépôt.")
        return 1
    print(f"{OK} HF_TOKEN est définie ({len(tok)} caractères).")

    print("2. Le compte")
    from huggingface_hub import HfApi
    api = HfApi(token=tok)
    try:
        moi = api.whoami()
        orgs = [o.get("name") for o in moi.get("orgs", [])]
        print(f"{OK} Clé valide, compte « {moi.get('name')} »" + (" (PRO)" if moi.get("isPro") else "") + ".")
        print(f"{INFO} Organisations : {', '.join(orgs) if orgs else 'aucune'}.")
        facture = os.environ.get("HF_BILL_TO")
        if facture:
            print(f"{INFO} Les appels sont facturés à « {facture} » (HF_BILL_TO).")
            if facture not in orgs:
                print(f"{KO} Ce compte n'est pas membre de « {facture} » : les appels seront refusés."); pb += 1
        else:
            print(f"{INFO} Les appels sont facturés à ce compte. Si les crédits du hackathon sont sur une organisation,")
            print("    mettre son nom dans HF_BILL_TO (fichier .env).")
    except Exception as e:
        print(f"{KO} Clé refusée : {type(e).__name__}: {str(e)[:160]}")
        print(f"{INFO} En recréer une : {PAGE_CLE}")
        return 1

    print("3. Le modèle qui lit les photos et rédige")
    try:
        from marcel_core import hf
        r = hf.chat([{"role": "user", "content": "Réponds uniquement par le mot : prêt"}], 20)
        print(f"{OK} {hf.MODELE} répond en {r['duree_s']} s : « {r['texte'][:40]} »")
    except Exception as e:
        pb += 1
        msg = str(e)
        print(f"{KO} {type(e).__name__}: {msg[:200]}")
        if "402" in msg or "credit" in msg.lower() or "payment" in msg.lower():
            print(f"{INFO} Plus de crédits sur ce compte : vérifier où sont les crédits du hackathon (HF_BILL_TO).")
        elif "401" in msg or "403" in msg:
            print(f"{INFO} La clé n'a pas le droit d'appeler les modèles : la recréer avec la permission « Inference Providers ».")

    print("4. Les modèles 3D (meubles)")
    for nom, space in SPACES.items():
        try:
            etat = api.space_info(space).runtime
            stade = getattr(etat, "stage", None) or "inconnu"
            if str(stade).upper() == "RUNNING":
                print(f"{OK} {nom} est allumé.")
            else:
                print(f"{KO} {nom} est à l'état « {stade} » : les meubles en 3D ne passeront pas pour l'instant."); pb += 1
        except Exception as e:
            print(f"{KO} {nom} : {type(e).__name__}: {str(e)[:120]}"); pb += 1
    print(f"{INFO} Le quota GPU gratuit est de quelques générations par jour. Les objets déjà faits restent en cache dans objets3d/.")

    print()
    if pb:
        print(f"{pb} point(s) à régler ci-dessus. Le reste fonctionne.")
        return 2
    print("Tout est prêt côté Hugging Face.")
    return 0


if __name__ == "__main__":
    t = time.monotonic()
    code = main()
    print(f"(vérification en {time.monotonic() - t:.1f} s)")
    sys.exit(code)
