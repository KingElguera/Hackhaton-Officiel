"""Brique 1 — Chiffrage fournisseurs.

Une liste de produits (le chantier) × N fournisseurs. Un agent H par fournisseur relève,
au format fixe : produit, prix, unité, stock, délai, lien. Le CODE calcule ensuite, pour
chaque produit, combien d'unités acheter chez chaque fournisseur (les conditionnements
diffèrent : pot 10 L contre 2,5 L) et compare les coûts totaux → meilleur prix par produit,
et un panier par fournisseur (liens + quantités).
"""
import math
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- la demande (le chantier)
class ProduitDemande(BaseModel):
    ref: str = Field(description="identifiant court, ex. 'p1'")
    designation: str = Field(description="ce qu'il faut acheter, ex. 'Peinture acrylique blanc mat murs'")
    besoin: Optional[float] = Field(None, description="quantité nécessaire dans unite_besoin (ex. 30 pour 30 L)")
    unite_besoin: Optional[Literal["L", "m2", "pieces", "kg", "m"]] = None
    precisions: Optional[str] = Field(None, description="dimensions, couleur, finition…")


class Chantier(BaseModel):
    nom: str
    code_postal: str
    email_artisan: Optional[str] = Field(None, description="destinataire du mail « Marcel a fini » (envoyé par n8n)")
    produits: List[ProduitDemande]
    fournisseurs: dict = Field(description="{'castorama': 'https://www.castorama.fr', …}")


# ---------------------------------------------------------------- la réponse de l'agent (format fixe)
class Ligne(BaseModel):
    ref: str = Field(description="identifiant du produit DEMANDÉ (p1, p2…), recopié tel quel — jamais le code-barres")
    reference_site: Optional[str] = Field(None, description="code-barres (EAN) ou référence du produit sur le site")
    produit: Optional[str] = Field(None, description="nom exact du produit trouvé")
    prix_eur: Optional[float] = Field(None, description="prix TTC d'une unité de vente")
    unite: Optional[str] = Field(None, description="unité de vente telle qu'affichée : 'pot de 10 L', 'paquet de 2,13 m²', 'pièce'…")
    contenance: Optional[float] = Field(None, description="contenu d'une unité de vente, en nombre (10 pour 10 L, 2.13 pour 2,13 m², 1 pour une pièce)")
    unite_contenance: Optional[Literal["L", "m2", "pieces", "kg", "m"]] = None
    stock: Optional[str] = Field(None, description="disponibilité en magasin, texte affiché")
    en_stock: Optional[bool] = None
    delai_texte: Optional[str] = Field(None, description="délai de livraison, texte affiché")
    delai_jours: Optional[int] = Field(None, description="délai en jours à partir d'aujourd'hui (date la plus tardive d'une plage)")
    lien: Optional[str] = Field(None, description="URL de la fiche produit")
    image_url: Optional[str] = None


class ReleveFournisseur(BaseModel):
    acces_site: Literal["ok", "partiel", "bloque"]
    obstacle: Optional[str] = None
    magasin: Optional[str] = None
    lignes: List[Ligne] = Field(default_factory=list)
    commentaire: str


CHAMPS_FORMAT = ("produit", "prix_eur", "unite", "lien")  # + stock ou délai


def consigne(chantier: Chantier, url: str, panier: bool = False, jour: Optional[date] = None) -> str:
    liste = "\n".join(
        f"- {p.ref} : {p.designation}" + (f" ({p.precisions})" if p.precisions else "")
        for p in chantier.produits)
    fin = ("Ajoute ensuite chaque produit trouvé au panier et relève le délai de livraison affiché au panier pour "
           f"{chantier.code_postal}. Arrête-toi au panier." if panier else
           "N'ajoute rien au panier : relève le délai de livraison s'il est affiché sur la fiche.")
    return f"""Tu relèves des prix pour un artisan sur {url}. Date du jour : {(jour or date.today()).isoformat()}. Code postal du chantier : {chantier.code_postal}.
Ne crée pas de compte, ne te connecte pas, ne paie rien : on travaille sur les prix visibles sans connexion.
Si tu tombes sur un CAPTCHA ou une page "accès refusé", ne le contourne pas : arrête-toi et réponds avec acces_site = bloque.
Choisis le magasin le plus proche de {chantier.code_postal} (indique-le dans magasin).

Pour CHAQUE produit ci-dessous, cherche-le, ouvre la fiche du produit le plus proche de la demande et remplis une ligne.
IMPORTANT : dans « ref », recopie l'identifiant de la liste (p1, p2, p3…) ; le code-barres ou la référence du site va dans « reference_site ».
Renvoie les lignes dans le même ordre que la liste. Pour chaque ligne :
nom exact, prix TTC d'une unité de vente, unité de vente telle qu'affichée, contenance d'une unité en nombre + son unité (L, m2, pieces, kg, m),
disponibilité en stock dans ce magasin (texte affiché), délai de livraison (texte + nombre de jours), lien de la fiche, URL de la photo.
{fin}
Si un produit est introuvable, renvoie quand même sa ligne avec seulement ref rempli. Ne devine jamais une valeur : laisse vide ce qui n'est pas affiché.

PRODUITS :
{liste}"""


