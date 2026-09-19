# Credence delivery plan and acceptance checks

This document outlines the phased build sequence and explicit acceptance checks for Credence.

## Phase 1: Repository contract and baseline
- [x] Initialize Git repository on `main`.
- [x] Create Python `.gitignore`.
- [x] Author `AGENTS.md` covering workflow, rules, and verification.
- [x] Author `CONTEXT.md` defining canonical domain terminology.
- [x] Author `docs/specification.md` defining inputs, outputs, rules, and codes.
- [x] Author `docs/workflows/new-feature.md` covering red-green-refactor standards.
- [x] Author ADR set (`0001-standard-library-runtime.md`, `0002-whole-file-duplicate-validation.md`, `0003-safe-deterministic-staged-output.md`).
- [x] Author initial `STATUS.md` checkpoint.
- [x] Commit baseline contract.

## Phase 2: Package structure and first vertical slice
- [ ] Define `pyproject.toml` targeting Python 3.13, console script `credence`, and `pytest` dev dependency.
- [ ] Set up local virtual environment `.venv` and install package in editable mode with dev tools.
- [ ] Implement core package layout in `src/credence/` (`__init__.py`, `__main__.py`, `cli.py`, `models.py`).
- [ ] Write failing end-to-end integration test asserting valid cashbook parsing and artifact writing.
- [ ] Implement narrow end-to-end path writing `clean-transactions.csv`, `validation-errors.csv`, and `summary.json`.
- [ ] Verify both `credence check` and `python -m credence check` work equivalently with exit code 0.
- [ ] Commit Phase 2.

## Phase 3: Complete validation semantics
- [ ] Implement strict header validation (exact 7 fields, case sensitivity, column order tolerance).
- [ ] Implement UTF-8 BOM stripping and line ending support (LF/CRLF).
- [ ] Implement physical line number tracking and blank line skipping.
- [ ] Implement row width mismatch detection (`ERR_ROW_WIDTH_MISMATCH`).
- [ ] Implement field-level validators with stable error codes:
  - `date`: ISO calendar date (`ERR_INVALID_DATE`).
  - `type`: `income`/`expense` case-insensitive normalization (`ERR_INVALID_TYPE`).
  - `category`: non-empty trimmed text (`ERR_REQUIRED_FIELD`).
  - `description`: non-empty trimmed text (`ERR_REQUIRED_FIELD`).
  - `amount`: strictly positive decimal with at most 2 fractional digits (`ERR_INVALID_AMOUNT`).
  - `reference`: optional text handling.
- [ ] Implement whole-file case-insensitive duplicate transaction ID validation (`ERR_DUPLICATE_ID`) that invalidates all occurrences.
- [ ] Accumulate all detectable errors per row.
- [ ] Write comprehensive unit tests for all boundary conditions and rules.
- [ ] Commit Phase 3.

## Phase 4: Complete safe reporting and CLI
- [ ] Implement deterministic `clean-transactions.csv` writer with canonical headers and 2-decimal amounts.
- [ ] Implement deterministic `validation-errors.csv` writer sorted by line number and field.
- [ ] Implement `summary.json` generation with exact decimal serialization as strings, sorted categories, and correct valid-only aggregates.
- [ ] Implement output safety: check for existing target artifacts before execution; abort with exit code 2 if collision detected.
- [ ] Implement staged output writing to guarantee atomic artifact publishing and cleanup on error.
- [ ] Implement terminal summary output matching specification.
- [ ] Implement exit code semantics: 0 for all-valid, 1 for row errors, 2 for file/safety errors.
- [ ] Ensure absence of Python tracebacks for all operational errors.
- [ ] Integration tests covering simulated write failure, duplicate protection, and collision checks.
- [ ] Commit Phase 4.

## Phase 5: Demonstration data and public documentation
- [ ] Create fictional valid cashbook fixture (`fixtures/valid_cashbook.csv`).
- [ ] Create fictional mixed-quality cashbook fixture (`fixtures/mixed_cashbook.csv`) exercising all major error conditions.
- [ ] Generate and commit canonical expected output artifacts for `mixed_cashbook.csv` (`fixtures/expected_mixed_output/`).
- [ ] Author comprehensive `README.md` including problem context, one-command demonstration, installation, schema, outputs, exit codes, PowerShell and POSIX examples, architecture, and trade-offs.
- [ ] Verify fresh clone reproducibility and exact match with expected output.
- [ ] Commit Phase 5.

## Phase 6: Public CI and release verification
- [ ] Author GitHub Actions workflow `.github/workflows/ci.yml` running on Python 3.13.
- [ ] Workflow steps: install dependencies, run test suite, test both entry points, verify demonstration outputs.
- [ ] Run complete local release verification in clean virtual environment.
- [ ] Check `git diff --check` and clean working tree.
- [ ] Update `STATUS.md`.
- [ ] Commit Phase 6.

## Phase 7: GitHub publication and release
- [ ] Create public GitHub repository `Lordt0m/credence`.
- [ ] Push `main` branch to remote.
- [ ] Verify GitHub Actions run passes cleanly.
- [ ] Compile final primary-builder handoff report.
