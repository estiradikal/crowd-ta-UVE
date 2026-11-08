from django import template

from ..panel_preferences import DEFAULT_LANGUAGE, translate

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, text):
    """{% t "Dashboard" %} -> texto en el idioma elegido en Configuración."""
    return translate(text, context.get('panel_lang', DEFAULT_LANGUAGE))
