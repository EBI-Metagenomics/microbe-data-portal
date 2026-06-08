import pytest
from django.urls import reverse

from microbe.models import Sample
from microbe.workflows import build_workflow


def active_choice_ids(workflow, stage_id):
    stage = next(stage for stage in workflow["stages"] if stage["id"] == stage_id)
    return {choice["id"] for choice in stage["choices"] if choice["active"]}


def test_workflow_normalises_real_soil_metadata_values():
    workflow = build_workflow(
        attributes={
            "preservation_method": "freezing",
            "cryoprotectant": "10% glycine betaine, 10% trehalose",
            "cooling_rate": "1",
            "storage_preservation_temperature": "-196",
            "preservation_duration": "371",
            "supporting_experiment": "MPN, Biolog, 4MU",
            "targets": "16S, ITS, Archaea",
        },
        mode="detail",
    )

    assert active_choice_ids(workflow, "preservation_method") == {"freezing"}
    assert active_choice_ids(workflow, "cryoprotectant") == {
        "glycine-betaine-trehalose"
    }
    assert active_choice_ids(workflow, "cooling_rate") == {"controlled"}
    assert active_choice_ids(workflow, "storage_temperature") == {"liquid-nitrogen"}
    assert active_choice_ids(workflow, "preservation_duration") == {"1-year"}
    assert active_choice_ids(workflow, "analysis") == {"mpn", "biolog", "4mu"}
    assert active_choice_ids(workflow, "targets") == {
        "16s-bacteria",
        "16s-archaea",
        "its",
    }


@pytest.mark.django_db
def test_soil_sample_detail_renders_workflow_and_all_source_samples(client):
    parents = [
        Sample.objects.create(
            accession=f"SAMEA11540704{index}",
            title=f"HG soil {index}",
            environment=Sample.Environment.SOIL,
            experiment_type=Sample.UseCase.CRYOPRESERVATION,
        )
        for index in range(5, 8)
    ]
    sample = Sample.objects.create(
        accession="SAMEA115407051",
        title="HG soil mix",
        environment=Sample.Environment.SOIL,
        experiment_type=Sample.UseCase.CRYOPRESERVATION,
        attributes={
            "preservation_method": "freezing",
            "cryoprotectant": "10% DMSO",
            "storage_preservation_temperature": "-80",
            "preservation_duration": "91",
        },
    )
    sample.derived_from.set(parents)

    response = client.get(reverse("sample_detail", args=[sample.accession]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Soil cryopreservation workflow" in content
    assert '<details class="vf-details sample-workflow-details" open>' in content
    assert 'data-workflow-mode="detail"' in content
    assert 'class="sample-workflow__choice is-current"' in content
    assert 'class="sample-workflow__relationship-label"' in content
    assert 'class="sample-workflow__source-junction"' in content
    assert 'd="M 16 178 V 204 H 32"' in content
    for parent in parents:
        assert parent.accession in content


@pytest.mark.django_db
def test_workflow_filters_soil_samples_using_raw_biosamples_values(client):
    matching = Sample.objects.create(
        accession="SAMEA121055795",
        title="DSMZ soil workflow sample",
        environment=Sample.Environment.SOIL,
        experiment_type=Sample.UseCase.CRYOPRESERVATION,
        attributes={
            "cryoprotectant": "10 % Glycine Betaine + 10% Trehalose",
            "storage_preservation_temperature": "-80",
            "preservation_duration": "91",
        },
    )
    Sample.objects.create(
        accession="SAMEA121055796",
        title="Different soil workflow sample",
        environment=Sample.Environment.SOIL,
        experiment_type=Sample.UseCase.CRYOPRESERVATION,
        attributes={
            "cryoprotectant": "none",
            "storage_preservation_temperature": "-80",
            "preservation_duration": "91",
        },
    )

    response = client.get(
        reverse("samples_list"),
        {
            "environment": Sample.Environment.SOIL,
            "experiment_type": Sample.UseCase.CRYOPRESERVATION,
            "workflow_cryoprotectant": "glycine-betaine-trehalose",
            "workflow_storage_temperature": "minus-80",
            "workflow_preservation_duration": "3-months",
        },
    )

    assert response.status_code == 200
    samples = list(response.context["samples"])
    assert samples == [matching]
    content = response.content.decode()
    assert 'data-workflow-mode="list"' in content
    assert 'id="show-workflow-filters"' in content
    assert 'id="workflow-filter-dialog"' in content
    assert 'id="workflow-form-fields"' in content
    assert (
        '<details class="vf-details workflow-form-fields"\n'
        '                 id="workflow-form-fields"\n'
        "                 open>"
    ) in content
    assert "Apply workflow filters" in content


@pytest.mark.django_db
def test_workflow_parent_filter_lists_direct_children(client):
    parent = Sample.objects.create(
        accession="SAMEA115407051",
        title="HG soil mix",
        environment=Sample.Environment.SOIL,
        experiment_type=Sample.UseCase.CRYOPRESERVATION,
    )
    child = Sample.objects.create(
        accession="SAMEA115408603",
        title="MB1",
        environment=Sample.Environment.SOIL,
        experiment_type=Sample.UseCase.CRYOPRESERVATION,
    )
    child.derived_from.add(parent)

    response = client.get(
        reverse("samples_list"),
        {"workflow_parent": parent.accession},
    )

    assert list(response.context["samples"]) == [child]
