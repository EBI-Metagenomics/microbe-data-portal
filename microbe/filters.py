import operator
from functools import reduce

import django_filters
from django import forms
from django.db.models import (
    Q,
    CharField,
    TextField,
)

from microbe.models import (
    Sample,
)


class MultiFieldSearchFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method="multiple_icontains",
        label="Search",
        help_text='E.g. "15% glycerol" grassland',
    )

    class Meta:
        fields = ["search"]

    def multiple_icontains(self, queryset, name, value):
        fields = filter(
            lambda field: isinstance(field, CharField) or isinstance(field, TextField),
            self.queryset.model._meta.fields,
        )
        return queryset.filter(
            reduce(
                operator.or_,
                (Q(**{f"{field.name}__icontains": value}) for field in fields),
            )
        )


class SampleFilter(MultiFieldSearchFilter):
    host_organism = django_filters.CharFilter(
        field_name="attributes__preservation_method",
        lookup_expr="icontains",
        label="Preservation method",
        widget=forms.TextInput(
            attrs={
                "list": "preservation-method-options",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = Sample
        fields = {
            "environment": ["exact"],
            "sample_type": ["exact"],
            "accession": ["icontains"],
        }


class SampleSynComFilter(MultiFieldSearchFilter):
    host_organism = django_filters.CharFilter(
        field_name="attributes__host_scientific_name",
        lookup_expr="icontains",
        label="Host organism",
        widget=forms.TextInput(
            attrs={
                "list": "host-organism-options",
                "autocomplete": "off",
            }
        ),
    )

    constituent_taxa = django_filters.CharFilter(
        field_name="syncom_constituents__organism",
        lookup_expr="icontains",
        label="Constituent taxa",
        help_text='E.g. "Filobasidium stepposum"',
    )

    class Meta:
        model = Sample
        fields = {
            "environment": ["exact"],
            "accession": ["icontains"],
        }
