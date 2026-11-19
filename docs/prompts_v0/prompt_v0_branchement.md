PROMPT — À COLLER DANS v0 POUR BRANCHER LE SITE SUR LE VRAI BACK
================================================================

Garde tout le design et toutes les pages tels quels. Ne modifie que `lib/api.ts` (et `lib/types.ts` si un champ ci-dessous manque), plus les petits ajustements de pages indiqués à la fin.

## Règle générale

- `lib/api.ts` lit `process.env.NEXT_PUBLIC_MARCEL_API_URL` (ex. `https://marcel-back.vercel.app`, sans `/` final). Si elle est vide, chaque fonction garde les données de démonstration actuelles. Si elle est définie, les fonctions marquées « API Marcel » appellent le back avec `fetch` (JSON, en-tête `Content-Type: application/json`).
- `verifierSiret` lit `process.env.NEXT_PUBLIC_N8N_SIRET_URL` (webhook n8n). Vide → démo.
- Pour vendredi, restent en démonstration (aucun appel réseau, garder dans `localStorage`) : `inscrire`, `seConnecter`, `lireProfil`, `enregistrerBlocProfil`, `envoyerEnvies`. Garde le prénom et l'e-mail saisis à l'inscription : ils sont envoyés avec chaque nouveau chantier.
- Erreurs : 409 sur le résultat → le chantier n'est pas prêt, redirige vers `/chantiers/[id]/en-cours`. 429 → « Marcel est très demandé, réessaie dans une minute ». 4xx/5xx → l'état d'erreur existant avec le message `detail` renvoyé par le back et un bouton Réessayer.

## Les appels (API Marcel)

| Fonction | Requête | Réponse |
|---|---|---|
| `listerChantiers()` | `GET /api/chantiers` | `ChantierResume[]` |
| `creerChantier(fiche)` | `POST /api/chantiers` corps `{ fiche, artisan: { prenom, email } }` | `{ id, questions: Question[], surfaces, analyse_photos }` |
| `questionsDuChantier(id)` | `GET /api/chantiers/{id}/questions` | `Question[]` |
| `envoyerReponses(id, reponses)` | `POST /api/chantiers/{id}/reponses` corps `{ reponses: Reponse[] }` | `Avancement` (lance les agents) |
| `etatDuChantier(id)` | `GET /api/chantiers/{id}/etat` | `Avancement` |
| `resultatDuChantier(id)` | `GET /api/chantiers/{id}/resultat` | `Resultat` (+ champ `surfaces`) |
| `changerUnChoix(id, choix)` | `POST /api/chantiers/{id}/choix` corps `{ id, valeur }` | `Resultat` |
| `repondreAuConseil(id, conseil, decision)` | `POST /api/chantiers/{id}/conseils` corps `{ conseil_id, decision: "garder" \| "changer" }` | `Resultat` |
| `exporterDevisPdf(id, infos)` | `POST /api/chantiers/{id}/devis.pdf` (corps ci-dessous) | **un fichier PDF** (`application/pdf`) |
| `marquerEnvoye(id)` (à ajouter) | `POST /api/chantiers/{id}/envoye` | `Avancement` |

Détails importants :

