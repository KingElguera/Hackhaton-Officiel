#!/bin/bash
# Marcel — une seule commande pour régler Hugging Face et lancer l'atelier.
#
#   ./demarrer.sh            vérifie que tout est prêt (clé, compte, modèles)
#   ./demarrer.sh essai      fabrique les images de l'exemple, sans Supabase (3 à 4 minutes)
#   ./demarrer.sh atelier    lance l'atelier : il attend les rendus demandés par le site
#   ./demarrer.sh meuble photo.jpg 210    transforme une photo de meuble en objet 3D (largeur en cm)
#
# Les clés sont demandées une fois, sans s'afficher, et rangées dans .env.
# Ce fichier est ignoré par Git : il ne part jamais dans le dépôt.

set -e
cd "$(dirname "$0")"

# uv s'installe souvent dans ~/.local/bin, que le terminal ne connaît pas toujours : on l'ajoute ici.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "L'outil « uv » n'est pas installé. L'installer une fois avec :"
  echo "    brew install uv"
  echo "ou, sans Homebrew :"
  echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

touch .env && chmod 600 .env
set -a; . ./.env; set +a

demander() {  # demander NOM "question" : lit une valeur sans l'afficher et la range dans .env
  local nom="$1" valeur
  printf "%s\n> " "$2"
  read -r -s valeur; echo
  if [ -z "$valeur" ]; then echo "Rien saisi, on continue sans."; return 1; fi
  grep -v "^${nom}=" .env > .env.tmp 2>/dev/null || true
  printf '%s=%s\n' "$nom" "$valeur" >> .env.tmp
  mv .env.tmp .env && chmod 600 .env
  export "$nom=$valeur"
}

if [ -z "$HF_TOKEN" ]; then
  echo "Il manque la clé Hugging Face. Pour la créer :"
  echo "  1. Ouvrir : https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained"
  echo "  2. Lui donner un nom (par exemple « marcel »), puis cliquer sur « Create token »."
  echo "  3. Copier la clé affichée (elle commence par hf_)."
  command -v open >/dev/null 2>&1 && open "https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained" || true
  for essai in 1 2 3; do
    demander HF_TOKEN "Coller la clé ici puis Entrée (elle ne s'affiche pas, c'est normal) :" || break
    case "$HF_TOKEN" in
      hf_*) [ ${#HF_TOKEN} -lt 60 ] && break ;;
    esac
    echo "Ce qui a été collé ne ressemble pas à une clé Hugging Face (${#HF_TOKEN} caractères)."
    echo "Une clé commence par « hf_ » et fait environ 37 caractères. Recopier la clé depuis la page, puis réessayer."
    grep -v "^HF_TOKEN=" .env > .env.tmp 2>/dev/null || true; mv .env.tmp .env; chmod 600 .env; unset HF_TOKEN
  done
fi

echo "Installation des dépendances (rapide après la première fois)…"
uv sync --group outils --quiet

case "${1:-verif}" in
  verif)
    uv run --group outils hf_verif.py
    ;;
  essai)
    uv run --group outils atelier.py --fichier cas/rendu_chambre.json
    echo "Les images sont dans out/atelier/"
    command -v open >/dev/null 2>&1 && open out/atelier || true
    ;;
  atelier)
    if [ -z "$SUPABASE_URL" ]; then
      demander SUPABASE_URL "Adresse du projet Supabase (https://xxxx.supabase.co), à demander à King :" || true
    fi
    if [ -z "$SUPABASE_SERVICE_KEY" ]; then
      demander SUPABASE_SERVICE_KEY "Clé de service Supabase (service_role), à demander à King :" || true
    fi
    uv run --group outils atelier.py
    ;;
  meuble)
    if [ -z "$2" ] || [ -z "$3" ]; then echo "Usage : ./demarrer.sh meuble photo.jpg largeur_en_cm"; exit 1; fi
    uv run --group outils meuble3d.py "$2" --largeur "$3"
    ;;
  *)
    echo "Commande inconnue : $1"; sed -n 3,7p "$0"; exit 1
    ;;
esac
