import logging
from typing import List

import requests
from requests.adapters import HTTPAdapter, Retry

from microbe.utils import microbe_config, clean_keys, CadenceEnforcer


class MgnifyApi:
    def __init__(self):
        self.session = requests.Session()
        self.api_root = microbe_config.mgnify.api_root.rstrip("/")
        self.session.mount(
            self.api_root,
            HTTPAdapter(
                max_retries=Retry(total=microbe_config.mgnify.request_retries)
            ),
        )
        self.request_options = {
            "timeout": microbe_config.mgnify.request_timeout.total_seconds(),
        }
        self._request_slower = CadenceEnforcer(
            min_period=microbe_config.mgnify.request_cadence
        )

    def get(self, endpoint):
        return self.session.get(
            f'{self.api_root}/{endpoint.lstrip("/")}', **self.request_options
        )

    def __str__(self):
        return f"MGnify API @ {self.api_root}"

    @staticmethod
    def assert_response_is_acceptable(response):
        if response.status_code not in (requests.codes.ok, requests.codes.not_found):
            raise Exception(
                f"Response from MGnify API for {response.request.url} was neither 200 (Okay) or 404 (Not found). "
                f"Instead, {response.status_code}"
            )

    def get_metagenomics_analyses_for_sample(self, sample: str) -> List[dict]:
        logging.info(f"Fetching analyses for {sample = } from {self}")
        response = requests.get(
            f"{self.api_root}/analyses?sample_accession={sample}&page_size=10",
            timeout=5,
        )
        self.assert_response_is_acceptable(response)
        return clean_keys(response.json()).get("data", [])
