PROMPT — À COLLER DANS v0 : AFFICHER LE RENDU 3D DANS L'ONGLET « VISUEL »
=======================================================================

Ne change que l'onglet « Visuel » de la page `/chantiers/[id]` (et `lib/types.ts` pour les nouveaux champs). Garde tout le reste du design, des textes et des pages tel quel.

## Ce que renvoie maintenant le back

Dans le résultat du chantier, `visuel` peut contenir :

```ts
type Visuel = {
  avant_url: string | null      // photo « avant » : souvent absente pour l'instant
  apres_url: string | null      // rendu 3D de la pièce finie (image PNG), fait par Blender
  dessus_url?: string | null    // vue de dessus (PNG)
  panorama_url?: string | null  // panorama 360° (JPG équirectangulaire, 2:1)
  etat?: "a_faire" | "en_cours" | "fait" | "echec"
  alertes?: string[]            // ex. « emplacement des portes et des fenêtres estimé… »
}
```

## Affichage voulu

1. **Si `avant_url` ET `apres_url` existent** : garde le comparateur avant / après actuel.
2. **Si seulement `apres_url` existe** (cas actuel) : affiche le rendu en grand (coins arrondis, même style que les autres cartes), avec la pastille « Rendu 3D · Marcel a calculé » et la légende « Pièce reconstruite à partir de tes mesures ».
   - En dessous, une rangée de vignettes cliquables pour passer d'une vue à l'autre : « Vue de la pièce » (`apres_url`), « Vue de dessus » (`dessus_url`), « 360° » (`panorama_url`). N'affiche que les vignettes dont l'URL existe.
   - Vue « 360° » : affiche le panorama dans un cadre de hauteur fixe (environ 420 px), image en `height: 100%` et largeur automatique, que l'on fait défiler horizontalement en glissant (souris ou doigt) ; petite mention « Glisse pour tourner dans la pièce ». Pas de bibliothèque externe.
3. **Si `alertes` n'est pas vide** : sous l'image, un encadré discret gris clair avec une icône info et le titre « Visuel indicatif », puis les alertes en liste.
4. **Si `apres_url` est nul** : garde l'état actuel « Rendu en préparation » avec la mascotte. Si `etat === "echec"`, remplace le texte par « Le rendu n'a pas pu être fait. Les prix et le devis restent valables. »
5. Un lien discret « Ouvrir l'image en grand » ouvre l'image affichée dans un nouvel onglet.

Les images viennent de Supabase Storage (`https://uzuafglughaiksiexsxg.supabase.co/storage/...`) : utilise une balise `<img>` simple (pas `next/image`, pour éviter d'avoir à déclarer le domaine).
