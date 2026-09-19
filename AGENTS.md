# Credence repository guidance

## Repository purpose

Credence is a focused Python command-line tool that processes small-business cashbook CSV files. It validates records, isolates invalid rows with actionable diagnostic error reports, produces normalized clean transaction files, and derives trustworthy, reconciled financial summaries in Nigerian Naira (NGN).

The tool emphasizes deterministic file handling, strict decimal arithmetic, whole-file duplicate detection, explicit CLI error codes, and safe output staging without external runtime dependencies.

## Authoritative documents

- `CONTEXT.md`: Canonical domain terminology, invariants, and boundaries.
- `docs/specification.md`: Formal specification of CLI, input contracts, validation rules, output formats, and exit codes.
- `docs/workflows/new-feature.md`: Standard workflow for new feature implementation and bug fixing.
- `docs/adr/`: Architecture Decision Records capturing foundational design choices.
- `docs/delivery-plan.md`: Dependency-ordered delivery plan and acceptance checks.
- `STATUS.md`: The active repository checkpoint, last verified state, known risks, and next safe action.

## Core engineering rules

1. **Python standard library runtime**: Runtime code must use only the Python standard library (`argparse`, `csv`, `dataclasses`, `datetime`, `decimal`, `enum`, `json`, `pathlib`, etc.). No external dependencies at runtime.
2. **Development dependencies**: `pytest` is permitted solely as a development dependency for readable, parameterized testing.
3. **Strict decimal arithmetic**: Never use binary floating-point (`float`) for monetary amounts or summary totals. Always use Python's `decimal.Decimal`.
4. **Physical source line preservation**: Line numbers reported in error logs and diagnostics must match the 1-indexed physical line numbers of the source file.
5. **Whole-file duplicate invalidation**: Every occurrence of a duplicated transaction identifier (case-insensitive) is invalid, including the first occurrence.
6. **Staged output safety and publication rollback**: Never overwrite existing target artifacts in an output directory without explicit intent (overwriting is excluded in MVP). Reports are completely generated in temporary staging before publication. Handled operational publication failures trigger best-effort rollback of artifacts newly published during that run, while preserving unrelated existing files. Multi-file filesystem crash consistency across power loss, OS crashes, or SIGKILL is not guaranteed.
7. **Clean CLI boundary**: Normal operational errors (missing files, malformed headers, invalid rows) must produce clean stderr/stdout diagnostics and documented exit codes (0, 1, 2) without raw Python tracebacks. Uncaught bugs remain visible in development.
8. **Cross-platform paths**: Support both Windows (`\`) and POSIX (`/`) paths consistently.

## Verification commands

- Setup virtual environment:
  ```powershell
  python -m venv .venv
  .venv\Scripts\python -m pip install -e .[dev]
  ```
- Run tests:
  ```powershell
  .venv\Scripts\pytest -v
  ```
- Run CLI check:
  ```powershell
  .venv\Scripts\credence check path\to\cashbook.csv --output-dir path\to\output
  ```
- Run package module:
  ```powershell
  .venv\Scripts\python -m credence check path\to\cashbook.csv --output-dir path\to\output
  ```

## Completion rules

A ticket or phase is complete only when:
- All acceptance checks in `docs/delivery-plan.md` are backed by automated tests.
- Code adhering to standards has been verified on Python 3.13.
- Both console script (`credence`) and module (`python -m credence`) entry points execute identically.
- Working tree is clean and `STATUS.md` reflects the current verified state.
