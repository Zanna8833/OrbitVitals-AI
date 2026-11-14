"""Verify, reacquire, and adapt authentic NASA data without changing the API."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError

from app.nasa_data.actigraphy import encode_report, import_dataset
from app.nasa_data.source import (
    DEFAULT_DATA_DIR,
    download_bundle,
    require_external_destination,
    verify_bundle,
)


def main(argv: list[str] | None = None) -> int:
    """Acquire external files or write private results; print only aggregate counts."""
    parser = argparse.ArgumentParser(
        prog="python -m app.nasa_data",
        description=(
            "Verify and import AUTHENTIC NASA ground-analog data locally. "
            "No fabricated timestamps, clinical assessments, or API writes."
        ),
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Verify original source bytes and NASA metadata offline.")
    importer = commands.add_parser("import", help="Compute and save a private local report.")
    importer.add_argument(
        "--output", type=Path, required=True, help="New JSON file outside the repository."
    )
    importer.add_argument(
        "--summary", action="store_true", help="Omit individual source records from the report."
    )
    downloader = commands.add_parser("download", help="Reacquire the pinned public NASA snapshot.")
    downloader.add_argument(
        "--output-dir", type=Path, help="External local cache; defaults to --data-dir."
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            require_external_destination(args.output)
            if args.output.exists():
                raise FileExistsError("Refusing to replace an existing local report")
            result = import_dataset(args.data_dir)
            if args.summary:
                del result["records"]
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encode_report(result))
            summary = result["summary"]
            print(
                json.dumps(
                    {
                        "dataset_id": result["dataset_id"],
                        "is_synthetic": result["is_synthetic"],
                        "source_record_count": summary["source_record_count"],
                        "observed_value_count": summary["observed_value_count"],
                        "missing_value_count": summary["missing_value_count"],
                        "statistical_group_count": len(result["descriptive_statistics"]),
                        "private_report_written": True,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        bundle = (
            download_bundle(args.output_dir or args.data_dir)
            if args.command == "download"
            else verify_bundle(args.data_dir)
        )
        print(
            json.dumps(
                {
                    "dataset_id": bundle.manifest["dataset_id"],
                    "is_synthetic": bundle.manifest["is_synthetic"],
                    "study_context": bundle.manifest["study_context"],
                    "verified_files": [entry["path"] for entry in bundle.manifest["files"]],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, URLError) as error:
        print(f"NASA data operation failed: {error}", file=sys.stderr)
        return 2
