PROMPT — À COLLER DANS v0 : DICTÉE DU CHANTIER (MICRO) + LECTURE DU PLAN + « 3 FOURNISSEURS »
============================================================================================

Ne change que ce qui est décrit ici. Garde le design, les textes et les pages tels quels.

## 1. Bouton micro discret sur `/chantiers/nouveau`

En haut du formulaire, juste sous le titre, ajoute UNE ligne compacte (pas une grande carte) :
- un petit bouton rond (40 px) avec une icône micro, couleur principale, et à côté le texte « Dicter mon chantier » en petit, couleur secondaire ;
- sous la ligne, en très petit et en gris : « Ex. : salon de 5 m sur 4, hauteur 2,50, une porte, deux fenêtres, murs gris clair, sol chêne clair, code postal 75011. »

Fonctionnement :
- Clic → demande l'accès au micro et enregistre avec `MediaRecorder` (type `audio/webm;codecs=opus` si `MediaRecorder.isTypeSupported` le permet, sinon `audio/mp4`).
- Pendant l'enregistrement : le bouton devient rouge avec une icône stop, un petit point rouge qui pulse et un compteur « 0:12 / 2:00 ». Arrêt automatique à 2 minutes. Re-clic = stop.
- Au stop : transforme l'enregistrement en data URL et envoie `POST {API}/api/dictee` avec `{ "audio": "<data URL>" }` (même adresse de back et même façon d'appeler que les autres appels du site).
- Pendant l'envoi (3 à 6 s) : à la place du bouton, la petite mascotte `MarcelMascot etat="reflechit"` (32 px) et « Marcel écoute… ».
- Micro refusé ou indisponible : message discret « Micro indisponible : autorise-le dans ton navigateur, ou remplis la fiche à la main. »
- Erreur du back (422) : affiche le champ `detail` de la réponse, en petit.

Réponse du back :
```ts
type Dictee = {
  texte: string                        // ce que Marcel a entendu
  fiche: Partial<FicheChantier> & { teinte_murs?: string; teinte_sol?: string }
  manquants: { champ: string; question: string }[]
  alertes: string[]
  a_confirmer: true
}
```
- Remplis les champs du formulaire avec les valeurs de `fiche` qui existent (nom, piece, longueur_m, largeur_m, hauteur_m, nb_portes, nb_fenetres, nb_portes_a_creer, nb_fenetres_a_creer, etat_murs, budget_client_eur, date_debut_souhaitee, code_postal, postes → coche les travaux et remplit « gamme ou produit » s'il est donné). Les champs absents ne sont pas touchés.
- Chaque champ rempli par la dictée prend un contour orange et une mini pastille « dicté », qui disparaissent dès que l'artisan modifie le champ.
- Sous le bouton, en petit et en gris, une ligne repliable « Ce que j'ai entendu » qui montre `texte`.
- Si `manquants` n'est pas vide : une ligne discrète « Il me manque : » suivie des `question`, séparées par des virgules.
- Les `alertes`, s'il y en a, en petit sous la même ligne.

## 2. Couleurs des murs et du sol dans la fiche

Ajoute deux champs texte facultatifs dans la zone « Le goût » : « Couleur des murs » (`fiche.teinte_murs`, aide : « Ex. : gris clair, mur du fond bleu canard ») et « Couleur du sol » (`fiche.teinte_sol`, aide : « Ex. : chêne clair »). La dictée les remplit. Envoie-les dans `fiche` à `creerChantier` s'ils sont remplis (Marcel ne reposera alors pas la question).

## 3. Bouton « Lire les cotes du plan »

Quand une image de plan a été ajoutée, affiche sous la vignette un petit bouton secondaire (contour, pas plein) « Lire les cotes du plan ».
- Clic → `POST {API}/api/plan` avec `{ "plan": "<data URL du plan, déjà réduite>" }`. Pendant ~2 s : petite mascotte `reflechit` et « Marcel lit le plan… ».
- Réponse : `{ longueur_m, largeur_m, hauteur_m, nb_portes, nb_fenetres, ouvertures, alertes, a_confirmer }`. Remplis longueur, largeur, hauteur, portes existantes, fenêtres existantes avec les valeurs non nulles, avec le même contour orange et la pastille « lu sur le plan ».
- Si TOUTES les `ouvertures` ont un `position_m` non nul, garde le tableau `ouvertures` et envoie-le dans `fiche.ouvertures` à `creerChantier` ; sinon ne l'envoie pas.
- Les `alertes` s'affichent en petit et en gris sous le bouton (« à vérifier »).
- Erreur 422 : affiche `detail` en petit (« le plan n'a pas pu être lu… »).

## 4. Texte de la page d'inscription
Dans la colonne de droite de `/inscription`, remplace « Prix comparés chez 5 fournisseurs » par « Prix comparés chez 3 fournisseurs ». Cherche aussi « 5 fournisseurs » ailleurs sur le site (accueil, textes de présentation) et remplace par « 3 fournisseurs ».

## 5. À ne pas faire
Pas de nouvelle bibliothèque (MediaRecorder et FileReader suffisent). Ne change ni l'envoi du chantier, ni les autres pages, ni le design général. Le bouton micro reste petit et discret.
