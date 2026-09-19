import csv
import json
import shutil
import tempfile
from pathlib import Path

from credence.constants import (
    CANONICAL_COLUMNS,
    CLEAN_TRANSACTIONS_FILENAME,
    SUMMARY_JSON_FILENAME,
    TARGET_ARTIFACTS,
    VALIDATION_ERRORS_FILENAME,
)
from credence.models import FinancialSummary, ValidationResult


class OutputSafetyError(Exception):
    """Raised when writing outputs violates safety guarantees (e.g. file collision)."""
    pass


def check_output_safety(output_dir: Path) -> None:
    """
    Check whether any target artifact already exists in output_dir.
    Refuses to run or overwrite existing artifacts.
    """
    if not output_dir.exists():
        return

    existing = [name for name in TARGET_ARTIFACTS if (output_dir / name).exists()]
    if existing:
        raise OutputSafetyError(
            f"Output directory already contains target artifacts: {', '.join(existing)}. "
            "Refusing to overwrite existing files."
        )


def write_clean_transactions(dest_path: Path, result: ValidationResult) -> None:
    """Write valid transactions to CSV using canonical columns."""
    with open(dest_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CANONICAL_COLUMNS)
        for tx in result.valid_transactions:
            writer.writerow([
                tx.transaction_id,
                tx.date.isoformat(),
                tx.type.value,
                tx.category,
                tx.description,
                f"{tx.amount:.2f}",
                tx.reference,
            ])


def write_validation_errors(dest_path: Path, result: ValidationResult) -> None:
    """Write detected validation issues to CSV."""
    with open(dest_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["line_number", "transaction_id", "field", "error_code", "message"])
        for issue in result.issues:
            writer.writerow([
                issue.line_number,
                issue.transaction_id,
                issue.field,
                issue.error_code,
                issue.message,
            ])


def write_summary_json(dest_path: Path, summary: FinancialSummary) -> None:
    """Write financial summary payload as formatted JSON."""
    with open(dest_path, mode="w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2)
        f.write("\n")


def stage_and_publish_reports(
    output_dir: Path,
    result: ValidationResult,
    summary: FinancialSummary,
) -> None:
    """
    Generate reports completely in a temporary staging directory before publication.
    If an operational failure (OSError) occurs during publication, triggers best-effort
    rollback of artifacts newly published during that run, while leaving existing
    unrelated files untouched.

    Credence does not guarantee multi-file filesystem crash consistency across power
    loss, OS crashes, or SIGKILL.
    """
    check_output_safety(output_dir)

    # Use a temporary directory for staging
    with tempfile.TemporaryDirectory() as tmp_stage:
        stage_path = Path(tmp_stage)
        temp_clean = stage_path / CLEAN_TRANSACTIONS_FILENAME
        temp_errors = stage_path / VALIDATION_ERRORS_FILENAME
        temp_summary = stage_path / SUMMARY_JSON_FILENAME

        write_clean_transactions(temp_clean, result)
        write_validation_errors(temp_errors, result)
        write_summary_json(temp_summary, summary)

        # Ensure target directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Move staged files into output_dir with rollback on publication failure
        published_files: list[Path] = []
        try:
            for name in TARGET_ARTIFACTS:
                src_file = stage_path / name
                dst_file = output_dir / name
                shutil.move(str(src_file), str(dst_file))
                published_files.append(dst_file)
        except OSError as exc:
            for published in published_files:
                try:
                    if published.exists():
                        published.unlink()
                except OSError:
                    pass
            raise OutputSafetyError(f"Failed to publish output artifacts: {exc}") from exc
