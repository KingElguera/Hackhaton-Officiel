"""Marcel — cœur partagé par l'API (api/index.py), l'atelier et les scripts."""
from .modeles import Besoin, Emplacement, Produit, Projet, Rapport  # noqa: F401

__all__ = ["Besoin", "Emplacement", "Produit", "Projet", "Rapport"]
