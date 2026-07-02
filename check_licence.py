import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'facturation.settings'
django.setup()

from societe.models import Societe
from superadmin.models import CleActivation

s = Societe.objects.first()
print(f'=== Societe: {s.nom if s else "AUCUNE"} ===')
if s:
    cle = s.cle_active
    print(f'cle_active: {cle}')
    if cle:
        print(f'  statut: {cle.statut}')
        print(f'  utilisee: {cle.utilisee}')
        print(f'  active: {cle.active}')
        print(f'  date_fin: {cle.date_fin}')
        print(f'  jours_restants: {cle.jours_restants}')
    
    print('\nToutes les cles:')
    for c in s.cles_activation.all():
        print(f'  {c.cle_visible} | statut={c.statut} | utilisee={c.utilisee} | active={c.active} | fin={c.date_fin}')
