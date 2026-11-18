"""Modèles de données de Marcel (partagés par le CLI, l'API et le front via JSON).

Trois familles de besoins :
- objet      : meuble, étagère, canapé, armoire, luminaire… → doit RENTRER dans l'emplacement
- surface    : peinture, papier peint, parquet, carrelage…  → quantité calculée selon la surface
- fourniture : vis, chevilles, rouleau, colle…              → quantité simple
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Famille = Literal["objet", "surface", "fourniture"]


class Emplacement(BaseModel):
    """Place disponible donnée PAR L'UTILISATEUR (la photo ne permet pas de mesurer)."""
    largeur_mm: Optional[float] = None
    profondeur_mm: Optional[float] = None
    hauteur_mm: Optional[float] = None
    marge_mm: float = 10


class Besoin(BaseModel):
    id: str = Field(description="identifiant court, ex. 'canape', 'peinture_murs'")
    famille: Famille
    categorie: str = Field(description="ex. étagère murale, canapé, peinture, parquet, vis")
    description: str = Field(description="ce que l'utilisateur veut, en une phrase")
    quantite: int = 1
    dans_emplacement: bool = Field(False, description="objet : doit tenir dans l'emplacement mesuré")
    # contraintes de taille (mm) calculées par le CODE à partir de l'emplacement
    largeur_max_mm: Optional[float] = None
    profondeur_max_mm: Optional[float] = None
    hauteur_max_mm: Optional[float] = None
    # surface
    surface_m2: Optional[float] = None
    surface_source: Optional[str] = None
    couches: Optional[int] = None
    couleur: Optional[str] = None
    perte_pct: Optional[float] = None
    style: Optional[str] = None


class Projet(BaseModel):
    nom: str
    piece: str
    code_postal: str
    budget_eur: Optional[float] = None
    niveau: Literal["débutant", "intermédiaire", "confirmé"] = "débutant"
    emplacement: Emplacement = Field(default_factory=Emplacement)
    besoins: List[Besoin]
    hors_perimetre: List[str] = Field(default_factory=list, description="demandes que Marcel ne traite pas")
    photo: Optional[dict] = None
    alertes: List[str] = Field(default_factory=list)
    enseignes: dict = Field(default_factory=lambda: {"castorama": "https://www.castorama.fr",
                                                     "ikea": "https://www.ikea.com/fr/fr/"})


# ---------------------------------------------------------------- réponse de l'agent H
class Produit(BaseModel):
    besoin_id: str = Field(description="id du besoin auquel répond ce produit")
    nom: str
    url: Optional[str] = None
    image_url: Optional[str] = Field(None, description="URL de la photo principale du produit")
    prix_eur: Optional[float] = Field(None, description="Prix unitaire TTC affiché")
    largeur_mm: Optional[float] = Field(None, description="Largeur/longueur en millimètres (1 cm = 10 mm)")
    profondeur_mm: Optional[float] = Field(None, description="Profondeur en millimètres")
    hauteur_mm: Optional[float] = Field(None, description="Hauteur ou épaisseur en millimètres")
    contenance: Optional[float] = Field(None, description="Contenu d'une unité vendue : litres d'un pot, m² d'un paquet/rouleau, nombre de pièces d'une boîte")
    unite_contenance: Optional[Literal["L", "m2", "pieces"]] = None
    rendement_m2_par_l: Optional[float] = Field(None, description="Peinture : rendement affiché en m² par litre (par couche)")
    magasin: Optional[str] = None
    en_stock_magasin: Optional[bool] = Field(None, description="True si disponible en retrait dans le magasin choisi")
    stock_texte: Optional[str] = Field(None, description="Disponibilité telle qu'affichée")
    delai_livraison_texte: Optional[str] = Field(None, description="Délai/date de livraison tel qu'affiché")
    delai_livraison_jours: Optional[int] = Field(None, description="Nombre de jours entre aujourd'hui et la livraison")
    ajoute_au_panier: bool = False


class Rapport(BaseModel):
    acces_site: Literal["ok", "partiel", "bloque"]
    obstacle: Optional[str] = None
    produits: List[Produit] = Field(default_factory=list)
    commentaire: str
