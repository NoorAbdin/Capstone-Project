from django import template
register = template.Library()

@register.filter
def split(value, arg):
     if isinstance(value, str):
        return value.split(arg)
     return value

@register.filter
def trim(value):
    if isinstance(value, str):
        return value.strip()
    return value