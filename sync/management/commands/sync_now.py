from django.core.management.base import BaseCommand

from superadmin.models import Societe
from sync.client import run_sync


class Command(BaseCommand):
    help = "Lance la synchronisation pour toutes les societes ayant un profil actif."

    def handle(self, *args, **opts):
        for soc in Societe.objects.all():
            profil = getattr(soc, 'sync_profile', None)
            if not profil or not profil.enabled:
                continue
            self.stdout.write(f"--- Sync {soc} ---")
            res = run_sync(soc)
            self.stdout.write(str(res))
