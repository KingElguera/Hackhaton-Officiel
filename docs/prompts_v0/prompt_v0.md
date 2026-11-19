PROMPT — À COLLER DANS v0 (v0.app) POUR CRÉER LE SITE MARCEL PRO
=================================================================

Construis une application web complète appelée « Marcel Pro ». Elle doit fonctionner tout de suite avec des données de démonstration, sans aucun service extérieur. Je brancherai le back, la base de données et les automatisations plus tard, en ne modifiant que `lib/api.ts`.

## Le produit

Marcel Pro est un outil pour les artisans rénovateurs (entreprises de 1 à 5 personnes). À chaque nouveau chantier, l'artisan décrit la pièce, et Marcel lui rend : les matériaux chiffrés chez 5 fournisseurs professionnels, un devis pré-rempli qu'il peut corriger, et un visuel de la pièce après travaux. L'artisan est le seul utilisateur. Son client final n'a pas de compte.

Marcel est aussi la mascotte : un petit monsieur à casquette, grosse moustache et bretelles orange, avec un rouleau de peinture. Fais un composant `MarcelMascot` (SVG simple, formes pleines, trait épais) avec une prop `pose` : `salue` (accueil), `peint` (écran d'attente, le rouleau bouge doucement), `metre` (états vides : il tient un mètre déroulé), `perplexe` (erreurs : il se gratte la casquette). Utilise-le sur la page d'accueil, l'écran d'attente, les états vides et les erreurs.

## Technique

- Next.js (App Router), TypeScript, Tailwind CSS, composants shadcn/ui, icônes lucide-react.
- Toute l'interface est en français. Marcel tutoie l'artisan.
- Conçu d'abord pour le téléphone : l'artisan remplit sa fiche sur un chantier. Gros boutons, champs larges, une seule colonne sur mobile.
- Toutes les données passent par un seul fichier `lib/api.ts`. Aucune page n'appelle autre chose que ce fichier.
- Dans `lib/api.ts`, lis `process.env.NEXT_PUBLIC_MARCEL_API_URL`. Tant qu'elle est vide, chaque fonction renvoie les données de démonstration de `lib/mock.ts` avec un petit délai simulé (400 à 900 ms). Quand elle est définie, les fonctions marquées « API Marcel » appellent cette URL (`fetch`, JSON, `POST` ou `GET` comme indiqué plus bas) et renvoient exactement les mêmes types.
- Mets au-dessus de chaque fonction un commentaire qui dit où elle sera branchée : `// À BRANCHER : API Marcel — POST /api/...`, `// À BRANCHER : Supabase — table ...` ou `// À BRANCHER : webhook n8n`.
- Tous les types sont dans `lib/types.ts` (voir plus bas, à reprendre tels quels : les noms de champs sont ceux du back). Les données de démonstration sont dans `lib/mock.ts`.
- Pas de paiement, pas d'envoi de mail réel, pas d'appel à une IA depuis le front.
- Les photos et le plan : avant l'envoi, réduis chaque image côté navigateur en JPEG de 1600 px maximum (canvas, `createImageBitmap(file, { imageOrientation: "from-image" })`), ce qui règle aussi les photos HEIC d'iPhone. Sur mobile, le champ photo ouvre l'appareil (`accept="image/*" capture="environment"`).

## Design

- Couleurs : bleu nuit #1F2A44 (titres, barre de navigation), crème #FBF6EE (fond), beige #F3EADB (cartes secondaires), orange brique #B8501C (boutons principaux, ce que fait Marcel), moutarde #F2B544 (résultats, mises en avant), bleu ciel #DCEAF7 (ce que l'artisan saisit).
- Polices Google : Fredoka pour les titres, DM Sans pour le texte.
- Cartes aux coins arrondis, beaucoup d'air, pas de dégradés, pas d'ombres lourdes.
- Ton chaleureux et direct, sans jargon. Exemple : « Tu n'as pas précisé la teinte des murs. »
- Le code couleur raconte qui fait quoi : tout ce que l'artisan saisit vit sur fond bleu ciel ; tout ce que Marcel a calculé ou décidé porte une petite pastille orange « Marcel » (tête de la mascotte + mot « Marcel ») à côté de la valeur.
- Chiffres : `font-variant-numeric: tabular-nums` dans tous les tableaux ; montants au format français (`1 234,56 €`, via `Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" })`) ; dimensions toujours avec leur unité (« 4,00 m × 3,50 m × 2,50 m »).
- États des chantiers en pastilles de couleur cohérentes partout : Brouillon (beige), Questions en attente (moutarde), Marcel travaille (orange, avec un point qui pulse doucement), Prêt (bleu nuit), Envoyé au client (vert sobre #2F7D5B).
- Respecte `prefers-reduced-motion` : sans animation, la mascotte reste immobile et le point ne pulse pas.

## Les pages

### 1. `/` Accueil
Une promesse en une phrase : « Photographie la pièce, Marcel te rend le devis. » Trois étapes illustrées (Tu décris, Marcel chiffre, Tu envoies). Un bouton « Essayer avec mon SIRET » vers `/inscription`. Une ligne : « Réservé aux professionnels. 3 chantiers offerts. »

### 2. `/inscription` et `/connexion`
Inscription en quatre champs : SIRET, prénom et nom, e-mail et mot de passe, code de parrainage (facultatif).
Quand le SIRET fait 14 chiffres, appelle `verifierSiret()` et affiche une carte « Entreprise trouvée » avec le nom, la forme juridique, l'adresse et l'activité. Si l'activité n'est pas dans le bâtiment (`est_batiment: false`), affiche : « Marcel Pro est réservé aux professionnels du bâtiment. »
Un code de parrainage valide affiche : « 5 chantiers offerts au lieu de 3. »

### 3. `/tableau-de-bord`
- En haut : « Bonjour Karim », le nombre de chantiers offerts restants, un grand bouton « Créer un chantier ».
- Deux onglets : « En cours » et « Exécutés ». Chaque chantier est une carte : nom, pièce, date, état (Brouillon, Questions en attente, Marcel travaille, Prêt, Envoyé au client).
- Une carte « Ton profil est complet à 55 % » avec une jauge et une seule suggestion : « Complète tes fournisseurs (2 minutes) : Marcel cherchera d'abord chez eux. »

### 4. `/chantiers/nouveau` La fiche du chantier
Un seul écran, en trois zones.

Zone « Obligatoire » :
1. Nom du chantier.
2. Type de pièce (chambre, salon, cuisine, salle de bain, entrée, autre).
3. Dimensions : longueur, largeur, hauteur, en mètres.
4. Plan : dépôt d'un fichier ou d'une photo. Texte d'aide : « Un croquis coté à main levée, pris en photo, suffit. »
5. Nombre de portes et de fenêtres.
6. Travaux à faire, en cases à cocher : murs, plafond, sol, plinthes, éclairage.
7. Pour chaque poste coché : la gamme ou le produit voulu. Ce champ peut rester vide, avec le texte d'aide : « Laisse vide si tu veux que Marcel te pose la question. »
8. Code postal du chantier.
9. Logement de plus de 2 ans ? (oui ou non)
10. Photos de la pièce : 2 au minimum. Texte d'aide : « Pas de personnes ni de papiers dans le cadre. »

Sous les dimensions, affiche en direct un petit encadré « Marcel a calculé » (pastille orange) : surface des murs, du plafond, du sol et longueur de plinthes, calculées dans le navigateur à partir des dimensions et du nombre d'ouvertures (porte comptée 0,83 m × 2,04 m, fenêtre 1,20 m × 1,35 m). C'est indicatif : le back refait le calcul.

Zone « Utile », repliée par défaut : état des murs et du sol (bon, à reprendre, abîmé), date de début souhaitée, budget du client, heures de main-d'œuvre.

Zone « Le goût », repliée par défaut : photos d'inspiration, photos des meubles déjà achetés pour la pièce, et un bouton « Envoyer la fiche envies à mon client » qui copie un lien vers `/envies/[jeton]`.

Le bouton « Lancer Marcel » reste grisé tant qu'une donnée obligatoire manque, avec la liste de ce qui manque.

### 5. `/chantiers/[id]/questions` Les questions de Marcel
Titre : « Tu n'as pas précisé… ». Les points sont groupés en trois blocs (champ `bloc` du type `Question`) :
- « Il me manque » (les faits : dimensions, plan, photos). Un champ pour compléter. Pas de bouton de délégation.
- « Tes choix techniques » (gamme, nombre de couches, type de pose). Pour chaque point : un champ de réponse, ou un bouton « Je fais confiance à Marcel ».
- « Tes choix de goût » (teinte, essence du parquet, style). Même fonctionnement.

En haut, un bouton « Fais confiance pour tout » qui délègue tous les choix techniques et de goût, jamais les faits.
Quand l'artisan répond à un choix technique, propose une case : « Garder cette réponse pour mes prochains chantiers. »
Bouton final : « C'est bon, lance-toi ».

### 6. `/chantiers/[id]/en-cours` L'attente
Affiche six étapes avec leur état (en attente, en cours, terminé, à relancer) : Comprendre, Chiffrer, Concevoir, Montrer, Rédiger, Contrôler. La mascotte en pose `peint` accompagne l'étape en cours.
Message bien visible : « Tu peux fermer cette page. Tu recevras un seul mail quand tout sera prêt. »
Pendant l'étape « Chiffrer », affiche une carte par fournisseur (champ `agents` de `Avancement`) : nom du fournisseur, état (« Marcel cherche… », « Fini », « Site bloqué »), nombre d'étapes faites, et un bouton secondaire « Regarder Marcel chercher » qui ouvre `live_url` dans un nouvel onglet (c'est l'agent en direct sur le site du fournisseur ; ne l'intègre pas dans une iframe).
La page interroge `etatDuChantier(id)` toutes les 5 secondes et redirige vers le résultat quand tout est terminé.

### 7. `/chantiers/[id]` Le résultat
Cinq onglets.

- **Résumé.** Une carte « Ce que Marcel a décidé pour toi » : chaque choix délégué, avec sa raison en une ligne et un bouton « Changer ». Les choix techniques apparaissent en premier, avec la mention « change le prix ». Une carte « Les conseils de Marcel », 3 au maximum : chaque conseil a une phrase d'explication et deux boutons, « Garder mon choix » et « Changer ».
- **Prix.** Un tableau des produits : une ligne par produit, une colonne par fournisseur, le meilleur prix surligné en moutarde, la quantité, la date du relevé. Sous chaque prix, en petit, le calcul fait par Marcel (champ `calcul`, ex. « 11 m² ÷ 1,44 → 8 × 24,90 € »). Sur mobile, la première colonne (produit) reste fixe et le tableau défile horizontalement dans son cadre. Sous le tableau, une carte par fournisseur avec le total du panier et un bouton « Voir le panier » qui déplie la liste des articles : quantité, nom, prix, et un lien « Ouvrir chez le fournisseur » vers la fiche produit. Une ligne : « Prix publics relevés le [date]. Ta remise habituelle n'est pas appliquée. »
- **Devis.** Un tableau modifiable ligne par ligne : désignation, quantité, unité, prix unitaire HT, total HT. On peut ajouter, supprimer et réordonner les lignes. Les totaux hors taxes, TVA et toutes taxes se recalculent à chaque modification, dans le navigateur ; sur mobile, ils restent visibles dans une barre fixée en bas de l'écran. Le taux de TVA vient de la fiche (10 % si logement de plus de 2 ans, sinon 20 %) et reste modifiable. Un bouton « Exporter en PDF » ouvre une fenêtre qui demande ce qui manque : nom et adresse du client, assurance décennale, conditions de paiement, durée de validité.
- **Visuel.** Un comparateur avant et après avec un curseur à glisser (utilisable au clavier avec les flèches). Une ligne : « Visuel indicatif : le rendu des matériaux peut différer du produit réel. »
- **Planning.** La liste des étapes dans l'ordre, avec la durée, la date de début et la date limite de commande des matériaux (champ `commander_avant`).

En bas de page : un bouton « Marquer comme envoyé au client ».

### 8. `/profil`
Une jauge générale et cinq blocs, chacun avec son pourcentage et ce qu'il rapporte :
- Identité (40 %, déjà rempli par le SIRET).
- Mon devis (25 %) : taux horaire, marge sur les matériaux, TVA par défaut, assurance décennale, conditions de paiement, durée de validité, logo, structure du devis, niveau de détail, variantes, clause d'aléas, montant minimum, majoration d'urgence. « Un devis prêt à envoyer, sans retouche. »
- Mes fournisseurs (15 %) : fournisseurs habituels, remise chez chacun, marques préférées, marques refusées. « Des prix proches de tes vrais prix. »
- Mon métier et mes pré-réglages (10 %) : corps de métier, zone d'intervention, certifications, ce que je ne fais jamais, sous-traitance, gamme habituelle, peinture (couches et finition), type de pose du sol, préparation des supports. « Marcel ne te repose pas les mêmes questions. »
- Mon style (10 %) : site ou portfolio, dépôt d'un ancien devis. « Des devis à ton image. »
Rien n'est obligatoire. Chaque bloc s'enregistre séparément.

### 9. `/envies/[jeton]` La fiche du client final
Page publique, sans compte ni navigation. Titre : « [Nom de l'artisan] prépare votre projet. » Cinq questions : le style que vous aimez, les couleurs que vous aimez, celles que vous refusez, ce que vous gardez dans la pièce, des photos d'inspiration.
En haut, un encadré d'information : « Vos réponses sont transmises à [nom de l'artisan] pour préparer votre devis. Elles sont conservées le temps du chantier. Vous pouvez demander leur suppression à tout moment. »
Cette page vouvoie.

## Les données de démonstration

- Un artisan : Karim Benali, « Benali Rénovation », profil complet à 55 %, 2 chantiers offerts restants.
- Quatre chantiers : un brouillon, un avec questions en attente, un prêt (« Chambre, rue des Lilas » : 4 m × 3,5 m × 2,5 m, murs et sol), un envoyé au client.
- Cinq fournisseurs fictifs nommés « Fournisseur A » à « Fournisseur E ». Je mettrai les vrais noms plus tard.
- Pour le chantier prêt : 10 produits avec leurs prix chez chaque fournisseur, un devis de 12 lignes, 3 choix délégués avec leur raison, 2 conseils, 5 étapes de planning, deux images de remplacement pour l'avant et l'après.
- Pour l'écran d'attente : 3 agents (Fournisseur A, B, C) dont un « Fini », un en cours à 23 étapes et un « Site bloqué », avec une `live_url` fictive.

## Les fonctions de `lib/api.ts`

| Fonction | Branchement prévu | Renvoie |
|---|---|---|
| `verifierSiret(siret)` | API Marcel — `GET /api/siret/{siret}` | `Entreprise` |
| `inscrire(donnees)` | Supabase — Auth + table `artisans` | `Artisan` |
| `seConnecter(email, motDePasse)` | Supabase — Auth | `Artisan` |
| `listerChantiers()` | Supabase — table `chantiers` | `ChantierResume[]` |
| `creerChantier(fiche)` | API Marcel — `POST /api/chantiers` | `{ id: string; questions: Question[] }` |
| `questionsDuChantier(id)` | API Marcel — `GET /api/chantiers/{id}/questions` | `Question[]` |
| `envoyerReponses(id, reponses)` | API Marcel — `POST /api/chantiers/{id}/reponses` (lance les agents) | `Avancement` |
| `etatDuChantier(id)` | API Marcel — `GET /api/chantiers/{id}/etat` | `Avancement` |
| `resultatDuChantier(id)` | API Marcel — `GET /api/chantiers/{id}/resultat` | `Resultat` |
| `changerUnChoix(id, choix)` | API Marcel — `POST /api/chantiers/{id}/choix` | `Resultat` |
| `repondreAuConseil(id, conseil, decision)` | API Marcel — `POST /api/chantiers/{id}/conseils` | `Resultat` |
| `enregistrerDevis(id, lignes)` | Supabase — table `devis` | `Devis` |
| `exporterDevisPdf(id, infosClient)` | API Marcel — `POST /api/chantiers/{id}/devis.pdf` | URL du PDF (`string`) |
| `lireProfil()` | Supabase — table `artisans` | `Profil` |
| `enregistrerBlocProfil(bloc, donnees)` | Supabase — table `artisans` | `Profil` |
| `envoyerEnvies(jeton, reponses)` | Supabase — table `envies` | `{ ok: true }` |

Le mail « tout est prêt » n'est pas envoyé par le front : il part tout seul (Supabase prévient n8n quand le chantier passe à « Prêt »).

## `lib/types.ts` (à reprendre tels quels, noms de champs du back)

```ts
export type EtatChantier = "brouillon" | "questions" | "en_recherche" | "pret" | "envoye";
export type Poste = "murs" | "plafond" | "sol" | "plinthes" | "eclairage";

export interface Entreprise { siret: string; nom: string; forme_juridique: string; adresse: string;
  activite: string; code_naf: string; est_batiment: boolean; }

export interface Artisan { id: string; prenom: string; nom: string; email: string; entreprise: Entreprise;
  chantiers_offerts_restants: number; profil_complet_pct: number; }

export interface ChantierResume { id: string; nom: string; piece: string; cree_le: string; etat: EtatChantier; }

export interface FicheChantier {
  nom: string; piece: "chambre" | "salon" | "cuisine" | "salle_de_bain" | "entree" | "autre";
  longueur_m: number; largeur_m: number; hauteur_m: number; nb_portes: number; nb_fenetres: number;
  postes: { poste: Poste; gamme_ou_produit?: string }[];
  code_postal: string; logement_plus_de_2_ans: boolean;
  plan?: string;          // data URL JPEG
  photos: string[];       // data URL JPEG, 2 minimum
  etat_murs?: "bon" | "a_reprendre" | "abime"; etat_sol?: "bon" | "a_reprendre" | "abime";
  date_debut_souhaitee?: string; budget_client_eur?: number; heures_main_oeuvre?: number;
  photos_inspiration?: string[]; photos_meubles?: string[];
}

export interface Question { id: string; bloc: "il_me_manque" | "choix_technique" | "choix_gout";
  poste?: Poste; question: string; delegable: boolean; }
export interface Reponse { question_id: string; reponse?: string; delegue: boolean; garder_pour_la_suite?: boolean; }

export type EtatEtape = "en_attente" | "en_cours" | "termine" | "a_relancer";
export interface Etape { nom: "comprendre" | "chiffrer" | "concevoir" | "montrer" | "rediger" | "controler";
  etat: EtatEtape; detail?: string; }
export interface AgentEnDirect { fournisseur: string; session_id: string; live_url: string | null;
  statut: "en_cours" | "fini" | "bloque" | "erreur"; etapes: number | null; }
export interface Avancement { chantier_id: string; etat: EtatChantier; etapes: Etape[]; agents: AgentEnDirect[]; }

export interface Offre { fournisseur: string; produit: string; prix_eur: number; unite: string;
  quantite: number; cout_eur: number; calcul: string; stock?: string; delai_texte?: string;
  lien: string; releve_le: string; }
export interface LignePrix { ref: string; designation: string; besoin: number | null; unite_besoin: string | null;
  meilleure_offre: Offre | null; offres: Offre[]; statut: "ok" | "a_comparer" | "introuvable"; }
export interface Panier { fournisseur: string; total_eur: number;
  articles: { ref: string; produit: string; quantite: number; prix_eur: number; cout_eur: number; lien: string }[]; }

export interface LigneDevis { id: string; designation: string; quantite: number; unite: string;
  prix_unitaire_ht: number; type: "materiau" | "main_oeuvre" | "autre"; source: "marcel" | "artisan"; }
export interface Devis { lignes: LigneDevis[]; taux_tva: number; }   // les totaux sont toujours recalculés par le code

export interface ChoixDelegue { id: string; sujet: string; valeur: string; raison: string; change_le_prix: boolean; }
export interface Conseil { id: string; texte: string; explication: string; }
export interface EtapePlanning { ordre: number; tache: string; duree_j: number; debut: string; commander_avant?: string; }

export interface Resultat {
  chantier: ChantierResume & { fiche: FicheChantier };
  choix_delegues: ChoixDelegue[]; conseils: Conseil[];
  prix: { lignes: LignePrix[]; paniers: Panier[]; releve_le: string; total_meilleurs_prix_eur: number };
  devis: Devis;
  visuel: { avant_url: string; apres_url: string };
  planning: EtapePlanning[];
}

export interface Profil { artisan: Artisan; blocs: Record<"identite" | "devis" | "fournisseurs" | "metier" | "style",
  { pct: number; donnees: Record<string, unknown> }>; }
```

## Les règles à respecter

1. Le total du devis est toujours calculé par du code, jamais affiché tel que reçu sans vérification.
2. Chaque prix affiche son fournisseur et la date du relevé.
3. Le nom et l'adresse du client final ne sont demandés qu'à l'export du PDF.
4. Un conseil de Marcel ne bloque jamais une action.
5. Les dimensions, le plan et les photos ne peuvent pas être délégués à Marcel.
6. Tous les états sont gérés : chargement (squelettes aux bonnes dimensions), vide (mascotte `metre`), erreur (mascotte `perplexe`), avec un message en français et un bouton pour réessayer.
7. Accessibilité : chaque champ a une étiquette visible, les contrastes sont suffisants (texte bleu nuit sur crème, blanc sur orange brique), tout est utilisable au clavier, le focus est visible.
8. Aucune page n'importe `lib/mock.ts` directement : seules les fonctions de `lib/api.ts` le font.

Commence par les pages 3, 4, 5, 6 et 7 : c'est le cœur de la démonstration. Fais ensuite les autres.
