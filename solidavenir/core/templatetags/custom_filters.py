from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter
def map_attribute(queryset, attribute_name):
    """Retourne une liste des valeurs d'un attribut pour des objets ou des dictionnaires"""
    result = []
    for item in queryset:
        if isinstance(item, dict):
            # Pour les dictionnaires
            result.append(item.get(attribute_name, ''))
        else:
            # Pour les objets
            result.append(getattr(item, attribute_name, ''))
    return result

@register.filter
def get_item(dictionary, key):
    """Retourne la valeur d'un dictionnaire par clé"""
    return dictionary.get(key)

@register.filter
def split(value, delimiter):
    """Split a string by the given delimiter"""
    return value.split(delimiter)



@register.filter
def get_statut_color(statut):
    """
    Retourne la classe Bootstrap en fonction du statut
    """
    color_map = {
        'brouillon': 'secondary',
        'en_cours': 'primary',
        'en_attente': 'warning',
        'termine': 'success',
        'annule': 'danger',
        'suspendu': 'info'
    }
    return color_map.get(statut, 'secondary')

@register.filter
def format_montant(value):
    """
    Formatte un montant avec intcomma et 2 décimales
    """
    if value is None:
        return ""
    try:
        # Utilise intcomma pour les séparateurs de milliers
        formatted = intcomma(floatformat(value, 2))
        return f"{formatted} FCFA"
    except (ValueError, TypeError):
        return str(value)

# Vous pouvez aussi enregistrer intcomma directement si besoin
register.filter('intcomma', intcomma)