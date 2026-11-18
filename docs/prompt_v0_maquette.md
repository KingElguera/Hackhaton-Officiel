PROMPT — À COLLER DANS v0 : REMPLACER LA VUE 360° PAR UNE MAQUETTE 3D QU'ON FAIT TOURNER
=======================================================================================

Ne change que l'onglet « Visuel » de la page `/chantiers/[id]` (et `lib/types.ts`). Garde le reste du design, des textes et des pages tel quel.

## Nouveau champ renvoyé par le back

```ts
type Visuel = {
  // … champs existants (avant_url, apres_url, dessus_url, panorama_url, etat, alertes)
  maquette_url?: string | null   // fichier 3D .glb de la pièce (Supabase Storage, CORS ouvert, ~0,1 à 5 Mo)
}
```

## Ce qu'il faut faire

1. **Remplace la vignette « 360° » par une vignette « Maquette 3D »** (icône cube), affichée seulement si `maquette_url` existe.
   Si `maquette_url` est absent mais `panorama_url` existe, garde l'ancienne vignette « 360° » comme aujourd'hui.
2. **Vue « Maquette 3D »** : affiche le fichier avec le composant web **`<model-viewer>`** de Google (paquet npm `@google/model-viewer`), dans le même cadre arrondi que l'image, hauteur ~460 px (360 px sur mobile), fond `#EEF0F5`.
   - Composant client uniquement : `"use client"`, et `import("@google/model-viewer")` dans un `useEffect` (le paquet touche à `window`, il ne doit pas être importé côté serveur). Déclare l'élément pour TypeScript (`declare global { namespace JSX { interface IntrinsicElements { "model-viewer": any } } }` ou équivalent pour React 19).
   - Attributs : `src={maquette_url}`, `camera-controls`, `touch-action="pan-y"`, `camera-orbit="-35deg 55deg 9m"`, `min-camera-orbit="auto 0deg auto"`, `max-camera-orbit="auto 88deg 14m"`, `environment-image="neutral"`, `exposure="1.1"`, `shadow-intensity="0"`, `interaction-prompt="auto"`, `style={{ width: "100%", height: "100%" }}`.
   - Pendant le chargement : la mascotte avec « Marcel monte la maquette… ». En cas d'erreur de chargement (événement `error`) : repasse automatiquement sur l'image `apres_url`.
   - Sous le cadre, à la place de « Glisse pour tourner dans la pièce » : « Fais tourner la pièce · molette ou pincement pour zoomer ». Le lien « Ouvrir l'image en grand » est masqué pour la maquette.
3. **Ordre des vignettes** : « Maquette 3D » en premier et **sélectionnée par défaut** quand elle existe, puis « Vue de la pièce », puis « Vue de dessus ».
4. La pastille « Rendu 3D · Marcel a calculé » et l'encadré « Visuel indicatif » restent identiques.

Ne pas utiliser `next/dynamic` avec SSR activé pour ce composant, ni de bibliothèque 3D supplémentaire (pas de three.js à la main).
