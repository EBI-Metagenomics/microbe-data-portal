from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlencode

SOIL_WORKFLOW = {
    "id": "soil-cryopreservation",
    "title": "Soil cryopreservation workflow",
    "description": (
        "Find MICROBE soil samples by the combination of preservation and analysis methods used."
    ),
    "environment": "Soil",
    "experiment_type": "Cryopreservation",
    "stages": [
        {
            "id": "preservation_method",
            "label": "Preservation",
            "attribute": "preservation_method",
            "choices": [
                {
                    "id": "freezing",
                    "label": "Freezing",
                    "values": ["freezing"],
                },
                {
                    "id": "freeze-free",
                    "label": "Freeze-free",
                    "values": ["freeze-free preservation", "freeze free"],
                },
            ],
        },
        {
            "id": "cryoprotectant",
            "label": "Cryoprotectant",
            "attribute": "cryoprotectant",
            "choices": [
                {"id": "none", "label": "None", "values": ["none"]},
                {
                    "id": "dmso",
                    "label": "10% DMSO",
                    "values": ["10% DMSO"],
                },
                {
                    "id": "glycerol",
                    "label": "15% glycerol",
                    "values": ["15% glycerol"],
                },
                {
                    "id": "trehalose",
                    "label": "15% trehalose",
                    "values": ["15% trehalose"],
                },
                {
                    "id": "glycine-betaine-trehalose",
                    "label": "Glycine betaine + trehalose",
                    "label_lines": ["Glycine betaine", "+ trehalose"],
                    "values": [
                        "10 % Glycine Betaine + 10% Trehalose",
                        "10% glycine betaine, 10% trehalose",
                    ],
                },
            ],
        },
        {
            "id": "cooling_rate",
            "label": "Cooling rate",
            "attribute": "cooling_rate",
            "choices": [
                {
                    "id": "uncontrolled",
                    "label": "Uncontrolled",
                    "values": ["uncontrolled"],
                },
                {
                    "id": "controlled",
                    "label": "1 C/min",
                    "values": ["1"],
                },
            ],
        },
        {
            "id": "storage_temperature",
            "label": "Storage",
            "attribute": "storage_preservation_temperature",
            "choices": [
                {"id": "plus-4", "label": "+4 C", "values": ["4"]},
                {"id": "minus-80", "label": "-80 C", "values": ["-80"]},
                {
                    "id": "liquid-nitrogen",
                    "label": "Liquid nitrogen",
                    "values": ["-196"],
                },
            ],
        },
        {
            "id": "preservation_duration",
            "label": "Duration",
            "attribute": "preservation_duration",
            "choices": [
                {"id": "0-days", "label": "0 days", "values": ["0"]},
                {"id": "1-day", "label": "1 day", "values": ["1"]},
                {"id": "1-week", "label": "1 week", "values": ["7"]},
                {"id": "15-days", "label": "15 days", "values": ["15"]},
                {"id": "3-months", "label": "3 months", "values": ["91", "93"]},
                {
                    "id": "6-months",
                    "label": "6 months",
                    "values": ["182", "183"],
                },
                {
                    "id": "1-year",
                    "label": "1 year",
                    "values": ["366", "370", "371"],
                },
                {"id": "2-years", "label": "2 years", "values": ["735"]},
                {"id": "289-days", "label": "289 days", "values": ["289"]},
            ],
        },
        {
            "id": "analysis",
            "label": "Analysis",
            "attribute": "supporting_experiment",
            "choices": [
                {
                    "id": "biolog",
                    "label": "Biolog",
                    "values": ["Biolog"],
                    "match": "contains",
                },
                {
                    "id": "4mu",
                    "label": "4MU",
                    "values": ["4MU"],
                    "match": "contains",
                },
                {
                    "id": "mpn",
                    "label": "MPN",
                    "values": ["MPN"],
                    "match": "contains",
                },
                {
                    "id": "cultivation",
                    "label": "Cultivation",
                    "attribute": "cultivation",
                    "values": [
                        "1/2 R2A",
                        "PDA",
                        "SSE/HD 1:10",
                        "SSE/HP",
                        "TWA",
                    ],
                },
            ],
        },
        {
            "id": "targets",
            "label": "Targets",
            "attribute": "targets",
            "choices": [
                {
                    "id": "16s-bacteria",
                    "label": "16S bacteria",
                    "values": ["16S bacteria", "16S"],
                    "match": "contains_any",
                },
                {
                    "id": "16s-archaea",
                    "label": "16S archaea",
                    "values": ["16S archaea", "Archaea"],
                    "match": "contains_any",
                },
                {
                    "id": "its",
                    "label": "ITS",
                    "values": ["ITS"],
                    "match": "contains",
                },
            ],
        },
    ],
}


