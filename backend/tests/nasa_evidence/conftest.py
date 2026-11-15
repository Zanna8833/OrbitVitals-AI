"""No NASA network requests or implicit developer caches in evidence tests."""

from pathlib import Path

import pytest

from app.nasa_data import source as actigraphy_source
from app.nasa_evidence import NasaEvidenceAdapter
from app.nasa_mr001g import source as mr001g_source
from tests.nasa_evidence.support import synthetic_adapter


@pytest.fixture(autouse=True)
def offline_only(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (actigraphy_source, mr001g_source):
        monkeypatch.setattr(
            module, "urlopen", lambda *a, **k: pytest.fail("Unexpected NASA download")
        )


@pytest.fixture
def adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NasaEvidenceAdapter:
    return synthetic_adapter(tmp_path, monkeypatch)
