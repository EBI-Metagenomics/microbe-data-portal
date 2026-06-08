import logging
import time
from datetime import timedelta
from functools import reduce
from typing import Any, Mapping

from django.conf import settings
from django.db.models import Aggregate, Func
from django.utils.text import slugify

from microbe.config import MicrobeConfig

microbe_config: MicrobeConfig = settings.MICROBE_CONFIG


def clean_keys(data: Any) -> Any:
    """
    Clean keys of a dictionary to be valid python variable names, by replacing spaces and hyphens with underscores.
    :param data: Dictionary (or list with potentially dicts inside) to clean, e.g. {'attributes': {'some-thing': [1, 2]}}
    :return: Data with dict keys cleaned, e.g. {'attributes': {'some_thing': [1, 2]}}
    """
    if isinstance(data, list):
        return list(map(clean_keys, data))
    elif isinstance(data, dict):
        return {
            (k or "").replace(" ", "_").replace("-", "_"): clean_keys(v)
            for k, v in data.items()
        }
    return data


def unnest_attributes(
    data: Any,
    collapse_text_only: bool = False,
) -> Any:
    if isinstance(data, Mapping):
        d = {
            slugify(str(key)): unnest_attributes(
                value,
                collapse_text_only=collapse_text_only,
            )
            for key, value in data.items()
        }
        return clean_keys(d)

    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], Mapping) and "text" in data[0]:
            if collapse_text_only or set(data[0]) == {"text"}:
                return data[0]["text"]
            elif len(data) == 1:
                return unnest_attributes(data[0], collapse_text_only=collapse_text_only)
        return [
            unnest_attributes(
                item,
                collapse_text_only=collapse_text_only,
            )
            for item in data
        ]
    return data


class CadenceEnforcer:
    def __init__(self, min_period: timedelta = timedelta(0)):
        """
        Ensures that at least min_period time has passed between invocations.
        :param min_period: Any timedelta e.g. datetime.timedelta(seconds=3)
        """
        self.cadence_seconds = min_period.total_seconds()
        self.prev_return = None

    def __call__(self):
        now = time.time()
        if self.prev_return:
            since = now - self.prev_return
            if since < self.cadence_seconds:
                logging.debug(f"Sleeping for {self.cadence_seconds - since:.2f}s")
                time.sleep(self.cadence_seconds - since)
        self.prev_return = now
        return


class StringAgg(Aggregate):
    dbengine = settings.DATABASES["default"]["ENGINE"].lower()
    if "postgres" in dbengine:
        function = "STRING_AGG"
        template = "%(function)s(%(distinct)s%(expressions)s, ',')"
    elif "sqlite" in dbengine:
        function = "GROUP_CONCAT"
    else:
        function = "MIN"
    name = "Concat"


class DistinctFunc(Func):
    template = "%(function)s(DISTINCT %(expressions)s)"


def find_by_path(object, attr_path: str):
    def getter(item, attr_or_key):
        if hasattr(item, attr_or_key):
            return getattr(item, attr_or_key)
        if type(item) is dict:
            return item.get(attr_or_key)

    return reduce(getter, attr_path.split("."), object)


def write_signpost(url: str, mimetype: str, signpost_type: str, profile: str) -> str:
    def resolve(_url):
        if _url.startswith("/"):
            return f"{microbe_config.portal.url_root}{_url}"
        else:
            return _url

    header_value = f"<{resolve(url)}>"
    header_value += f' ; rel="{signpost_type}" ; type="{mimetype}"'
    if profile:
        header_value += f' ; profile="{resolve(profile)}"'
    return header_value
