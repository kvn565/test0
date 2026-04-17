import os
from django.conf import settings
from django.utils import timezone

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def creer_dossier(type_export):
    chemin = os.path.join(settings.MEDIA_ROOT, 'rapports', type_export)
    os.makedirs(chemin, exist_ok=True)
    return chemin


def supprimer_ancien_fichier(chemin_complet):
    if os.path.exists(chemin_complet):
        try:
            os.remove(chemin_complet)
        except Exception:
            pass


def generer_pdf(titre, colonnes, lignes, type_rapport, orientation="portrait"):
    """Génère un PDF - un seul fichier par type de rapport (remplace le précédent)"""
    dossier = creer_dossier('pdf')
    nom_fichier = f"{type_rapport}.pdf"                    # ← Nom fixe (pas de timestamp)
    chemin_complet = os.path.join(dossier, nom_fichier)

    supprimer_ancien_fichier(chemin_complet)               # Supprime l'ancien avant de créer le nouveau

    # Orientation
    if orientation.lower() == "landscape":
        pagesize = landscape(A4)
    else:
        pagesize = A4

    try:
        doc = SimpleDocTemplate(
            chemin_complet, 
            pagesize=pagesize,
            rightMargin=30, 
            leftMargin=30, 
            topMargin=30, 
            bottomMargin=30
        )
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"<b>{titre}</b>", styles['Title']))
        elements.append(Spacer(1, 20))

        # Largeurs selon orientation
        if orientation.lower() == "landscape":
            col_widths = [3.8*cm, 2.3*cm, 4.2*cm, 2.8*cm, 2.2*cm, 2*cm, 2.3*cm, 2.6*cm, 3.2*cm]
        else:
            col_widths = [5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3*cm, 3.5*cm]

        data = [colonnes] + lignes
        table = Table(data, colWidths=col_widths)

        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        elements.append(table)
        doc.build(elements)

        return f"rapports/pdf/{nom_fichier}"

    except Exception as e:
        print(f"[ERREUR PDF] {e}")
        raise


def generer_excel(titre, colonnes, lignes, type_rapport):
    """Génère un Excel - un seul fichier par type de rapport"""
    dossier = creer_dossier('excel')
    nom_fichier = f"{type_rapport}.xlsx"                   # ← Nom fixe
    chemin_complet = os.path.join(dossier, nom_fichier)

    supprimer_ancien_fichier(chemin_complet)

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = titre[:31]

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="374151", end_color="374151", fill_type="solid")

        ws.append(colonnes)
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill

        for ligne in lignes:
            ws.append(ligne)

        # Ajustement colonnes
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        wb.save(chemin_complet)
        return f"rapports/excel/{nom_fichier}"

    except Exception as e:
        print(f"[ERREUR EXCEL] {e}")
        raise