"""Print a reproducible SYNTHETIC fixture example; never load authentic caches."""

from pathlib import Path
from tempfile import TemporaryDirectory

from pytest import MonkeyPatch

from app.nasa_evidence import encode_response
from tests.nasa_evidence.support import synthetic_adapter


def main() -> None:
    with (
        TemporaryDirectory(prefix="orbitvitals-synthetic-evidence-") as directory,
        MonkeyPatch.context() as monkeypatch,
    ):
        adapter = synthetic_adapter(Path(directory), monkeypatch)
        print(encode_response(adapter.retrieve("data_quality")), end="")


if __name__ == "__main__":
    main()
