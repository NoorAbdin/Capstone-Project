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

from datetime import date


@register.filter
def days_until(expiration_date):
    if not expiration_date:
        return None
    today = date.today()
    if hasattr(expiration_date, 'date'):
        expiration_date = expiration_date.date()
    return (expiration_date - today).days
