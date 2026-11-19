"""Parcours artisan (Marcel Pro) : fiche → questions → produits à chiffrer → résultat → devis.

Tout ce qui est chiffré est calculé ici, par le code : surfaces à partir des dimensions,
quantités (rendement, couches, pertes), choix par défaut avec leur raison, planning, devis,
TVA. Les modèles ne servent qu'à lire les photos et à relever les prix.
Les noms de champs suivent docs/prompt_v0.md (lib/types.ts du front).
"""
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .chiffrage import Chantier, ProduitDemande

PORTE_M2, PORTE_LARGEUR_M = 0.83 * 2.04, 0.83
FENETRE_M2 = 1.20 * 1.35
RENDEMENT_L_M2 = 10.0           # m² par litre et par couche (valeur courante)
TAUX_HORAIRE_DEFAUT = 45.0      # € HT, à régler dans le profil de l'artisan
TVA_MATERIAUX_ACHAT = 0.20      # les prix publics relevés sont TTC à 20 %
FOURNISSEURS_DEFAUT = {
    "castorama": "https://www.castorama.fr",
    "bricorama": "https://www.bricorama.fr",
    "bricodepot": "https://www.bricodepot.fr",
}
ETAPES = ["comprendre", "chiffrer", "concevoir", "montrer", "rediger", "controler"]
ETAT_FRONT = {"brouillon": "brouillon", "questions": "questions", "valide": "en_recherche",
              "en_recherche": "en_recherche", "termine": "pret", "envoye": "envoye", "erreur": "en_recherche"}


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- 1. surfaces (le code mesure)
def a_creer(f: dict):
    """Portes et fenêtres que l'artisan veut créer (en plus de celles qui existent déjà)."""
    return int(f.get("nb_portes_a_creer") or 0), int(f.get("nb_fenetres_a_creer") or 0)


def ouvertures_finales(f: dict):
    """Portes et fenêtres de la pièce APRÈS travaux : celles qui existent + celles à créer."""
    pc, fc = a_creer(f)
    return int(f.get("nb_portes") or 0) + pc, int(f.get("nb_fenetres") or 0) + fc


def surfaces(f: dict) -> dict:
    L, l, H = float(f["longueur_m"]), float(f["largeur_m"]), float(f.get("hauteur_m") or 0)
    portes, fenetres = ouvertures_finales(f)
    perimetre = 2 * (L + l)
    murs = max(perimetre * H - portes * PORTE_M2 - fenetres * FENETRE_M2, 0) if H else None
    return {"perimetre_m": round(perimetre, 2), "murs_m2": round(murs, 2) if murs is not None else None,
            "plafond_m2": round(L * l, 2), "sol_m2": round(L * l, 2),
            "plinthes_m": round(max(perimetre - portes * PORTE_LARGEUR_M, 0), 2)}


# ---------------------------------------------------------------- 2. questions (générées par le code)
GAMMES = ["Entrée de gamme", "Milieu de gamme", "Haut de gamme"]
CATALOGUE_QUESTIONS = {
    "murs": [("gamme_murs", "choix_technique", "Quelle gamme de peinture pour les murs ?", GAMMES),
             ("couches_murs", "choix_technique", "Combien de couches de finition sur les murs ?", ["1", "2", "3"]),
             ("teinte_murs", "choix_gout", "Tu n'as pas précisé la teinte des murs.", None)],
    "plafond": [("gamme_plafond", "choix_technique", "Quelle gamme de peinture pour le plafond ?", GAMMES)],
    "sol": [("revetement_sol", "choix_technique", "Quel revêtement de sol ?",
             ["Parquet stratifié", "Parquet contrecollé", "Carrelage", "Sol vinyle"]),
            ("pose_sol", "choix_technique", "Quel type de pose pour le sol ?", ["Flottante", "Collée", "Clouée"]),
            ("teinte_sol", "choix_gout", "Quelle teinte ou essence pour le sol ?", None)],
    "plinthes": [("plinthes", "choix_technique", "Quelles plinthes ?", ["MDF à peindre", "Bois massif", "Carrelage"])],
    "eclairage": [("eclairage", "choix_technique", "Quel éclairage ?", ["Plafonnier", "Suspension", "Applique murale"]),
                  ("style_eclairage", "choix_gout", "Quel style pour le luminaire ?", None)],
}
DEFAUTS = {  # ce que Marcel choisit quand on lui fait confiance, et pourquoi (une ligne)
    "gamme_murs": ("Milieu de gamme", "Bon rapport qualité/prix, lessivable, tient bien dans une pièce à vivre."),
    "couches_murs": ("2", "Deux couches donnent une teinte uniforme sans reprise visible."),
    "teinte_murs": ("Blanc cassé", "Neutre, agrandit la pièce et va avec tous les sols."),
    "gamme_plafond": ("Milieu de gamme", "Une peinture plafond mate masque mieux les défauts."),
    "revetement_sol": ("Parquet stratifié", "Le plus rapide à poser et le moins cher au m²."),
    "pose_sol": ("Flottante", "Sans colle ni temps de séchage, compatible stratifié."),
    "teinte_sol": ("Chêne clair", "Le plus demandé, cache bien la poussière."),
    "plinthes": ("MDF à peindre", "Peu cher et se peint en même temps que les murs."),
    "eclairage": ("Plafonnier", "Se branche sur le point lumineux existant, sans travaux d'électricité."),
    "style_eclairage": ("Sobre et moderne", "S'accorde avec la plupart des intérieurs."),
}


