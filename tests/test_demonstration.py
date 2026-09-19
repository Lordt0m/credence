import subprocess
import sys
import json
from pathlib import Path

from credence.constants import TARGET_ARTIFACTS


def test_demonstration_mixed_cashbook_matches_expected_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    fixtures_dir = repo_root / "fixtures"
    mixed_csv = fixtures_dir / "mixed_cashbook.csv"
    expected_dir = fixtures_dir / "expected_mixed_output"

    output_dir = tmp_path / "actual_mixed_output"

    cmd = [sys.executable, "-m", "credence", "check", str(mixed_csv), "--output-dir", str(output_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)

    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Stderr: {res.stderr}"

    for artifact in TARGET_ARTIFACTS:
        expected_file = expected_dir / artifact
        actual_file = output_dir / artifact

        assert actual_file.exists(), f"Missing output artifact: {artifact}"
        assert actual_file.read_text(encoding="utf-8") == expected_file.read_text(encoding="utf-8"), (
            f"Artifact {artifact} does not match expected output byte-for-byte."
        )


def test_demonstration_valid_cashbook_succeeds(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    fixtures_dir = repo_root / "fixtures"
    valid_csv = fixtures_dir / "valid_cashbook.csv"

    output_dir = tmp_path / "actual_valid_output"

    cmd = [sys.executable, "-m", "credence", "check", str(valid_csv), "--output-dir", str(output_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)

    assert res.returncode == 0, f"Expected returncode 0, got {res.returncode}. Stderr: {res.stderr}"

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["processed_rows"] == 10
    assert summary["valid_rows"] == 10
    assert summary["invalid_rows"] == 0
    assert summary["error_count"] == 0
    assert summary["total_income"] == "445000.00"
    assert summary["total_expenses"] == "154700.50"
    assert summary["net_cash_movement"] == "290299.50"
