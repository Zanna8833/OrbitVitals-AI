"""Print the same privacy-limited evidence contract used by the HTTP endpoint."""

import argparse
from pathlib import Path

from app.nasa_evidence import DatasetId, EvidenceTopic, NasaEvidenceAdapter, encode_response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only NASA dataset evidence; never crew telemetry."
    )
    parser.add_argument("--topic", choices=list(EvidenceTopic), required=True)
    parser.add_argument("--dataset-id", choices=list(DatasetId))
    parser.add_argument("--actigraphy-cache", type=Path)
    parser.add_argument("--mr001g-cache", type=Path)
    args = parser.parse_args(argv)
    caches = {
        dataset: path
        for dataset, path in (
            (DatasetId.ACTIGRAPHY, args.actigraphy_cache),
            (DatasetId.MR001G, args.mr001g_cache),
        )
        if path is not None
    }
    response = NasaEvidenceAdapter(caches).retrieve(args.topic, args.dataset_id)
    print(encode_response(response), end="")
    return 2 if response.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
