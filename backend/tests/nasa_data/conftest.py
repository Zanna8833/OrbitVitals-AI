"""NASA adapter tests are offline and use only visibly synthetic fixture bytes."""

from pathlib import Path

import pytest

from app.nasa_data import cli, source
from app.nasa_data.source import VerifiedBundle
from tests.nasa_data.support import synthetic_bundle


@pytest.fixture(autouse=True)
def offline_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent tests from using the network or a developer's real default cache."""
    monkeypatch.setattr(
        source, "urlopen", lambda *args, **kwargs: pytest.fail("Unexpected network access")
    )
    monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", tmp_path / "empty-default-cache")


@pytest.fixture
def bundle() -> VerifiedBundle:
    """Invent a fresh fixture with synthetic labels, values and digests."""
    return synthetic_bundle()


@pytest.fixture
def fixture_manifest(bundle: VerifiedBundle, monkeypatch: pytest.MonkeyPatch) -> VerifiedBundle:
    """Substitute only test provenance; never relax production manifest validation."""
    monkeypatch.setattr(source, "load_manifest", lambda: (bundle.manifest, bundle.manifest_bytes))
    return bundle
