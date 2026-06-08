import logging
from json import JSONDecodeError
from typing import List

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
    webin_filter: List[str],
    max_pages: int = None,
    begin_at_cursor: str = None,
    updated_since: str = None,
) -> List[dict]:
    """
    Generator for pages of biosamples for a specific project. Each page is up to 200 biosamples.

    :param updated_since: ISO8601 formatted date string to filter for samples updated since
    :param begin_at_cursor: Starting cursor value for pagination
    :param project_attr: e.g. MICROBE - the biosamples search value for attr:project:<value>
    :param webin_filter: list of webin IDs to limit results to. Discards samples from other submitters.
    :param max_pages: Max number of pages to yield.
    :return: List of dicts, each representing the JSON for a biosample.
    """
    auth_headers = get_auth_headers()
    if auth_headers:
        logging.info("Using authenticated BioSamples API")
        logging.info(auth_headers)

    logging.info(
        f"Fetching samples from Biosamples {API_ROOT = } for {project_attr = }"
    )

    next_url = f"{API_ROOT}/samples?filter=attr:project:{project_attr.strip()}&size=200"
    if updated_since:
        next_url = f"{next_url}&filter=dt:update:from={updated_since}"
    if begin_at_cursor:
        next_url = f"{next_url}&cursor={begin_at_cursor}"
    pages = 0

    while next_url is not None:
        response = requests.get(next_url, headers=auth_headers)
        logging.info(f"Fetching samples page from Biosamples {next_url}")
        try:
            data = response.json()
        except (JSONDecodeError, KeyError, AttributeError) as e:
            logging.error("Could not read samples from biosamples")
            raise e
        try:
            next_url = data["_links"].get("next", {}).get("href")
        except KeyError as e:
            logging.error("Could not find URL for next page of data")
            raise e
        else:
            pages += 1
            if max_pages and pages >= max_pages:
                logging.warning(f"Truncating biosamples pagination after {pages} pages")
                next_url = None

        samples = data.get("_embedded", {}).get("samples", [])
        for sample in samples:
            if sample.get("webinSubmissionAccountId") in webin_filter:
                yield sample


def add_samples_from_top_level(
    biosample_accession: str, max_derivations_per_level: int = 1e6
):
    from microbe.models import Sample

    json_data = get_biosample(biosample_accession)
    if not json_data:
        logging.error(f"Could not fetch BioSample {biosample_accession}")
        return

    attributes = unnest_attributes(json_data.get("characteristics", {}))
    environmental_medium = attributes.get("environmental_medium", "")
    environment = None
    if environmental_medium and "soil" in environmental_medium.lower():
        environment = Sample.Environment.SOIL
    if environmental_medium and "seed" in environmental_medium.lower():
        environment = Sample.Environment.SEED
    # TODO: codes for marine

    preservation_method = attributes.get("preservation_method", None)
    # TODO generalise
    if type(preservation_method) is dict:
        preservation_method = preservation_method.get("text", "")
    if type(preservation_method) is list and len(preservation_method) > 0:
        preservation_method = preservation_method[0].get("text", "")

    sample, created = Sample.objects.update_or_create(
        accession=json_data.get("accession"),
        defaults={
            "title": json_data.get("name"),
            "attributes": attributes,
            "environment": environment,
            "preservation_method": preservation_method,
            "use_case": Sample.UseCase.SYNCOMS
            if attributes.get("sample_type") == "synthetic community"
            else Sample.UseCase.CRYOPRESERVATION,
        },
    )

    if created:
        logging.info(f"Created Sample {sample.accession}")
    else:
        logging.info(f"Updated Sample {sample.accession}")

    # Import Biolog structured data if present
    structured_data = json_data.get("structuredData", [])
    for entry in structured_data:
        if entry.get("type") == "Biolog":
            sample.import_biologs(entry)

    # Process samples that are derived from this one
    # The JSON's relationships list contains entries where this sample is the 'target'
    # and the derived sample is the 'source'.
    relationships = json_data.get("relationships", [])
    for r, rel in enumerate(relationships):
        if r > max_derivations_per_level:
            break
        if (
            rel.get("target") == biosample_accession
            and rel.get("type") == "derived_from"
        ):
            child_accession = rel.get("source")
            # Recursive call to process the child
            child_sample = add_samples_from_top_level(child_accession)
            if child_sample:
                child_sample.derived_from.add(sample)

    return sample
