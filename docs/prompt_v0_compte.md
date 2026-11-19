PROMPT — À COLLER DANS v0 : SE DÉCONNECTER + NE VOIR QUE SES PROPRES CHANTIERS
==============================================================================

Ne change que ce qui est décrit ici. Garde le design, les textes et les pages tels quels.

## 1. Bouton « Se déconnecter »
- Dans l'en-tête, le lien « Profil » ouvre un petit menu (ou, à défaut, la page Profil) avec en bas « Se déconnecter » (icône sortie, texte rouge discret).
- Ajoute aussi un bouton « Se déconnecter » en bas de la page `/profil`.
- Se déconnecter : efface la session de l'artisan connecté (là où le site la garde aujourd'hui), efface aussi le brouillon de fiche et les réponses en cours s'ils existent (`marcel_brouillon_fiche`, `marcel_reponses_*`, et les images du brouillon dans IndexedDB), puis redirige vers `/connexion`.
- Après déconnexion, les pages `/chantiers…` et `/profil` redirigent vers `/connexion`.

## 2. Ne voir que ses propres chantiers
- L'appel qui liste les chantiers (`GET {API}/api/chantiers`) doit envoyer l'e-mail de l'artisan connecté : `GET {API}/api/chantiers?email=<e-mail encodé avec encodeURIComponent>`.
- Vérifie que `creerChantier` envoie bien `artisan: { prenom, email }` avec l'e-mail de l'artisan connecté (c'est ce qui rattache le chantier à son compte).
- Si aucun artisan n'est connecté, n'appelle pas la liste : redirige vers `/connexion`.
- Liste vide : garde l'état vide actuel (« Aucun chantier pour l'instant » avec la mascotte et le bouton « Nouveau chantier »).

## 3. À ne pas faire
Ne change ni l'inscription, ni la connexion, ni les autres appels au back, ni le design.
