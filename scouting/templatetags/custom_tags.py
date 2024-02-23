from django import template

register = template.Library()


@register.filter
def getattribute(value, arg):
    """Gets an attribute of an object dynamically from a string name"""

    if hasattr(value, str(arg)):
        return getattr(value, arg)
    elif hasattr(value, 'has_key') and value.has_key(arg):
        return value[arg]
    elif isinstance(value, dict) and arg in value:
        return value[arg]
    else:
        return ''


@register.filter
def get_form_field(form, field_name):
    """Gets a form field by its name"""
    return form[field_name]
