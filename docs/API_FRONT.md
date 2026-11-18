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
