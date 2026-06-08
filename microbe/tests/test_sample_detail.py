import pytest
from django.urls import reverse

from microbe.models import Sample, SynComConstituent


@pytest.mark.django_db
def test_syncom_sample_detail_renders_constituent_taxa(client):
    sample = Sample.objects.create(
        accession="SAMEA120442968",
        title="Synthetic community",
        experiment_type=Sample.ExperimentType.SYNCOMS,
    )
    constituent = SynComConstituent.objects.create(
        organism="Filobasidium stepposum",
        accession="SAMEA120538186",
        attributes={
            "organism": {
                "text": "Filobasidium stepposum",
                "ontologyterms": [
                    "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=350811"
                ],
            }
        },
    )
    sample.syncom_constituents.add(constituent)

    response = client.get(reverse("sample_detail", args=[sample.accession]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Constituent taxa" in content
    assert constituent.organism in content
    assert constituent.organism_ontology_url in content
    assert (
        f"https://www.ebi.ac.uk/biosamples/samples/{constituent.accession}" in content
    )


@pytest.mark.django_db
def test_syncom_constituent_without_ontology_term_renders_plain_taxon(client):
    sample = Sample.objects.create(
        accession="SAMEA120442970",
        title="Synthetic community without ontology metadata",
        experiment_type=Sample.ExperimentType.SYNCOMS,
    )
    constituent = SynComConstituent.objects.create(
        organism="Taxon without ontology term",
        accession="SAMEA120538187",
    )
    sample.syncom_constituents.add(constituent)

    response = client.get(reverse("sample_detail", args=[sample.accession]))

    assert response.status_code == 200
    content = response.content.decode()
    assert constituent.organism in content
    assert f'href="None"' not in content


@pytest.mark.django_db
def test_non_syncom_sample_detail_does_not_render_constituent_taxa(client):
    sample = Sample.objects.create(
        accession="SAMEA120442969",
        title="Ordinary sample",
        experiment_type=Sample.ExperimentType.CRYOPRESERVATION,
    )

    response = client.get(reverse("sample_detail", args=[sample.accession]))

    assert response.status_code == 200
    assert "Constituent taxa" not in response.content.decode()
