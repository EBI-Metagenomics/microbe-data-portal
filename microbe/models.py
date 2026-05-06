from __future__ import annotations

import logging
from typing import List

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from martor.models import MartorField

from microbe.external_apis.biosamples.api import (
    get_sample_structured_data,
    get_biosample,
)
from microbe.external_apis.ena.browser_api import get_checklist_metadata
from microbe.external_apis.ena.portal_api import get_filereport
from microbe.external_apis.metabolights.api import get_metabolights_assays
from microbe.external_apis.mgnify.api import MgnifyApi

_mgnify = MgnifyApi()


class SampleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class Sample(models.Model):
    """
    An extraction-level BioSample.
    """

    class UseCase(models.TextChoices):
        SYNCOMS = "SynComs", "SynComs"
        CRYOPRESERVATION = "Cryopreservation", "Cryopreservation"

    class Environment(models.TextChoices):
        SOIL = "Soil", "Soil"
        SEED = "Seed", "Seed"
        MARINE = "Marine", "Marine"

    METAGENOMIC_ASSEMBLY = "metagenomic_assembly"
    METAGENOMIC_AMPLICON = "metagenomic_amplicon"
    METABOLOMIC = "metabolomic"
    METABOLOMIC_TARGETED = "metabolomic_targeted"
    HISTOLOGICAL = "histological"
    HOST_GENOMIC = "host_genomic"
    TRANSCRIPTOMIC = "transcriptomic"
    META_TRANSCRIPTOMIC = "metatranscriptomic"
    IODINE = "iodine"
    FATTY_ACIDS = "fatty_acids"
    HEAVY_METALS = "heavy_metals"
    INFLAMMATORY_MARKERS = "inflammatory_markers"

    SAMPLE_TYPE_CHOICES = [
        (METAGENOMIC_ASSEMBLY, METAGENOMIC_ASSEMBLY),
        (METAGENOMIC_AMPLICON, METAGENOMIC_AMPLICON),
        (METABOLOMIC, METABOLOMIC),
        (METABOLOMIC_TARGETED, METABOLOMIC_TARGETED),
        (HISTOLOGICAL, HISTOLOGICAL),
        (HOST_GENOMIC, HOST_GENOMIC),
        (TRANSCRIPTOMIC, TRANSCRIPTOMIC),
        (META_TRANSCRIPTOMIC, META_TRANSCRIPTOMIC),
        (IODINE, IODINE),
        (FATTY_ACIDS, FATTY_ACIDS),
        (HEAVY_METALS, HEAVY_METALS),
        (INFLAMMATORY_MARKERS, INFLAMMATORY_MARKERS),
    ]

    objects = SampleManager()

    accession = models.CharField(primary_key=True, max_length=15)

    title = models.CharField(max_length=200)
    use_case = models.CharField(
        max_length=20, choices=UseCase.choices, null=True, blank=True
    )
    environment = models.CharField(
        max_length=10, choices=Environment.choices, null=True, blank=True
    )

    sample_type = models.CharField(
        max_length=20, choices=SAMPLE_TYPE_CHOICES, null=True, blank=True
    )

    metabolights_study = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return f"Sample {self.accession} - {self.title}"

    class Meta:
        ordering = ("accession",)

    @property
    def is_sequencing_sample(self):
        return self.sample_type in [
            self.HOST_GENOMIC,
            self.METAGENOMIC_AMPLICON,
            self.METAGENOMIC_ASSEMBLY,
            self.TRANSCRIPTOMIC,
            self.META_TRANSCRIPTOMIC,
        ]

    @property
    def is_metagenomic_sample(self):
        return self.sample_type in [
            self.METAGENOMIC_ASSEMBLY,
            self.METAGENOMIC_AMPLICON,
            self.META_TRANSCRIPTOMIC,
        ]

    def refresh_structureddata(
        self, structured_metadata: dict = None, checklist: list = None
    ):
        """
        Set the metadata on Sample, either using a dict of structured metadata from BioSamples,
        or optionally fetching that from the BioSamples API.
        :param checklist: Optional list of checklist data like ENA API returns, e.g. if known from sample import.
        :param structured_metadata: Optional dict of metadata sections, e.g. if known from sample import.
        :return:
        """
        if not structured_metadata:
            metadata = get_sample_structured_data(self.accession)
        else:
            metadata = structured_metadata

        for metadata_type, metadata_content in metadata.items():
            if not metadata_content:
                logging.debug(
                    f"{metadata_type=} from {self.accession} was null – skipping"
                )
                continue
            for metadatum in metadata_content:
                marker, created = SampleMetadataMarker.objects.update_or_create(
                    name=metadatum["marker"]["value"],
                    type=metadata_type,
                    defaults={"iri": metadatum["marker"]["iri"]},
                )
                if created:
                    logging.info(f"Created new SampleMetadataMarker {marker}")
                self.structured_metadata.update_or_create(
                    marker=marker,
                    defaults={
                        "source": SampleStructuredDatum.BIOSAMPLES,
                        "measurement": metadatum["measurement"]["value"],
                        "partner_name": metadatum.get("partner", {}).get("value"),
                        "partner_iri": metadatum.get("partner", {}).get("iri"),
                        "units": metadatum.get("measurement_units", {}).get("value"),
                    },
                )

        if checklist:
            checklist_metadata = checklist
        else:
            checklist_metadata = get_checklist_metadata(self.accession)

        for metadatum in checklist_metadata:
            marker, created = SampleMetadataMarker.objects.update_or_create(
                name=metadatum.tag, type="ENA Checklist"
            )
            if created:
                logging.info(f"Created new SampleMetadataMarker {marker}")
            self.structured_metadata.update_or_create(
                marker=marker,
                defaults={
                    "source": SampleStructuredDatum.ENA,
                    "measurement": metadatum.value,
                    "units": metadatum.units,
                },
            )

    def refresh_external_references(self, external_references_list: List[dict] = None):
        """
        Set the details on Sample, that come from biosamples External References.
        Either the biosamples externalReferences response section is provided,
        or optionally fetching that from the BioSamples API.
        :param external_references_list: Optional structure of `externalReferences` biosamples API response if already known.
        :return:
        """
        if not external_references_list:
            refs = get_biosample(self.accession).get("externalReferences")
        else:
            refs = external_references_list
        if not refs:
            return
        for ref in refs:
            if "MTBLS" in ref.get("url", ""):
                self.metabolights_study = f"MTBLS{ref['url'].split('MTBLS')[1]}"
                self.save()

    def get_metabolights_files(self):
        mtbls = self.metabolights_study
        if not mtbls:
            logging.info(f"No MTBLS accession is present in {self}")
            return
        assays = get_metabolights_assays(self.metabolights_study, self.accession)
        logging.info(assays)
        return assays

    def get_ena_records(self):
        return get_filereport(self.accession)


