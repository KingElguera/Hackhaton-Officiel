"""Brique 2 — Devis PDF avec les mentions obligatoires d'un devis de travaux (France).

Les totaux sont recalculés ici (jamais repris tels quels du front). Les informations
absentes sont imprimées « À compléter » plutôt qu'inventées.
"""
from datetime import date, timedelta

from fpdf import FPDF

from .chantier import totaux

BLEU = (31, 42, 68)
GRIS = (110, 116, 128)
A_COMPLETER = "À compléter"


def _eur(x: float) -> str:
    return f"{x:,.2f} €".replace(",", " ").replace(".", ",")


def _txt(v) -> str:
    if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":  # date ISO → format français
        return f"{v[8:10]}/{v[5:7]}/{v[:4]}"
    return str(v) if v not in (None, "") else A_COMPLETER


def generer(devis: dict, infos: dict, chantier: dict, numero: str) -> bytes:
    artisan = infos.get("artisan") or {}
    client = infos.get("client") or {}
    lignes = infos.get("lignes") or devis["lignes"]
    taux = float(infos.get("taux_tva") or devis["taux_tva"])
    t = totaux({"lignes": lignes, "taux_tva": taux})
    emis = date.today()
    validite = int(infos.get("validite_jours") or 30)

    pdf = FPDF(format="A4")
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    pdf.set_margins(16, 16, 16)

    # en-tête : artisan à gauche, devis à droite
    pdf.set_text_color(*BLEU)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(110, 8, _txt(artisan.get("nom_entreprise")))
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 8, "DEVIS", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=9)
    y0 = pdf.get_y()
    for l in [_txt(artisan.get("forme_juridique")), _txt(artisan.get("adresse")), f"SIRET : {_txt(artisan.get('siret'))}",
              f"{_txt(artisan.get('email'))}  ·  {_txt(artisan.get('telephone'))}"]:
        pdf.cell(110, 5, l, new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(126, y0)
    for l in [f"N° {numero}", f"Date : {emis.strftime('%d/%m/%Y')}",
              f"Valable jusqu'au {(emis + timedelta(days=validite)).strftime('%d/%m/%Y')}", "Devis gratuit"]:
        pdf.cell(0, 5, l, align="R", new_x="LEFT", new_y="NEXT")
        pdf.set_x(126)

    # client + chantier
    pdf.ln(6)
    pdf.set_fill_color(243, 245, 249)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(88, 6, "Client", fill=True)
    pdf.cell(4, 6, "")
    pdf.cell(0, 6, "Chantier", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    y = pdf.get_y()
    pdf.multi_cell(88, 5, f"{_txt(client.get('nom'))}\n{_txt(client.get('adresse'))}")
    y_fin = pdf.get_y()
    pdf.set_xy(108, y)
    pdf.multi_cell(0, 5, f"{_txt(chantier.get('nom'))} ({_txt(chantier.get('piece'))})\n"
                         f"{_txt(infos.get('adresse_chantier') or chantier.get('code_postal'))}\n"
                         f"Début prévu : {_txt(infos.get('debut_travaux'))} · durée estimée : {_txt(infos.get('duree_jours'))} j")
    pdf.set_y(max(y_fin, pdf.get_y()) + 4)

    # lignes
    cols = [("Désignation", 84, "L"), ("Qté", 16, "R"), ("Unité", 22, "L"), ("PU HT", 28, "R"), ("Total HT", 28, "R")]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*BLEU)
    pdf.set_text_color(255, 255, 255)
    for nom, w, a in cols:
        pdf.cell(w, 7, nom, align=a, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=9)
    for i, l in enumerate(lignes):
        qte = float(l["quantite"])
        pu = float(l["prix_unitaire_ht"])
        h = 6
        x, y = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(84, h, str(l["designation"]), new_x="RIGHT", new_y="TOP")
        hauteur = max(pdf.get_y(), y + h) - y
        hauteur = max(h, pdf.get_y() - y) if pdf.get_y() > y else h
        pdf.set_xy(x + 84, y)
        pdf.cell(16, h, f"{qte:g}".replace(".", ","), align="R")
        pdf.cell(22, h, str(l.get("unite") or ""))
        pdf.cell(28, h, _eur(pu), align="R")
        pdf.cell(28, h, _eur(qte * pu), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(max(pdf.get_y(), y + hauteur))
        pdf.set_draw_color(225, 228, 235)
        pdf.line(16, pdf.get_y(), 194, pdf.get_y())

    # totaux
    pdf.ln(3)
    for lib, val, gras in [("Total HT", t["total_ht"], False), (f"TVA {taux:g} %", t["tva"], False),
                           ("Total TTC", t["total_ttc"], True)]:
        pdf.set_font("Helvetica", "B" if gras else "", 10 if gras else 9)
        pdf.cell(150, 6, lib, align="R")
        pdf.cell(28, 6, _eur(val), align="R", new_x="LMARGIN", new_y="NEXT")

    # mentions
    pdf.ln(4)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(*GRIS)
    mentions = []
    if taux == 10:
        mentions.append("TVA au taux réduit de 10 % : travaux d'amélioration et d'entretien d'un local d'habitation achevé depuis "
                        "plus de deux ans (article 279-0 bis du CGI). Le client remet une attestation simplifiée avant le début des travaux.")
    mentions += [
        f"Conditions de paiement : {_txt(infos.get('conditions_paiement'))}.",
        f"Assurance décennale : {_txt(infos.get('decennale'))}.",
        f"Médiateur de la consommation : {_txt(infos.get('mediateur'))}.",
        "Prix des fournitures établis à partir des prix publics relevés le " + _txt(infos.get("releve_le")) + " ; ils peuvent évoluer.",
        "Devis à retourner signé, précédé de la mention « Bon pour accord ».",
    ]
    for m in mentions:
        pdf.multi_cell(0, 4, m)
        pdf.ln(1)

    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(88, 6, "L'entreprise")
    pdf.cell(0, 6, "Le client : « Bon pour accord », date et signature", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 205, 215)
    pdf.rect(16, pdf.get_y() + 1, 84, 26)
    pdf.rect(108, pdf.get_y() + 1, 86, 26)
    return bytes(pdf.output())
