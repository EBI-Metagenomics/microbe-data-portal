from typing import List, Optional, Any
from pydantic import BaseModel, Field, AliasChoices


class StructuredDatumValue(BaseModel):
    value: Optional[Any] = None
    iri: Optional[str] = None


class BiologContent(BaseModel):
    sample_name: StructuredDatumValue = Field(
        validation_alias=AliasChoices("sample name", "sample_name")
    )
    centre: StructuredDatumValue
    file_name: StructuredDatumValue = Field(
        validation_alias=AliasChoices("file name", "file_name")
    )
    type_of_measurement: StructuredDatumValue = Field(
        validation_alias=AliasChoices("type of measurement", "type_of_measurement")
    )
    reader_device: StructuredDatumValue = Field(
        validation_alias=AliasChoices("reader device", "reader_device")
    )
    reading_type_method: StructuredDatumValue = Field(
        validation_alias=AliasChoices("reading type/method", "reading_type_method")
    )
    plate_type: StructuredDatumValue = Field(
        validation_alias=AliasChoices("plate type", "plate_type")
    )
    incubation_temperature: StructuredDatumValue = Field(
        validation_alias=AliasChoices(
            "incubation temperature", "incubation_temperature"
        )
    )
    incubation_duration: StructuredDatumValue = Field(
        validation_alias=AliasChoices("incubation duration", "incubation_duration")
    )
    data_preprocessing_status: StructuredDatumValue
    link_to_file: StructuredDatumValue = Field(
        validation_alias=AliasChoices("link to file", "link_to_file")
    )


class BiologStructuredData(BaseModel):
    domain: Optional[str] = None
    webinSubmissionAccountId: Optional[str] = None
    type: str
    schema_url: Optional[str] = Field(None, alias="schema")
    content: List[BiologContent]