1. **`creerChantier`** : `fiche` suit `FicheChantier`. Envoie au maximum 2 photos de la pièce + le plan (déjà réduits en JPEG 1600 px) ; pour `photos_inspiration` et `photos_meubles`, n'envoie que leur nombre (le corps doit rester sous 4 Mo). La création prend ~5 à 10 s (Marcel lit les photos) : affiche « Marcel regarde tes photos… » avec la mascotte. Ensuite : s'il y a des questions → `/chantiers/[id]/questions` ; sinon → appelle tout de suite `envoyerReponses(id, [])` puis va sur `/chantiers/[id]/en-cours`.
2. **Les questions** ont les champs `id`, `bloc`, `poste?`, `question`, `delegable`, `type_reponse` (`texte` | `nombre` | `photo` | `choix`), `options?`, `unite?`, `min?`, `max?`, `grandeur?`. Une réponse : `{ question_id, reponse?: string, delegue: boolean, garder_pour_la_suite?: boolean }` (« Marcel choisit » → `delegue: true`). Pour une photo, `reponse` est la data URL JPEG.
3. **`envoyerReponses` ne doit être appelée qu'une fois** (bouton désactivé après le clic) : chaque appel lance des agents payants. Le back refuse de relancer un chantier déjà lancé.
4. **L'écran d'attente** interroge `etatDuChantier` toutes les 5 s et redirige vers `/chantiers/[id]` quand `etat === "pret"`. Les agents : `statut` vaut `en_cours` (« Marcel cherche… »), `fini`, `bloque` (« Site bloqué ») ou `erreur` ; `etapes` peut être `null` ; le bouton « Regarder Marcel chercher » ouvre `live_url` dans un nouvel onglet.
5. **Le résultat** : dans les offres, `stock`, `delai_texte` et `meilleure_offre` peuvent être `null` ; `statut` d'une ligne vaut `ok`, `a_comparer` ou `introuvable`. Les colonnes du tableau Prix = les fournisseurs présents dans les offres. `visuel.avant_url` / `apres_url` peuvent être `null` : affiche alors « Rendu en préparation » avec la mascotte (pose `peint`) au lieu du comparateur. `surfaces` (`murs_m2`, `plafond_m2`, `sol_m2`, `plinthes_m`, `perimetre_m`) peut s'afficher dans le Résumé avec la pastille « Marcel a calculé ».
6. **Le devis** : `devis.lignes` est modifiable dans le navigateur, les totaux sont recalculés dans le navigateur ; `enregistrerDevis` garde les lignes dans l'état de la page (pas d'appel réseau) et elles partent avec l'export PDF.
7. **`exporterDevisPdf`** : corps
   ```json
   { "client": { "nom": "...", "adresse": "..." },
     "artisan": { "nom_entreprise": "...", "forme_juridique": "...", "adresse": "...", "siret": "...", "email": "...", "telephone": "..." },
     "decennale": "...", "conditions_paiement": "...", "validite_jours": 30, "mediateur": "...",
     "adresse_chantier": "...", "lignes": [ ...les lignes du devis telles que corrigées... ], "taux_tva": 10 }
   ```
   `artisan` vient de l'inscription (entreprise trouvée par le SIRET) et du profil. La réponse est un **PDF binaire** : lis-la avec `res.blob()`, crée `URL.createObjectURL(blob)` et ouvre-la dans un nouvel onglet, avec un lien « Télécharger le devis » en secours.
8. **Le bouton « Marquer comme envoyé au client »** appelle `marquerEnvoye(id)`.

## `verifierSiret` (webhook n8n d'Erwan)

Adresse : `https://erwan222.app.n8n.cloud/webhook/verifier-siret` (à mettre dans `NEXT_PUBLIC_N8N_SIRET_URL`). `POST {NEXT_PUBLIC_N8N_SIRET_URL}` corps `{ "siret": "12345678900012" }`. Réponse :
- refus : `{ "valide": false, "raison": "format" | "numero_invalide" | "introuvable" | "entreprise_fermee" | "service_indisponible", "nom"? }` → messages : « Le SIRET doit faire 14 chiffres », « Ce numéro de SIRET n'est pas valide, vérifie-le », « SIRET introuvable », « Cette entreprise est fermée », « Vérification indisponible, réessaie dans un instant » (dans ce dernier cas, laisse continuer l'inscription) ;
- accepté : `{ "valide": true, "siret", "nom", "forme_juridique", "adresse", "code_activite", "libelle_activite", "batiment", "rge" }` → convertis en `Entreprise` : `activite = libelle_activite`, `code_naf = code_activite`, `est_batiment = batiment`. Si `batiment` est faux : « Marcel Pro est réservé aux professionnels du bâtiment. » Si `rge` est vrai, affiche une petite pastille « RGE ».

## À ne pas changer

Le design, les textes, les données de démonstration (elles restent utilisées quand les variables d'environnement sont vides), l'ordre des pages.
