# clean_duplicates.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facturation.settings')  # ← Change avec ton vrai nom de projet
django.setup()

from stock.models import EntreeStock
from django.db.models import Count

print("Début du nettoyage des doublons d'entrées stock...")

# Trouver les doublons sur la clé (societe, produit, facture, type_entree)
doublons = EntreeStock.objects.values(
    'societe_id', 'produit_id', 'facture_id', 'type_entree'
).annotate(count=Count('id')).filter(count__gt=1)

for doublon in doublons:
    print(f"Doublon détecté → Societe:{doublon['societe_id']} | Produit:{doublon['produit_id']} | "
          f"Facture:{doublon['facture_id']} | Type:{doublon['type_entree']}")

    # Garder uniquement l'entrée la plus récente (la plus grande pk)
    entrees = EntreeStock.objects.filter(
        societe_id=doublon['societe_id'],
        produit_id=doublon['produit_id'],
        facture_id=doublon['facture_id'],
        type_entree=doublon['type_entree']
    ).order_by('-pk')

    to_keep = entrees.first()
    to_delete = entrees[1:]  # tout sauf la première

    for entree in to_delete:
        print(f"   → Suppression de l'entrée #{entree.pk} (quantité {entree.quantite})")
        entree.delete()

    # Optionnel : additionner les quantités sur l'entrée gardée
    if len(to_delete) > 0:
        total_quantite = sum(e.quantite for e in to_delete) + to_keep.quantite
        to_keep.quantite = total_quantite
        to_keep.save()
        print(f"   → Quantité totale mise à jour sur entrée #{to_keep.pk} → {total_quantite}")

print("\nNettoyage terminé !")