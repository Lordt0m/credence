# Project status: Credence

## Repository checkpoint
- Phase: Phase 5 complete (Demonstration data and public documentation).
- Repository: `C:\Users\Lord\Documents\Codex\credence` (branch: `main`).

## Last verified result
- 27 automated tests passing in `.venv` with pytest.
- Fictional demonstration fixtures committed in `fixtures/`:
  - `fixtures/valid_cashbook.csv`: 10 rows spanning Jan-Feb 2026 across 6 business categories.
  - `fixtures/mixed_cashbook.csv`: 10 processed rows with 4 valid rows and 6 invalid rows demonstrating duplicate identifiers, column count mismatch, invalid amounts, invalid dates, and multiple row-level errors.
  - `fixtures/expected_mixed_output/`: Canonical `clean-transactions.csv`, `validation-errors.csv`, and `summary.json`.
- Demonstration reproduction test (`tests/test_demonstration.py`) proves fresh runs reproduce committed demonstration artifacts byte-for-byte.
- Comprehensive user-facing `README.md` complete with problem framing, copyable PowerShell and POSIX demonstration commands, input schema table, output formats, exit codes, architecture rationale, and test execution guide.

## Known risks
- GitHub Actions CI workflow must be authored and verified before remote publication.
- Public GitHub repository creation and push pending in Phase 7.

## Next safe action
- Commit Phase 5.
- Begin Phase 6: Author GitHub Actions CI workflow `.github/workflows/ci.yml`, verify complete local release gate, and check repository cleanliness.
