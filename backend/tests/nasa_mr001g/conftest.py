"""Block NASA networking and real developer caches in all ordinary MR001G tests."""

from pathlib import Path

import pytest

from app.nasa_mr001g import cli, source
from app.nasa_mr001g.source import Mr001gBundle
from tests.nasa_mr001g.support import synthetic_bundle


@pytest.fixture(autouse=True)
def offline_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        source, "urlopen", lambda *a, **k: pytest.fail("Unexpected NASA network access")
    )
    monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", tmp_path / "empty-default-cache")


@pytest.fixture
def bundle() -> Mr001gBundle:
    return synthetic_bundle()


@pytest.fixture
def trusted_fixture(bundle: Mr001gBundle, monkeypatch: pytest.MonkeyPatch) -> Mr001gBundle:
    """Inject test provenance; the real loader still rejects this synthetic identity."""
    monkeypatch.setattr(source, "load_manifest", lambda: (bundle.manifest, bundle.manifest_bytes))
    return bundle
