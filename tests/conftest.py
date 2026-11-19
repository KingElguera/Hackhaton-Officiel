"""Rend le dossier du projet importable pour les tests (marcel_core, api)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
