"""Acquire MR001G data externally and write private, source-scale review reports."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError

from app.nasa_data.source import require_external_destination
from app.nasa_mr001g.analysis import encode_report, import_dataset
from app.nasa_mr001g.source import DEFAULT_DATA_DIR, download_bundle, verify_bundle


def main(argv: list[str] | None = None) -> int:
    """Print aggregate verification counts only; never publish source records to stdout."""
    parser = argparse.ArgumentParser(
        prog="python -m app.nasa_mr001g",
        description=(
            "Review authentic NASA MR001G terrestrial-analog data. Source units are "
            "unverified; no canonical clinical measurements or API evaluations are created."
        ),
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("download", help="Acquire the complete pinned snapshot directly from NASA.")
    commands.add_parser("verify", help="Verify an external local cache without network access.")
    importer = commands.add_parser("import", help="Compute a private source-scale report.")
    importer.add_argument(
        "--output", type=Path, required=True, help="New file outside the checkout."
    )
    importer.add_argument(
        "--summary", action="store_true", help="Omit raw records from the local report."
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            require_external_destination(args.output)
            if args.output.exists():
                raise FileExistsError("Refusing to replace an existing MR001G report")
            report = import_dataset(args.data_dir)
            if args.summary:
                del report["records"]
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encode_report(report))
            summary = report["summary"]
            print(
                json.dumps(
                    {
                        "dataset_id": report["dataset_id"],
                        "is_synthetic": report["is_synthetic"],
                        "private_report_written": True,
                        "unit_status": "unverified_for_this_export",
                        "canonical_measurements_created": 0,
                        **{
                            key: summary[key]
                            for key in [
                                "source_csv_files",
                                "csv_data_records",
                                "entirely_empty_source_records",
                                "identified_campaign_subject_pairs",
                                "finite_reported_values",
                                "source_missing_cells",
                                "invalid_numeric_cells",
                                "descriptive_groups",
                                "sbp_below_dbp_records",
                            ]
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        bundle = (
            download_bundle(args.data_dir)
            if args.command == "download"
            else verify_bundle(args.data_dir)
        )
        print(
            json.dumps(
                {
                    "dataset_id": bundle.manifest["dataset_id"],
                    "is_synthetic": bundle.manifest["is_synthetic"],
                    "verified_source_files": len(bundle.files),
                    "observation_files": sum(
                        item["role"] == "observations" for item in bundle.manifest["files"]
                    ),
                    "redistribution_status": "unconfirmed",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, URLError) as error:
        print(f"MR001G operation stopped: {error}", file=sys.stderr)
        return 2
