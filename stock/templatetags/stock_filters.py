from django import template
from decimal import Decimal, ROUND_DOWN

register = template.Library()

@register.filter(name='decimal3')
def decimal3(value):
    """Affiche un nombre avec exactement 3 décimales (troncature, sans arrondi)"""
    if value is None:
        return "0.000"
    
    try:
        if isinstance(value, (int, float)):
            dec = Decimal(str(value))
        else:
            dec = Decimal(value)
        
        truncated = dec.quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        return f"{truncated:.3f}"
    
    except Exception:
        return str(value)


@register.filter(name='money3')
def money3(value, devise=""):
    """Optionnel : affiche montant + devise"""
    if value is None:
        return "0.000"
    formatted = decimal3(value)
    return f"{formatted} {devise}".strip()


@register.filter(name='stock3')
def stock3(value):
    """Stock display: tronque à 3 décimales mais sans .000 superflus"""
    if value is None:
        return "0"
    try:
        if isinstance(value, (int, float)):
            dec = Decimal(str(value))
        else:
            dec = Decimal(value)
        truncated = dec.quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        result = str(truncated).rstrip('0').rstrip('.')
        return result if result else "0"
    except Exception:
        return "0"