import subprocess
import sys
import json
import shutil
from pathlib import Path

def test_first_slice_valid_file(tmp_path):
    # Setup a small valid cashbook CSV
    input_csv = tmp_path / "simple_valid.csv"
    input_csv.write_text(
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX001,2026-01-10,income,Sales,Client invoice 101,50000.00,INV-101\n"
        "TX002,2026-01-15,expense,Supplies,Office stationery,12500.50,REC-442\n",
        encoding="utf-8"
    )

    output_dir = tmp_path / "output"
    
    # Run via python -m credence
    cmd = [sys.executable, "-m", "credence", "check", str(input_csv), "--output-dir", str(output_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, f"Process failed with stderr: {result.stderr}\nstdout: {result.stdout}"
    
    # Check artifacts exist
    clean_csv = output_dir / "clean-transactions.csv"
    errors_csv = output_dir / "validation-errors.csv"
    summary_json = output_dir / "summary.json"

    assert clean_csv.is_file()
    assert errors_csv.is_file()
    assert summary_json.is_file()

    # Verify clean transactions content
    clean_content = clean_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(clean_content) == 3
    assert clean_content[0] == "transaction_id,date,type,category,description,amount,reference"
    assert clean_content[1] == "TX001,2026-01-10,income,Sales,Client invoice 101,50000.00,INV-101"
    assert clean_content[2] == "TX002,2026-01-15,expense,Supplies,Office stationery,12500.50,REC-442"

    # Verify errors CSV has header only
    errors_content = errors_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(errors_content) == 1
    assert errors_content[0] == "line_number,transaction_id,field,error_code,message"

    # Verify summary.json content
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["source_file"] == input_csv.name
    assert summary["currency"] == "NGN"
    assert summary["processed_rows"] == 2
    assert summary["valid_rows"] == 2
    assert summary["invalid_rows"] == 0
    assert summary["error_count"] == 0
    assert summary["earliest_date"] == "2026-01-10"
    assert summary["latest_date"] == "2026-01-15"
    assert summary["total_income"] == "50000.00"
    assert summary["total_expenses"] == "12500.50"
    assert summary["net_cash_movement"] == "37499.50"
    assert summary["income_by_category"] == {"Sales": "50000.00"}
    assert summary["expenses_by_category"] == {"Supplies": "12500.50"}


def test_console_script_entry_point(tmp_path):
    input_csv = tmp_path / "simple_valid.csv"
    input_csv.write_text(
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX001,2026-01-10,income,Sales,Client invoice 101,50000.00,INV-101\n",
        encoding="utf-8"
    )

    output_dir = tmp_path / "output_script"

    # Locate the installed console script executable in virtual environment
    venv_bin = Path(sys.executable).parent
    credence_bin = venv_bin / "credence"
    if not credence_bin.exists():
        credence_bin = venv_bin / "credence.exe"

    assert credence_bin.exists(), f"Console script {credence_bin} not found"

    cmd = [str(credence_bin), "check", str(input_csv), "--output-dir", str(output_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    assert (output_dir / "clean-transactions.csv").is_file()
    assert (output_dir / "summary.json").is_file()
