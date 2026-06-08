from typing import Union, List, Mapping

from django import template
from django.utils.html import format_html
from django.utils.safestring import SafeString

from microbe.models import Sample, SampleStructuredDatum
from microbe.utils import microbe_config

register = template.Library()


@register.filter(name="environment_metadatum")
def environment_metadatum(environment, marker_name: str) -> Union[str, None]:
    """
    Fetch a metadatum value for an environment.
    :param environment: Environment object
    :param marker_name: Metadata marker name.
    Can include '||' to denote a list of marker names that will be checked in order.
    The first present marker will be returned,
    :return: Value if one of the marker_names exists.
    """
    primary_marker_list = (
        microbe_config.tables.animals_list.default_metadata_marker_columns
    )
    datum = None
    possible_marker_names = marker_name.split("||")
    for possible_marker_name in possible_marker_names:
        if (
            hasattr(environment, "primary_metadata")
            and possible_marker_name in primary_marker_list
        ):
            try:
                datum = next(
                    m
                    for m in environment.primary_metadata
                    if m.marker.name == possible_marker_name
                )
            except StopIteration:
                # Metadata was prefetched but didn't exist on this sample
                continue
            else:
                break
        else:
            # Metadata not prefetched
            datum = environment.structured_metadata.filter(
                marker__name=possible_marker_name
            ).first()
            if datum:
                break

    if datum is None:
        return None
    measurement_includes_units = str(datum.measurement).endswith(str(datum.units))
    return f'{datum.measurement}{datum.units if datum.units and not measurement_includes_units else ""}'


@register.inclusion_tag("microbe/components/data_type_icons.html", name="data_types")
def data_type_icons(sample: Sample) -> dict:
    data_types = {sample_type[0]: False for sample_type in Sample.SAMPLE_TYPE_CHOICES}

    if not sample:
        return data_types
    if type(sample) is Sample:
        data_types[sample.sample_type] = True
    return data_types


@register.filter(name="microbe_ordering_rules")
def order_metadata_by_microbe_rules(
    metadata: List[SampleStructuredDatum],
) -> List[SampleStructuredDatum]:
    def metadata_priority(metadatum: SampleStructuredDatum):
        marker_name_lower = metadatum.marker.name.lower()
        rules = (
            microbe_config.tables.metadata_list.bring_to_top_if_metadata_marker_name_contains
        )
        for idx, rule in enumerate(rules):
            if rule in marker_name_lower:
                return idx
        return len(rules) + 1

    return sorted(metadata, key=metadata_priority)


@register.filter(name="significant_digits")
def format_significant_digits_if_number(value, sig_digits: int = 5) -> str:
    if type(value) is not str:
        return value
    try:
        return f"{float(value):.{sig_digits}g}"
    except ValueError:
        return value


@register.simple_tag
def pprint_metadatum(value) -> str | SafeString:
    if type(value) is str:
        return value
    if not isinstance(value, Mapping):
        return str(value)
    print(value)
    units = value.get("unit", "")
    label = f"{value.get('text', 'Unknown')}"
    if units:
        label += f" ({units})"
    if "ontologyterms" in value:
        first_term = (
            value["ontologyterms"][0]
            if type(value["ontologyterms"]) is list
            else value["ontologyterms"]
        )
        return format_html(
            '<a class="vf-link" href="{}" target="_blank">{}</a>', first_term, label
        )
    return label
