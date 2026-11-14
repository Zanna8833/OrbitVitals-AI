"""The files in /schemas must stay in sync with the Pydantic contract models."""

import pytest
from jsonschema import Draft202012Validator

from app.models import CONTRACT_MODELS
from scripts.export_schemas import stale_files
from tests.support import load_example, load_schema

CONTRACT_NAMES = sorted(CONTRACT_MODELS)


def test_committed_schema_files_match_the_models() -> None:
    assert stale_files() == [], (
        "Files in /schemas are stale. Run `python -m scripts.export_schemas` "
        "from backend/ and commit the result."
    )


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_schema_file_is_a_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(load_schema(name))


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_example_is_accepted_by_the_schema_file(name: str) -> None:
    Draft202012Validator(load_schema(name)).validate(load_example(name))


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_example_is_accepted_by_the_model(name: str) -> None:
    CONTRACT_MODELS[name].model_validate(load_example(name))
