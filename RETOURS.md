# Marcel — Résultats des tests et retours sur l'Agent API H Company

## Accès des enseignes

| Enseigne | Verdict | Vérifié à la main | Notes |
|---|---|---|---|
| IKEA | ✅ faisable | ✅ prix + dimensions conformes | 80 s, 15 étapes, ~0,04 de coût (flash). Stock magasin OK (Paris-Rivoli). Délai de livraison non trouvé sur la fiche produit. |
| Castorama | ✅ faisable | ✅ conforme | 72 s, 13 étapes, ~0,034. Les 4 infos trouvées (prix 10,90 €, dimensions, stock magasin Nation, livraison « sous 4 jours ouvrés »). |
| Leroy Merlin | ❌ bloqué | ✅ replay | CAPTCHA slider « Slide right to secure your access » dès l'accueil. 22 s, 2 étapes, ~0,005. Un nouvel essai possible plus tard. |
| Bricorama | ✅ faisable (partiel) | à vérifier | 138 s, 33 étapes, ~0,084 (2× Castorama). Prix 9,70 €, dimensions 60×18×1,8 cm, stock : aucun magasin à 100 km. Livraison visible seulement au panier. Une erreur interne de l'agent à l'étape 32, récupérée seule. |
| ManoMano | ❌ bloqué | | CAPTCHA Cloudflare « Verify you are human » dès l'accueil. 28 s, 3 étapes, ~0,006. |

**Bilan au 17/11 :** 2 enseignes sur 4 accessibles (IKEA, Castorama). 4 sessions, coût total ~0,085. Les blocages coûtent peu (l'agent s'arrête en 2-3 étapes au lieu de forcer).

## Parcours complet n°1 — 17/11 (cas chambre : niche 800×250 mm + 30 m² de peinture, 150 €)

