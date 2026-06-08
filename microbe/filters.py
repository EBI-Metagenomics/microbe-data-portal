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
from microbe.workflows import workflow_choice, workflow_filter_choices


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
    preservation_method = django_filters.CharFilter(
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

    workflow_preservation_method = django_filters.ChoiceFilter(
        label="Workflow: preservation",
        choices=workflow_filter_choices("preservation_method"),
        method="filter_workflow_choice",
    )
    workflow_cryoprotectant = django_filters.ChoiceFilter(
        label="Workflow: cryoprotectant",
        choices=workflow_filter_choices("cryoprotectant"),
        method="filter_workflow_choice",
    )
    workflow_cooling_rate = django_filters.ChoiceFilter(
        label="Workflow: cooling rate",
        choices=workflow_filter_choices("cooling_rate"),
        method="filter_workflow_choice",
    )
    workflow_storage_temperature = django_filters.ChoiceFilter(
        label="Workflow: storage",
        choices=workflow_filter_choices("storage_temperature"),
        method="filter_workflow_choice",
    )
    workflow_preservation_duration = django_filters.ChoiceFilter(
        label="Workflow: duration",
        choices=workflow_filter_choices("preservation_duration"),
        method="filter_workflow_choice",
    )
    workflow_analysis = django_filters.ChoiceFilter(
        label="Workflow: analysis",
        choices=workflow_filter_choices("analysis"),
        method="filter_workflow_choice",
    )
    workflow_targets = django_filters.ChoiceFilter(
        label="Workflow: targets",
        choices=workflow_filter_choices("targets"),
        method="filter_workflow_choice",
    )
    workflow_parent = django_filters.CharFilter(
        field_name="derived_from__accession",
        lookup_expr="exact",
        label="Direct parent BioSample",
    )

    def filter_workflow_choice(self, queryset, name, value):
        if not value:
            return queryset

        stage_id = name.removeprefix("workflow_")
        workflow_item = workflow_choice(stage_id, value)
        if not workflow_item:
            return queryset.none()
        stage, choice = workflow_item
        attribute = choice.get("attribute", stage["attribute"])
        lookup = (
            "icontains"
            if choice.get("match", "exact").startswith("contains")
            else "iexact"
        )
        filters = [
            Q(**{f"attributes__{attribute}__{lookup}": raw_value})
            for raw_value in choice["values"]
        ]
        return queryset.filter(reduce(operator.or_, filters))

    class Meta:
        model = Sample
        fields = {
            "environment": ["exact"],
            "use_case": ["exact"],
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
