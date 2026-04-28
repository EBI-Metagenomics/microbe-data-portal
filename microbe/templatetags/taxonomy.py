from django import template

register = template.Library()


@register.inclusion_tag("microbe/components/atoms/taxonomy_tooltip.html")
def taxonomy_tooltip(taxonomy: str, separator: str = ">", default: str = "—") -> dict:
    if not taxonomy:
        return {"short_tax": default, "long_tax": None}
    if separator not in taxonomy:
        return {"short_tax": taxonomy, "long_tax": None}
    return {"short_tax": taxonomy.split(separator)[-1].strip(), "long_tax": taxonomy}