| Enseigne | Statut | Durée | Étapes | Coût | Produits relevés |
|---|---|---|---|---|---|
| Castorama | completed | 273 s | 42 | ~0,135 | 2 étagères + 2 peintures, délai livraison lu (4 j ouvrés) |
| IKEA | completed | 303 s | 54 | ~0,156 | 2 étagères ; pas de peinture murale chez IKEA (constaté par l'agent) |

- Résultat : liste vérifiée de 77,89 € (étagère IKEA KLAVRESTRÖM + peinture Valspar 10 L Castorama), ordre des travaux daté (peinture le 17/11, pose de l'étagère le 24/11 à la livraison).
- La vérification par le code a rejeté les 2 étagères Castorama de 800 mm (pas de jeu dans une niche de 800 mm) : l'agent les avait proposées malgré la contrainte.
- L'agent IKEA a coché « en stock magasin » sans texte de stock affiché, et son propre commentaire parlait de livraison → règle : le retrait magasin n'est retenu que si un texte de stock est recopié.
- Coût d'un parcours complet : 2 sessions, ~5 min en parallèle, ~0,29.

## Retours sur l'Agent API

### Ce qui a marché
- Installation SDK `hai-agents` + premier run réussi en quelques minutes.
- `answer_schema` (Pydantic) : sortie structurée propre et directement exploitable.
- Le replay de session sur la plateforme permet de vérifier visuellement ce que l'agent a fait.
- `max_steps` / `max_time_s` pour plafonner le coût de chaque session.

### Ce qui a coincé / surpris
- SDK requiert Python ≥ 3.10 (le Python système macOS est en 3.9).
- Bandeau « Nos services sont actuellement indisponibles » sur la plateforme le 17/11, alors que l'API fonctionnait.
- Clés Free limitées à 5 requêtes/min : le suivi de session par long-poll consomme ~3 req/min, donc 3 sessions en parallèle dépassent la limite → runs séquentiels.
- L'agent s'auto-évalue « ok » alors qu'un champ demandé (délai de livraison) manque → verdict recalculé côté code.
- Castorama : le champ `dimensions` dit « 80 x 80 x 18 cm » alors que le commentaire du même agent dit « 18 mm » → erreur d'unité. Dimensions à demander en champs numériques en mm.
- Le SDK renvoie le statut `idle` (et pas `completed`) pour des sessions pourtant terminées avec une réponse.
- Le magasin « le plus proche » n'est pas toujours choisi activement : sur Castorama l'agent a gardé le magasin présélectionné par le site.
- Dans l'interface Sessions, une session terminée affiche parfois « Aucun événement » jusqu'au rechargement de la page.
- L'agent respecte bien la consigne de ne pas contourner un CAPTCHA et s'arrête proprement.
- Bricorama : événement « agent Error » au milieu de la session, sans explication, mais l'agent reprend et termine.
- Le délai de livraison n'apparaît souvent qu'au panier (IKEA, Bricorama) : l'interdiction d'ajouter au panier empêche de le relever.

## Hugging Face (Inference Providers) — 17/11

Modèle : `Qwen/Qwen3.8-27B` via le routeur HF (token « Inference » uniquement, crédits perso).

| Test | Résultat | Durée | Tokens |
|---|---|---|---|
| ping | ✅ « Marcel est prêt. » | 0,4 s | — |
| plan (guide de travaux depuis le run n°1) | ✅ après 2 corrections | 3,6–3,8 s | ~700 in / ~1 000 out |
| photo (description de la pièce) | ✅ honnête | 3,1 s | — |

- **Piège n°1 :** Qwen3 « réfléchit » avant de répondre et a épuisé tout `max_tokens` (2 000 puis 4 000) en réflexion → réponse vide malgré un statut « ok ». `chat_template_kwargs.enable_thinking=false` réduit mais ne supprime pas la réflexion ; **`reasoning_effort: "none"`** la coupe vraiment (29 s → 3,7 s). On logue désormais `finish_reason` et on considère une réponse vide comme un échec.
- **Piège n°2 (hallucinations) :** 1re version du guide : « budget total 150 € » (c'est le plafond, le vrai total est 77,89 €) et « murs et plafond » (30 m² = murs seuls). Corrigé en donnant au modèle le total calculé par le code et la nature exacte de la surface. Règle : tout chiffre affiché vient du code, le modèle ne fait que rédiger.
- Produits, prix, enseignes, quantités et dates du guide : conformes aux données vérifiées.
- **Test photo piège** (photo iPhone d'un couloir, alors que la consigne annonce « chambre avec niche 80 × 25 cm ») : le modèle répond `couloir`, `niche_visible: false`, ajoute en point d'attention « la niche mentionnée n'est pas visible sur la photo » et se déclare en confiance « moyenne » (photo un peu floue). Les éléments listés sont exacts (porte, extincteur, alarme, sortie de secours, sol mosaïque, fresque, poubelle). Il a oublié la prise électrique. Le conseil « sous-couche » est générique (blanc sur blanc). Bilan : il ne se laisse pas influencer par la consigne et n'invente rien. Point à surveiller : les HEIC iPhone sont à convertir en JPEG et à redresser (EXIF) avant l'envoi.

## 3D avec Hugging Face — 17/11 (gratuit : Spaces ZeroGPU)

Aucun modèle « image → 3D » n'est servi par Inference Providers : on passe par des **Spaces** HF (GPU gratuits avec quota quotidien), appelés en code via `gradio_client`. Entrée : la photo produit IKEA (fond blanc) de l'étagère retenue par le parcours.

| Modèle (Space) | Résultat | Durée | Notes |
|---|---|---|---|
| Stable Fast 3D (`stabilityai/stable-fast-3d`) | ❌ | 2 s | erreur interne du Space, sans détail |
| Hunyuan3D-2 (`tencent/Hunyuan3D-2`) | ✅ forme seule | 11–14 s | la version avec texture est en panne sur le Space (`texgen_worker`) ; forme très fidèle |
| TRELLIS.2 (`microsoft/TRELLIS.2`) | ✅ forme + texture bois | ~37 s | meilleur rendu, ~100 000 faces |

- **Les dimensions viennent du code, pas du modèle** : l'objet est remis à l'échelle exacte de la fiche produit (600 × 170 × 200 mm) puis placé dans la niche (800 × 250 mm, 1 cm de jeu de chaque côté au minimum).
- Proportions brutes du modèle comparées au réel (profondeur/largeur, hauteur/largeur) : Hunyuan 0,286/0,356 et TRELLIS 0,315/0,347, pour un réel de 0,283/0,333. Le modèle est proche mais pas exact, d'où la remise à l'échelle par le code.
- Limites : on dépend de Spaces publics (pannes possibles, quota GPU gratuit). Pour la démo, on pré-génère les objets et on garde un modèle de secours.
- Front : le fichier `.glb` s'affiche dans le navigateur avec `<model-viewer>`, sans aucun calcul côté Vercel.

### Comparatif image → 3D (17/11, même photo, réglages par défaut)

| Modèle | Durée | Texture | Écart de forme* | Faces | Fichier web |
|---|---|---|---|---|---|
| Hunyuan3D-2 (Tencent) | 12 s | non (module texture en panne) | **3,9 %** | 210 684 | 3,5 Mo |
| TRELLIS.2 (Microsoft) | 37 s | oui | 7,6 % | 98 754 | 2,3 Mo |
| TRELLIS v1 (Microsoft) | 27 s | oui | 8,5 % | **6 970** | **0,2 Mo** |
| Hunyuan3D-2.1 (Tencent) | 29 s | non (quota) | ❌ 138 % (plateau parasite collé à l'objet) | 322 200 | 6,4 Mo |
| TripoSG (VAST) | — | — | ❌ erreur interne du Space | | |
| Stable Fast 3D | — | — | ❌ erreur interne du Space | | |
| Unique3D, Hi3DGen, Pixal3D, frogleo | — | — | non testés : quota épuisé | | |

\* écart moyen des proportions brutes par rapport à la fiche produit, avant notre remise à l'échelle.

- **Contrainte majeure :** le quota GPU gratuit (ZeroGPU) n'est que de quelques minutes par compte et par jour, et il se recharge en ~24 h. On l'a épuisé avec ~8 générations. Les modèles lourds réservent de 270 à 600 s de GPU par appel et sont refusés dès que le reste est inférieur. Le compte PRO offre 25 min/jour, mais il est payant.
- Conséquence : on ne peut pas générer la 3D en direct pour chaque utilisateur avec un compte gratuit. Pour la démo, on **pré-génère** les objets et on les met en cache par produit (un produit = un fichier 3D, réutilisé).
- Pour le web et la réalité augmentée, **TRELLIS v1** est le meilleur compromis : texturé, 0,2 Mo, chargement instantané. **TRELLIS.2** offre le rendu le plus riche.

## Insertion d'un produit dans la photo de l'utilisateur — 17/11 (idée du tuteur)

Photo iPhone (couloir), zone libre entre le coin et le cadre de porte. Échelle calculée par le code à partir de la porte (204 cm = 505 px, soit 2,48 px/cm), donc une zone de 68 cm pour une étagère de 60 cm. Modèles d'édition d'image payés avec les crédits Inference Providers.

| Méthode | Produit fidèle ? | Taille respectée ? | Photo préservée ? | Durée |
|---|---|---|---|---|
| A0 · collé par le code | ✅ (vraie photo IKEA) | ✅ | ✅ | instantané |
| C · code + ombre portée calculée | ✅ | ✅ | ✅ | instantané |
| A · Qwen-Image-Edit-2511 « harmonise » | ❌ dessin | ❌ gros plan | ❌ recadrée en carré | 90 s |
| A · FLUX.1-Kontext « harmonise » | ❌ remplacée par un caisson | ≈ | ✅ | 19 s |
| A2 · FLUX.1-Kontext, consigne stricte | ✅ (bon modèle d'étagère) | ❌ ~2,5× trop grande | ✅ | 18 s |
| B · Qwen libre | ❌ générique | ❌ | ❌ couleurs saturées vert/orange | 15 s |
| B · FLUX libre | ❌ console générique | ❌ et mal placée | ✅ | 18 s |

- **Conclusion :** aucun modèle d'édition ne respecte à la fois le vrai produit, sa taille et sa position. Même avec une consigne stricte, FLUX agrandit l'étagère d'environ 2,5×. Une image générée « montre » donc qu'un meuble rentre alors que ce n'est pas vrai. Ça confirme la règle : **les dimensions et le placement viennent du code, jamais de l'IA générative.**
- La version « code + ombre » est fidèle mais fait un peu « collage », parce que la photo produit est en vue de 3/4 alors que le mur est vu de face. Piste : utiliser **notre objet 3D** (déjà à l'échelle) affiché par-dessus la photo et orienté comme le mur, directement dans le navigateur.
