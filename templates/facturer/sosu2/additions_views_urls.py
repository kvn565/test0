# ═══════════════════════════════════════════════════════════════
#  À AJOUTER dans facturer/views.py
# ═══════════════════════════════════════════════════════════════

# ── Ajouter ces 2 imports en haut si pas déjà présents ──
from django.shortcuts import render, get_object_or_404
# (déjà présent normalement)


# ── Objet entreprise (à adapter selon votre modèle de paramètres) ──
# Option 1 : Depuis un modèle Parametre / Entreprise
#   from parametres.models import Entreprise
#   entreprise = Entreprise.objects.first()

# Option 2 : Dictionnaire simple (si pas de modèle paramètres)
ENTREPRISE_INFO = {
    'nom':              'BLANSA COMPANY',
    'nif':              '4002869750',
    'registre_commerce':'0063103/24',
    'telephone':        '+257 67 20 26 46',
    'email':            'blansacompany1@gmail.com',
    'commune':          'MUKAZA',
    'quartier':         'ROHERO II',
    'avenue':           'Chaussée du Prince Louis Rwagasore',
    'numero_rue':       '-',
    'assujeti_tva':     False,
    'centre_fiscal':    'DPMC',
    'forme_juridique':  'SOCIETE PRIVE',
    'secteur_activite': 'AUTRES SERVICES MARCHANTS',
    'titre_signataire': 'Directeur Gérant',
    'nom_signataire':   'NSAVYUMUREMYI Blaise',
}


# ══════════════════════════════════════════════
#  VUE — IMPRESSION A4
# ══════════════════════════════════════════════
def facture_imprimer_a4(request, pk):
    facture     = get_object_or_404(Facture.objects.select_related('client'), pk=pk)
    lignes      = facture.lignes.select_related('produit', 'service').all()

    # Montant en lettres (installez num2words : pip install num2words)
    # from num2words import num2words
    # montant_lettres = num2words(facture.total_ttc, lang='fr').capitalize() + ' franc burundais.'
    montant_lettres = ''   # ← remplacez par la ligne ci-dessus si num2words installé

    return render(request, 'facturer/print_a4.html', {
        'facture':         facture,
        'lignes':          lignes,
        'entreprise':      ENTREPRISE_INFO,   # ou votre objet Entreprise
        'montant_lettres': montant_lettres,
        'qr_code_url':     None,              # URL vers image QR OBR si disponible
    })


# ══════════════════════════════════════════════
#  VUE — IMPRESSION POS (ticket thermique)
# ══════════════════════════════════════════════
def facture_imprimer_pos(request, pk):
    facture     = get_object_or_404(Facture.objects.select_related('client'), pk=pk)
    lignes      = facture.lignes.select_related('produit', 'service').all()

    # Montant en lettres
    # from num2words import num2words
    # montant_lettres = num2words(facture.total_ttc, lang='fr').capitalize() + ' franc burundais.'
    montant_lettres = ''

    return render(request, 'facturer/print_pos.html', {
        'facture':         facture,
        'lignes':          lignes,
        'entreprise':      ENTREPRISE_INFO,
        'montant_lettres': montant_lettres,
        'qr_code_url':     None,
    })


# ═══════════════════════════════════════════════════════════════
#  À AJOUTER dans facturer/urls.py
# ═══════════════════════════════════════════════════════════════
#
#  from . import views
#
#  urlpatterns = [
#      ...
#      path('<int:pk>/imprimer/a4/',   views.facture_imprimer_a4,  name='imprimer_a4'),
#      path('<int:pk>/imprimer/pos/',  views.facture_imprimer_pos, name='imprimer_pos'),
#      ...
#  ]
#
# ═══════════════════════════════════════════════════════════════
