import operator
from enum import Enum
from functools import reduce
from typing import Optional, List

from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.urls import reverse
from ninja import ModelSchema, NinjaAPI, Field
from ninja.pagination import RouterPaginated
from pydantic import AnyHttpUrl

from microbe.models import (
    Sample,
    SampleStructuredDatum,
    SampleMetadataMarker,
    AnalysisSummary,
    GenomeCatalogue,
    Genome,
    ViralCatalogue,
    ViralFragment,
    UseCase,
    Environment,
    GenomeSampleContainment,
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


class UseCaseEnum(Enum):
    SynComs: str = UseCase.SYNCOMS
    Cryopreservation: str = UseCase.CRYOPRESERVATION


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


class UseCaseSlimSchema(ModelSchema):
    class Meta:
        model = UseCase
        fields = ["name"]


class EnvironmentSlimSchema(ModelSchema):
    class Meta:
        model = Environment
        fields = ["name", "use_case"]


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


class UseCaseSchema(UseCaseSlimSchema):
    environments: List[EnvironmentSlimSchema]


class EnvironmentSchema(EnvironmentSlimSchema):
    samples: List[SampleSlimSchema]


class GenomeCatalogueSchema(ModelSchema):
    analysis_summaries: List[RelatedAnalysisSummarySchema]

    class Meta:
        model = GenomeCatalogue
        fields = ["id", "title", "biome", "related_mag_catalogue_id", "use_case"]


class GenomeSchema(ModelSchema):
    @staticmethod
    def resolve_representative_url(obj: Genome):
        return f"{microbe_config.mgnify.api_root}/genomes/{obj.cluster_representative}"

    representative_url: Optional[str]

    class Meta:
        model = Genome
        fields = [
            "accession",
            "cluster_representative",
            "taxonomy",
            "metadata",
            "annotations",
        ]


class GenomeSampleContainmentSchema(ModelSchema):
    class Meta:
        model = GenomeSampleContainment
        fields = ["sample", "containment"]


class GenomeWithContainingSamplesSchema(GenomeSchema):
    samples_containing: List[GenomeSampleContainmentSchema]


class ViralCatalogueSchema(ModelSchema):
    related_genome_catalogue: GenomeCatalogueSchema
    analysis_summaries: List[RelatedAnalysisSummarySchema]

    @staticmethod
    def resolve_related_genome_catalogue_url(obj: ViralCatalogue):
        return reverse(
            "api:get_genome_catalogue",
            kwargs={"catalogue_id": obj.related_genome_catalogue_id},
        )

    related_genome_catalogue_url: str

    class Meta:
        model = ViralCatalogue
        fields = ["id", "title", "biome", "use_case"]


class ViralFragmentSchema(ModelSchema):
    cluster_representative: Optional["ViralFragmentSchema"]

    @staticmethod
    def resolve_contig_url(obj: ViralFragment):
        return f"{microbe_config.mgnify.api_root}/analyses/{obj.mgnify_analysis_accession}/contigs/{obj.contig_id}"

    contig_url: AnyHttpUrl

    @staticmethod
    def resolve_mgnify_analysis_url(obj: ViralFragment):
        return (
            f"{microbe_config.mgnify.api_root}/analyses/{obj.mgnify_analysis_accession}"
        )

    mgnify_analysis_url: AnyHttpUrl

    @staticmethod
    def resolve_gff_url(obj: ViralFragment):
        return reverse("viral_fragment_gff", kwargs={"pk": obj.id})

    gff_url: str

    class Meta:
        model = ViralFragment
        fields = [
            "id",
            "contig_id",
            "mgnify_analysis_accession",
            "start_within_contig",
            "end_within_contig",
            "metadata",
            "viral_type",
            "taxonomy",
        ]


class AnalysisSummarySchema(RelatedAnalysisSummarySchema):
    samples: List[SampleSlimSchema]
    genome_catalogues: List[GenomeCatalogueSchema]
    viral_catalogues: List[ViralCatalogueSchema]

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
    use_case: UseCaseEnum = None,
):
    q_objects = []
    if use_case:
        q_objects.append(Q(environment__use_case=use_case.value))
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
    "/use-cases/{use_case_name}",
    response=UseCaseSchema,
    summary="Fetch a single Use Case from the MICROBE database.",
    description="Retrieve a single Use Case by its name. ",
    url_name="use_case_detail",
    tags=[SAMPLES],
)
def get_use_case(request, use_case_name: str):
    use_case = get_object_or_404(UseCase, pk=use_case_name)
    return use_case


@api.get(
    "/use-cases",
    response=List[UseCaseSlimSchema],
    summary="Fetch a list of Use Cases.",
    tags=[SAMPLES],
)
def list_use_cases(request):
    return UseCase.objects.all()