def _juste_une_gamme(texte: str) -> bool:
    """« entrée de gamme », « haut de gamme »… : une gamme, pas un produit (pour le sol, ce n'est pas un revêtement)."""
    t = (texte or "").strip().lower()
    return bool(t) and ("gamme" in t or t in ("premier prix", "standard", "luxe", "économique", "economique")) and len(t) < 30


def generer_questions(f: dict) -> list:
    qs = []
    n_photos = len(f.get("photos") or [])
    if n_photos < 2:
        qs.append({"id": "photos", "bloc": "il_me_manque", "question": f"Il me faut encore {2 - n_photos} photo(s) de la pièce.",
                   "delegable": False, "type_reponse": "photo"})
    if not f.get("hauteur_m"):
        qs.append({"id": "hauteur_m", "bloc": "il_me_manque", "question": "Tu n'as pas précisé la hauteur sous plafond.",
                   "delegable": False, "type_reponse": "nombre", "unite": "m", "min": 1.8, "max": 5, "grandeur": "hauteur"})
    if not f.get("plan"):
        qs.append({"id": "plan", "bloc": "il_me_manque", "question": "Il me manque le plan (un croquis coté pris en photo suffit).",
                   "delegable": False, "type_reponse": "photo"})
    for p in f.get("postes") or []:
        poste, gamme = p.get("poste"), (p.get("gamme_ou_produit") or "").strip()
        for qid, bloc, texte, options in CATALOGUE_QUESTIONS.get(poste, []):
            if gamme and qid in ("gamme_murs", "gamme_plafond", "revetement_sol", "plinthes", "eclairage") \
                    and not (qid == "revetement_sol" and _juste_une_gamme(gamme)):
                continue  # l'artisan a déjà donné la gamme ou le produit pour ce poste
            q = {"id": qid, "bloc": bloc, "poste": poste, "question": texte, "delegable": True,
                 "type_reponse": "choix" if options else "texte"}
            if options:
                q["options"] = options
            qs.append(q)
    return qs


def appliquer_reponses(f: dict, questions: list, reponses: list):
    """Renvoie (fiche complétée, choix finaux {id: valeur}, choix délégués [ChoixDelegue])."""
    rep = {r["question_id"]: r for r in reponses or []}
    choix, delegues = {}, []
    for q in questions:
        r = rep.get(q["id"], {})
        if q["bloc"] == "il_me_manque":
            if q["id"] == "hauteur_m" and r.get("reponse"):
                f["hauteur_m"] = float(str(r["reponse"]).replace(",", "."))
            continue
        if r.get("reponse") and not r.get("delegue"):
            choix[q["id"]] = str(r["reponse"])
        else:
            valeur, raison = DEFAUTS.get(q["id"], ("Au choix de Marcel", "Choix standard."))
            choix[q["id"]] = valeur
            delegues.append({"id": q["id"], "sujet": q["question"].rstrip(" ?."), "valeur": valeur, "raison": raison,
                             "change_le_prix": q["bloc"] == "choix_technique"})
    for p in f.get("postes") or []:  # gamme saisie dans la fiche = choix de l'artisan
        g = (p.get("gamme_ou_produit") or "").strip()
        if g and p["poste"] == "sol" and _juste_une_gamme(g):
            choix.setdefault("gamme_sol", g)   # le revêtement reste à choisir (question ou défaut de Marcel)
        elif g:
            choix.setdefault({"murs": "gamme_murs", "plafond": "gamme_plafond", "sol": "revetement_sol",
                              "plinthes": "plinthes", "eclairage": "eclairage"}[p["poste"]], g)
    delegues.sort(key=lambda d: not d["change_le_prix"])  # les choix techniques d'abord
    return f, choix, delegues


