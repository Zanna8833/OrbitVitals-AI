"""Reuse existing invented source fixtures; never read an authentic local cache."""

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from app.nasa_data import source as actigraphy_source
from app.nasa_evidence import DatasetId, NasaEvidenceAdapter
from app.nasa_evidence.catalog import reviewed_profiles
from app.nasa_mr001g import source as mr001g_source
from tests.nasa_data.support import materialize as materialize_actigraphy
from tests.nasa_data.support import synthetic_bundle as actigraphy_bundle
from tests.nasa_mr001g.support import materialize as materialize_mr001g
from tests.nasa_mr001g.support import synthetic_bundle as mr001g_bundle


def synthetic_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NasaEvidenceAdapter:
    """Inject reviewed test manifests; run real integrity checks and real importers."""
    bundles = {DatasetId.ACTIGRAPHY: actigraphy_bundle(), DatasetId.MR001G: mr001g_bundle()}
    caches = {dataset: tmp_path / dataset.value for dataset in DatasetId}
    materialize_actigraphy(bundles[DatasetId.ACTIGRAPHY], caches[DatasetId.ACTIGRAPHY])
    materialize_mr001g(bundles[DatasetId.MR001G], caches[DatasetId.MR001G])
    profiles = []
    for profile in reviewed_profiles():
        bundle = bundles[profile.dataset_id]
        source = actigraphy_source if profile.dataset_id == DatasetId.ACTIGRAPHY else mr001g_source

        def loader(bundle=bundle):
            return bundle.manifest, bundle.manifest_bytes

        monkeypatch.setattr(source, "load_manifest", loader)
        profiles.append(
            replace(
                profile,
                manifest_path=(
                    "backend/tests/nasa_data/support.py::synthetic_bundle"
                    if profile.dataset_id == DatasetId.ACTIGRAPHY
                    else "backend/tests/nasa_mr001g/support.py::synthetic_bundle"
                ),
                load_manifest=loader,
                source_identity=bundle.manifest["dataset_id"],
                manifest_sha256=hashlib.sha256(bundle.manifest_bytes).hexdigest(),
                synthetic_fixture=True,
            )
        )
    return NasaEvidenceAdapter(caches, _profiles=tuple(profiles))