@api.get(
    "/environments",
    response=List[EnvironmentSlimSchema],
    summary="Fetch a list of Environments.",
    tags=[SAMPLES],
)
def list_environments(request):
    return Environment.objects.all()


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


@api.get(
    "/genome-catalogues",
    response=List[GenomeCatalogueSchema],
    summary="Fetch a list of Genome (MAG) Catalogues",
    description="Genome Catalogues are lists of Metagenomic Assembled Genomes (MAGs)"
    "MAGs originating from MICROBE samples are organised into biome-specific catalogues.",
    tags=[GENOMES],
)
def list_genome_catalogues(request):
    return GenomeCatalogue.objects.all()


@api.get(
    "/genome-catalogues/{catalogue_id}",
    response=GenomeCatalogueSchema,
    summary="Fetch a single Genome Catalogue",
    description="A Genome Catalogue is a list of Metagenomic Assembled Genomes (MAGs)."
    "MAGs originating from MICROBE samples are organised into biome-specific catalogues."
    "To list the genomes for a catalogue, use `/genome-catalogues/{catalogue_id}/genomes`.",
    url_name="get_genome_catalogue",
    tags=[GENOMES],
)
def get_genome_catalogue(request, catalogue_id: str):
    catalogue = get_object_or_404(GenomeCatalogue, id=catalogue_id)
    return catalogue


@api.get(
    "/genome-catalogues/{catalogue_id}/genomes",
    response=List[GenomeSchema],
    summary="Fetch the list of Genomes within a Catalogue",
    description="Genome Catalogues are lists of Metagenomic Assembled Genomes (MAGs)."
    "MAGs listed originate from MICROBE samples."
    "Each MAG has also been clustered with MAGs from other projects."
    "Each MICROBE MAG references the best representative of these clusters, in MGnify.",
    tags=[GENOMES],
)
def list_genome_catalogue_genomes(request, catalogue_id: str):
    catalogue = get_object_or_404(GenomeCatalogue, id=catalogue_id)
    return catalogue.genomes.all()


@api.get(
    "/genome-catalogues/{genome_catalogue_id}/genomes/{genome_id}",
    response=GenomeWithContainingSamplesSchema,
    summary="Fetch the detail of a Genome",
    description="A Genomes is a Metagenomic Assembled Genome (MAG)."
    "Each MAG originates from MICROBE samples."
    "Each MAG has also been clustered with MAGs from other projects."
    "Each MICROBE MAG references the best representative of these clusters, in MGnify."
    "Each MAG has also been searched in all of the project samples, to find samples which contain the kmers of genome.",
    tags=[GENOMES],
    url_name="get_genome",
)
def get_genome(request, genome_catalogue_id: str, genome_id: str):
    genome = get_object_or_404(Genome, accession=genome_id)
    return genome


@api.get(
    "/viral-catalogues",
    response=List[ViralCatalogueSchema],
    summary="Fetch a list of Viral (contig fragment) Catalogues",
    description="Viral Catalogues are lists of Viral Sequences,"
    "detected in the assembly contigs of MICROBE samples from a specific biome.",
    tags=[VIRUSES],
)
def list_viral_catalogues(request):
    return ViralCatalogue.objects.all()


@api.get(
    "/viral-catalogues/{catalogue_id}",
    response=ViralCatalogueSchema,
    summary="Fetch a single Viral Catalogue",
    description="A Viral Catalogue is a list of Viral Sequences,"
    "detected in the assembly contigs of MICROBE samples from a specific biome."
    "To list the viral sequences (“fragments”) for a catalogue, use `/viral-catalogues/{catalogue_id}/fragments`.",
    tags=[VIRUSES],
)
def get_viral_catalogue(request, catalogue_id: str):
    catalogue = get_object_or_404(ViralCatalogue, id=catalogue_id)
    return catalogue


@api.get(
    "/viral-catalogues/{catalogue_id}/fragments",
    response=List[ViralFragmentSchema],
    summary="Fetch the list of viral fragments (sequences) from a Catalogue",
    description="Viral fragments are sequences predicted to be viral, "
    "found in the assembly contigs of MICROBE samples."
    "The Catalogue’s viral fragments are all from the same biome."
    "Viral sequences are clustered by sequence identity, at a species-level."
    "Both cluster representatives and cluster members are included.",
    tags=[VIRUSES],
)
def list_viral_catalogue_fragments(request, catalogue_id: str):
    catalogue = get_object_or_404(ViralCatalogue, id=catalogue_id)
    return catalogue.viral_fragments.all()
