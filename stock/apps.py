# stock/apps.py

from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stock'
    verbose_name = "Stock"

    def ready(self):
        """
        Cette méthode est exécutée quand l'application stock est prête.
        On importe ici nos services pour éviter les erreurs d'import circulaire.
        """
        try:
            from .services.stock_service import nettoyer_avant_nouvelle_entree
            
            # Optionnel : tu peux enregistrer des signaux ici plus tard
            # Exemple :
            # from django.db.models.signals import pre_save
            # from .models import EntreeStock
            # pre_save.connect(nettoyer_avant_nouvelle_entree, sender=EntreeStock)
            
            print("Stock app : services charges avec succes")
            
        except ImportError as e:
            print(f"Stock app : Impossible de charger les services - {e}")
        except Exception as e:
            print(f"X Erreur inattendue dans StockConfig.ready() : {e}")