class SampleMetadataMarker(models.Model):
    """
    A metadata marker is a definition for measurements on an Animal or Sample.
    Often the definition is linked via an IRI to an ontology/controlled vocabulary.
    """

    name = models.CharField(max_length=100)
    iri = models.CharField(max_length=100, null=True, blank=True)
    type = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
        ]
        ordering = ("type",)
        unique_together = [("name", "type")]

    def __str__(self):
        return f"Sample Metadata Marker {self.id}: {self.name} ({self.type})"


class StructuredDatumManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("marker")


class AbstractStructuredDatum(models.Model):
    """
    An individual measurement on an Animal(-level Sample) or (extraction level-)Sample.
    Keyed to a SampleMetadataMarker.
    """

    ENA = "ena"
    BIOSAMPLES = "biosamples"
    SOURCE_CHOICES = [(ENA, ENA), (BIOSAMPLES, BIOSAMPLES)]

    source = models.CharField(choices=SOURCE_CHOICES, max_length=15)

    marker = models.ForeignKey(SampleMetadataMarker, on_delete=models.CASCADE)
    measurement = models.CharField(max_length=300)
    units = models.CharField(max_length=100, null=True, blank=True)

    partner_name = models.CharField(max_length=100, null=True, blank=True)
    partner_iri = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        abstract = True


class SampleStructuredDatum(AbstractStructuredDatum):
    """
    An individual measurement on an (extraction level-)Sample.
    Keyed by a SampleMetadataMarker.
    """

    objects = StructuredDatumManager()

    sample = models.ForeignKey(
        Sample, on_delete=models.CASCADE, related_name="structured_metadata"
    )

    def __str__(self):
        return f"Sample {self.sample.accession} metadata {self.marker.id}: {self.marker.name}"

    class Meta:
        ordering = (
            "marker__type",
            "marker__name",
            "id",
        )


class AnalysisSummary(models.Model):
    """
    A Markdown document describing some analysis performed by the collaboration,
    related to (e.g. using) other data types.
    """

    slug = models.SlugField(primary_key=True, max_length=200, unique=True)
    title = models.CharField(max_length=200)
    content = MartorField(
        help_text="Markdown document describing an analysis of one or more catalogues/samples"
    )
    samples = models.ManyToManyField(
        Sample, related_name="analysis_summaries", blank=True
    )
    author = models.CharField(max_length=200)
    created = models.DateTimeField(auto_created=True, auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.slug} - {self.title}"

    def get_absolute_url(self):
        return reverse("analysis_summary_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):  # new
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "analysis summaries"
        permissions = [("publish_annotation", "Can publish an analysis summary")]
