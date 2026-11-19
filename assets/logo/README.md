# Logo et animations de Marcel

Marcel est un raton laveur. Sa tête sert de logo, et trois animations l'accompagnent pendant que le produit travaille.
Tout est en SVG : net à toutes les tailles, sans bibliothèque à installer.

| Fichier | Usage |
|---|---|
| `marcel-tete.svg` | le logo, sur fond clair |
| `marcel-tete-clair.svg` | le logo, sur fond espresso `#2A1D17` |
| `marcel-tete-une-couleur.svg` | version noire, pour un devis ou un tampon |
| `favicon.svg` | l'icône de l'onglet |
| `marcel-reflechit.svg` | animation : Marcel lit la fiche et les photos |
| `marcel-cherche.svg` | animation : les agents relèvent les prix chez les fournisseurs |
| `marcel-dessine.svg` | animation : le visuel de la pièce se construit |

## Dans le site

```html
<link rel="icon" href="/logo/favicon.svg" type="image/svg+xml">
<img src="/logo/marcel-tete.svg" alt="Marcel Pro" width="40" height="40">
<img src="/logo/marcel-cherche.svg" alt="Marcel cherche chez les fournisseurs" width="120">
```

Dans un projet Next.js, copier ces fichiers dans `public/logo/`.

- Le nom « Marcel Pro » s'écrit en texte à côté de la tête, en police Fredoka.
- Les animations tournent en boucle (2,6 à 3 s) et restent sur une pose fixe si l'appareil demande moins d'animations.
- Couleurs : espresso `#2A1D17`, nuage `#F4F1EC`, brique `#B4532A`.
- Le museau est fermé : le logo se pose sur n'importe quel fond.

## Quelle image à quel moment

| Écran | Image |
|---|---|
| En-tête, accueil, états vides, erreurs | `marcel-tete.svg` (fixe) |
| Attente : étape « Comprendre » | `marcel-reflechit.svg` |
| Attente : étape « Chiffrer » | `marcel-cherche.svg` |
| Attente : étapes « Montrer » et suivantes | `marcel-dessine.svg` |

## À remplacer dans `docs/prompt_v0.md`

Le prompt du site décrit encore l'ancienne mascotte (un monsieur à casquette, moustache et bretelles, avec quatre poses).
Paragraphe de remplacement :

> Marcel est aussi la mascotte : un raton laveur, dont la tête sert de logo. N'invente pas de dessin : utilise les fichiers
> SVG fournis dans `public/logo/`. Fais un composant `MarcelMascot` avec une prop `etat` : `fixe` (`marcel-tete.svg` : en-tête,
> accueil, états vides, erreurs), `reflechit`, `cherche` et `dessine` (les trois animations, sur l'écran d'attente, selon l'étape
> en cours). Chaque image a un texte alternatif qui dit ce que Marcel fait.
