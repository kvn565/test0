from django.core.management.base import BaseCommand

from superadmin.models import Societe
from sync.models import SyncProfile


class Command(BaseCommand):
    help = "Configure le profil de synchronisation local (URL online, jeton, plage de numerotation)."

    def add_arguments(self, parser):
        parser.add_argument('societe_id', type=int, help="PK de la societe")
        parser.add_argument('remote_base_url', help="URL de base online, ex: https://app.exemple.bi")
        parser.add_argument('api_token', help="Token cree par create_sync_token cote online")
        parser.add_argument('--offset', type=int, default=1000000,
                            help="Debut de numerotation local (evite les doublons OBR)")
        parser.add_argument('--disable', action='store_true', help="Desactive la sync")

    def handle(self, *args, **opts):
        soc = Societe.objects.get(pk=opts['societe_id'])
        profil, _ = SyncProfile.objects.get_or_create(societe=soc)
        profil.remote_base_url = opts['remote_base_url'].rstrip('/')
        profil.api_token = opts['api_token']
        profil.numero_offset = opts['offset']
        profil.enabled = not opts['disable']
        profil.save()

        # Applique le decalage de numerotation local (utilise par get_starting_sequence)
        soc.numero_depart = opts['offset']
        soc.save()

        self.stdout.write(
            f"SyncProfile -> enabled={profil.enabled} url={profil.remote_base_url} "
            f"offset={profil.numero_offset} (numero_depart societe={soc.numero_depart})"
        )
