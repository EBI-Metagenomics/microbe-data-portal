import operator
import shlex
from functools import reduce

import django_filters
from django.db.models import (
    Q,
    CharField,
    TextField,
    QuerySet,
    F,
    Subquery,
    OuterRef,
    Func,
)
from django.forms import NumberInput
from django.utils.safestring import mark_safe

from microbe.forms import CazyAnnotationsFilterForm
from microbe.models import (
    Sample,
    Genome,
    ViralFragment,
    GenomeSampleContainment,
    UseCase,
    Environment,
)
from microbe.utils import microbe_config


class MultiFieldSearchFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="multiple_icontains", label="Search")

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


class UseCaseFilter(django_filters.FilterSet):
    class Meta:
        model = UseCase
        fields = {
            "name": ["exact"],
        }


class EnvironmentFilter(django_filters.FilterSet):
    class Meta:
        model = Environment
        fields = {
            "name": ["exact"],
            "use_case": ["exact"],
        }


class SampleFilter(MultiFieldSearchFilter):
    class Meta:
        model = Sample
        fields = {
            "sample_type": ["exact"],
            "accession": ["icontains"],
            "environment": ["exact"],
            "environment__use_case": ["exact"],
        }


class GenomeFilter(django_filters.FilterSet):
    class Meta:
        model = Genome
        form = CazyAnnotationsFilterForm

        fields = {
            "accession": ["icontains"],
            "cluster_representative": ["icontains"],
            "taxonomy": ["icontains"],
        }

    def filter_queryset(self, queryset):
        qs = queryset
        for name, value in self.form.cleaned_data.items():
            if name in self.filters:
                qs = self.filters[name].filter(qs, value)

        filters = Q()
        if self.data:
            cazy_annotations = self.data.getlist("cazy_annotations")
            for key in cazy_annotations:
                filters &= Q(**{f"annotations__cazy__{key}__gt": 0})
        return qs.filter(filters)


class GenomeSampleContainmentFilter(django_filters.FilterSet):
    minimum_containment = django_filters.NumberFilter(
        field_name="containment",
        label="Minimum containment",
        lookup_expr="gte",
        min_value=0.0,
        max_value=1.0,
        help_text=mark_safe("Fraction of MAG kmers present in samples"),
        widget=NumberInput(
            attrs={"type": "range", "min": "0.2", "max": "1.0", "step": "0.05"}
        ),
    )

    class Meta:
        model = GenomeSampleContainment

        fields = {
            "sample__accession": ["icontains"],
        }


class ViralFragmentFilter(django_filters.FilterSet):
    ALL = "Include species-cluster members"
    REPS = "Species-cluster representatives only"

    cluster_representative_id_contains = django_filters.CharFilter(
        method="cluster_representative_id", label="Cluster representative contains"
    )

    cluster_visibility = django_filters.ChoiceFilter(
        choices=[(ALL, ALL), (REPS, REPS)],
        method="cluster_representative_status",
        label="Cluster visibility",
        help_text="Species-level cluster representatives always shown.",
    )

    class Meta:
        model = ViralFragment

        fields = {
            "id": ["icontains"],
            "contig_id": ["icontains"],
            "viral_type": ["exact"],
            "taxonomy": ["icontains"],
        }

    def cluster_representative_status(self, queryset, name, value):
        if value == self.ALL:
            return queryset
        else:
            return queryset.filter(cluster_representative__isnull=True)

    def cluster_representative_id(self, queryset, name, value):
        matches_representative = Q(id__icontains=value)
        matches_member = Q(cluster_representative__id__icontains=value)
        return queryset.filter(matches_member | matches_representative)

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            if not data.get("cluster_visibility"):
                data["cluster_visibility"] = self.REPS

        super().__init__(data, *args, **kwargs)
