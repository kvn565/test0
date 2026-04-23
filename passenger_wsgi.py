import os
import sys

# ====================== CHEMINS ======================
project_home = '/home/gcbvghdlauy/app.facturation.bi'

# Ajoute le dossier du projet au PYTHONPATH
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ====================== VIRTUALENV ======================
# Important : ajoute le site-packages du virtual environment
venv_path = '/home/gcbvghdlauy/virtualenv/app.facturation.bi/3.12'
if venv_path not in sys.path:
    sys.path.insert(0, venv_path + '/lib/python3.12/site-packages')

# ====================== DJANGO SETTINGS ======================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facturation.settings')

# ====================== WSGI APPLICATION ======================
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
