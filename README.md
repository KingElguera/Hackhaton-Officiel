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
```
Clés dans les variables d'environnement, **jamais dans le repo** : `HAI_API_KEY` (H Company), `HF_TOKEN` (Hugging Face, preset Inference).

## Scripts
| Commande | Rôle |
|---|---|
| `uv run test_enseignes.py ikea` | teste l'accès d'un agent H à une enseigne |
| `uv run marcel.py` | parcours complet sur `cas/chambre.json` → `out/<date>/` (rapport, résultat) |
| `uv run marcel.py --rejouer out/<date>` | recalcule sans relancer d'agent |
| `uv run hf_test.py plan out/<date>` | guide de travaux rédigé par Hugging Face |
| `uv run hf_test.py photo <image>` | description de la photo de la pièce |
| `uv run test3d.py test3d/etagere.jpg --modele trellis` | objet 3D du produit, remis à l'échelle, posé dans la niche |
| `uv run bench3d.py test3d/etagere.jpg` | comparatif des modèles image → 3D |
| `uv run insertion.py` | test d'insertion du produit dans la photo |

## Résultats et retours sur l'API
Voir **[RETOURS.md](RETOURS.md)** : accès des enseignes, parcours complet, Hugging Face, comparatif 3D, insertion photo, retours sur l'Agent API.
