# Marcel — agent de rénovation DIY

Hackathon Build The Future (H Company × Vercel × Eugenia School), équipe 15.

Marcel envoie des agents **H Company** sur les sites des enseignes (Castorama, IKEA) pour relever le prix, les dimensions,
le stock et le délai de livraison. **Notre code** vérifie que les produits rentrent dans la pièce, choisit les produits,
contrôle le budget et date les travaux. **Hugging Face** lit la photo de la pièce, rédige le guide de travaux et génère les objets 3D.
L'agent s'arrête toujours avant le paiement.

## Installation
```bash
brew install uv            # une fois
uv sync                    # installe les dépendances (Python 3.12)
uv sync --group outils     # + outils 3D / images (scripts test3d, bench3d, insertion)
```
Clés dans les variables d'environnement, **jamais dans le repo** : `HAI_API_KEY` (H Company), `HF_TOKEN` (Hugging Face, preset Inference).

## Back en ligne (API pour le front)
- Code : `api/index.py` (FastAPI, fonctions Python Vercel) + `marcel_core/` (cœur partagé).
- Contrat front ↔ back : **[docs/API_FRONT.md](docs/API_FRONT.md)**.
- Lancer en local : `uv run uvicorn api.index:app --port 8787` puis `curl localhost:8787/api/sante`.
- Vercel : variables d'environnement `HAI_API_KEY` et `HF_TOKEN` à saisir dans le projet Vercel (jamais dans le code).

## Scripts
| Commande | Rôle |
|---|---|
| `uv run test_enseignes.py ikea` | teste l'accès d'un agent H à une enseigne |
| `uv run marcel.py` | parcours complet sur `cas/chambre.json` → `out/<date>/` (rapport, résultat) |
| `uv run marcel.py --rejouer out/<date>` | recalcule sans relancer d'agent |
| `uv run hf_test.py plan out/<date>` | guide de travaux rédigé par Hugging Face |
| `uv run hf_test.py photo <image>` | description de la photo de la pièce |
| `uv run --group outils test3d.py test3d/etagere.jpg --modele trellis` | objet 3D du produit, remis à l'échelle, posé dans la niche |
| `uv run --group outils bench3d.py test3d/etagere.jpg` | comparatif des modèles image → 3D |
| `uv run --group outils insertion.py` | test d'insertion du produit dans la photo |
| `uv run --group outils meuble3d.py photo.jpg --largeur 210` | photo d'un meuble → objet 3D à l'échelle (TRELLIS), mis en cache dans `objets3d/` |
| `uv run --group outils atelier.py` | l'atelier : surveille la file des rendus, déclenche TRELLIS puis Blender, dépose les images (`--fichier cas/rendu_chambre.json` pour essayer sans Supabase) |
| `Blender --background --python rendu/marcel_rendu.py -- rendu/chantier_exemple.json out/rendu` | fichier de chantier → photos et panorama à 360° de la pièce (voir [docs/MEUBLES_3D.md](docs/MEUBLES_3D.md)) |

## Logo
Le logo (un raton laveur) et ses trois animations de chargement sont dans **[assets/logo/](assets/logo/README.md)**, en SVG, prêts pour le site.

## Logo
Le logo (un raton laveur) et ses trois animations de chargement sont dans **[assets/logo/](assets/logo/README.md)**, en SVG, prêts pour le site.

## Résultats et retours sur l'API
Voir **[RETOURS.md](RETOURS.md)** : accès des enseignes, parcours complet, Hugging Face, comparatif 3D, insertion photo, retours sur l'Agent API.
