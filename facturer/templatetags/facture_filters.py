from django import template
from decimal import Decimal, ROUND_DOWN

register = template.Library()

@register.filter(name='truncate3')
def truncate_to_3_decimals(value):
    """Tronque strictement à 3 décimales sans arrondi (ex: 12.45678 → 12.456)"""
    if value is None:
        return "0.000"
    try:
        dec = Decimal(str(value))
        return f"{dec.quantize(Decimal('0.001'), rounding=ROUND_DOWN):.3f}"
    except:
        return "0.000"