def complete(l: dict) -> bool:
    return all(l.get(c) not in (None, "") for c in CHAMPS_FORMAT) and (
        l.get("stock") not in (None, "") or l.get("delai_texte") not in (None, ""))


def evaluer(chantier: Chantier, reponse: Optional[dict]) -> dict:
    """Critères de la grille : format respecté ? combien de lignes complètes ?"""
    refs = {p.ref for p in chantier.produits}
    lignes = (reponse or {}).get("lignes") or []
    vues = {l.get("ref") for l in lignes}
    return {"nb_produits_attendus": len(refs),
            "nb_produits_corrects": sum(1 for l in lignes[:len(refs)] if complete(l)),
            "format_respecte": bool(reponse) and bool(reponse.get("acces_site")) and (refs <= vues or len(lignes) == len(refs))}


# ---------------------------------------------------------------- synthèse (le code compare)
UNITES_FR = {"m2": "m²", "pieces": "pièce(s)", "L": "L", "kg": "kg", "m": "m"}
UNITES_MOT = {"m2": "au m²", "pieces": "à la pièce", "L": "au litre", "kg": "au kilo", "m": "au mètre"}


def _fr(x, dec=None) -> str:
    """Nombre au format français : 5,23 ; 1 363,88 (dec=2 pour les prix)."""
    t = f"{x:,.{dec}f}" if dec is not None else f"{x:,g}" if abs(x) < 1e6 else f"{x:,.0f}"
    return t.replace(",", " ").replace(".", ",")


def _cout(p: ProduitDemande, l: dict):
    """Nombre d'unités à acheter et coût total pour couvrir le besoin. None si non comparable."""
    prix = l.get("prix_eur")
    if prix is None:
        return None, None, "prix absent"
    if p.besoin and p.unite_besoin == "pieces":
        cont = l.get("contenance") if l.get("unite_contenance") == "pieces" and l.get("contenance") else 1
        n = math.ceil(p.besoin / cont - 1e-9)
        return n, round(n * prix, 2), f"{_fr(p.besoin)} pièce(s)" + (f" ÷ lot de {_fr(cont)}" if cont != 1 else "") + f" → {n} × {_fr(prix, 2)} €"
    if p.besoin and p.unite_besoin:
        cont, u = l.get("contenance"), l.get("unite_contenance")
        if not cont or u != p.unite_besoin:
            vendu = f"vendu {UNITES_MOT[u]}" if u in UNITES_MOT else "contenance non affichée"
            return None, None, f"Marcel n'a pas pu comparer : {vendu}, besoin {UNITES_MOT.get(p.unite_besoin, '')}".rstrip(", ")
        n = math.ceil(p.besoin / cont - 1e-9)
        u_fr = UNITES_FR.get(p.unite_besoin, p.unite_besoin)
        return n, round(n * prix, 2), f"{_fr(p.besoin)} {u_fr} ÷ {_fr(cont)} → {n} × {_fr(prix, 2)} €"
    return 1, round(prix, 2), "1 unité (pas de besoin chiffré)"


