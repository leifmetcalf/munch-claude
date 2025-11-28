from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def url_with_next(context, view_name, *args, **kwargs):
    """
    Like {% url %} but appends ?next=<path> to the URL.

    Uses request.path if available, otherwise falls back to '/'.

    Guarantees:
        - The returned URL always contains '?next=...'
        - Additional query params can be safely appended with '&'

    Usage:
        {% url_with_next 'view_name' %}
        {% url_with_next 'view_name' %}&restaurant={{ restaurant.id }}
    """
    request = context.get("request")
    next_path = request.path if request else "/"
    return reverse(view_name, args=args, kwargs=kwargs, query={"next": next_path})
