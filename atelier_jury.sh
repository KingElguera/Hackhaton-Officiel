#!/bin/zsh
# Marcel — garde l'atelier (Blender + TRELLIS) allumé pendant que le jury teste.
#   ./atelier_jury.sh
# - empêche le Mac de se mettre en veille tant que cette fenêtre est ouverte ;
# - relance l'atelier tout seul s'il s'arrête (coupure internet, erreur) ;
# - écrit tout dans logs/atelier_jury.log.
# Pour arrêter : Ctrl+C deux fois, ou fermer la fenêtre du Terminal.

cd "$(dirname "$0")" || exit 1
source ~/.zshrc 2>/dev/null
mkdir -p logs
echo "Atelier Marcel lancé — laisse cette fenêtre ouverte, Mac sur secteur et sur le wifi."
while true; do
  echo "[$(date '+%H:%M:%S')] démarrage de l'atelier" | tee -a logs/atelier_jury.log
  caffeinate -dimsu uv run --group outils atelier.py 2>&1 | tee -a logs/atelier_jury.log
  echo "[$(date '+%H:%M:%S')] l'atelier s'est arrêté, nouveau départ dans 10 s" | tee -a logs/atelier_jury.log
  sleep 10
done
