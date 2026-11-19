# Marcel Pro : modèle économique

Hackathon Build The Future · Team 15 · 19 novembre 2026 · version de travail

> **En une phrase.** Marcel Pro fait gagner à un rénovateur de 1 à 5 personnes plusieurs heures par devis (sourcing et comparaison des prix en environ 10 minutes) pour **79 € HT par mois**. Un client qui fait 7 chantiers par mois nous coûte environ **4 €** et nous laisse environ **75 €**.
> **Tous les chiffres sont des hypothèses de travail**, signalées comme telles et à valider.

## Chiffres clés

| Prix | Marge par client | Valeur pour l'artisan |
|---|---|---|
| **79 € HT par mois** (69 € en annuel) | **≈ 75 € par mois** pour 7 chantiers (≈ 95 %) | **× 7 à × 39 le prix** selon le temps manuel par devis |

## 1. L'offre

| Sujet | Décision | Statut |
|---|---|---|
| Modèle | Abonnement mensuel, pas de freemium permanent | Décidé |
| Prix | **79 € HT par mois** (≈ 95 € TTC). Annuel : 69 € HT par mois, soit 828 € par an (−13 %). Une seule formule au départ | Décidé |
| Usage | **Limité à 20 chantiers par mois.** Au plafond, coût technique d'environ 2 € par client (hors relevé des prix) | Décidé |
| Essai | 1 dossier gratuit après vérification SIRET et code NAF (divisions 41, 42, 43). Coût d'un essai : ≈ 0,10 € | Décidé |
| Parrainage | Parrain : −10 % par filleul qui paie son premier mois, plafond −50 % (39,50 € par mois à 79 €). Filleul : jusqu'à 3 essais | Décidé |
| Cible | Rénovateurs tous corps d'état, structure de 1 à 5 personnes | Décidé |

## 2. La valeur pour l'artisan : le temps gagné

Marcel propose un devis complet **en environ 10 minutes** à partir des besoins du chantier.

**Formule :** gain par devis = (heures manuelles − 10 minutes) × taux horaire.
Taux horaire retenu : **45 € HT** (les sources donnent 30 à 75 € selon le métier).

