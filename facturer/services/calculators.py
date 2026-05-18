# facturer/services/calculators.py
from decimal import Decimal
from taux.models import TauxTVA


def get_taux_tva_effectif(societe, objet=None, facture=None):
    """
    Retourne l'objet TauxTVA correct selon les règles métier.
    
    Priorités :
    1. Si société NON assujettie → toujours 0%
    2. Si facture existe et `applique_tva=False` → 0%
    3. Taux défini sur le Produit ou Service
    4. Taux par défaut de la société
    5. Fallback 0%
    """
    if not societe:
        return None

    # Règle forte : Société non assujettie à la TVA
    if not getattr(societe, 'assujeti_tva', False):
        return TauxTVA.objects.filter(
            societe=societe,
            valeur=Decimal('0.00')
        ).first()

    # Si on passe une facture et qu'elle ne veut pas appliquer la TVA
    if facture and not getattr(facture, 'applique_tva', True):
        return TauxTVA.objects.filter(
            societe=societe,
            valeur=Decimal('0.00')
        ).first()

    # Priorité au taux défini sur le Produit ou le Service
    if objet and hasattr(objet, 'taux_tva') and objet.taux_tva:
        return objet.taux_tva

    # Utilisation du manager intelligent (recommandé)
    return TauxTVA.objects.get_taux_defaut(societe)