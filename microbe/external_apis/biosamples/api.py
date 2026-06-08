import logging
from json import JSONDecodeError
from typing import Iterator, Optional, Sequence, Tuple

import requests

from microbe.utils import microbe_config, unnest_attributes

API_ROOT = microbe_config.biosamples.api_root.rstrip("/")


def get_auth_headers():
    if microbe_config.biosamples.username:
        auth_data = {
            "authRealms": ["ENA"],
            "username": microbe_config.biosamples.username,
            "password": microbe_config.biosamples.password,
        }
        token_response = requests.post(
            f"{microbe_config.biosamples.auth_url}", json=auth_data
        )
        if not token_response.status_code == 200:
            logging.error(token_response.text)
            raise Exception("Could not get token for BioSamples API")
        return {"Authorization": f"Bearer {token_response.text}"}
    return {}


def get_sample_structured_data(sample: str) -> dict:
    auth_headers = get_auth_headers()
    if auth_headers:
        logging.info("Using authenticated BioSamples API")

    logging.info(f"Fetching {sample} structured data from Biosamples {API_ROOT = }")

    response = requests.get(f"{API_ROOT}/structureddata/{sample}", headers=auth_headers)
    if response.status_code == requests.codes.not_found:
        logging.info(f"No structureddata for sample {sample}")
        return {}
    try:
        data = response.json()
    except (JSONDecodeError, KeyError, AttributeError) as e:
        logging.error("Could not read structureddata from biosamples")
        raise e

    return {
        data_section.get("type"): data_section.get("content", [])
        for data_section in data.get("data", [])
    }


def get_biosample(sample: str) -> dict:
    auth_headers = get_auth_headers()
    if auth_headers:
        logging.info("Using authenticated BioSamples API")

    logging.info(f"Fetching {sample} from Biosamples {API_ROOT = }")

    response = requests.get(f"{API_ROOT}/samples/{sample}", headers=auth_headers)
    if response.status_code == requests.codes.not_found:
        logging.info(f"No biosample for sample {sample}")
        return {}
    try:
        data = response.json()
    except (JSONDecodeError, KeyError, AttributeError) as e:
        logging.error("Could not read response from biosamples")
        raise e
    return data


def get_project_samples(
    project_attr: str,
    webin_filter: Optional[Sequence[str]] = None,
    max_pages: Optional[int] = None,
    begin_at_cursor: Optional[str] = None,
    updated_since: Optional[str] = None,
) -> Iterator[dict]:
    """
    Generator for pages of biosamples for a specific project. Each page is up to 200 biosamples.

    :param updated_since: ISO8601 formatted date string to filter for samples updated since
    :param begin_at_cursor: Starting cursor value for pagination
    :param project_attr: e.g. MICROBE - the biosamples search value for attr:project:<value>
    :param webin_filter: Webin IDs to limit results to. An empty value includes all submitters.
    :param max_pages: Max number of pages to yield.
    :return: List of dicts, each representing the JSON for a biosample.
    """
    auth_headers = get_auth_headers()
    if auth_headers:
        logging.info("Using authenticated BioSamples API")

    logging.info(
        f"Fetching samples from Biosamples {API_ROOT = } for {project_attr = }"
    )

    next_url = f"{API_ROOT}/samples"
    params = {
        "filter": f"attr:project name:{project_attr.strip()}",
        "size": 200,
    }
    if updated_since:
        params["filter"] = [
            params["filter"],
            f"dt:update:from={updated_since}",
        ]
    if begin_at_cursor:
        params["cursor"] = begin_at_cursor

    allowed_webins = set(webin_filter or [])
    pages = 0

    while next_url is not None:
        logging.info(f"Fetching samples page from Biosamples {next_url}")
        response = requests.get(next_url, headers=auth_headers, params=params)
        response.raise_for_status()
        try:
            data = response.json()
        except (JSONDecodeError, ValueError, AttributeError) as e:
            logging.error("Could not read samples from biosamples")
            raise e

        next_url = data.get("_links", {}).get("next", {}).get("href")
        params = None
        pages += 1
        if max_pages and pages >= max_pages:
            if next_url:
                logging.warning(f"Truncating biosamples pagination after {pages} pages")
            next_url = None

        samples = data.get("_embedded", {}).get("samples", [])
        for sample in samples:
            if (
                not allowed_webins
                or sample.get("webinSubmissionAccountId") in allowed_webins
            ):
                yield sample


def _attribute_text(value):
    if isinstance(value, dict):
        return value.get("text", "")
    if isinstance(value, list):
        return _attribute_text(value[0]) if value else ""
    return value


def import_biosample(json_data: dict) -> Tuple["Sample", bool]:
    """Create or update a Sample from an already-fetched BioSamples record."""
    from microbe.models import Sample

    accession = json_data.get("accession")
    if not accession:
        raise ValueError("BioSamples record has no accession")

    attributes = unnest_attributes(json_data.get("characteristics", {}))
    environmental_medium = str(
        _attribute_text(attributes.get("environmental_medium", ""))
    ).lower()
    environment = None
    if "soil" in environmental_medium:
        environment = Sample.UseCase.SOIL
    elif "seed" in environmental_medium:
        environment = Sample.UseCase.SEED
    elif "marine" in environmental_medium or "sea" in environmental_medium:
        environment = Sample.UseCase.MARINE

    preservation_method = _attribute_text(attributes.get("preservation_method"))
    sample_type = str(_attribute_text(attributes.get("sample_type", ""))).lower()

    sample, created = Sample.objects.update_or_create(
        accession=accession,
        defaults={
            "title": json_data.get("name") or accession,
            "attributes": attributes,
            "environment": environment,
            "preservation_method": preservation_method or None,
            "experiment_type": (
                Sample.ExperimentType.SYNCOMS
                if sample_type == "synthetic community"
                else Sample.ExperimentType.CRYOPRESERVATION
            ),
        },
    )

    logging.info("%s Sample %s", "Created" if created else "Updated", sample.accession)

    for entry in json_data.get("structuredData", []):
        if entry.get("type") == "Biolog":
            sample.import_biologs(entry)

    external_references = json_data.get("externalReferences")
    if external_references:
        sample.refresh_external_references(external_references)

    return sample, created


def add_samples_from_top_level(
    biosample_accession: str, max_derivations_per_level: int = 1e6
):
    json_data = get_biosample(biosample_accession)
    if not json_data:
        logging.error(f"Could not fetch BioSample {biosample_accession}")
        return

    sample, _ = import_biosample(json_data)

    # Process samples that are derived from this one
    # The JSON's relationships list contains entries where this sample is the 'target'
    # and the derived sample is the 'source'.
    relationships = json_data.get("relationships", [])
    derivations_processed = 0
    for rel in relationships:
        if derivations_processed >= max_derivations_per_level:
            break
        if (
            rel.get("target") == biosample_accession
            and str(rel.get("type", "")).lower() == "derived_from"
        ):
            derivations_processed += 1
            child_accession = rel.get("source")
            # Recursive call to process the child
            child_sample = add_samples_from_top_level(
                child_accession, max_derivations_per_level
            )
            if child_sample:
                child_sample.derived_from.add(sample)

    return sample
