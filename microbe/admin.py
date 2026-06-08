from django.contrib import admin
from django_admin_inline_paginator.admin import TabularInlinePaginated
from unfold.admin import ModelAdmin

from microbe.models import (
    Sample,
    SampleStructuredDatum,
    AnalysisSummary,
)


class SampleMetadataInline(TabularInlinePaginated):
    model = SampleStructuredDatum
    per_page = 5
    can_delete = True
    show_change_link = True
    show_full_result_count = True


@admin.register(SampleStructuredDatum)
class SampleStructuredDatumAdmin(ModelAdmin):
    search_fields = ("sample__accession", "marker__name")


@admin.register(Sample)
class SampleAdmin(ModelAdmin):
    inlines = [SampleMetadataInline]
    list_filter = (
        "sample_type",
        "experiment_type",
        "environment",
    )
    search_fields = (
        "accession",
        "title",
    )


@admin.register(AnalysisSummary)
class AnalysisSummaryAdmin(ModelAdmin):
    readonly_fields = ["created", "updated"]
    prepopulated_fields = {"slug": ("title",)}
    fields = (
        "title",
        "author",
        "slug",
        "content",
        "samples",
        "created",
        "updated",
        "is_published",
    )
    filter_horizontal = ("samples",)

    def changeform_view(self, request, *args, **kwargs):
        self.readonly_fields = list(self.readonly_fields)
        if not request.user.is_superuser:
            self.readonly_fields = ["created", "updated", "is_published"]

        return super().changeform_view(request, *args, **kwargs)
