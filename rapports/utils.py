import os
from django.conf import settings
from django.utils import timezone

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER

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


def generer_pdf(titre, colonnes, lignes, type_rapport, orientation="landscape"):
    """Génère un PDF en paysage avec retour à la ligne automatique sur les colonnes longues"""
    dossier = creer_dossier('pdf')
    nom_fichier = f"{type_rapport}.pdf"
    chemin_complet = os.path.join(dossier, nom_fichier)

    supprimer_ancien_fichier(chemin_complet)

    # Forcer le paysage
    pagesize = landscape(A4)

    try:
        doc = SimpleDocTemplate(
            chemin_complet,
            pagesize=pagesize,
            rightMargin=30,
            leftMargin=30,
            topMargin=40,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        # Style optimisé pour le wrapping (retour à la ligne)
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            wordWrap='CJK',           # Important pour le wrapping
            spaceAfter=2,
            allowWidows=0,
            allowOrphans=0,
            splitLongWords=True,
        )

        # Style pour l'en-tête
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            textColor=colors.whitesmoke,
        )

        elements = []
        elements.append(Paragraph(f"<b>{titre}</b>", styles['Title']))
        elements.append(Spacer(1, 20))

        # Préparation des données avec Paragraph pour le wrapping
        data = [[]]
        for col in colonnes:
            data[0].append(Paragraph(str(col), header_style))

        for row in lignes:
            new_row = []
            for i, cell in enumerate(row):
                cell_str = str(cell) if cell is not None else '—'

                # Colonnes qui ont besoin de wrapping (à adapter selon tes colonnes)
                if i in [2, 3, 7, 8]:  # Exemple : Produit, Désignation, Code, Commentaire, etc.
                    new_row.append(Paragraph(cell_str, cell_style))
                else:
                    new_row.append(cell_str)
            data.append(new_row)

        # Table avec largeur automatique + contrainte pour ne pas dépasser la page
        table = Table(
            data,
            colWidths=None,           # Important : laisser ReportLab calculer
            repeatRows=1,             # En-tête répété sur chaque page
            splitByRow=True           # Découpage par ligne si nécessaire
        )

        # Style du tableau
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        elements.append(table)
        doc.build(elements)

        return f"rapports/pdf/{nom_fichier}"

    except Exception as e:
        print(f"[ERREUR PDF] {e}")
        raise


# La fonction generer_excel reste inchangée (elle est déjà bien faite)
def generer_excel(titre, colonnes, lignes, type_rapport):
    """Génère un Excel - un seul fichier par type"""
    dossier = creer_dossier('excel')
    nom_fichier = f"{type_rapport}.xlsx"
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

        # Ajustement automatique des largeurs
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value or "")) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 3, 60)  # limite raisonnable
            ws.column_dimensions[column_letter].width = adjusted_width

        wb.save(chemin_complet)
        return f"rapports/excel/{nom_fichier}"

    except Exception as e:
        print(f"[ERREUR EXCEL] {e}")
        raise