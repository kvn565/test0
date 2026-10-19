from django.core.management.base import BaseCommand
import uuid

from superadmin.models import Societe
from sync.models import SyncToken


class Command(BaseCommand):
    help = "Cree (ou regenere) un jeton d'API de synchronisation pour une societe."

    def add_arguments(self, parser):
        parser.add_argument('societe_id', type=int, help="PK de la societe")
        parser.add_argument('--show', action='store_true', help="Afficher le jeton existant sans le regenerer")

    def handle(self, *args, **opts):
        soc = Societe.objects.get(pk=opts['societe_id'])
        tok, _ = SyncToken.objects.get_or_create(societe=soc)
        if not opts['show'] or not tok.token:
            tok.token = uuid.uuid4().hex
            tok.save()
        self.stdout.write(f"Societe : {soc.nom if hasattr(soc,'nom') else soc}")
        self.stdout.write(f"URL a configurer cote local : https://<domaine-cpanel>/sync/")
        self.stdout.write(f"Token : {tok.token}")