# ---------------------------------------------------------------- 3. produits à chiffrer (le code calcule les quantités)
def produits(f: dict, choix: dict) -> list:
    s = surfaces(f)
    postes = {p["poste"] for p in f.get("postes") or []}
    prepa = f.get("etat_murs") in ("a_reprendre", "abime")
    P, n = [], 0

    def ajouter(designation, besoin, unite, precisions=None):
        nonlocal n
        n += 1
        P.append(ProduitDemande(ref=f"p{n}", designation=designation, besoin=round(besoin, 2), unite_besoin=unite,
                                precisions=precisions))

    if "murs" in postes and s["murs_m2"]:
        couches = int(choix.get("couches_murs", "2"))
        gamme = choix.get("gamme_murs", "milieu de gamme")
        teinte = choix.get("teinte_murs", "blanc")
        from .rendus import lire_peinture   # la même lecture que le rendu 3D : prix et maquette restent d'accord
        base, accents, _ = lire_peinture(str(teinte))
        if accents:  # « blanc cassé sur 3 murs, vert sauge sur le mur gauche » : un pot par couleur, chacun sa surface
            L, l = float(f["longueur_m"]), float(f["largeur_m"])
            cote = {"fond": L, "avant": L, "gauche": l, "droit": l}
            part = {}
            for mur, t in accents.items():
                part[t] = part.get(t, 0) + cote[mur] / (2 * (L + l))
            part_base = max(1 - sum(part.values()), 0)
            for t, k in ([(base, part_base)] if part_base else []) + list(part.items()):
                m2 = round(s["murs_m2"] * k, 2)
                murs_txt = " + ".join("mur " + m for m, x in accents.items() if x == t) if t != base or not part_base else "autres murs"
                ajouter(f"Peinture murs intérieurs {t} mat, {gamme}", m2 * couches / RENDEMENT_L_M2, "L",
                        f"{murs_txt} : ≈ {m2} m² × {couches} couches")
        else:
            ajouter(f"Peinture murs intérieurs {teinte} mat, {gamme}",
                    s["murs_m2"] * couches / RENDEMENT_L_M2, "L", f"{s['murs_m2']} m² × {couches} couches")
        if prepa:
            ajouter("Sous-couche murs intérieurs", s["murs_m2"] / RENDEMENT_L_M2, "L")
            ajouter("Enduit de rebouchage prêt à l'emploi", 1, "pieces")
    if "plafond" in postes:
        ajouter(f"Peinture plafond blanc mat, {choix.get('gamme_plafond', 'milieu de gamme')}",
                s["plafond_m2"] * 2 / RENDEMENT_L_M2, "L", f"{s['plafond_m2']} m² × 2 couches")
    if "sol" in postes:
        rev = choix.get("revetement_sol", "Parquet stratifié")
        teinte = choix.get("teinte_sol", "")
        ajouter(f"{rev} {teinte} {choix.get('gamme_sol', '')}".strip(), s["sol_m2"] * 1.10, "m2", f"{s['sol_m2']} m² + 10 % de chutes")
        if "carrelage" in rev.lower():
            ajouter("Colle carrelage sol intérieur sac 25 kg", s["sol_m2"] * 5, "kg", "≈ 5 kg/m²")
            ajouter("Joint carrelage", s["sol_m2"] * 0.5, "kg", "≈ 0,5 kg/m²")
        elif choix.get("pose_sol", "Flottante").lower().startswith("flott"):
            ajouter("Sous-couche acoustique pour parquet", s["sol_m2"] * 1.05, "m2")
    if "plinthes" in postes:
        ajouter(f"Plinthes {choix.get('plinthes', 'MDF à peindre')}", s["plinthes_m"] * 1.10, "m", f"{s['plinthes_m']} m + 10 %")
    pc, fc = a_creer(f)
    if pc:
        ajouter("Bloc-porte intérieur prêt à poser 83 x 204 cm", pc, "pieces", f"{pc} porte(s) à créer")
    if fc:
        ajouter("Fenêtre PVC 2 vantaux 120 x 135 cm", fc, "pieces", f"{fc} fenêtre(s) à créer")
    if pc or fc:
        ajouter("Mousse polyuréthane de calfeutrement", math.ceil((pc + fc) / 2), "pieces", "≈ 1 bombe pour 2 ouvertures")
    if "eclairage" in postes:
        ajouter(f"{choix.get('eclairage', 'Plafonnier')} {choix.get('style_eclairage', '')}".strip(), 1, "pieces")
    if postes & {"murs", "plafond"}:
        ajouter("Ruban de masquage peinture 50 m", 2, "pieces")
        ajouter("Bâche de protection sol 4 x 5 m", 1, "pieces")
    return P[:10]