def synthese(chantier: Chantier, releves: List[dict]) -> dict:
    """releves : [{'fournisseur': 'castorama', 'agent': ..., 'reponse': {...}}, …]"""
    par_ref = {p.ref: [] for p in chantier.produits}
    for r in releves:
        rep = r.get("reponse") or {}
        if rep.get("acces_site") == "bloque":
            continue
        for i, l in enumerate(rep.get("lignes") or []):
            p = next((x for x in chantier.produits if x.ref == l.get("ref")), None)
            if p is None and i < len(chantier.produits):  # l'agent a mis le code-barres dans ref : on se fie à l'ordre
                p = chantier.produits[i]
                l = dict(l, reference_site=l.get("reference_site") or l.get("ref"), ref=p.ref)
            if not p or not l.get("produit"):
                continue
            n, cout, calcul = _cout(p, l)
            par_ref[p.ref].append(dict(l, fournisseur=r["fournisseur"], agent=r.get("agent"),
                                       quantite=n, cout_eur=cout, calcul=calcul, complet=complete(l)))
    lignes, paniers = [], {}
    for p in chantier.produits:
        offres = sorted(par_ref[p.ref], key=lambda o: (o["cout_eur"] is None, o["cout_eur"] or 0,
                                                       o.get("delai_jours") if o.get("delai_jours") is not None else 99))
        best = offres[0] if offres and offres[0]["cout_eur"] is not None else None
        lignes.append({"ref": p.ref, "designation": p.designation, "besoin": p.besoin, "unite_besoin": p.unite_besoin,
                       "meilleure_offre": best, "offres": offres,
                       "statut": "ok" if best else ("à comparer à la main" if offres else "introuvable")})
        if best:
            paniers.setdefault(best["fournisseur"], []).append(
                {"ref": p.ref, "produit": best["produit"], "quantite": best["quantite"], "prix_eur": best["prix_eur"],
                 "cout_eur": best["cout_eur"], "lien": best.get("lien")})
    total = round(sum(l["meilleure_offre"]["cout_eur"] for l in lignes if l["meilleure_offre"]), 2)
    return {"chantier": chantier.model_dump(), "lignes": lignes, "paniers": paniers, "total_meilleurs_prix_eur": total,
            "trouves": sum(1 for l in lignes if l["meilleure_offre"]), "demandes": len(lignes)}


def synthese_md(s: dict, sessions: List[dict]) -> str:
    L = [f"# Chiffrage — {s['chantier']['nom']}", "",
         f"{s['trouves']}/{s['demandes']} produits chiffrés · **total au meilleur prix : {s['total_meilleurs_prix_eur']:.2f} € TTC**", "",
         "## Meilleur prix par produit", "", "| Réf | Produit demandé | Meilleure offre | Fournisseur | Qté | Coût | Dispo |", "|---|---|---|---|---|---|---|"]
    for l in s["lignes"]:
        b = l["meilleure_offre"]
        if b:
            dispo = b.get("stock") or b.get("delai_texte") or "—"
            L.append(f"| {l['ref']} | {l['designation']} | [{b['produit']}]({b.get('lien') or ''}) | {b['fournisseur']} | "
                     f"{b['quantite']} × {b['prix_eur']:.2f} € | **{b['cout_eur']:.2f} €** | {dispo} |")
        else:
            L.append(f"| {l['ref']} | {l['designation']} | {l['statut']} | | | | |")
    L += ["", "## Paniers prêts (liens + quantités)", ""]
    for f, items in s["paniers"].items():
        L.append(f"**{f}** — {sum(i['cout_eur'] for i in items):.2f} €")
        L += [f"- {i['quantite']} × [{i['produit']}]({i.get('lien') or ''}) — {i['cout_eur']:.2f} €" for i in items]
        L.append("")
    L += ["## Toutes les offres", "", "| Réf | Fournisseur | Produit | Unité | Prix | Calcul | Complet |", "|---|---|---|---|---|---|---|"]
    for l in s["lignes"]:
        for o in l["offres"]:
            L.append(f"| {l['ref']} | {o['fournisseur']} | {o['produit']} | {o.get('unite') or '—'} | "
                     f"{o['prix_eur'] if o['prix_eur'] is not None else '—'} | {o['calcul']} | {'✅' if o['complet'] else '⚠️'} |")
    L += ["", "## Agents", "", "| Fournisseur | Agent | Statut | Accès | Durée | Étapes | Coût | Lignes complètes | Format | Replay |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for x in sessions:
        L.append(f"| {x.get('fournisseur')} | {x.get('agent')} | {x.get('statut')} | {(x.get('reponse') or {}).get('acces_site', '—')} | "
                 f"{x.get('duree_s')} s | {x.get('etapes')} | {x.get('cout_total')} | {x.get('nb_produits_corrects')}/{x.get('nb_produits_attendus')} | "
                 f"{'✅' if x.get('format_respecte') else '❌'} | {x.get('replay_url') or ''} |")
    L += ["", "_Prix publics visibles sans connexion. Rien n'a été commandé ni payé._"]
    return "\n".join(L)
