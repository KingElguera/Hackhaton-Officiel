# Meubles en 3D et rendu de la pièce

Deux briques, qui tournent **hors de Vercel** (sur un poste ou un serveur avec Python et Blender) :

1. `meuble3d.py` — une photo de meuble → un objet 3D à l'échelle, avec TRELLIS (Space Hugging Face).
2. `rendu/marcel_rendu.py` — un fichier de chantier → des photos et un panorama à 360°, avec Blender.

```
photo du meuble + largeur ──► meuble3d.py ──► objets3d/<clé>_<dimensions>.glb
                                                   │
fichier de chantier (dimensions, peinture, sol, ───┴──► rendu/marcel_rendu.py ──► photo1.png, photo2.png,
ouvertures, meubles)                                                              dessus.png, panorama_360.jpg
```

## 1. Photo de meuble → objet 3D

```bash
uv sync --group outils
export HF_TOKEN=...            # jamais dans le dépôt

# Les trois dimensions connues : mise à l'échelle exacte
uv run --group outils meuble3d.py test3d/etagere.jpg --largeur 60 --profondeur 17 --hauteur 20

# Seule la largeur connue : les proportions du modèle sont gardées
uv run --group outils meuble3d.py canape.jpg --largeur 210

# Avec le mur : affiche la ligne à coller dans les « meubles » du chantier
uv run --group outils meuble3d.py canape.jpg --largeur 210 --mur fond --position 0.5
```

Les dimensions sont en **centimètres**. La largeur est obligatoire : le modèle ne connaît pas les vraies mesures.

| Option | Rôle |
|---|---|
| `--modele trellis2` (défaut) ou `trellis1` | TRELLIS.2 : rendu le plus riche, ~37 s. TRELLIS v1 : fichier léger, ~27 s |
| `--brut fichier.glb` | refait seulement la mise à l'échelle, sans appeler le modèle |
| `--regenerer` | ignore le cache et relance le modèle |
| `--mur`, `--position`, `--pose` | mur, distance au coin gauche (m), hauteur de pose (m) pour un élément mural |

Ce que fait le code, dans `marcel_core/objets3d.py` :

- **Cache par photo.** Le fichier brut du modèle est gardé dans `objets3d/` sous l'empreinte de la photo.
  Relancer la commande, ou changer les dimensions, ne consomme pas de quota GPU.
- **Modèle de secours.** Si TRELLIS.2 échoue pour une autre raison que le quota, TRELLIS v1 est essayé.
- **Quota.** Si le quota GPU du compte est épuisé, la commande s'arrête avec un message clair (code de sortie 2).
- **Mise à l'échelle.** L'objet sort centré, posé au sol, en mètres. La texture est conservée.
- **Contrôle.** L'écart entre les proportions du modèle et les vraies dimensions est calculé.
  Au-delà de 25 %, une alerte demande de vérifier que l'objet ressemble bien au meuble.
- **Journal.** Chaque appel au modèle est noté dans `logs/hf.jsonl`, comme les autres essais.

Depuis du code Python :

```python
from marcel_core import objets3d
r = objets3d.objet_3d("canape.jpg", largeur_mm=2100)
meuble = objets3d.entree_chantier(r, mur="fond", position_m=0.5)
```

## 2. Fichier de chantier → images

```bash
# régénère l'objet 3D de l'exemple à partir d'un fichier déjà dans le dépôt (aucun appel au modèle)
uv run --group outils meuble3d.py test3d/etagere.jpg --largeur 60 --profondeur 17 --hauteur 20 --brut test3d/trellis_brut.glb

/Applications/Blender.app/Contents/MacOS/Blender --background --python rendu/marcel_rendu.py -- rendu/chantier_exemple.json out/rendu
```

Le fichier de chantier (`rendu/chantier_exemple.json`) :

| Clé | Contenu |
|---|---|
| `largeur`, `profondeur`, `hauteur` | dimensions de la pièce, en mètres |
| `peinture`, `plinthe` | couleurs, en hexadécimal |
| `sol_image`, `sol_image_taille_m` | photo du revêtement et taille réelle qu'elle couvre. Sans photo : `sol`, deux teintes de lames |
| `ouvertures` | `type` (`fenetre` ou `porte`), `mur`, `position`, `largeur`, `hauteur`, `allege` |
| `meubles` | soit `modele` (fichier .glb) + `mur`, `position`, `largeur_m`, `hauteur_pose_m` ; soit un volume simple : `taille`, `pos`, `couleur` |
| `vues` | parmi `photo1`, `photo2`, `dessus`, `panorama` |
| `qualite` | `rapide` ou `finale` |