def _scalar_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        if "text" in value:
            return _scalar_values(value["text"])
        values = []
        for nested_value in value.values():
            values.extend(_scalar_values(nested_value))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for nested_value in value:
            values.extend(_scalar_values(nested_value))
        return values
    return [str(value).strip()]


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def choice_matches_attributes(choice: dict, stage: dict, attributes: dict) -> bool:
    attribute = choice.get("attribute", stage["attribute"])
    actual_values = [
        _normalise(value) for value in _scalar_values(attributes.get(attribute))
    ]
    expected_values = [_normalise(value) for value in choice["values"]]
    match = choice.get("match", "exact")

    if match in {"contains", "contains_any"}:
        return any(
            expected in actual
            for actual in actual_values
            for expected in expected_values
        )
    return any(actual in expected_values for actual in actual_values)


def build_workflow(
    *,
    attributes: dict | None = None,
    query_params=None,
    list_url: str = "/samples/",
    mode: str,
) -> dict:
    workflow = deepcopy(SOIL_WORKFLOW)
    attributes = attributes or {}
    selected_params = query_params or {}
    stage_width = 170
    source_stage_width = 190 if mode == "detail" else 0

    for stage_index, stage in enumerate(workflow["stages"]):
        stage["x"] = 20 + source_stage_width + (stage_index * stage_width)
        stage["width"] = stage_width
        stage["content_width"] = stage_width - 8
        stage["choice_width"] = stage_width - 28
        stage["choice_center"] = 10 + ((stage_width - 28) / 2)
        stage["header_center"] = (stage_width - 8) / 2
        stage["filter_name"] = f"workflow_{stage['id']}"

        next_y = 92
        for choice in stage["choices"]:
            choice["label_lines"] = choice.get("label_lines", [choice["label"]])
            choice["height"] = max(38, 24 + (len(choice["label_lines"]) * 14))
            choice["y"] = next_y
            choice["text_y"] = (
                choice["y"]
                + ((choice["height"] - ((len(choice["label_lines"]) - 1) * 14)) / 2)
                + 4
            )
            next_y += choice["height"] + 14
            choice["active"] = choice_matches_attributes(choice, stage, attributes)
            choice["selected"] = (
                selected_params.get(stage["filter_name"]) == choice["id"]
            )

            params = {
                "environment": workflow["environment"],
                "experiment_type": workflow["experiment_type"],
                stage["filter_name"]: choice["id"],
            }
            if mode == "list":
                params = dict(selected_params)
                params.update(
                    {
                        "environment": workflow["environment"],
                        "experiment_type": workflow["experiment_type"],
                        stage["filter_name"]: choice["id"],
                    }
                )
                params.pop("page", None)
            choice["url"] = f"{list_url}?{urlencode(params, doseq=True)}"

    workflow["viewbox_width"] = (
        40 + source_stage_width + (len(workflow["stages"]) * stage_width)
    )
    workflow["viewbox_height"] = 590
    workflow["mode"] = mode
    workflow["has_selected_filters"] = any(
        choice["selected"]
        for stage in workflow["stages"]
        for choice in stage["choices"]
    )
    return workflow


def workflow_filter_choices(stage_id: str) -> list[tuple[str, str]]:
    stage = next(stage for stage in SOIL_WORKFLOW["stages"] if stage["id"] == stage_id)
    return [(choice["id"], choice["label"]) for choice in stage["choices"]]


def workflow_choice(stage_id: str, choice_id: str) -> tuple[dict, dict] | None:
    stage = next(
        (stage for stage in SOIL_WORKFLOW["stages"] if stage["id"] == stage_id),
        None,
    )
    if not stage:
        return None
    choice = next(
        (choice for choice in stage["choices"] if choice["id"] == choice_id),
        None,
    )
    if not choice:
        return None
    return stage, choice
