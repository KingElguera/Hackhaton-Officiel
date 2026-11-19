PROMPT — À COLLER DANS v0 : CORRECTIONS D'AFFICHAGE AVANT LA DÉMO
=================================================================

Petites corrections de textes et d'affichage. Ne change rien d'autre (design, pages, appels au back, données).

## 1. Page d'inscription
Dans la colonne de droite, remplace « Prix comparés chez 5 fournisseurs » par « Prix comparés chez 3 fournisseurs ».

## 2. Onglet « Prix » — colonne Quantité et unités
Aujourd'hui on lit « 2 La pièces », « 22 M2s », « 4 m²s », « 1 1 porte ». Le back envoie maintenant une unité déjà propre (`pièce`, `m²`, `L`, `m`, ou un texte comme `pot de 2,5 L`).
- N'ajoute plus de « s » automatiquement à l'unité.
- Seul cas de pluriel : si l'unité vaut exactement `pièce` et la quantité est > 1, écris `pièces`.
- Format : `{quantite} {unite}` (ex. « 2 pièces », « 22 m² », « 1 porte », « 3 pot de 2,5 L »). Si l'unité est vide, n'affiche que le nombre.

## 3. Onglet « Prix » — prix non comparable
Quand une offre a `cout_eur` nul (null) — le produit a été trouvé mais sa contenance ne permet pas de calculer la quantité — n'affiche jamais « 0,00 € ». Affiche à la place, en gris : « À comparer », puis le prix unitaire relevé (`prix_eur`, s'il existe) et la phrase `calcul` en petit dessous.
Ces offres ne sont jamais surlignées comme meilleure offre.

## 4. Onglet « Prix » — les paniers
Le bloc « Tout chez un seul fournisseur » est faux : `prix.paniers` est la répartition de la commande au meilleur prix (chaque article chez le fournisseur le moins cher), pas un panier complet par fournisseur.
- Renomme le titre en « Ta commande au meilleur prix, fournisseur par fournisseur ».
- Supprime le badge « Panier le moins cher ».
- Au-dessus des cartes, affiche le total : « Total matériaux au meilleur prix : {prix.total_meilleurs_prix_eur} € TTC ».
- Chaque carte garde : nom du fournisseur, nombre d'articles, total, bouton « Voir le panier ».

## 5. Formulaire `/chantiers/nouveau` — champ « gamme ou produit voulu »
Sous chaque champ « gamme ou produit voulu » des travaux cochés, remplace le texte d'aide par :
« La gamme (entrée, milieu, haut de gamme) ou un produit précis — pas la couleur : Marcel te la demande juste après. Laisse vide si tu veux qu'il te pose la question. »