def chantier_chiffrage(projet_id: str, f: dict, choix: dict, fournisseurs: Optional[dict] = None,
                       email: Optional[str] = None) -> Chantier:
    return Chantier(nom=f.get("nom") or f"Chantier {projet_id[:8]}", code_postal=str(f.get("code_postal") or ""),
                    email_artisan=email, produits=produits(f, choix), fournisseurs=fournisseurs or FOURNISSEURS_DEFAUT)


# ---------------------------------------------------------------- 4. planning (murs → sol → finitions)
def planning(f: dict, choix: dict, synth: dict) -> list:
    s = surfaces(f)
    postes = {p["poste"] for p in f.get("postes") or []}
    delais = {}
    for l in synth.get("lignes", []):
        b = l.get("meilleure_offre") or {}
        d = 0 if b.get("stock") else (b.get("delai_jours") or 3)
        delais[l["ref"]] = d
    delai_max = max(delais.values(), default=3)
    souhait = f.get("date_debut_souhaitee")
    debut = max(date.fromisoformat(souhait) if souhait else date.today(), date.today() + timedelta(days=delai_max + 1))
    commander_avant = (debut - timedelta(days=delai_max + 1)).isoformat()
    taches = []
    pc, fc = a_creer(f)
    if pc or fc:  # les ouvertures d'abord : la poussière et les reprises avant la peinture
        quoi = " et ".join(x for x in (f"{pc} porte(s)" if pc else "", f"{fc} fenêtre(s)" if fc else "") if x)
        taches.append((f"Créer les ouvertures et poser {quoi}", max(1, math.ceil((pc + fc) / 2))))
    if f.get("etat_murs") in ("a_reprendre", "abime") and "murs" in postes:
        taches.append(("Reboucher et poncer les murs, sous-couche", 1))
    if "plafond" in postes:
        taches.append(("Peindre le plafond (2 couches)", 1))
    if "murs" in postes:
        taches.append((f"Peindre les murs ({choix.get('couches_murs', '2')} couches)", 1 if (s["murs_m2"] or 0) <= 40 else 2))
    if "sol" in postes:
        taches.append((f"Poser le sol : {choix.get('revetement_sol', 'parquet stratifié').lower()}", max(1, math.ceil(s["sol_m2"] / 20))))
    if "plinthes" in postes:
        taches.append(("Poser les plinthes", 1))
    if "eclairage" in postes:
        taches.append(("Installer le luminaire", 1))
    out, jour = [], debut
    for i, (t, d) in enumerate(taches, 1):
        out.append({"ordre": i, "tache": t, "duree_j": d, "debut": jour.isoformat(),
                    "commander_avant": commander_avant if i == 1 else None})
        jour += timedelta(days=d)
    return out


# ---------------------------------------------------------------- 5. devis (pré-rempli, l'artisan corrige)
def heures_estimees(f: dict, choix: dict) -> list:
    s = surfaces(f)
    postes = {p["poste"] for p in f.get("postes") or []}
    h = []
    if "murs" in postes and s["murs_m2"]:
        h.append(("Main-d'œuvre : préparation et peinture des murs", s["murs_m2"] * int(choix.get("couches_murs", "2")) * 0.15))
    if "plafond" in postes:
        h.append(("Main-d'œuvre : peinture du plafond", s["plafond_m2"] * 2 * 0.2))
    if "sol" in postes:
        h.append(("Main-d'œuvre : pose du sol", s["sol_m2"] * 0.5))
    if "plinthes" in postes:
        h.append(("Main-d'œuvre : pose des plinthes", s["plinthes_m"] * 0.15))
    if "eclairage" in postes:
        h.append(("Main-d'œuvre : installation du luminaire", 1))
    pc, fc = a_creer(f)
    if pc:
        h.append((f"Main-d'œuvre : pose de {pc} bloc(s)-porte (ouverture prête)", 3 * pc))
    if fc:
        h.append((f"Main-d'œuvre : pose de {fc} fenêtre(s) (ouverture prête)", 4 * fc))
    return [(t, round(max(x, 0.5) * 2) / 2) for t, x in h]  # arrondi à la demi-heure


