# Marcel — brief technique pour le front

Le back est une API JSON **sans état** (Vercel, Python/FastAPI). Le front garde en mémoire le `projet` et les `sessions`
et les renvoie à chaque appel. Base URL : celle du déploiement Vercel du back (ex. `https://marcel-back.vercel.app`).

## Les 4 écrans et les appels

| Écran | L'utilisateur | Appel | Durée |
|---|---|---|---|
| 1. Mon projet | photo + texte libre + mesures + code postal + budget | — | — |
| 2. J'ai compris | relit la demande structurée, corrige si besoin, valide | `POST /api/comprendre` | ~2–5 s |
| 3. Marcel cherche | voit les agents naviguer en direct | `POST /api/parcours` puis `GET /api/statut` toutes les 30 s | ~5 min |
| 4. Résultat | liste vérifiée, total/budget, planning, guide, 3D | `POST /api/resultat` | ~15–20 s |

Marcel s'arrête **toujours avant le paiement** : il prépare des paniers, il n'achète rien.

---

## 1. `POST /api/comprendre`

```json
{
  "texte": "Je veux un canapé 3 places gris et repeindre les murs en vert sauge",
  "code_postal": "75011",
  "photo": "data:image/jpeg;base64,/9j/4AAQ...",
  "budget_eur": 900,
  "largeur_cm": 220, "profondeur_cm": 95, "hauteur_cm": null,
  "surface_murs_m2": 35, "surface_sol_m2": null,
  "niveau": "débutant"
}
```
Seuls `texte` et `code_postal` sont obligatoires. **Les mesures sont indispensables** pour vérifier qu'un objet rentre :
la photo ne sert PAS à mesurer.

