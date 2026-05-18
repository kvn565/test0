# societe/templatetags/facture_extras.py
#
# Enregistrez ce fichier dans :
#   societe/templatetags/facture_extras.py
#
# Assurez-vous que le dossier templatetags contient un __init__.py vide.
# Chargez le filtre dans le template avec :  {% load facture_extras %}

from django import template

register = template.Library()


@register.filter(name='splitlines')
def splitlines(value):
    """
    Découpe un TextField en liste de lignes non vides.
    Utilisé dans le template de facture pour afficher
    exactement les deux premières lignes du pied de page.

    Exemple dans le template :
        {% with lignes=societe.facture_pied_page|splitlines %}
            {{ lignes.0 }}   {# ligne 1 #}
            {{ lignes.1 }}   {# ligne 2 #}
        {% endwith %}
    """
    if not value:
        return []
    # On ne garde que les lignes non vides pour éviter les lignes blanches
    return [line for line in value.splitlines() if line.strip()]
