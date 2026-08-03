from io import StringIO

import pytest
from django.core.management import call_command

from microbe.external_apis.biosamples.api import API_ROOT
from microbe.models import Sample, SynComConstituent


@pytest.mark.django_db
def test_fetch_project_samples_imports_filtered_hierarchy_idempotently(requests_mock):
    Sample.objects.create(
        accession="SAMEA_ISOLATE",
        title="Previously misclassified isolate",
        experiment_type=Sample.ExperimentType.CRYOPRESERVATION,
    )

    requests_mock.get(
        f"{API_ROOT}/samples",
        json={
            "_links": {"next": {"href": None}},
            "_embedded": {
                "samples": [
                    {
                        "accession": "SAMEA_PARENT",
                        "name": "Top-level soil sample",
                        "webinSubmissionAccountId": "Webin-good",
                        "relationships": [
                            {
                                "source": "SAMEA_CHILD",
                                "target": "SAMEA_PARENT",
                                "type": "derived_from",
                            }
                        ],
                        "characteristics": {
                            "environmental medium": [{"text": "bulk soil"}],
                            "project": [{"text": "MICROBE"}],
                        },
                    },
                    {
                        "accession": "SAMEA_CHILD",
                        "name": "Derived synthetic community",
                        "webinSubmissionAccountId": "Webin-good",
                        "relationships": [
                            {
                                "source": "SAMEA_CHILD",
                                "target": "SAMEA_PARENT",
                                "type": "DERIVED_FROM",
                            },
                            {
                                "source": "SAMEA_CHILD",
                                "target": "SAMEA_ISOLATE",
                                "type": "DERIVED_FROM",
                            },
                        ],
                        "characteristics": {
                            "environmental medium": [{"text": "seed surface"}],
                            "preservation method": [{"text": "frozen"}],
                            "sample type": [{"text": "synthetic community"}],
                            "project": [{"text": "MICROBE"}],
                        },
                        "externalReferences": [
                            {"url": "fake://fakebiosamples/MTBLSDONUT"}
                        ],
                    },
                    {
                        "accession": "SAMEA_ISOLATE",
                        "name": "Y1",
                        "webinSubmissionAccountId": "Webin-good",
                        "relationships": [
                            {
                                "source": "SAMEA_CHILD",
                                "target": "SAMEA_ISOLATE",
                                "type": "derived_from",
                            }
                        ],
                        "characteristics": {
                            "organism": [
                                {
                                    "text": "Filobasidium stepposum",
                                    "ontologyTerms": [
                                        "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=350811"
                                    ],
                                }
                            ],
                            "sample type": [{"text": "isolate"}],
                            "project": [{"text": "MICROBE"}],
                        },
                    },
                    {
                        "accession": "SAMEA_EXCLUDED",
                        "name": "Excluded sample",
                        "webinSubmissionAccountId": "Webin-bad",
                        "characteristics": {
                            "project": [{"text": "MICROBE"}],
                        },
                    },
                ]
            },
        },
    )

    stdout = StringIO()
    call_command(
        "fetch_project_samples",
        webin_filter=["Webin-good"],
        stdout=stdout,
    )

    assert (
        "Added 2 samples, updated 0, and added 1 derivation relationships."
        in stdout.getvalue()
    )
    assert Sample.objects.count() == 2
    assert not Sample.objects.filter(accession="SAMEA_EXCLUDED").exists()
    assert not Sample.objects.filter(accession="SAMEA_ISOLATE").exists()

    parent = Sample.objects.get(accession="SAMEA_PARENT")
    child = Sample.objects.get(accession="SAMEA_CHILD")
    assert parent.environment == Sample.UseCase.SOIL
    assert child.environment == Sample.UseCase.SEED
    assert child.preservation_method == "frozen"
    assert child.experiment_type == Sample.ExperimentType.SYNCOMS
    assert child.metabolights_study == "MTBLSDONUT"
    assert list(child.derived_from.all()) == [parent]
    constituent = SynComConstituent.objects.get(accession="SAMEA_ISOLATE")
    assert constituent.organism == "Filobasidium stepposum"
    assert list(child.syncom_constituents.all()) == [constituent]

    stdout = StringIO()
    call_command(
        "fetch_project_samples",
        webin_filter=["Webin-good"],
        stdout=stdout,
    )
    assert (
        "Added 0 samples, updated 2, and added 0 derivation relationships."
        in stdout.getvalue()
    )
    assert Sample.objects.count() == 2
    child = Sample.objects.get(accession="SAMEA_CHILD")
    assert child.derived_from.count() == 1
    assert child.syncom_constituents.count() == 1
    assert SynComConstituent.objects.count() == 1
