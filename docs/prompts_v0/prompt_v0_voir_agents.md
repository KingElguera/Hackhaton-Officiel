PROMPT — À COLLER DANS v0 : REMETTRE LE BOUTON « REGARDER MARCEL CHERCHER »
==========================================================================

Ne change que l'écran d'attente `/chantiers/[id]/en-cours`. Garde le design, les couleurs et les textes actuels.

Sur l'écran d'attente, pour chaque fournisseur dont l'agent a un `live_url` non nul (champ déjà renvoyé par `etatDuChantier`),
remets un petit bouton secondaire (contour, pas plein) « Regarder Marcel chercher » à droite de la ligne du fournisseur :
- il ouvre `live_url` dans un nouvel onglet (`target="_blank"`, `rel="noopener noreferrer"`) ;
- sous les boutons, une seule ligne en petit et en gris : « Vue en direct sur la plateforme H Company (connexion H Company requise). » ;
- quand l'agent est fini, bloqué ou en erreur, le bouton devient « Revoir la recherche » (même lien).
Si `live_url` est nul, pas de bouton pour ce fournisseur. Ne change rien d'autre.
