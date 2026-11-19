PROMPT — À COLLER DANS v0 : DESIGN DÉFINITIF — COULEURS, LOGO, MASCOTTE, ERGONOMIE
==================================================================================

Ce prompt remplace `prompt_v0_da_raton.md` pour tout ce qui touche aux couleurs et au logo.
Il réunit : la palette définitive (vert et marron sur blanc, touche de beige), les 7 fichiers du logo à jour,
et les corrections d'ergonomie relevées sur https://marcel-front.vercel.app le 19 novembre 2026 (ordinateur et téléphone,
plus un chantier lancé de bout en bout).

Ne change AUCUN appel au back, AUCUNE route, AUCUNE forme de données. Si une correction demande une donnée que le back
n'envoie pas, ne l'invente pas : laisse l'affichage actuel et signale-le.
Garde le ton : tutoiement, phrases courtes, vocabulaire du chantier.
Si une correction ci-dessous est déjà faite, passe à la suivante.

Ordre de travail : parties 1 à 4 d'abord (elles suffisent pour la démonstration), puis 5.

## 1. Palette définitive

Remplace toutes les anciennes couleurs par celles-ci, en passant par les variables du thème (pas de couleur écrite en dur
dans un composant).

| Ancienne couleur | Rôle | Nouvelle couleur |
|---|---|---|
| bleu nuit `#1F2A44` | texte, titres, barre de navigation, bandeaux sombres | marron espresso `#2A1D17` |
| crème `#FBF6EE` | fond de page | blanc `#FFFFFF` |
| beige `#F3EADB` | cartes secondaires | beige `#F4F1EC` |
| bleu ciel `#DCEAF7` | ce que l'artisan saisit (fond des champs) | beige `#F4F1EC` |
| orange brique `#B8501C` | boutons principaux, liens | vert `#007850`, texte blanc |
| — | survol et appui d'un bouton | vert foncé `#004F35` |
| orange brique `#B8501C` | pastille « Marcel », icônes, coches, anneau de progression | vert `#009C69` |
| moutarde `#F2B544` | résultats mis en avant, « meilleur prix » | fond vert très clair `#E6F5EF`, texte `#004F35` |
| — | accent sur fond sombre uniquement | `#00C986` et `#00F2A1` |
| — | bordures et séparateurs | `#E2D9CF` |
| — | texte secondaire | marron `#6E4A3A` |
| — | erreurs | rouge `#B3261E` (inchangé s'il existe déjà) |

Règles de contraste (vérifiées) :
- Le bouton principal est en `#007850` avec texte blanc (contraste d'environ 5,5). N'utilise PAS `#009C69` pour un bouton
  avec du petit texte blanc : le contraste tombe à environ 3,5.
- `#00C986` et `#00F2A1` ne vont jamais sur fond blanc ou beige. Uniquement sur `#2A1D17` ou `#004F35`.
- Le vert ne sert qu'à l'action et à ce que fait Marcel. Pas de grand aplat vert en fond de page, pas de dégradé.
- Texte courant : contraste de 4,5 au minimum. Gros titres et icônes : 3 au minimum.

Qui fait quoi (le code couleur du produit) :
- Ce que l'artisan saisit : champ sur fond beige `#F4F1EC`.
- Ce que Marcel a calculé ou décidé : pastille « Marcel » (tête du raton + mot « Marcel ») en vert `#009C69` sur fond `#E6F5EF`.

États des chantiers, en pastilles identiques partout, toujours avec un mot (jamais la couleur seule) :
- Brouillon : fond beige `#F4F1EC`, texte `#6E4A3A`.
- Questions en attente : fond `#F4F1EC`, bordure `#2A1D17`, texte `#2A1D17`.
- Marcel travaille : fond `#E6F5EF`, texte `#004F35`, point vert `#009C69` qui pulse doucement.
- Prêt : fond `#2A1D17`, texte blanc.
- Envoyé au client : fond `#004F35`, texte blanc, avec une coche.

Polices : inchangées (Fredoka pour les titres, la police de texte actuelle pour le reste).

## 2. Logo et mascotte : fichiers à créer (copie exacte, ne redessine rien)

Remplace les 7 fichiers de `public/logo/` par EXACTEMENT le contenu ci-dessous.
Ce qui a changé par rapport à l'ancienne version : couleurs (espresso, beige clair, vert), museau fermé (plus de carré
beige sous la tête, le logo se pose sur n'importe quel fond), crayon remonté plus près du visage et qui passe derrière la tête.

### `public/logo/favicon.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="Marcel Pro"><title>Marcel Pro</title><rect width="120" height="120" rx="26" fill="#F4F1EC"/><g transform="translate(9 6) scale(.85)"><g class="head">
<path fill="#2A1D17" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#F4F1EC" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#F4F1EC" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#2A1D17" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#F4F1EC" cx="39" cy="76" r="5.2"/><circle fill="#F4F1EC" cx="81" cy="76" r="5.2"/></g>
</g></g></svg>
```

### `public/logo/marcel-tete.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="Marcel Pro"><title>Marcel Pro</title><g class="head">
<path fill="#2A1D17" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#F4F1EC" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#F4F1EC" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#2A1D17" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#F4F1EC" cx="39" cy="76" r="5.2"/><circle fill="#F4F1EC" cx="81" cy="76" r="5.2"/></g>
</g></svg>
```

### `public/logo/marcel-tete-clair.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="Marcel Pro, version pour fond sombre"><title>Marcel Pro, version pour fond sombre</title><g class="head">
<path fill="#F4F1EC" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#2A1D17" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#2A1D17" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#F4F1EC" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#2A1D17" cx="39" cy="76" r="5.2"/><circle fill="#2A1D17" cx="81" cy="76" r="5.2"/></g>
</g></svg>
```

### `public/logo/marcel-tete-une-couleur.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="Marcel Pro, une couleur"><title>Marcel Pro, une couleur</title><g class="head">
<path fill="#000000" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#FFFFFF" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#FFFFFF" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#000000" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#FFFFFF" cx="39" cy="76" r="5.2"/><circle fill="#FFFFFF" cx="81" cy="76" r="5.2"/></g>
</g></svg>
```

### `public/logo/marcel-reflechit.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 150" role="img" aria-label="Marcel réfléchit"><title>Marcel réfléchit</title><style>.head,.eyes,.loupe,.crayon{transform-box:fill-box;transform-origin:center}
.head{animation:pencher 3s ease-in-out infinite}
.eyes{animation:cligner 3s linear infinite}
.p1,.p2,.p3{animation:point 3s ease-in-out infinite}.p2{animation-delay:.25s}.p3{animation-delay:.5s}
@keyframes pencher{0%,100%{transform:rotate(-5deg)}50%{transform:rotate(4deg)}}
@keyframes cligner{0%,44%,50%,100%{transform:scaleY(1)}47%{transform:scaleY(.1)}}
@keyframes point{0%,15%{opacity:0;transform:translateY(4px)}35%,80%{opacity:1;transform:none}100%{opacity:0}}@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style><g transform="translate(14 26)"><g class="head">
<path fill="#2A1D17" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#F4F1EC" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#F4F1EC" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#2A1D17" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#F4F1EC" cx="39" cy="76" r="5.2"/><circle fill="#F4F1EC" cx="81" cy="76" r="5.2"/></g>
</g></g><circle class="p1" fill="#009C69" cx="118" cy="32" r="4"/><circle class="p2" fill="#009C69" cx="131" cy="20" r="5.5"/><circle class="p3" fill="#009C69" cx="147" cy="10" r="7"/></svg>
```

### `public/logo/marcel-cherche.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 150" role="img" aria-label="Marcel cherche"><title>Marcel cherche</title><style>.head,.eyes,.loupe,.crayon{transform-box:fill-box;transform-origin:center}
.loupe{animation:balayer 2.6s ease-in-out infinite}
.eyes{animation:suivre 2.6s ease-in-out infinite}
@keyframes balayer{0%,100%{transform:translate(-30px,2px) rotate(-8deg)}50%{transform:translate(30px,-2px) rotate(8deg)}}
@keyframes suivre{0%,100%{transform:translateX(-2.5px)}50%{transform:translateX(2.5px)}}@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style><g transform="translate(20 8)"><g class="head">
<path fill="#2A1D17" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#F4F1EC" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#F4F1EC" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#2A1D17" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#F4F1EC" cx="39" cy="76" r="5.2"/><circle fill="#F4F1EC" cx="81" cy="76" r="5.2"/></g>
</g></g><g class="loupe"><circle cx="80" cy="84" r="17" fill="#F4F1EC" fill-opacity=".35" stroke="#009C69" stroke-width="5"/><path d="M92 97l17 17" stroke="#009C69" stroke-width="7" stroke-linecap="round"/></g></svg>
```

### `public/logo/marcel-dessine.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 136" role="img" aria-label="Marcel dessine"><title>Marcel dessine</title><style>.head,.eyes,.loupe,.crayon{transform-box:fill-box;transform-origin:center}
.crayon{animation:tracer 3s ease-in-out infinite}
.trait{stroke-dasharray:1;animation:trait 3s ease-in-out infinite}
.eyes{animation:regard 3s ease-in-out infinite}
@keyframes tracer{0%{transform:translateX(-84px)}70%,88%{transform:none}100%{transform:translateX(-84px)}}
@keyframes trait{0%{stroke-dashoffset:1;opacity:1}70%,85%{stroke-dashoffset:0;opacity:1}95%,100%{stroke-dashoffset:0;opacity:0}}
@keyframes regard{0%,100%{transform:translate(-2.5px,2px)}70%,88%{transform:translate(2.5px,2px)}}@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style><g class="crayon"><g transform="translate(122 124) rotate(32)"><path fill="#2A1D17" d="M-6 -12h12v48a6 6 0 0 1-12 0z" transform="translate(0 -52)"/><rect x="-6" y="-26" width="12" height="5" fill="#F4F1EC"/><rect x="-6" y="-38" width="12" height="5" fill="#F4F1EC"/><rect x="-6" y="-50" width="12" height="5" fill="#F4F1EC"/><path fill="#009C69" d="M-6 -12h12L0 0z"/><path fill="#2A1D17" d="M-2.4 -4.8h4.8L0 0z"/></g></g><g transform="translate(34 0) scale(.78)"><g class="head">
<path fill="#2A1D17" d="M23 43c-7-10-8-22-3-30 9 1 18 8 23 17 11-4 23-4 34 0 5-9 14-16 23-17 5 8 4 20-3 30 6 7 10 15 11 23l9 8c-7 2-12 5-16 9-10 14-25 22-41 22s-31-8-41-22c-4-4-9-7-16-9l9-8c1-8 5-16 11-23z"/>
<path fill="#F4F1EC" d="M8 70C20 49 45 45 60 59 75 45 100 49 112 70 99 58 76 56 62 68H58C44 56 21 58 8 70z"/>
<path fill="#F4F1EC" d="M60 62C55 70 54 80 46 90C41 97 50 102 60 102C70 102 79 97 74 90C66 80 65 70 60 62z"/>
<ellipse fill="#2A1D17" cx="60" cy="92.5" rx="8" ry="5.5"/>
<g class="eyes"><circle fill="#F4F1EC" cx="39" cy="76" r="5.2"/><circle fill="#F4F1EC" cx="81" cy="76" r="5.2"/></g>
</g></g><path class="trait" pathLength="1" d="M38 124H122" fill="none" stroke="#009C69" stroke-width="4" stroke-linecap="round"/></svg>
```

## 3. Où utiliser chaque image

| Écran | Image |
|---|---|
| En-tête, accueil, états vides, erreurs, pastille « Marcel » | `marcel-tete.svg` (fixe) |
| Sur un fond sombre (`#2A1D17` ou `#004F35`) | `marcel-tete-clair.svg` |
| Devis PDF, tampon | `marcel-tete-une-couleur.svg` |
| Onglet du navigateur | `favicon.svg` |
| Attente « Marcel regarde tes photos… » et étape « Comprendre » | `marcel-reflechit.svg` |
| Attente étape « Chiffrer » | `marcel-cherche.svg` |
| Attente étapes « Concevoir », « Montrer » et suivantes | `marcel-dessine.svg` |

- Le nom « Marcel Pro » s'écrit en texte à côté de la tête, en Fredoka.
- Les animations tournent en boucle et s'arrêtent sur une pose fixe si l'appareil demande moins d'animations.
- Chaque image a un texte alternatif qui dit ce que Marcel fait.

## 4. Corrections urgentes (à faire avant la démonstration)

1. **Animation d'arrivée trop lente.** Sur le tableau de bord et la page d'un chantier, le bandeau du haut reste flou et illisible pendant 2 à 3 secondes. Ramène toute animation d'entrée à 200 ms au maximum, sans flou, et supprime-la si l'appareil demande moins d'animations (`prefers-reduced-motion`). Le texte doit être lisible dès le premier affichage.
2. **Pages de l'application accessibles sans connexion.** `/tableau-de-bord` et `/chantiers/...` s'ouvrent sans être connecté. Si c'est voulu pour la démonstration, ne change rien ; sinon renvoie vers `/connexion`.
3. **Onglet Prix : chiffres mal affichés.**
   - Quantités illisibles : « 1 10 L », « 7 2,26 m2 (boîte de 9 lames)s », « 2 50ms », « 1 1 ». Affiche « 1 pot de 10 L », « 7 boîtes de 2,26 m² », « 2 rouleaux de 50 m », « 1 bâche ».
   - Nombres au format anglais dans le détail du calcul (« 5.23 L ÷ 10 → 1 × 8.99 € »). Utilise partout le format français : virgule décimale, espace avant €, « m² » et non « m2 ».
   - Un produit non chiffré s'affiche « 0,00 € » avec « contenance non comparable (1.0 pieces pour un besoin en m) ». Affiche « Prix à saisir » et une phrase simple : « Marcel n'a pas pu comparer : vendu à la pièce, besoin en mètres. »
   - Noms des fournisseurs en minuscules (« castorama », « bricodepot »). Affiche « Castorama », « Bricorama », « Brico Dépôt ».
   - Le libellé du produit répète toute la description du chantier. Garde le nom court du produit sur une ligne, le reste en petit dessous.
4. **« Panier le moins cher » trompeur.** Le bloc « Tout chez un seul fournisseur » compare des paniers de 3 articles sur 10 et couronne le moins cher. Affiche « 3 articles sur 10 » sur chaque panier, et ne donne le badge « Panier le moins cher » qu'à un panier complet. Sinon écris « Panier incomplet ».
5. **Message technique visible par l'artisan.** Dans l'onglet Visuel : « objet 3D impossible (QuotaGPU) — affiché en volume simple ». Remplace par : « La commode est montrée en volume simple pour l'instant. » Aucun nom d'erreur technique ne doit apparaître à l'écran.
6. **Contrôle des dimensions.** Dans « Nouveau chantier », une largeur de 350 m ou une hauteur de −2 m est acceptée sans message, alors que « Portes existantes : −1 » affiche bien « Entre 0 et 6 ». Applique le même contrôle aux trois dimensions : longueur et largeur entre 1 et 15 m, hauteur entre 2 et 4 m, message sous le champ (« Entre 1 et 15 m. Tu as peut-être saisi des centimètres ? »).
7. **Planning qui démarre un samedi et travaille le dimanche.** Les dates viennent du back : ne les recalcule pas dans le site. (À corriger côté back : sauter les week-ends.)

8. **Bouton « Regarder Marcel chercher ».** Il ouvre une page de connexion H Company (essai du 19 novembre). Masque ce bouton tant que le lien ne mène pas à une page visible sans compte.
9. **Phrase fausse dans « Nouveau chantier ».** « Tout ce que tu saisis est en bleu » : remplace par « Ce que tu saisis est sur fond beige, ce que Marcel calcule porte la pastille verte. »

## 5. Ergonomie : faciliter la vie de l'artisan sur le chantier

10. **Formulaire « Nouveau chantier » découpé en étapes.** Aujourd'hui tout tient sur une seule page très longue. Passe à 4 étapes avec une barre de progression : ① la pièce (nom, type, dimensions, portes et fenêtres) ② les travaux (postes, état des murs et du sol) ③ les photos et le plan ④ le reste (code postal, âge du logement, budget, goût). Bouton « Suivant » collé en bas de l'écran, comme sur la page des questions. Ce qui est saisi est gardé si l'artisan revient en arrière ou ferme la page.
11. **Claviers adaptés sur téléphone.** Dimensions : `inputmode="decimal"`. Nombres de portes et code postal : `inputmode="numeric"`. Accepte la virgule comme le point.
12. **Bouton « Nouveau chantier » absent sur téléphone.** En 375 px, l'en-tête ne montre plus que deux icônes sans texte. Ajoute une barre de navigation en bas de l'écran avec trois entrées et leur libellé : Chantiers, Nouveau (bouton central mis en avant), Profil.
13. **Onglets d'un chantier coupés sur téléphone.** « Planning » sort de l'écran sans indice. Fais tenir les cinq onglets dans la largeur (libellés courts, icône au-dessus) ou ajoute un fondu sur le bord droit qui montre qu'on peut faire défiler.
14. **Bandeau du haut trop grand.** Sur la page d'un chantier, le bandeau foncé occupe près de la moitié de l'écran et repousse le contenu. Réduis-le à une ligne de titre plus une ligne d'infos, et ajoute un lien « ← Mes chantiers ».
15. **Action principale introuvable.** « Marquer comme envoyé au client » est tout en bas de chaque onglet. Mets en haut à droite du chantier un bouton principal « Exporter le devis en PDF » et, à côté, « Marquer comme envoyé ».
16. **Devis : séparer fournitures et main-d'œuvre.** Les 13 lignes sont à plat. Regroupe-les en deux blocs avec un sous-total chacun. Laisse la désignation passer sur deux lignes au lieu de la couper (« Peinture murs et plafonds blanc mat 1… »). Remplace les flèches monter/descendre par une poignée de glisser-déposer sur ordinateur ; garde les flèches sur téléphone.
17. **Liste des chantiers.** Ajoute sur chaque ligne le montant TTC et un état clair en couleur : « Questions en attente », « Prêt », « Envoyé ». Ajoute une recherche par nom au-dessus de 8 chantiers.
18. **Résumé d'un chantier.** Quand Marcel n'a rien décidé, le bloc « Ce que Marcel a décidé pour toi » montre une grande illustration vide. Remplace-le par une ligne discrète. Mets en tête du résumé les trois chiffres que l'artisan cherche : total TTC, nombre de jours, date limite de commande.
19. **Visuel 3D.** Par défaut, montre l'image « Vue de la pièce » (plus parlante pour un client) et propose la maquette 3D en second. Regroupe les avertissements sous un seul lien « Pourquoi ce visuel est indicatif ».

## 6. Règles à respecter partout

- **Téléphone d'abord.** Chaque écran est pensé en 375 px, utilisable d'une main, parfois avec des gants : zones tactiles d'au moins 44 × 44 px (40 éléments sur 105 sont en dessous aujourd'hui sur la page d'un chantier), 8 px entre deux boutons.
- **Une action principale par écran**, toujours au même endroit : en bas sur téléphone, en haut à droite sur ordinateur.
- **Texte de 16 px au minimum** dans les champs (sinon le téléphone zoome), 14 px pour les aides, jamais moins de 12 px.
- **Chaque erreur dit quoi faire**, sous le champ concerné, en une phrase. Jamais de code ni de nom d'erreur.
- **Chaque attente dit ce que Marcel fait** et combien de temps cela prend, avec la mascotte animée correspondante.
- **Chaque chiffre de Marcel est modifiable et marqué comme tel.** L'artisan garde la main.
- **Accessibilité.** Les cases « Travaux à faire » sont annoncées « on » par les lecteurs d'écran : donne-leur leur vrai nom (Murs, Plafond…). Chaque bouton icône a un nom. Le focus au clavier est visible. La couleur n'est jamais le seul signal (ajoute une icône ou un mot au « meilleur prix »).
- **Formats français** : `1 363,88 €`, `13,02 m²`, dates en « sam. 28 nov. ».
- **États vides, de chargement et d'erreur** prévus pour chaque liste et chaque onglet.

## 7. Comment vérifier

Fais le parcours complet en 375 px puis en 1280 px : accueil → tableau de bord → nouveau chantier (avec une largeur de 350
pour voir l'erreur) → questions → attente → résumé → prix → devis → visuel → planning.
Pour chaque écran : plus aucune trace de bleu marine, d'orange ou de moutarde ; lisible en moins d'une seconde ; action
principale visible sans faire défiler ; aucun texte coupé ; aucun défilement horizontal ; aucun message technique.
