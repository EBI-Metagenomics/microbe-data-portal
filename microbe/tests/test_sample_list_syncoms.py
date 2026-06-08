import pytest
from django.urls import reverse

from microbe.models import Sample, SynComConstituent


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("ordering", "expected_accessions"),
    [
        ("constituents_count", ["SAMPLE_ZERO", "SAMPLE_ONE", "SAMPLE_TWO"]),
        ("-constituents_count", ["SAMPLE_TWO", "SAMPLE_ONE", "SAMPLE_ZERO"]),
    ],
)
def test_syncom_samples_can_be_ordered_by_constituent_count(
    client, ordering, expected_accessions
):
    samples = [
        Sample.objects.create(
            accession=f"SAMPLE_{count_name}",
            title=f"SynCom with {constituent_count} constituents",
            experiment_type=Sample.ExperimentType.SYNCOMS,
        )
        for count_name, constituent_count in [
            ("ZERO", 0),
            ("ONE", 1),
            ("TWO", 2),
        ]
    ]
    constituents = [
        SynComConstituent.objects.create(
            accession=f"CONSTITUENT_{index}",
            organism=f"Organism {index}",
        )
        for index in range(2)
    ]
    samples[1].syncom_constituents.add(constituents[0])
    samples[2].syncom_constituents.add(*constituents)

    response = client.get(
        reverse("samples_list_syncoms"),
        {"ordering": ordering},
    )

    assert response.status_code == 200
    assert [
        sample.accession for sample in response.context["samples"]
    ] == expected_accessions