Réponse (extrait) :
```json
{
  "projet": {
    "nom": "Salon : canapé + peinture", "piece": "salon", "code_postal": "75011", "budget_eur": 900,
    "emplacement": {"largeur_mm": 2200, "profondeur_mm": 950, "hauteur_mm": null, "marge_mm": 10},
    "besoins": [
      {"id": "canape_3_places", "famille": "objet", "categorie": "canapé 3 places", "description": "...",
       "dans_emplacement": true, "largeur_max_mm": 2190, "profondeur_max_mm": 940, "couleur": "gris"},
      {"id": "peinture_murs", "famille": "surface", "categorie": "peinture murale", "surface_m2": 35,
       "surface_source": "formulaire", "couches": 2, "couleur": "vert sauge"}
    ],
    "hors_perimetre": ["Changement du robinet de la cuisine"],
    "photo": {"type_piece": "...", "etat_murs": "bon", "couleur_murs_actuelle": "blanc",
              "emplacement_visible": false, "points_attention": ["..."], "confiance": "moyenne"},
    "alertes": []
  },
  "questions": []
}
```
À afficher sur l'écran 2 : `besoins` (modifiables), `hors_perimetre` (« Marcel ne sait pas encore faire ça »),
`alertes`, `questions`, `photo.points_attention`. Familles : `objet` (doit rentrer), `surface` (quantité selon m²),
`fourniture` (à l'unité). Maximum 4 besoins par projet.

## 2. `POST /api/parcours`

```json
{ "projet": { ...le projet validé à l'écran 2... }, "enseignes": ["castorama", "ikea"] }
```
`enseignes` est optionnel (par défaut castorama + ikea). **Chaque enseigne consomme 1 session H** (quota limité) :
n'appeler qu'au clic sur « Lancer Marcel ».

Réponse :
```json
{ "projet": {...}, "sessions": [
  {"enseigne": "castorama", "session_id": "4e36…", "live_url": "https://platform.hcompany.ai/agents/sessions/4e36…", "lance_le": "2026-11-18T…"},
  {"enseigne": "ikea", "session_id": "79ba…", "live_url": "…", "lance_le": "…"}
]}
```
Garder `projet` et `sessions` tels quels pour les appels suivants. Afficher `live_url` (vue live de l'agent).
⚠️ À vérifier : si la page H refuse l'iframe, ouvrir `live_url` dans un nouvel onglet.

## 3. `GET /api/statut?ids=<id1>,<id2>`

```json
{ "sessions": [{"session_id": "4e36…", "statut": "running", "etapes": 23, "termine": false}, ...],
  "tous_termines": false }
```
⚠️ **Appeler toutes les 30 s, pas plus** : la clé H Free est limitée à 5 requêtes/minute (sinon HTTP 429).
Quand `tous_termines` est vrai → appeler `/api/resultat`.

## 4. `POST /api/resultat`

```json
{ "projet": {...}, "sessions": [ ...les objets renvoyés par /api/parcours... ], "guide": true }
```
Réponse (extrait) :
```json
{
  "achats": [{"besoin_id": "etagere", "nom": "KLAVRESTRÖM Étagère murale, chêne, 60x20 cm", "enseigne": "ikea",
              "url": "https://www.ikea.com/…", "image_url": "…", "prix_eur": 29.99, "quantite": 1, "cout_eur": 29.99,
              "dispo_mode": "livraison", "dispo_jours": 7,
              "raisons": ["rentre dans l'emplacement (600×170×200 mm, marge 10 mm comprise)"]}],
  "besoins_sans_produit": [],
  "total_eur": 77.89, "budget_eur": 150, "dans_budget": true,
  "taches": [{"besoin_id": "peinture", "tache": "Préparer les murs et peindre (2 couches + séchage)",
              "debut": "2026-11-18", "jour": "mer. 18/11", "duree_j": 3, "attend": "peinture murale (retrait magasin (Castorama Nation))"}],
  "taches_non_planifiees": [], "fin_travaux": "2026-11-26",
  "candidats": [ ...tous les produits vus, avec valide true/false et raisons... ],
  "agents": [{"enseigne": "castorama", "statut": "completed", "duree_s": 273, "etapes": 42, "cout_total": 0.13, "replay_url": "…"}],
  "guide": {"guide_md": "### 1. Résumé …", "duree_s": 4.4}
}
```
- `raisons` : pourquoi un produit est retenu ou rejeté (ex. « trop large : 800 mm > 790 mm ») — à montrer, c'est la preuve.
- `candidats` avec `valide: false` : produits écartés par la vérification (transparence).
- `guide.guide_md` : Markdown à afficher tel quel.

---

## Recettes front

**Photo (écran 1)** — ouvre l'appareil photo sur mobile, puis réduit en JPEG ≤ 1600 px (règle aussi le HEIC iPhone et l'orientation) :
```html
<input type="file" accept="image/*" capture="environment" id="photo">
```
```js
async function photoEnDataUrl(file) {
  const img = await createImageBitmap(file, { imageOrientation: "from-image" });
  const k = Math.min(1, 1600 / Math.max(img.width, img.height));
  const c = Object.assign(document.createElement("canvas"), { width: img.width * k, height: img.height * k });
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.85);   // < 4,5 Mo (limite du corps de requête Vercel)
}
```

**3D (écran 4)** — fichiers `.glb` à l'échelle exacte en mètres (dossier `test3d/` du repo) :
```html
<script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
<model-viewer src="/3d/klavrestrom.glb" camera-controls auto-rotate ar ar-modes="webxr scene-viewer quick-look"></model-viewer>
```
L'attribut `ar` ajoute le bouton « Voir chez moi » (réalité augmentée) sur mobile : l'objet est déjà à la bonne taille.

**Erreurs** : `429` = trop d'appels H (attendre 30 s et réessayer) ; `502` = service externe en échec (message dans `detail`).
`GET /api/sante` vérifie que le back répond et que les clés sont configurées.

---

## 5. Rendu 3D de la pièce : `POST /api/rendu` puis `GET /api/rendu?id=…`

Les images sont fabriquées **hors de Vercel**, par l'atelier (`atelier.py`, sur un poste avec Blender).
L'API met seulement la demande en file et dit où elle en est. Compter 1 à 4 minutes.

```json
{
  "piece": {"largeur_cm": 400, "profondeur_cm": 350, "hauteur_cm": 250},
  "peinture": "vert sauge",
  "sol": {"image": "https://…/parquet.jpg", "taille_cm": 340},
  "ouvertures": [
    {"type": "fenetre", "mur": "gauche", "position_cm": 110, "largeur_cm": 120, "hauteur_cm": 125, "allege_cm": 90},
    {"type": "porte", "mur": "fond", "position_cm": 300, "largeur_cm": 83, "hauteur_cm": 204}
  ],
  "meubles": [
    {"nom": "canapé", "photo": "data:image/jpeg;base64,…", "largeur_cm": 210, "mur": "fond", "position_cm": 60}
  ],
  "vues": ["photo1", "photo2", "dessus", "panorama"],
  "qualite": "rapide"
}
```

- Seule `piece` est obligatoire. Toutes les mesures sont en **centimètres**.
- `peinture` : un nom courant (« blanc », « vert sauge », « terracotta »…) ou un code `#RRGGBB`.
- `sol.image` : la photo du revêtement (lien ou data URL) et `taille_cm`, la taille réelle qu'elle couvre.
  Sans photo : `sol.teintes`, deux couleurs de lames.
- `mur` : `fond`, `avant`, `gauche` ou `droit`. La caméra des photos est côté `avant`.
- `position_cm` : du coin gauche du mur au bord gauche de l'élément, vu de l'intérieur de la pièce.
- Un meuble **avec `photo`** est modélisé en 3D par TRELLIS (30 à 40 s la première fois, puis en cache).
  Sa `largeur_cm` est obligatoire. Sans photo, donner aussi `profondeur_cm` et `hauteur_cm` : il est affiché en volume simple.
- 6 meubles au maximum.

Réponse immédiate : `{"id": "…", "etat": "a_faire"}`. Une demande incohérente (porte qui dépasse du mur…) renvoie `400` avec la raison.

Ensuite, `GET /api/rendu?id=…` toutes les 10 s jusqu'à `"termine": true` :

```json
{
  "id": "…", "etat": "fait", "termine": true,
  "resultat": {
    "images": [
      {"fichier": "photo1.png", "url": "https://…/rendus/<id>/photo1.png", "secondes": 16.1},
      {"fichier": "panorama_360.jpg", "url": "https://…/rendus/<id>/panorama_360.jpg", "secondes": 88.7}
    ],
    "meubles_3d": [{"nom": "canapé", "modele": "TRELLIS.2 (Microsoft)", "url": "https://…/objets3d/….glb", "ecart_proportions_pct": 7.8}],
    "alertes": ["canapé : profondeur et hauteur déduites du modèle : donner les trois dimensions pour un objet exact"],
    "total_secondes": 194.1
  }
}
```

- `etat` : `a_faire` → `en_cours` → `fait` ou `echec` (avec `erreur`).
- `panorama_360.jpg` est une image équirectangulaire, à afficher dans une visionneuse de panorama (visite à 360°).
- Les fichiers `.glb` de `meubles_3d` s'affichent avec `<model-viewer>`.
- **Toujours afficher `alertes`** : elles disent ce qui a été remplacé ou estimé.
- Si Supabase n'est pas configuré côté back, les deux routes renvoient `503`.


### Le rendu d'un chantier du parcours artisan

Rien à appeler : dès qu'un chantier est chiffré, son rendu est mis en file tout seul.
Le site lit ensuite `resultat.visuel` dans `GET /api/chantiers/<id>/resultat` :

- `etat` : `a_faire`, puis `fait` quand l'atelier a fini (quelques minutes) ;
- `apres_url` (photo), `dessus_url` (vue de dessus), `panorama_url` (visite à 360°) ;
- `alertes` : par exemple « emplacement des portes et des fenêtres estimé », car la fiche donne leur nombre, pas leur position.

Pour relancer un rendu à la main : `POST /api/chantiers/<id>/rendu` (sans corps).
Il faut que la table `rendus` existe (`supabase/rendus.sql`) et qu'un atelier tourne (`./demarrer.sh atelier`).

## Lire les cotes sur la photo du plan

`POST /api/plan` avec `{"plan": "data:image/jpeg;base64,..."}` (photo du plan coté, 1600 px maximum). Réponse en 2 à 5 secondes :

- `longueur_m`, `largeur_m`, `hauteur_m`, `surface_m2`, `nb_portes`, `nb_fenetres` : à mettre dans les champs du formulaire ;
- `ouvertures` : chaque porte et fenêtre avec sa taille et son emplacement. À renvoyer telle quelle dans la fiche (`fiche.ouvertures`) : le rendu 3D place alors les ouvertures au bon endroit au lieu de les estimer ;
- `cotes_lues` : ce que Marcel a lu, à montrer à l'artisan ;
- `alertes` : cote illisible, surface incohérente, hauteur absente…

Rien n'est enregistré par cet appel. Le site pré-remplit les champs, l'artisan vérifie et valide : les chiffres restent les siens.