**Convention pour `position`** : distance en mètres entre le coin gauche du mur et le bord gauche de l'élément,
quand on regarde ce mur depuis l'intérieur de la pièce. Murs : `fond`, `avant`, `gauche`, `droit`.

La dernière ligne affichée commence par `RESULTAT` et contient en JSON la liste des images, leur durée
et les dimensions réelles des meubles posés.

Le panorama (`panorama_360.jpg`) est une image équirectangulaire : n'importe quelle visionneuse de panorama
l'affiche façon Street View dans le navigateur.

## 3. Les déclencheurs : l'atelier

Personne ne lance ces commandes à la main : `atelier.py` surveille la file `rendus` de Supabase.

```
site ──POST /api/rendu──► table « rendus » (a_faire)
                              │  l'atelier prend la ligne (en_cours)
                              ▼
            pour chaque meuble avec photo : TRELLIS  ──► objets3d/
                              ▼
                           Blender ──► images
                              ▼
        stockage Supabase + ligne « fait » ──► GET /api/rendu ──► le site
                              ▼
                 n8n prévenu (N8N_WEBHOOK_RENDU) ──► mail à l'artisan
```

Mise en place, une fois :

1. Dans Supabase → SQL Editor, exécuter `supabase/rendus.sql` (table `rendus`, stockages `rendus` et `objets3d`).
2. Dans Vercel, ajouter `SUPABASE_URL` et `SUPABASE_SERVICE_KEY` au projet du back. `GET /api/sante` doit répondre `"supabase": true`.
3. Sur le poste de l'atelier (Blender installé) :

```bash
export SUPABASE_URL=...  SUPABASE_SERVICE_KEY=...  HF_TOKEN=...
export N8N_WEBHOOK_RENDU=...        # facultatif : n8n envoie le mail quand le rendu est fini
uv run --group outils atelier.py
```

Sans Supabase, pour essayer ou en secours pendant la démo :

```bash
uv run --group outils atelier.py --fichier cas/rendu_chambre.json     # images dans out/atelier/
```

Comportement :

- **Une demande n'est prise que par un seul atelier**, même si deux postes tournent.
- **Un meuble dont la 3D échoue** (quota, Space en panne) est affiché en volume simple si ses dimensions sont complètes, et une alerte le dit. Le rendu n'est pas bloqué.
- **Une demande incohérente** est refusée par l'API avant d'entrer dans la file.
- **En cas d'échec**, la ligne passe à `echec` avec l'erreur, et n8n est prévenu.
- La clé de service Supabase contourne les règles d'accès : elle ne va **que** dans Vercel et sur le poste de l'atelier.

Le format de la demande est décrit dans [API_FRONT.md](API_FRONT.md), section 5.

## Mesures (18/11, MacBook, qualité rapide)

| Étape | Durée |
|---|---|
| Mise à l'échelle d'un objet TRELLIS.2 (98 754 faces) | ~1 s |
| Deux photos + vue de dessus | ~45 s |
| Panorama 2048 × 1024 | ~60 à 90 s |

## Ce qui n'a pas été testé

- **La vraie base Supabase.** La file d'attente, le dépôt des images et les deux routes de l'API ont été testés
  contre une fausse base en mémoire, pas contre le projet Supabase de l'équipe : pas de clé sur le poste de test.
  `supabase/rendus.sql` n'a jamais été exécuté.

- **L'appel en direct à TRELLIS depuis `meuble3d.py`** : pas de `HF_TOKEN` sur le poste de test. Les appels reprennent
  ceux de `test3d.py` (TRELLIS.2) et `bench3d.py` (TRELLIS v1), qui ont tourné le 17/11. La mise à l'échelle et le rendu
  ont été vérifiés avec `test3d/trellis_brut.glb`.
- **Les photos de meubles prises par un artisan.** Les essais du 17/11 portent sur une photo produit sur fond blanc.
  Une photo prise dans une pièce encombrée donnera sans doute un objet moins propre.

## Limites connues

- Le modèle invente les faces que la photo ne montre pas.
- Quota GPU gratuit : quelques générations par compte et par jour (voir RETOURS.md). D'où le cache.
- Le rendu ne déduit pas l'emplacement d'un meuble depuis une photo : c'est le fichier de chantier qui le donne.
- Les plinthes passent devant les portes, et la caméra peut se trouver derrière un meuble haut placé dans un coin.
- Blender ne tourne pas sur Vercel : il faut un poste ou un serveur qui lance la commande et dépose les images.
