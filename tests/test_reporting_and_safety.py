import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest

from credence.constants import TARGET_ARTIFACTS
from credence.models import Transaction, TransactionType, ValidationIssue, ValidationResult
from credence.reporting import (
    OutputSafetyError,
    check_output_safety,
    stage_and_publish_reports,
)
from credence.validator import calculate_summary


def test_collision_prevention_aborts_with_code_2(tmp_path):
    output_dir = tmp_path / "output_collision"
    output_dir.mkdir(parents=True)
    # Pre-create one of the target artifacts
    existing_file = output_dir / "clean-transactions.csv"
    existing_file.write_text("dummy", encoding="utf-8")

    input_csv = tmp_path / "valid.csv"
    input_csv.write_text(
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX1,2026-01-01,income,Sales,Item,100.00,\n",
        encoding="utf-8"
    )

    cmd = [sys.executable, "-m", "credence", "check", str(input_csv), "--output-dir", str(output_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)

    assert res.returncode == 2
    assert "Refusing to overwrite existing files" in res.stderr
    assert "Traceback" not in res.stderr
    # Confirm existing file was not modified
    assert existing_file.read_text(encoding="utf-8") == "dummy"
    # Confirm no other artifacts were created
    assert not (output_dir / "summary.json").exists()
    assert not (output_dir / "validation-errors.csv").exists()


def test_staged_publishing_cleans_up_on_failure(tmp_path, monkeypatch):
    output_dir = tmp_path / "output_staging_fail"

    result = ValidationResult(processed_rows=1, valid_rows=1)
    result.valid_transactions.append(
        Transaction("T1", date(2026, 1, 1), TransactionType.INCOME, "Sales", "Desc", Decimal("50.00"), "")
    )
    summary = calculate_summary("test.csv", result)

    # Monkeypatch write_summary_json to raise an error midway
    import credence.reporting
    def mock_write_summary_json(path, summary):
        raise RuntimeError("Simulated disk error during staging")

    monkeypatch.setattr(credence.reporting, "write_summary_json", mock_write_summary_json)

    with pytest.raises(RuntimeError, match="Simulated disk error"):
        stage_and_publish_reports(output_dir, result, summary)

    # Ensure output_dir was either not created or contains no target artifacts
    if output_dir.exists():
        for name in TARGET_ARTIFACTS:
            assert not (output_dir / name).exists()


def test_mixed_file_exit_code_1_and_financial_reconciliation(tmp_path):
    # Setup mixed cashbook: 2 valid rows, 2 invalid rows (1 bad date, 1 duplicate ID)
    input_csv = tmp_path / "mixed.csv"
    input_csv.write_text(
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX101,2026-02-01,income,Sales,Valid income 1,20000.00,INV-01\n"
        "TX102,2026-02-05,expense,Rent,Shop rent,8500.50,RENT-01\n"
        "TX103,2026-99-99,income,Sales,Invalid date,5000.00,INV-02\n"
        "TX101,2026-02-10,income,Sales,Duplicate ID,3000.00,INV-03\n",
        encoding="utf-8"
    )

    output_dir = tmp_path / "output_mixed"
    cmd = [sys.executable, "-m", "credence", "check", str(input_csv), "--output-dir", str(output_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)

    # Exit code 1 for invalid rows
    assert res.returncode == 1
    assert "Traceback" not in res.stderr

    # Check terminal output
    assert "Processed rows: 4 (Valid: 1, Invalid: 3, Errors: 3)" in res.stdout

    # Read clean transactions
    clean_lines = (output_dir / "clean-transactions.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(clean_lines) == 2  # header + 1 valid row (TX102 only, since TX101 duplicated!)
    assert "TX102,2026-02-05,expense,Rent,Shop rent,8500.50,RENT-01" == clean_lines[1]

    # Read summary JSON
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["processed_rows"] == 4
    assert summary["valid_rows"] == 1
    assert summary["invalid_rows"] == 3
    assert summary["error_count"] == 3
    assert summary["total_income"] == "0.00"
    assert summary["total_expenses"] == "8500.50"
    assert summary["net_cash_movement"] == "-8500.50"
    assert summary["earliest_date"] == "2026-02-05"
    assert summary["latest_date"] == "2026-02-05"

    # Read errors CSV
    error_lines = (output_dir / "validation-errors.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(error_lines) == 4  # header + 3 errors
    # Errors should be for line 2 (TX101 duplicate), line 4 (TX103 invalid date), line 5 (TX101 duplicate)
    assert "ERR_DUPLICATE_ID" in error_lines[1]
    assert "ERR_INVALID_DATE" in error_lines[2]
    assert "ERR_DUPLICATE_ID" in error_lines[3]


def test_deterministic_output(tmp_path):
    input_csv = tmp_path / "deterministic.csv"
    input_csv.write_text(
        "transaction_id,date,type,category,description,amount,reference\n"
        "T2,2026-01-05,expense,Utilities,Power,150.00,REF2\n"
        "T1,2026-01-02,income,Sales,Widgets,200.00,REF1\n",
        encoding="utf-8"
    )

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    cmd1 = [sys.executable, "-m", "credence", "check", str(input_csv), "-o", str(out1)]
    cmd2 = [sys.executable, "-m", "credence", "check", str(input_csv), "-o", str(out2)]

    res1 = subprocess.run(cmd1, capture_output=True, text=True)
    res2 = subprocess.run(cmd2, capture_output=True, text=True)

    assert res1.returncode == 0
    assert res2.returncode == 0

    for artifact in TARGET_ARTIFACTS:
        f1_bytes = (out1 / artifact).read_bytes()
        f2_bytes = (out2 / artifact).read_bytes()
        assert f1_bytes == f2_bytes, f"Artifact {artifact} differs between runs"


@pytest.mark.parametrize(
    "bad_args,expected_code,error_substring",
    [
        (["nonexistent_file.csv", "-o", "out"], 2, "Input file does not exist"),
        ([], 2, "usage:"),
    ],
)
def test_cli_expected_errors_exit_code_2_without_traceback(tmp_path, bad_args, expected_code, error_substring):
    cmd = [sys.executable, "-m", "credence", "check"] + [
        arg.replace("out", str(tmp_path / "out")) for arg in bad_args
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == expected_code
    assert "Traceback" not in res.stderr
    assert error_substring in res.stderr


def test_publication_failure_rolls_back_published_artifacts(tmp_path, monkeypatch):
    import shutil
    import credence.reporting
    from credence.constants import (
        CLEAN_TRANSACTIONS_FILENAME,
        SUMMARY_JSON_FILENAME,
        VALIDATION_ERRORS_FILENAME,
    )

    output_dir = tmp_path / "rollback_test"
    output_dir.mkdir(parents=True)
    unrelated_file = output_dir / "unrelated.txt"
    unrelated_file.write_text("keep this file", encoding="utf-8")

    result = ValidationResult(processed_rows=1, valid_rows=1)
    result.valid_transactions.append(
        Transaction("T1", date(2026, 1, 1), TransactionType.INCOME, "Sales", "Desc", Decimal("50.00"), "")
    )
    summary = calculate_summary("test.csv", result)

    real_move = shutil.move
    def failing_move(src, dst):
        if Path(dst).name == VALIDATION_ERRORS_FILENAME:
            raise OSError("Simulated disk error during publication")
        return real_move(src, dst)

    monkeypatch.setattr(credence.reporting.shutil, "move", failing_move)

    with pytest.raises((OutputSafetyError, OSError), match="Simulated disk error"):
        stage_and_publish_reports(output_dir, result, summary)

    # All target artifacts must be rolled back
    assert not (output_dir / CLEAN_TRANSACTIONS_FILENAME).exists(), "clean-transactions.csv was not rolled back"
    assert not (output_dir / VALIDATION_ERRORS_FILENAME).exists()
    assert not (output_dir / SUMMARY_JSON_FILENAME).exists()
    # Unrelated file must remain untouched
    assert unrelated_file.read_text(encoding="utf-8") == "keep this file"


def test_malformed_csv_quoting_cli_exit_code_2_no_artifacts(tmp_path):
    input_csv = tmp_path / "malformed_quote.csv"
    input_csv.write_text(
        'transaction_id,date,type,category,description,amount,reference\n'
        'TX1,2026-01-01,income,Sales,"unclosed description,100.00,REF1\n',
        encoding="utf-8"
    )
    output_dir = tmp_path / "malformed_output"

    cmd = [sys.executable, "-m", "credence", "check", str(input_csv), "-o", str(output_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)

    assert res.returncode == 2
    assert "Traceback" not in res.stderr
    assert "Malformed CSV" in res.stderr
    if output_dir.exists():
        for name in TARGET_ARTIFACTS:
            assert not (output_dir / name).exists()


def test_cli_unexpected_programming_defect_surfaces_traceback(tmp_path):
    input_csv = tmp_path / "valid.csv"
    input_csv.write_text(
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX1,2026-01-01,income,Sales,Widget,100.00,REF1\n",
        encoding="utf-8"
    )
    output_dir = tmp_path / "bug_output"

    # Run Python code that patches validate_cashbook to raise an unexpected defect
    runner_code = (
        "import sys\n"
        "from unittest.mock import patch\n"
        "import credence.cli\n"
        "def buggy_validator(*args, **kwargs):\n"
        "    raise ZeroDivisionError('simulated unexpected programming bug')\n"
        "with patch('credence.cli.validate_cashbook', side_effect=buggy_validator):\n"
        f"    sys.exit(credence.cli.main(['check', r'{str(input_csv)}', '-o', r'{str(output_dir)}']))\n"
    )
    cmd = [sys.executable, "-c", runner_code]
    res = subprocess.run(cmd, capture_output=True, text=True)

    # Must NOT be converted to exit code 2
    assert res.returncode != 2
    assert res.returncode != 0
    # Traceback must remain visible
    assert "Traceback (most recent call last)" in res.stderr
    assert "ZeroDivisionError: simulated unexpected programming bug" in res.stderr