def devis(f: dict, choix: dict, synth: dict, taux_horaire: float = TAUX_HORAIRE_DEFAUT, marge_pct: float = 0) -> dict:
    lignes, n = [], 0
    for l in synth.get("lignes", []):
        b = l.get("meilleure_offre")
        if not b:
            continue
        n += 1
        ht = b["prix_eur"] / (1 + TVA_MATERIAUX_ACHAT) * (1 + marge_pct / 100)
        lignes.append({"id": f"l{n}", "designation": b["produit"], "quantite": b["quantite"], "unite": b.get("unite") or "u",
                       "prix_unitaire_ht": round(ht, 2), "type": "materiau", "source": "marcel"})
    if f.get("heures_main_oeuvre"):
        n += 1
        lignes.append({"id": f"l{n}", "designation": "Main-d'œuvre", "quantite": float(f["heures_main_oeuvre"]), "unite": "h",
                       "prix_unitaire_ht": taux_horaire, "type": "main_oeuvre", "source": "artisan"})
    else:
        for t, h in heures_estimees(f, choix):
            n += 1
            lignes.append({"id": f"l{n}", "designation": t, "quantite": h, "unite": "h",
                           "prix_unitaire_ht": taux_horaire, "type": "main_oeuvre", "source": "marcel"})
    return {"lignes": lignes, "taux_tva": 10 if f.get("logement_plus_de_2_ans") else 20}


def totaux(d: dict) -> dict:
    """Toujours recalculés par le code (règle n°1 du front)."""
    ht = round(sum(l["quantite"] * l["prix_unitaire_ht"] for l in d["lignes"]), 2)
    tva = round(ht * d["taux_tva"] / 100, 2)
    return {"total_ht": ht, "tva": tva, "total_ttc": round(ht + tva, 2)}


# ---------------------------------------------------------------- 6. conseils (3 au maximum, ne bloquent jamais)
def conseils(f: dict, choix: dict, synth: dict, d: dict) -> list:
    c = []
    pc, fc = a_creer(f)
    if pc or fc:
        c.append({"id": "ouvertures", "texte": "Création d'ouverture : vérifie que le mur n'est pas porteur.",
                  "explication": "Le devis chiffre les portes/fenêtres et leur pose, pas le percement du mur ni un linteau "
                                 "(mur porteur : étude obligatoire)." + (" Une nouvelle fenêtre modifie la façade : "
                                 "déclaration préalable en mairie." if fc else "")})
    budget = f.get("budget_client_eur")
    if budget:
        ttc = totaux(d)["total_ttc"]
        if ttc > budget:
            c.append({"id": "budget", "texte": f"Le devis dépasse le budget du client de {ttc - budget:.0f} €.",
                      "explication": "Passer les peintures en entrée de gamme ou retirer un poste le ferait baisser."})
    manquants = [l["designation"] for l in synth.get("lignes", []) if not l.get("meilleure_offre")]
    if manquants:
        c.append({"id": "introuvables", "texte": f"{len(manquants)} produit(s) n'ont pas pu être chiffrés.",
                  "explication": "Ajoute leur prix à la main dans le devis : " + ", ".join(manquants[:3]) + "."})
    if f.get("etat_murs") == "abime" and choix.get("couches_murs") == "1":
        c.append({"id": "couches", "texte": "Une seule couche sur des murs abîmés risque de laisser des reprises.",
                  "explication": "Deux couches après sous-couche donnent un rendu uniforme."})
    return c[:3]


