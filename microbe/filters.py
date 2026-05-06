import operator
from functools import reduce

import django_filters
from django.db.models import (
    Q,
    CharField,
    TextField,
)

from microbe.models import (
    Sample,
)


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


class SampleFilter(MultiFieldSearchFilter):
    class Meta:
        model = Sample
        fields = {
            "use_case": ["exact"],
            "environment": ["exact"],
            "sample_type": ["exact"],
            "accession": ["icontains"],
        }
