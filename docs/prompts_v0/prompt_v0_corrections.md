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

## 6. Bouton « Retour » sur chaque écran du parcours
Ajoute en haut à gauche de ces écrans un lien discret « ← Retour » (icône flèche, couleur du texte secondaire) :
- `/chantiers/nouveau` → retour à `/chantiers` ;
- `/chantiers/[id]/questions` → « ← Modifier la fiche » : revient à `/chantiers/nouveau` avec la fiche déjà remplie (voir point 7) ;
- `/chantiers/[id]/en-cours` → retour à `/chantiers` (les agents continuent de travailler, rien n'est annulé) ;
- `/chantiers/[id]` (résultat) → retour à `/chantiers`.
Utilise une navigation normale (`router.push` / `<Link>`), pas `replace`, pour que le bouton « précédent » du navigateur marche aussi.

## 7. Ne plus perdre ce qui a été tapé (brouillon automatique)
- Formulaire `/chantiers/nouveau` : enregistre automatiquement tout ce qui est saisi (champs, travaux cochés, portes/fenêtres, meubles, photos, plan) dans le navigateur à chaque modification (avec un petit délai, ~500 ms) et recharge-le à l'ouverture de la page.
  Les champs texte et nombres vont dans `localStorage` (clé `marcel_brouillon_fiche`) ; les images (déjà réduites) vont dans IndexedDB (API native du navigateur, pas de bibliothèque), car `localStorage` est trop petit pour elles.
  Entoure chaque lecture/écriture d'un try/catch : si le stockage est indisponible, le formulaire marche comme avant.
- Affiche au-dessus du formulaire, quand un brouillon a été rechargé : « Brouillon retrouvé » et un lien « Tout effacer » qui vide le formulaire et le brouillon.
- Le brouillon est gardé quand on passe aux questions (pour pouvoir revenir le modifier) et n'est effacé qu'une fois le chantier lancé (après la réponse réussie de `envoyerReponses`).
- Écran des questions : garde aussi les réponses en cours dans `localStorage` (clé `marcel_reponses_<id du chantier>`), rechargées si on revient sur la page.
- Revenir modifier la fiche puis la renvoyer crée un nouveau chantier : c'est normal (l'ancien n'a lancé aucun agent).
