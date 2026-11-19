"""Tests du cœur de Marcel : tout ce que le CODE calcule (aucun appel réseau, aucune clé, aucun crédit).

    uv run --with pytest pytest -q tests

Les modèles (agents H, Qwen, Whisper, TRELLIS) sont testés à part, en vrai, par les scripts du dépôt
(résultats dans RETOURS.md) : ici on vérifie ce qui transforme leurs réponses en quantités, prix, plannings et rendus.
"""
from datetime import date
from pathlib import Path

import pytest

from marcel_core import chantier as ch
from marcel_core import chiffrage as cf
from marcel_core import dictee, plan, rendus

SALON = {"longueur_m": 5, "largeur_m": 4, "hauteur_m": 2.5, "nb_portes": 1, "nb_fenetres": 2,
         "postes": [{"poste": "murs"}, {"poste": "sol"}, {"poste": "plinthes"}]}


# ---------------------------------------------------------------- surfaces et quantités
def test_surfaces_retirent_portes_et_fenetres():
    s = ch.surfaces(SALON)
    assert s["perimetre_m"] == 18
    assert s["sol_m2"] == 20
    # 18 m × 2,5 m − 1 porte (0,83 × 2,04) − 2 fenêtres (1,20 × 1,35)
    assert s["murs_m2"] == pytest.approx(45 - 0.83 * 2.04 - 2 * 1.2 * 1.35, abs=0.01)
    assert s["plinthes_m"] == pytest.approx(18 - 0.83, abs=0.01)


def test_porte_a_creer_comptee_et_chiffree():
    f = {**SALON, "nb_portes_a_creer": 1}
    assert ch.surfaces(f)["murs_m2"] < ch.surfaces(SALON)["murs_m2"]   # la nouvelle porte n'est pas peinte
    noms = [p.designation for p in ch.produits(f, {})]
    assert any("Bloc-porte" in n for n in noms) and any("Mousse" in n for n in noms)
    assert any("bloc(s)-porte" in t for t, _ in ch.heures_estimees(f, {}))
    assert any(c["id"] == "ouvertures" for c in ch.conseils(f, {}, {"lignes": []}, {"lignes": [], "taux_tva": 10}))


def test_mur_d_accent_deux_pots_meme_quantite_totale():
    une = [p for p in ch.produits(SALON, {"teinte_murs": "gris clair", "couches_murs": "2"}) if "Peinture" in p.designation]
    deux = [p for p in ch.produits(SALON, {"teinte_murs": "gris clair, mur du fond bleu canard", "couches_murs": "2"})
            if "Peinture" in p.designation]
    assert len(une) == 1 and len(deux) == 2
    assert sum(p.besoin for p in deux) == pytest.approx(une[0].besoin, abs=0.02)
    assert "bleu canard" in deux[1].designation


# ---------------------------------------------------------------- couleurs (chiffrage et rendu 3D lisent la même chose)
@pytest.mark.parametrize("texte, base, accents", [
    ("Blanc cassé mat sur 3 murs, vert sauge mat sur le mur gauche (tête de lit)", "blanc cassé", {"gauche": "vert sauge"}),
    ("gris clair, mur du fond bleu canard", "gris clair", {"fond": "bleu canard"}),
    ("3 murs en bleu ciel et 1 mur en gris", "bleu ciel", {"fond": "gris"}),
    ("Murs blancs, mur de droite gris anthracite", "blanc", {"droit": "gris anthracite"}),
    ("rouge", "rouge", {}),
])
def test_lire_peinture(texte, base, accents):
    b, a, _ = rendus.lire_peinture(texte)
    assert b.lower() == base and a == accents


def test_sol_de_couleur_et_teinte_inconnue_signalee():
    d, alertes = rendus.depuis_fiche(SALON, {"teinte_sol": "bleu"})
    assert d.sol.teintes[0] == rendus.TEINTES["bleu"]
    _, alertes = rendus.depuis_fiche(SALON, {"teinte_sol": "fuchsia"})
    assert any("fuchsia" in a for a in alertes)


# ---------------------------------------------------------------- placement des meubles
def test_meubles_sans_chevauchement_ni_porte_bouchee():
    f = {**SALON, "meubles": [{"nom": "canapé", "largeur_cm": 210, "profondeur_cm": 95, "hauteur_cm": 85},
                              {"nom": "armoire", "largeur_cm": 100, "profondeur_cm": 58, "hauteur_cm": 185},
                              {"nom": "buffet géant", "largeur_cm": 900, "profondeur_cm": 50, "hauteur_cm": 90}]}
    d, alertes = rendus.depuis_fiche(f, {})
    assert rendus.verifier(d) == []
    assert [m.nom for m in d.meubles] == ["canapé", "armoire"]
    assert any("buffet géant" in a for a in alertes)            # ne tient nulle part : signalé, pas de plantage
    for m in d.meubles:
        for o in d.ouvertures:
            if o.mur == m.mur and o.type == "porte":
                assert m.position_cm + m.largeur_cm <= o.position_cm or m.position_cm >= o.position_cm + o.largeur_cm


