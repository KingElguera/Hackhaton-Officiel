#!/usr/bin/env python3
"""Marcel — test Hugging Face (les deux usages prévus dans le projet).

  ping                 : vérifie que le token marche (1 petit appel texte)
  photo <image>        : lit la photo de la pièce → description structurée
  plan <dossier out/>  : à partir d'un vrai run H Company, rédige le guide
                         de travaux pour un bricoleur débutant

Le token est lu dans HF_TOKEN. Si les crédits viennent d'une organisation
(ex. celle du hackathon), mettre son nom dans HF_BILL_TO.
Chaque appel est loggué dans logs/hf.jsonl (modèle, durée, tokens, succès).
"""
import base64
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import InferenceClient

ICI = Path(__file__).parent
LOG = ICI / "logs" / "hf.jsonl"
MODELE = os.environ.get("HF_MODELE", "Qwen/Qwen3.8-27B")


def appeler(tache: str, messages: list, max_tokens: int = 1500) -> str:
    client = InferenceClient(bill_to=os.environ.get("HF_BILL_TO") or None)
    ligne = {"ts": datetime.now(timezone.utc).isoformat(), "tache": tache, "modele": MODELE}
    t0 = time.monotonic()
    try:
        # Qwen3 « réfléchit » avant de répondre : on coupe ce mode, sinon il épuise
        # max_tokens en réflexion et ne rédige jamais la réponse.
        r = client.chat_completion(model=MODELE, messages=messages, max_tokens=max_tokens, temperature=0.2,
                                   extra_body={"reasoning_effort": "none"})
        texte = r.choices[0].message.content or ""
        texte = re.sub(r"<think>.*?(</think>|$)", "", texte, flags=re.S).strip()
        u = getattr(r, "usage", None)
        ligne.update(succes=bool(texte), tokens_in=getattr(u, "prompt_tokens", None),
                     tokens_out=getattr(u, "completion_tokens", None),
                     fin=getattr(r.choices[0], "finish_reason", None))
        if not texte:
            ligne["erreur"] = f"réponse vide (fin = {ligne['fin']}, {ligne['tokens_out']} tokens)"
    except Exception as e:
        texte = ""
        ligne.update(succes=False, erreur=f"{type(e).__name__}: {e}"[:500])
    ligne["duree_s"] = round(time.monotonic() - t0, 1)
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    print(f"[{tache}] {MODELE} — {ligne['duree_s']} s — "
          + ("ok" if ligne["succes"] else ligne["erreur"]), file=sys.stderr)
    return texte


def extraire_json(texte: str):
    texte = re.sub(r"<think>.*?</think>", "", texte, flags=re.S)
    m = re.search(r"\{.*\}", texte, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def ping():
    print(appeler("ping", [{"role": "user", "content": "Réponds juste : Marcel est prêt."}], 50))


PROMPT_PHOTO = """Tu aides Marcel, un assistant de rénovation DIY. Voici la photo d'une pièce.
Dimensions données par l'utilisateur (ne les remets PAS en cause, ne mesure rien sur la photo) : {dims}.
Projet de l'utilisateur : {projet}.

Réponds UNIQUEMENT avec un objet JSON :
{{
  "type_piece": "...",
  "elements_visibles": ["..."],
  "etat_murs": "bon | à reboucher | à poncer | inconnu",
  "couleur_murs_actuelle": "...",
  "niche_visible": true/false,
  "preparation_conseillee": ["..."],
  "points_attention": ["..."],
  "confiance": "haute | moyenne | basse"
}}
N'invente rien : si un élément n'est pas visible, dis-le."""


def photo(chemin: str, dims: str = "chambre 10 m², niche 80 × 25 cm, 30 m² de murs",
          projet: str = "repeindre les murs en blanc et poser une étagère dans la niche"):
    p = Path(chemin)
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode()
    texte = appeler("photo", [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
        {"type": "text", "text": PROMPT_PHOTO.format(dims=dims, projet=projet)},
    ]}], 800)
    js = extraire_json(texte)
    print(json.dumps(js, ensure_ascii=False, indent=2) if js else texte)


PROMPT_PLAN = """Tu es Marcel, assistant de rénovation pour bricoleurs {niveau}s. Rédige en français un guide de travaux
clair et concret, à partir UNIQUEMENT des données vérifiées ci-dessous (n'invente aucun produit ni prix ni date).

Structure :
1. Résumé en 2 phrases (ce qu'on fait, total des achats comparé au budget max, date de fin).
2. Liste d'achats (produit, enseigne, quantité, prix) — reprends exactement les données.
3. Outils nécessaires non inclus dans la liste (à préciser comme « à prévoir si vous ne l'avez pas »).
4. Planning jour par jour en suivant l'ordre des travaux fourni, avec les étapes concrètes pour un {niveau}.
5. 3 conseils de sécurité.
N'ajoute aucune surface, pièce ou tâche qui n'est pas dans les données.

DONNÉES VÉRIFIÉES :
{donnees}"""


def plan(dossier: str):
    res = json.loads((Path(dossier) / "resultat.json").read_text(encoding="utf-8"))
    donnees = {
        "piece": res["cas"]["piece"], "niche": res["cas"]["niche"], "peinture": res["cas"]["peinture"],
        "surface_peinte": "murs uniquement (pas le plafond)",
        "budget_max_eur": res["cas"]["budget_eur"],
        "total_achats_eur": round(sum((c or {}).get("cout_eur") or 0 for c in res["choix"].values()), 2),
        "achats": {b: c and {k: c.get(k) for k in ("nom", "enseigne", "quantite", "prix_eur", "cout_eur", "dispo_mode", "url")}
                   for b, c in res["choix"].items()},
        "ordre_travaux": res["taches"],
    }
    texte = appeler("plan", [{"role": "user", "content": PROMPT_PLAN.format(
        niveau=res["cas"]["niveau"], donnees=json.dumps(donnees, ensure_ascii=False, default=str))}], 4000)
    texte = re.sub(r"<think>.*?</think>", "", texte, flags=re.S).strip()
    if not texte:
        print("Aucun guide généré (voir l'erreur ci-dessus) : rien n'a été enregistré.", file=sys.stderr)
        sys.exit(1)
    (Path(dossier) / "guide.md").write_text(texte, encoding="utf-8")
    print(texte)
    print(f"\n→ enregistré dans {Path(dossier) / 'guide.md'}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("ping", "photo", "plan"):
        print(__doc__)
        sys.exit(1)
    if not os.environ.get("HF_TOKEN"):
        print("HF_TOKEN manquant : ajoute-le dans ~/.zshrc puis `source ~/.zshrc`.")
        sys.exit(1)
    {"ping": ping, "photo": photo, "plan": plan}[sys.argv[1]](*sys.argv[2:])
