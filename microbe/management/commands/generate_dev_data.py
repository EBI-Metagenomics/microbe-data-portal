from typing import Union

from django.core.management.base import BaseCommand, CommandError

from microbe.external_apis.biosamples.api import add_samples_from_top_level
from microbe.models import (
    Sample,
    SampleMetadataMarker,
    AnalysisSummary,
    SynComConstituent,
)
from microbe.utils import unnest_attributes


def _attach_metadata_to(
    marker_name: str,
    marker_type: str,
    sample: Union[Sample],
    measurement=None,
    units: str = None,
):
    marker, _ = SampleMetadataMarker.objects.get_or_create(
        name=marker_name,
        defaults={"iri": f"http://example.com/{marker_name}", "type": marker_type},
    )
    sample.structured_metadata.create(
        marker=marker, measurement=measurement, units=units
    )


class Command(BaseCommand):
    help = "Fills the database with a few pieces of data for development purposes."

    def handle(self, *args, **options):
        AnalysisSummary.objects.all().delete()
        SynComConstituent.objects.all().delete()
        Sample.objects.all().delete()

        isolate_one = SynComConstituent.objects.create(
            organism="Filobasidium stepposum",
            accession="SAMEA120538186",
            attributes=unnest_attributes(
                {
                    "SRA accession": [{"text": "ERS27238873"}],
                    "center": [{"text": "INRAE"}],
                    "checklist": [{"text": "ERC000011"}],
                    "collection date": [{"text": "not provided"}],
                    "culture collection": [{"text": "not provided"}],
                    "geographic location (country and/or sea)": [
                        {"text": "not provided"}
                    ],
                    "host scientific name": [{"text": "Brassica napus"}],
                    "organism": [
                        {
                            "text": "Filobasidium stepposum",
                            "ontologyTerms": [
                                "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=350811"
                            ],
                        }
                    ],
                    "project name": [{"text": "MICROBE"}],
                    "sample subtype": [{"text": "seed"}],
                    "sample type": [{"text": "isolate"}],
                }
            ),
        )

        syncom_one = Sample.objects.create(
            accession="SAMEA120442968",
            use_case=Sample.UseCase.SYNCOMS,
            environment=Sample.Environment.SEED,
            title="S0_BYF_G_0",
            attributes=unnest_attributes(
                {
                    "SRA accession": [{"text": "ERS27143654"}],
                    "center": [{"text": "INRAE"}],
                    "checklist": [{"text": "ERC000011"}],
                    "collection date": [{"text": "2021-07-01"}],
                    "cooling rate": [{"text": "uncontrolled"}],
                    "cryoprotectant": [{"text": "none"}],
                    "environmental medium": [{"text": "Seed lot"}],
                    "freezing method": [
                        {
                            "text": "Ultra Low Temperature Freezer",
                            "ontologyTerms": [
                                "http://purl.obolibrary.org/obo/NCIT_C107398"
                            ],
                        }
                    ],
                    "freezing temperature": [
                        {
                            "text": "-80",
                            "ontologyTerms": [
                                "http://purl.obolibrary.org/obo/UO_0000027"
                            ],
                            "unit": "degree Celsius",
                        }
                    ],
                    "geographic location (country and/or sea)": [{"text": "France"}],
                    "geographic location (latitude)": [
                        {"text": "48.10889934", "unit": "DD"}
                    ],
                    "geographic location (longitude)": [
                        {"text": "-1.79270048", "unit": "DD"}
                    ],
                    "geographic location (region and locality)": [
                        {"text": "Ile et Vilaine"}
                    ],
                    "host scientific name": [{"text": "Brassica napus"}],
                    "organism": [{"text": "synthetic microbial community"}],
                    "preservation duration": [{"text": "none"}],
                    "preservation finish date": [{"text": "2025-04-30"}],
                    "preservation method": [{"text": "none"}],
                    "preservation start date": [{"text": "none"}],
                    "project name": [{"text": "MICROBE"}],
                    "sample subtype": [{"text": "seed"}],
                    "sample type": [{"text": "synthetic community"}],
                    "storage preservation temperature": [{"text": "none"}],
                }
            ),
        )

        syncom_one.syncom_constituents.add(isolate_one)

        # TODO: use fixtures instead of real API!
        add_samples_from_top_level("SAMEA115407048", 3)  # soil env, SEG20

        add_samples_from_top_level("SAMEA115716685")  # seed env, has some biolog

        summary = AnalysisSummary.objects.create(
            slug="brassica-napus-keystone-taxa",
            title="Identifying keystone taxa in the seed microbiome of Brassica Napus",
            content="""\
## Keystone taxa
In _Brassica Napus_ (Rapeseed), the keystone taxa were...

![Brassica Napus](https://upload.wikimedia.org/wikipedia/commons/5/57/Brassica_napus_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-169.jpg)
Image credit: Walther Otto Müller, Public domain, via Wikimedia Commons
""",
            is_published=True,
            author="MICROBE Team",
        )
        summary.samples.add(
            Sample.objects.filter(use_case=Sample.UseCase.SYNCOMS).first()
        )