# ---------------------------------------------------------------- 7. formats attendus par le front
def avancement(p: dict) -> dict:
    statut = p.get("statut") or "brouillon"
    sessions = p.get("sessions") or []
    etats = {e: "en_attente" for e in ETAPES}
    if statut not in ("brouillon", "questions"):
        etats["comprendre"] = "termine"
    if statut in ("valide", "en_recherche"):
        etats["chiffrer"] = "en_cours"
    if statut in ("termine", "envoye"):
        etats = {e: "termine" for e in ETAPES}
    if statut == "erreur":
        etats["chiffrer"] = "a_relancer"
    agents = [{"fournisseur": s["fournisseur"], "session_id": s.get("session_id"), "live_url": s.get("live_url"),
               "statut": s.get("etat_agent", "en_cours"), "etapes": s.get("etapes")} for s in sessions]
    details = {"chiffrer": f"{sum(1 for a in agents if a['statut'] != 'en_cours')}/{len(agents)} fournisseurs terminés"} if agents else {}
    if statut in ("termine", "envoye"):
        details["montrer"] = "visuel indicatif"
    return {"chantier_id": p["id"], "etat": ETAT_FRONT.get(statut, "brouillon"),
            "etapes": [{"nom": e, "etat": etats[e], **({"detail": details[e]} if e in details else {})} for e in ETAPES],
            "agents": agents}


def unite_propre(u) -> str:
    """« La pièce » → « pièce », « M2 » → « m² », « Le litre » → « L » : l'unité affichée sur les sites, en propre."""
    t = " ".join(str(u or "").replace("\u00a0", " ").split())
    bas = t.lower()
    for article in ("la ", "le ", "l'", "l’", "1 ", "à la ", "au "):
        if bas.startswith(article):
            t, bas = t[len(article):].strip(), bas[len(article):].strip()
    if bas in ("m2", "m²", "mètre carré", "metre carre", "m2s"):
        return "m²"
    if bas in ("pièce", "piece", "pièces", "pieces", "unité", "unite", "u", "pce"):
        return "pièce"
    if bas in ("litre", "litres", "l"):
        return "L"
    if bas in ("mètre", "metre", "ml", "m linéaire", "mètre linéaire"):
        return "m"
    return t


def resultat_front(p: dict) -> dict:
    r = p.get("resultat") or {}
    synth = r.get("synthese") or {}
    releve_le = r.get("releve_le") or p.get("created_at")

    def offre(o):
        return {"fournisseur": o["fournisseur"], "produit": o.get("produit"), "prix_eur": o.get("prix_eur"),
                "unite": unite_propre(o.get("unite")), "quantite": o.get("quantite"), "cout_eur": o.get("cout_eur"),
                "calcul": o.get("calcul") or "", "stock": o.get("stock"), "delai_texte": o.get("delai_texte"),
                "lien": o.get("lien") or "", "releve_le": releve_le}

    lignes = [{"ref": l["ref"], "designation": l["designation"], "besoin": l.get("besoin"), "unite_besoin": l.get("unite_besoin"),
               "meilleure_offre": offre(l["meilleure_offre"]) if l.get("meilleure_offre") else None,
               "offres": [offre(o) for o in l.get("offres", []) if o.get("prix_eur") is not None],
               "statut": {"ok": "ok", "introuvable": "introuvable"}.get(l.get("statut"), "a_comparer")}
              for l in synth.get("lignes", [])]
    paniers = [{"fournisseur": f, "total_eur": round(sum(i["cout_eur"] for i in items), 2),
                "articles": [{**i, "lien": i.get("lien") or ""} for i in items]}
               for f, items in (synth.get("paniers") or {}).items()]
    fiche = p.get("fiche") or {}
    return {
        "chantier": {"id": p["id"], "nom": p.get("nom") or fiche.get("nom"), "piece": fiche.get("piece"),
                     "cree_le": p.get("created_at"), "etat": ETAT_FRONT.get(p.get("statut"), "brouillon"), "fiche": fiche},
        "choix_delegues": p.get("choix_delegues") or [],
        "conseils": r.get("conseils") or [],
        "prix": {"lignes": lignes, "paniers": paniers, "releve_le": releve_le,
                 "total_meilleurs_prix_eur": synth.get("total_meilleurs_prix_eur", 0)},
        "devis": p.get("devis") or {"lignes": [], "taux_tva": 20},
        "visuel": r.get("visuel") or {"avant_url": None, "apres_url": None},
        "planning": r.get("planning") or [],
        "surfaces": surfaces(fiche) if fiche.get("longueur_m") else None,
    }
