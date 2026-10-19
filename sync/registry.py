"""Registre des modeles synchronises.

Chaque entree decrit :
  - 'model' : la classe Django
  - 'fields' : champs simples a copier (hors FK)
  - 'fk' : dictionnaire attr -> label du modele relié (résolu par sync_uuid)

L'ordre de SYNC_ORDER garantit que les dépendances (client, produit, service)
sont poussées/recues AVANT les factures et leurs lignes.
"""

from facturer.models import Facture, LigneFacture
from clients.models import Client, TypeClient
from produits.models import Produit
from services.models import Service
from fournisseurs.models import Fournisseur

SYNC_REGISTRY = {
    'clients.TypeClient': {
        'model': TypeClient,
        'fields': ['nom'],
        'fk': {},
        'natural': ['nom'],
    },
    'clients.Client': {
        'model': Client,
        'fields': ['nom', 'nif', 'telephone', 'email', 'adresse', 'obr_mode_envoye'],
        'fk': {'type_client': 'clients.TypeClient'},
        'natural': ['nif'],
    },
    'produits.Produit': {
        'model': Produit,
        'fields': ['designation', 'code', 'prix_achat', 'prix_vente', 'unite',
                   'taux_tva', 'obr_mode_envoye', 'actif'],
        'fk': {},
        'natural': ['code'],
    },
    'services.Service': {
        'model': Service,
        'fields': ['designation', 'prix', 'obr_mode_envoye', 'actif'],
        'fk': {},
        'natural': ['designation'],
    },
    'fournisseurs.Fournisseur': {
        'model': Fournisseur,
        'fields': ['nom', 'nif', 'telephone', 'email', 'adresse', 'obr_mode_envoye'],
        'fk': {},
        'natural': ['nif'],
    },
    'facturer.Facture': {
        'model': Facture,
        'fields': [
            'numero', 'type_facture', 'date_facture', 'heure_facture',
            'bon_commande', 'devise', 'taux_tva_defaut', 'montant_remise',
            'motif_avoir', 'statut_obr', 'obr_mode_envoye', 'obr_registered_number',
            'obr_registered_date', 'electronic_signature', 'invoice_identifier',
            'message_obr', 'date_annulation', 'est_abandonnee',
        ],
        'fk': {
            'client': 'clients.Client',
            'facture_originale': 'facturer.Facture',
        },
        'natural': ['numero', 'obr_mode_envoye'],
    },
    'facturer.LigneFacture': {
        'model': LigneFacture,
        'fields': [
            'designation', 'quantite', 'prix_vente_tvac', 'prix_unitaire_ht',
            'montant_ht', 'montant_tva', 'montant_ttc', 'taux_tva', 'ordre',
        ],
        'fk': {
            'facture': 'facturer.Facture',
            'produit': 'produits.Produit',
            'service': 'services.Service',
        },
        'natural': [],
    },
}

# Ordre de synchronisation (dependances d'abord)
SYNC_ORDER = [
    'clients.TypeClient',
    'clients.Client',
    'produits.Produit',
    'services.Service',
    'fournisseurs.Fournisseur',
    'facturer.Facture',
    'facturer.LigneFacture',
]


def get_model(label):
    return SYNC_REGISTRY[label]['model']
