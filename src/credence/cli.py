import argparse
import csv
import sys
from pathlib import Path

from credence.models import FinancialSummary, ValidationResult
from credence.reporting import (
    OutputSafetyError,
    check_output_safety,
    stage_and_publish_reports,
)
from credence.validator import FileValidationError, read_source_rows, validate_cashbook


def format_currency(amount) -> str:
    """Format decimal amount with thousands separator and two decimal places."""
    return f"{amount:,.2f}"


def print_terminal_summary(
    source_name: str,
    output_dir: Path,
    result: ValidationResult,
    summary: FinancialSummary,
) -> None:
    print(f"Source: {source_name}")
    print(
        f"Processed rows: {result.processed_rows} "
        f"(Valid: {result.valid_rows}, Invalid: {result.invalid_rows}, Errors: {result.total_errors})"
    )
    print(f"Artifacts written to: {output_dir}")
    print("Financial summary (valid records, NGN):")
    print(f"  Total income:        {format_currency(summary.total_income):>14}")
    print(f"  Total expenses:      {format_currency(summary.total_expenses):>14}")
    print(f"  Net cash movement:   {format_currency(summary.net_cash_movement):>14}")


def run_check(input_path_str: str, output_dir_str: str) -> int:
    input_path = Path(input_path_str)
    output_dir = Path(output_dir_str)

    # 1. Input path checks
    if not input_path.exists():
        sys.stderr.write(f"Error: Input file does not exist: {input_path}\n")
        return 2

    if not input_path.is_file():
        sys.stderr.write(f"Error: Input path is not a regular file: {input_path}\n")
        return 2

    # 2. Output directory pre-flight safety check
    try:
        check_output_safety(output_dir)
    except OutputSafetyError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"Error checking output directory: {e}\n")
        return 2

    # 3. Read and parse CSV with UTF-8 encoding
    try:
        with open(input_path, mode="r", encoding="utf-8") as f:
            header, source_rows = read_source_rows(f)
    except UnicodeDecodeError as e:
        sys.stderr.write(f"Error: File is not valid UTF-8: {e}\n")
        return 2
    except FileValidationError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2
    except (csv.Error, OSError) as e:
        sys.stderr.write(f"Error reading source file: {e}\n")
        return 2

    # 4. Validate records
    try:
        result, summary = validate_cashbook(input_path.name, header, source_rows)
    except FileValidationError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2

    # 5. Stage and publish reports
    try:
        stage_and_publish_reports(output_dir, result, summary)
    except OutputSafetyError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"Error writing reports: {e}\n")
        return 2

    # 6. Print summary
    print_terminal_summary(input_path.name, output_dir, result, summary)

    # 7. Return exit code: 0 if valid, 1 if invalid rows were found
    return 1 if result.invalid_rows > 0 else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="credence",
        description="Deterministic small-business cashbook CSV validator and reporting tool.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    check_parser = subparsers.add_parser(
        "check",
        help="Validate a cashbook CSV and generate reports",
    )
    check_parser.add_argument(
        "input",
        help="Path to the input cashbook CSV file",
    )
    check_parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Directory to write output artifacts",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return run_check(args.input, args.output_dir)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
