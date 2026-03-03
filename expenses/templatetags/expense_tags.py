from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, key, value):
    """Return query string with one parameter replaced, preserving others."""
    params = context["request"].GET.copy()
    params[key] = value
    return params.urlencode()
