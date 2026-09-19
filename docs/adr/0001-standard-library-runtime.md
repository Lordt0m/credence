# ADR 0001: Standard-library runtime architecture

## Context

Credence is designed for small-business owners, bookkeepers, and developers who need to validate financial cashbooks locally without complex toolchains, accounts, cloud infrastructure, or heavy third-party dependencies like `pandas` or `pydantic`. The application runs on modest hardware (including machines with 4 GB RAM) and must install cleanly with minimal friction across Windows, macOS, and Linux environments.

## Decision

Credence will use strictly the Python 3.13 standard library for all runtime functionality:
- `argparse` for command-line parsing.
- `csv` for reading and writing comma-separated value files.
- `dataclasses` for domain models (`Transaction`, `ValidationIssue`, etc.).
- `datetime` for ISO date parsing and formatting.
- `decimal` for all monetary parsing, validation, and arithmetic.
- `enum` for typed enumerations (`TransactionType`).
- `json` for serializing summary reports.
- `pathlib` for cross-platform filesystem path manipulation.
- `tempfile` and `shutil` for staged output generation and publication rollback.

External dependencies are restricted entirely to development:
- `pytest` for test execution, parameterization, and assertions.

## Consequences

### Positive
- Zero runtime dependency footprint; instant installation.
- No supply chain vulnerabilities or dependency rot at runtime.
- Predictable, deterministic behavior with no hidden runtime overhead.
- Total control over exact error formats and validation semantics without fighting framework abstractions.

### Negative
- Built-in CSV parser requires manual tracking of physical line numbers.
- Data validation rules and schema enforcement must be hand-crafted rather than delegated to third-party validators.
