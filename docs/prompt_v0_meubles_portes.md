PROMPT — À COLLER DANS v0 : PORTES / FENÊTRES « EXISTANTES » ET « À CRÉER », MEUBLES AVEC PHOTO ET DIMENSIONS
==========================================================================================================

Ne change que le formulaire `/chantiers/nouveau`, l'appel `creerChantier` et `lib/types.ts`. Garde le reste du design, des textes et des pages tel quel.

## 1. Portes et fenêtres

Remplace le champ « Nombre de portes et de fenêtres » par quatre petits champs numériques (0 par défaut, minimum 0, maximum 6), sur deux lignes :

- **Portes existantes** → `fiche.nb_portes` · **Portes à créer** → `fiche.nb_portes_a_creer`
- **Fenêtres existantes** → `fiche.nb_fenetres` · **Fenêtres à créer** → `fiche.nb_fenetres_a_creer`

Texte d'aide sous la ligne : « Existantes : celles qu'on voit aujourd'hui dans la pièce. À créer : celles que tu vas ajouter (Marcel chiffre la porte ou la fenêtre et sa pose). »
Si un champ « à créer » est supérieur à 0, affiche dessous un petit encadré orange clair : « Pense à vérifier que le mur n'est pas porteur : le percement n'est pas chiffré. »

L'encadré « Marcel a calculé » sous les dimensions compte toutes les ouvertures (existantes + à créer) pour la surface des murs et des plinthes.

## 2. Meubles déjà achetés (zone « Le goût »)

Remplace le simple dépôt de photos de meubles par une liste de meubles (4 au maximum), avec un bouton « + Ajouter un meuble ». Chaque meuble est une petite carte :

- **Photo du meuble** (obligatoire) — aide : « Une photo du meuble seul, idéalement sur fond blanc (photo du site du vendeur). »
- **Nom** (texte court, ex. « Armoire », facultatif)
- **Largeur (cm)** — obligatoire, nombre > 0
- **Profondeur (cm)** et **Hauteur (cm)** — facultatifs
- **Contre quel mur ?** — liste : « Marcel choisit » (par défaut), « Mur du fond », « Mur de gauche », « Mur de droite », « Mur de l'entrée »
  → valeurs envoyées : absent, `"fond"`, `"gauche"`, `"droit"`, `"avant"`
- Une croix pour retirer le meuble.

Une carte sans largeur bloque le bouton « Lancer Marcel », et la liste de ce qui manque le dit (« Largeur de l'armoire »).

Sous la liste, une ligne discrète : « Marcel modélise chaque meuble en 3D et le place dans la maquette de la pièce. »

## 3. Ce qui part au back (`creerChantier`)

```ts
type MeubleFiche = {
  photo: string            // data URL JPEG, réduite à 1000 px de côté maximum, qualité 0.8
  nom?: string
  largeur_cm: number
  profondeur_cm?: number
  hauteur_cm?: number
  mur?: "fond" | "gauche" | "droit" | "avant"   // absent = Marcel choisit
}

// dans FicheChantier :
nb_portes: number
nb_fenetres: number
nb_portes_a_creer?: number
nb_fenetres_a_creer?: number
meubles?: MeubleFiche[]
photos_meubles?: number      // continue d'envoyer seulement le nombre (= meubles.length)
```

Les photos des meubles partent dans `fiche.meubles[].photo` (le back les range dans le stockage). Elles doivent être réduites dans le navigateur (canvas → `toDataURL("image/jpeg", 0.8)`, 1000 px maximum) pour que le corps de la requête reste sous 4 Mo avec les photos de la pièce et le plan.

## 4. Résultat

Rien à changer : les meubles apparaissent dans les images et dans la maquette 3D de l'onglet « Visuel », et les alertes (« meuble non affiché : pas assez de place… ») sont déjà dans `visuel.alertes`. Le conseil « Création d'ouverture : vérifie que le mur n'est pas porteur » arrive dans `conseils` comme les autres.