def test_meuble_bas_sous_une_fenetre_mais_pas_un_meuble_haut():
    base = {**SALON, "nb_fenetres": 1}
    d, _ = rendus.depuis_fiche({**base, "meubles": [{"nom": "lit", "largeur_cm": 160, "profondeur_cm": 200, "hauteur_cm": 50,
                                                      "mur": "gauche"}]}, {})
    assert len(d.meubles) == 1
    _, alertes = rendus.depuis_fiche({**base, "meubles": [{"nom": "biblio", "largeur_cm": 160, "profondeur_cm": 35,
                                                            "hauteur_cm": 200, "mur": "gauche"}]}, {})
    assert any("biblio" in a for a in alertes)


def test_emplacements_lus_sur_le_plan_respectes():
    f = {**SALON, "nb_portes_a_creer": 1, "ouvertures": [
        {"type": "porte", "mur": "avant", "position_m": 3.87, "largeur_m": 0.83},
        {"type": "fenetre", "mur": "gauche", "position_m": 1.4, "largeur_m": 1.2},
        {"type": "fenetre", "mur": "droit", "position_m": 1.4, "largeur_m": 1.2}]}
    d, _ = rendus.depuis_fiche(f, {})
    assert ("porte", "avant", 387.0) in [(o.type, o.mur, o.position_cm) for o in d.ouvertures]
    assert len(d.ouvertures) == 4                                # 3 lues sur le plan + 1 à créer
    assert rendus.verifier(d) == []


# ---------------------------------------------------------------- prix, unités, planning
def test_calcul_des_quantites_au_format_francais():
    p = cf.ProduitDemande(ref="p1", designation="Peinture", besoin=5.23, unite_besoin="L")
    n, cout, calcul = cf._cout(p, {"prix_eur": 8.99, "contenance": 2.5, "unite_contenance": "L"})
    assert (n, cout) == (3, 26.97) and calcul == "5,23 L ÷ 2,5 → 3 × 8,99 €"


def test_prix_non_comparable_explique_sans_jargon():
    p = cf.ProduitDemande(ref="p2", designation="Plinthes", besoin=15.15, unite_besoin="m")
    n, cout, calcul = cf._cout(p, {"prix_eur": 4.5, "contenance": 1, "unite_contenance": "pieces"})
    assert n is None and cout is None and calcul.startswith("Marcel n'a pas pu comparer")


@pytest.mark.parametrize("brut, propre", [("La pièce", "pièce"), ("M2", "m²"), ("Le litre", "L"), ("pot de 2,5 L", "pot de 2,5 L")])
def test_unites_affichees(brut, propre):
    assert ch.unite_propre(brut) == propre


def test_planning_saute_les_week_ends():
    f = {**SALON, "postes": [{"poste": "murs"}, {"poste": "sol"}, {"poste": "plinthes"}], "etat_murs": "abime",
         "date_debut_souhaitee": "2030-01-04"}   # un vendredi
    jours = [date.fromisoformat(t["debut"]).weekday() for t in ch.planning(f, {}, {"lignes": []})]
    assert jours and all(j < 5 for j in jours)


# ---------------------------------------------------------------- lecture de la dictée et du plan (contrôles du code)
def test_dictee_range_les_couleurs_a_part_et_bornes():
    r = dictee.controler({"piece": "Salon", "longueur_m": 420, "largeur_m": 5, "hauteur_m": 2.5, "nb_portes": 1,
                          "nb_portes_a_creer": 1, "teinte_murs": "vert sauge", "code_postal": "75 011",
                          "postes": [{"poste": "murs", "gamme_ou_produit": None}, {"poste": "toit"}]})
    f = r["fiche"]
    assert f["longueur_m"] == 5 and f["largeur_m"] == 4.2          # « 420 » compris en centimètres, puis rangé longueur ≥ largeur
    assert f["teinte_murs"] == "vert sauge" and f["nb_portes_a_creer"] == 1 and f["code_postal"] == "75011"
    assert [p["poste"] for p in f["postes"]] == ["murs"]             # « toit » n'est pas un poste connu


def test_plan_convertit_les_centimetres_et_controle_la_surface():
    r = plan.controler({"unite": "cm", "cote_horizontale": 500, "cote_verticale": 400, "hauteur_sous_plafond": 250,
                        "surface_ecrite_m2": 30, "ouvertures": [{"type": "porte", "mur": "bas", "largeur": 83, "debut": 30}]})
    assert (r["longueur_m"], r["largeur_m"], r["hauteur_m"]) == (5.0, 4.0, 2.5)
    assert r["nb_portes"] == 1 and r["ouvertures"][0]["mur"] == "avant"
    assert any("surface écrite" in a for a in r["alertes"])         # 30 m² écrit ≠ 5 × 4 : signalé


# ---------------------------------------------------------------- cache des meubles 3D
def test_empreinte_visuelle_tolere_la_recompression(tmp_path: Path):
    PIL = pytest.importorskip("PIL.Image")
    from marcel_core import objets3d
    im = PIL.new("RGB", (400, 300), "white")
    for x in range(80, 320):
        for y in range(60, 240):
            im.putpixel((x, y), (120 + x % 40, 90, 60))
    a, b = tmp_path / "a.png", tmp_path / "b.jpg"
    im.save(a)
    im.resize((200, 150)).save(b, quality=55)                         # réduite et recompressée, comme par le site
    ea, eb = objets3d.empreinte_visuelle(a), objets3d.empreinte_visuelle(b)
    assert sum(x != y for x, y in zip(ea, eb)) <= 12
