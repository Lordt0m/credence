# Feature and maintenance workflow

This document prescribes the engineering discipline for adding features, extending validation, or fixing bugs in Credence.

## Workflow stages

### 1. Understand
- Review the requirement against `docs/specification.md` and `CONTEXT.md`.
- Determine whether the change affects the input contract, validation semantics, summary calculation, or output format.
- Ensure the proposed change falls within the product boundaries (standard library runtime, local execution, explicit error codes).

### 2. Inspect
- Examine relevant domain models in `src/credence/models.py`.
- Identify existing unit and integration test fixtures under `tests/`.
- Trace how source data flows from CSV reader -> row validator -> whole-file duplicate pass -> financial summary -> staged output writers.

### 3. Plan
- Define the smallest coherent vertical slice.
- Identify the invariant or contract boundary to verify.
- Decide on error codes or data model updates if applicable.

### 4. Test-first implementation (Red-Green-Refactor)
- Write an automated unit or integration test in `tests/` that specifies the desired behavior and fails for the expected reason.
- Run `pytest` to confirm the test fails as expected.
- Implement the minimal code in `src/credence/` required to satisfy the test.
- Re-run `pytest` to ensure all tests pass.
- Refactor code for clarity, typing, and standard library idiom under green tests.

### 5. Verification
- Verify edge cases: Windows CRLF vs Unix LF, empty fields, whitespace trimming, extreme decimals, case insensitivity.
- Run the full test suite:
  ```powershell
  pytest -v
  ```
- Run both CLI entry points:
  ```powershell
  credence check fixtures/mixed_cashbook.csv --output-dir temp_output
  python -m credence check fixtures/mixed_cashbook.csv --output-dir temp_output_2
  ```
- Inspect exit codes ($LASTEXITCODE in PowerShell, $? in POSIX).

### 6. Review
- Check for zero runtime dependencies outside Python 3.13 stdlib.
- Check that all error paths handle exceptions gracefully without dumping tracebacks for user input errors.
- Confirm deterministic output ordering (e.g. sorted keys in JSON, stable line-number ordering in CSV).
- Verify that tests clean up any temporary directories or files.

### 7. Commit discipline
- Ensure `git status` shows only intentional modifications.
- Create atomic, truthful commits with descriptive messages following conventional structure:
  ```text
  <component>: <short summary>

  <details on why and what was verified>
  ```
- Keep `STATUS.md` updated with the active repository checkpoint.
