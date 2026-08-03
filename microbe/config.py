"""

Copyright EMBL-European Bioinformatics Institute, 2022

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

from __future__ import annotations
from datetime import timedelta
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class BiosamplesConfig(BaseModel):
    api_root: AnyHttpUrl = "https://www.ebi.ac.uk/biosamples"
    project_id: str = "HF"
    username: str = ""
    password: str = ""
    auth_url: AnyHttpUrl = "https://www.ebi.ac.uk/ena/submit/webin/auth/token"


class EnaConfig(BaseModel):
    systems: dict = {}
    username: str = ""
    password: str = ""
    portal_api_root: AnyHttpUrl = "https://www.ebi.ac.uk/ena/portal/api"
    browser_api_root: AnyHttpUrl = "https://www.ebi.ac.uk/ena/browser/api"
    browser_url: AnyHttpUrl = "https://www.ebi.ac.uk/ena/browser/view"


class MgnifyConfig(BaseModel):
    api_root: AnyHttpUrl = "https://www.ebi.ac.uk/metagenomics/api/v1"
    web_url: AnyHttpUrl = "https://www.ebi.ac.uk/metagenomics"
    request_cadence: timedelta = timedelta(seconds=3)
    request_timeout: timedelta = timedelta(seconds=15.05)
    request_retries: int = 3


class MetabolightsConfig(BaseModel):
    api_root: AnyHttpUrl = "https://www.ebi.ac.uk/metabolights/ws"
    web_url: AnyHttpUrl = "https://www.ebi.ac.uk/metabolights"
    user_token: str = None
    biosample_column_name_in_sample_table: str = "Characteristics[BioSamples accession]"


class SampleTableConfig(BaseModel):
    default_metadata_marker_columns: list[str] = Field(default_factory=list)


class MetadataTableConfig(BaseModel):
    bring_to_top_if_metadata_marker_name_contains: list[str] = Field(
        default_factory=list
    )


class TablesConfig(BaseModel):
    animals_list: SampleTableConfig = Field(default_factory=SampleTableConfig)
    metadata_list: MetadataTableConfig = Field(default_factory=MetadataTableConfig)


class DocsConfig(BaseModel):
    docs_url: AnyHttpUrl = "https://ebi-metagenomics.github.io/microbe-data-portal/"
    portal_doi: str = "10.5281/zenodo.7684071"


class PortalConfig(BaseModel):
    url_root: AnyHttpUrl = "https://www.microbedata.org"


class MicrobeConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="microbe_",
        env_nested_delimiter="__",
        json_file=Path("config/data_config.json"),
        json_file_encoding="utf-8",
    )

    mock_apis: bool = False

    biosamples: BiosamplesConfig = BiosamplesConfig()
    ena: EnaConfig = EnaConfig()
    mgnify: MgnifyConfig = MgnifyConfig()
    docs: DocsConfig = DocsConfig()
    metabolights: MetabolightsConfig = MetabolightsConfig()
    tables: TablesConfig = TablesConfig()
    portal: PortalConfig = PortalConfig()

    # E.g. set `MICROBE_BIOSAMPLES__API_ROOT` to override the default.
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
