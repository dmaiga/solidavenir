from django import template

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