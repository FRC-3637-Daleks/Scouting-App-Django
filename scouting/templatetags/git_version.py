from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def git_version():
    return settings.GIT_VERSION