| Scénario (temps manuel par devis) | Gain par devis | Par mois à 7 chantiers | Rapport à l'abonnement (79 €) |
|---|---|---|---|
| **Prudent** : 2 h (estimation de King) | 82,50 € | 578 € | × 7 |
| **Intermédiaire** : 5 h (reconstitué étape par étape) | 217,50 € | 1 523 € | × 19 |
| **Haute** : 10 h (hypothèse de l'équipe) | 442,50 € | 3 098 € | × 39 |

- **Seuil de rentabilité** : dans le scénario prudent, un seul devis par mois rembourse l'abonnement.
- Le temps gagné n'est de l'argent encaissé que si l'artisan le réinvestit en chantiers facturés : à présenter comme « valeur du temps ».
- **Sources indirectes** : aucune étude indépendante ne mesure le temps passé à comparer les prix des matériaux. Repères : Flouzeo (7 à 12 h par semaine sur les devis, éditeur de logiciel), CAPEB (l'administratif prend un quart du temps pour près d'un patron sur deux). À valider par 3 à 5 entretiens d'artisans.

## 3. L'économie d'un client : 7 chantiers par mois, 79 € HT

| Ligne | Calcul | Montant par mois |
|---|---|---|
| Revenu | Abonnement HT (la TVA est reversée à l'État) | 79,00 € |
| Coût technique | 7 chantiers × 0,10 € | − 0,70 € |
| Frais de paiement en ligne | ≈ 1,5 % + 0,25 € (ordre de grandeur, à vérifier) | − 1,44 € |
| Part des frais fixes | 1 500 € par mois ÷ 800 clients | − 2,00 € |
| **Coût total du client** | | **≈ 4,14 €** |
| **Ce qu'on gagne** | 79 € − 4,14 € (≈ 95 % ; environ 900 € par an) | **≈ 75 €** |

Cette marge ne couvre ni les salaires, ni le support, ni le coût d'acquisition d'un client.

Cas particuliers : client au plafond de 20 chantiers par mois : coût technique 2 €, coût total ≈ 5,44 €, on gagne ≈ 73,50 €. Parrain à −50 % : il paie 39,50 €, nous gagnons environ 36 €. Chaque essai gratuit coûte environ 0,10 €.

## 4. Les coûts de Marcel

> **Le coût du relevé des prix chez les fournisseurs, cœur du service, n'est pas inclus** dans ces calculs : il est compté à 0 € en attendant d'être chiffré. À préciser avant le pitch.

**Coût variable par chantier** (estimation de King, ordres de grandeur, prix publics non vérifiés) :

| Poste | Ce que ça fait | Coût |
|---|---|---|
| Qwen (Hugging Face) | Lecture des photos, du plan, de la dictée | 0,02 € |
| Whisper | Dictée (1 minute) | 0,01 € |
| TRELLIS | Meubles 3D (2 par chantier) | 0,04 € |
| Blender | Rendu et maquette, sur serveur | 0,02 € |
| Supabase, Vercel, e-mails | Stockage, pages, mail de fin | 0,007 € |
| **Total variable (hors relevé des prix)** | | **≈ 0,10 €** |

**Frais fixes** (Supabase, Vercel, serveurs de rendu, n8n, e-mails, outils de développement) : environ 1 000 à 3 000 € par mois à grande échelle.

| | Année 1 (hypothèse) | À l'échelle (illustratif) |
|---|---|---|
| Clients payants | 530 à 820 | 30 000 |
| Chantiers par mois (3 à 6 par client) | 1 600 à 4 900 | 180 000 |
| Coût variable par mois | 160 à 490 € | ≈ 17 500 € |
| Frais fixes par mois | ≈ 1 000 € | ≈ 3 000 € |
| Coût technique par an | ≈ 14 000 à 18 000 € | ≈ 245 000 € |
| Chiffre d'affaires annualisé à 79 € | 0,50 à 0,78 M€ | 28,4 M€ |
| **Marge sur coûts techniques** | **≈ 97 %** | **≈ 99 %** |

« Année 1 » désigne un rythme de croisière annualisé (530 clients × 948 € par an), pas le chiffre d'affaires encaissé la première année. 30 000 clients représentent environ 37 % du marché cible des employeurs : illustration d'échelle, pas une prévision.

## 5. Le marché en France

Entreprises du bâtiment par taille (CAPEB, chiffres clés 2023, effectifs Acoss 2020). L'Insee compte 587 898 entreprises de construction en 2023, ce qui est cohérent.

| Taille | Entreprises |
|---|---|
| 0 salarié (dont 200 386 micro-entreprises) | 457 650 |
| 1 ou 2 salariés | 86 919 |
| 3 à 5 salariés | 49 386 |
| **Total de 0 à 5 salariés** | **593 955** |

| Niveau | Définition | Entreprises | Par an |
|---|---|---|---|
| TAM | Bâtiment, 0 à 5 salariés, actives en rénovation (60 %, **hypothèse**). 69 € par mois pour les solos, 79 € pour les employeurs | ≈ 356 000 | ≈ 305 M€ |
| SAM | Cible du projet : rénovateurs employeurs de 1 à 5 salariés (136 305 × 60 %) | ≈ 81 800 | ≈ 78 M€ |
| SOM | 1 % du SAM sur quelques années | ≈ 820 | ≈ 0,78 M€ |

- Pour le pitch, mettre en avant le SAM (≈ 82 000 entreprises, 78 M€) : plus solide qu'un TAM qui repose sur plus d'hypothèses.
- **Limites** : la part « tous corps d'état » est inconnue (le SAM réel est plus petit) ; beaucoup de micro-entreprises ont une activité faible ; seul l'abonnement est compté, sans commission fournisseur ; les architectes d'intérieur et les entreprises de plus de 5 salariés sont des extensions non comptées.

## 6. Hypothèses non alignées et points ouverts

| Hypothèse | Valeurs en circulation | Qui |
|---|---|---|
| Prix de l'abonnement | **Validé par l'équipe : 79 € HT** (King avait estimé 49 €) | Décidé |
| Temps manuel par devis | King : 2 à 3 h · étape par étape : 3 à 6 h · Jade : 10 h | Jade, entretiens |
| Chantiers par mois et par artisan | King : 6 · Jade : 7 · estimation initiale : 3 | Jade, entretiens |
| Coût du relevé des prix chez les fournisseurs | Non chiffré (0 € provisoire) | King, groupe |
| Fournisseurs | Castorama et IKEA validés ; une seule enseigne matériaux, comparaison encore faible | Erwan |
| Revendeur ou mandataire | Mandataire recommandé (pas de stock) | Groupe |
| Coûts (King) et frais de paiement | Ordres de grandeur, prix publics non vérifiés | King |
| Part rénovation du bâtiment | 60 % (hypothèse) | Jade |

**Questions d'entretien (3 à 5 artisans)** : combien de temps passes-tu à sourcer et comparer les prix pour un chantier moyen ? Combien de chantiers par mois ? À partir de quel prix mensuel serait-ce trop cher ? À quel prix te dirais-tu que ça vaut le coup ?

## Sources

- CAPEB, [chiffres clés 2023](https://www.capeb.fr/www/capeb/media/document/chiffres-cles-2023-4.pdf)
- Insee, [caractéristiques de la construction selon la taille des entreprises, 2023](https://www.insee.fr/fr/statistiques/2015246)
- [Obat](https://www.obat.fr/blog/tarifs-btp/) et [Habitatpresto](https://www.habitatpresto.com/pro/conseils/administratif-fiscalite/taux-horaire) (taux horaires)
- [Flouzeo](https://www.flouzeo.fr/blog/temps-perdu-devis-artisan) (temps passé sur les devis)
- [Kojo 2022](https://www.ecmag.com/magazine/articles/article-detail/report-explores-materials-management-in-ec-firms-of-all-sizes) (gestion des matériaux, électriciens américains)
- Estimation de coûts de King, 19 novembre 2026

Toutes les valeurs de prix, de temps et de coût sont des hypothèses de travail, à remplacer par des mesures.
