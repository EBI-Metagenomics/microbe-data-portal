import json

from pydantic_settings import SettingsConfigDict

from microbe.config import MicrobeConfig


def test_loads_json_and_dotenv_settings(tmp_path):
    data_config = tmp_path / "data_config.json"
    data_config.write_text(
        json.dumps({"ena": {"systems": {"DMC": "microbe"}}}), encoding="utf-8"
    )
    env_file = tmp_path / "local.env"
    env_file.write_text(
        'MICROBE_BIOSAMPLES__PROJECT_ID="TEST_PROJECT"\n', encoding="utf-8"
    )

    class TestMicrobeConfig(MicrobeConfig):
        model_config = SettingsConfigDict(
            **{**MicrobeConfig.model_config, "json_file": data_config}
        )

    config = TestMicrobeConfig(_env_file=env_file)

    assert config.ena.systems == {"DMC": "microbe"}
    assert config.biosamples.project_id == "TEST_PROJECT"


def test_empty_json_uses_valid_table_defaults(tmp_path):
    data_config = tmp_path / "data_config.json"
    data_config.write_text("{}", encoding="utf-8")

    class TestMicrobeConfig(MicrobeConfig):
        model_config = SettingsConfigDict(
            **{**MicrobeConfig.model_config, "json_file": data_config}
        )

    config = TestMicrobeConfig(_env_file=None)

    assert config.tables.animals_list.default_metadata_marker_columns == []
    assert (
        config.tables.metadata_list.bring_to_top_if_metadata_marker_name_contains == []
    )
