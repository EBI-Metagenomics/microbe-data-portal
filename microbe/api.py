import operator
from enum import Enum
from functools import reduce
from typing import Optional, List

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from ninja import ModelSchema, NinjaAPI, Field
from ninja.pagination import RouterPaginated

from microbe.models import (
    Sample,
    SampleStructuredDatum,
    SampleMetadataMarker,
    AnalysisSummary,
)
from microbe.utils import microbe_config

api = NinjaAPI(
    title="MICROBE Data Portal API",
    description="The API to browse [MICROBE](https://www.microbeproject.eu) samples and metadata, "
    "and navigate to datasets stored in public archives. \n\n #### Useful links: \n"
    "- [Documentation](https://docs.microbeproject.eu/)\n"
    "- [MICROBE Data Portal home](/)\n"
    "- [MICROBE Project Website](https://www.microbeproject.eu)\n"
    "- [Helpdesk](https://www.ebi.ac.uk/contact)\n"
    "- [TSV Export endpoints](/export/docs)",
    urls_namespace="api",
    default_router=RouterPaginated(),
)


SAMPLES = "Samples"
ANALYSES = "Analysis Summaries"
GENOMES = "Genomes"
VIRUSES = "Viruses"


class ExperimentTypeEnum(Enum):
    SynComs: str = Sample.ExperimentType.SYNCOMS
    Cryopreservation: str = Sample.ExperimentType.CRYOPRESERVATION


class SampleType(Enum):
    metagenomic_assembly: str = Sample.METAGENOMIC_ASSEMBLY
    metagenomic_amplicon: str = Sample.METAGENOMIC_AMPLICON
    metabolomic: str = Sample.METABOLOMIC
    metabolomic_targeted: str = Sample.METABOLOMIC_TARGETED
    histological: str = Sample.HISTOLOGICAL
    host_genomic: str = Sample.HOST_GENOMIC
    iodine: str = Sample.IODINE
    heavy_metals: str = Sample.HEAVY_METALS
    fatty_acids: str = Sample.FATTY_ACIDS
    transcriptomic: str = Sample.TRANSCRIPTOMIC
    meta_transcriptomic: str = Sample.META_TRANSCRIPTOMIC
    inflammatory_markers: str = Sample.INFLAMMATORY_MARKERS


class SampleMetadataMarkerSchema(ModelSchema):
    canonical_url: str = Field(None, alias="iri")

    class Meta:
        model = SampleMetadataMarker
        fields = ["name", "type"]


class SampleStructuredDatumSchema(ModelSchema):
    marker: SampleMetadataMarkerSchema

    class Meta:
        model = SampleStructuredDatum
        fields = ["marker", "measurement", "units"]


class RelatedAnalysisSummarySchema(ModelSchema):
    @staticmethod
    def resolve_canonical_url(obj: AnalysisSummary):
        return reverse("analysis_summary_detail", kwargs={"slug": obj.slug})

    canonical_url: str

    class Meta:
        model = AnalysisSummary
        fields = ["title"]


class SampleSlimSchema(ModelSchema):
    @staticmethod
    def resolve_canonical_url(obj: Sample):
        if obj.sample_type in [
            Sample.METAGENOMIC_AMPLICON,
            Sample.METAGENOMIC_ASSEMBLY,
            Sample.HOST_GENOMIC,
        ]:
            # Sample is nucleotide sequence based
            return f"{microbe_config.ena.browser_url}/{obj.accession}"
        else:
            return f"{microbe_config.biosamples.api_root}/{obj.accession}"

    canonical_url: str

    @staticmethod
    def resolve_metagenomics_url(obj: Sample):
        return (
            f"{microbe_config.mgnify.api_root}/samples/{obj.accession}"
            if obj.sample_type
            in [
                obj.METAGENOMIC_AMPLICON,
                obj.METAGENOMIC_ASSEMBLY,
                obj.META_TRANSCRIPTOMIC,
            ]
            else None
        )

    metagenomics_url: Optional[str]

    @staticmethod
    def resolve_metabolomics_url(obj: Sample):
        return (
            f"{microbe_config.metabolights.web_url}/{obj.metabolights_study}"
            if obj.metabolights_study
            else None
        )

    metabolomics_url: Optional[str]

    class Meta:
        model = Sample
        fields = ["accession", "title", "sample_type", "environment"]


class SampleSchema(SampleSlimSchema):
    structured_metadata: List[SampleStructuredDatumSchema]
    analysis_summaries: List[RelatedAnalysisSummarySchema]


class AnalysisSummarySchema(RelatedAnalysisSummarySchema):
    samples: List[SampleSlimSchema]

    class Meta:
        model = AnalysisSummary
        fields = ["title"]


@api.get(
    "/samples/{sample_accession}",
    response=SampleSchema,
    summary="Fetch a single Sample from the MICROBE database.",
    description="Retrieve a single Sample by its ENA accession, including all structured metadata available. ",
    url_name="sample_detail",
    tags=[SAMPLES],
)
def get_sample(request, sample_accession: str):
    sample = get_object_or_404(Sample, accession=sample_accession)
    return sample


@api.get(
    "/samples",
    response=List[SampleSlimSchema],
    summary="Fetch a list of Samples.",
    description="Long lists will be paginated, so use the `page=` query parameter to get more pages. "
    "Several filters are available, which mostly perform case-insensitive containment lookups. "
    "Sample metadata are *not* returned for each item. "
    "Use the `/samples/{sample_accession}` endpoint to retrieve those. "
    "Use `/sample_metadata_markers` to find the exact marker name of interest.",
    tags=[SAMPLES],
)
def list_samples(
    request,
    accession: str = None,
    title: str = None,
    sample_type: SampleType = None,
    experment_type: ExperimentTypeEnum = None,
):
    q_objects = []
    if experment_type:
        q_objects.append(Q(experment_type=experment_type.value))
    if accession:
        q_objects.append(Q(accession__icontains=accession))
    if title:
        q_objects.append(Q(title__icontains=title))
    if sample_type:
        q_objects.append(Q(sample_type=sample_type.value))

    if not q_objects:
        return Sample.objects.all()
    return Sample.objects.filter(reduce(operator.and_, q_objects))


@api.get(
    "/sample_metadata_markers",
    response=List[SampleMetadataMarkerSchema],
    summary="Fetch a list of structured metadata markers (i.e. keys).",
    description="Each marker is present in the metadata of at least one sample. "
    "Not every sample will have every metadata marker. "
    "Long lists will be paginated, so use the `page=` query parameter to get more pages. "
    "Use `name=` to search for a marker by name (case insensitive partial matches). ",
    tags=[SAMPLES],
)
def list_sample_metadata_markers(
    request,
    name: str = None,
):
    if name:
        return SampleMetadataMarker.objects.filter(name__icontains=name)
    return SampleMetadataMarker.objects.all()


@api.get(
    "/analysis-summaries",
    response=List[AnalysisSummarySchema],
    summary="Fetch a list of Analysis Summary documents.",
    description="Analysis Summary documents are produced by MICROBE partners and collaborators. "
    "Each summary is tagged as involving 1 or more Samples or Catalogues. "
    "Typically these are aggregative or comparative analyses of the Samples. "
    "These are text and graphic documents. "
    "They are not intended for programmatic consumption, so a website URL is returned for each. ",
    tags=[ANALYSES],
)
def list_analysis_summaries(
    request,
):
    return AnalysisSummary.objects.filter(is_published=True)
