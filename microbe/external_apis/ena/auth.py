from requests.auth import HTTPBasicAuth

from microbe.utils import microbe_config

if microbe_config.ena.username:
    ENA_AUTH = HTTPBasicAuth(microbe_config.ena.username, microbe_config.ena.password)
else:
    ENA_AUTH = None
