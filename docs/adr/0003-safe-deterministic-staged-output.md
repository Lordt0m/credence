# ADR 0003: Safe staged output and deterministic generation

## Context

A tool that produces multiple output artifacts (`clean-transactions.csv`, `validation-errors.csv`, `summary.json`) can leave the destination directory in an inconsistent state if:
1. It overwrites previous run outputs silently, destroying user work.
2. A crash or error occurs halfway through writing, leaving partial or orphaned files.
3. Output ordering is non-deterministic (e.g., hash-map iteration), causing spurious differences in version control or checksum validation.

## Decision

Credence adopts a strict output safety and determinism protocol:

1. **Pre-flight collision check**: Before any row parsing or processing begins, Credence checks whether any of the three target files exist in the specified `--output-dir`. If any target artifact already exists, the process fails immediately with exit code `2` and does not alter the directory.
2. **Staged writing via temporary directory and publication rollback**: Artifacts are generated inside an isolated temporary directory (`tempfile.TemporaryDirectory`). Only after all three artifacts are successfully constructed, formatted, and closed are they published to `--output-dir`. If publication of a subsequent file fails due to a handled exception (such as an `OSError`), Credence performs best-effort rollback by removing any target artifacts newly published during that run, ensuring no partial set of Credence outputs remains. Any pre-existing unrelated files in the output directory remain untouched.
3. **Safety boundary and non-guarantees**: The application-level safety guarantees apply to handled operational exceptions and pre-flight collision prevention. Credence does not provide multi-file filesystem-level crash consistency across sudden OS crashes, power loss, or unhandled SIGKILL signals.
4. **Deterministic output generation**:
   - `clean-transactions.csv` maintains original source row ordering with canonical column order.
   - `validation-errors.csv` is sorted by line number ascending, then by field name.
   - `summary.json` categories (`income_by_category`, `expenses_by_category`) are sorted case-insensitively by key, and JSON serialization uses indentation and sorted keys.
   - Monetary values in `summary.json` are serialized as strings with exactly two decimal places to prevent floating-point ambiguity.

## Consequences

### Positive
- Prevents accidental overwriting of existing target artifacts via pre-flight checks.
- Handled operational failures during processing or publication do not leave partial or orphaned Credence artifacts in the output directory.
- Idempotent and deterministic: identical inputs produce byte-for-byte identical output files.
- Version-control friendly for automated reporting pipelines.

### Negative
- Users must explicitly supply a fresh or collision-free directory for `--output-dir` (overwrite flag is intentionally excluded in MVP).
- File operations across distinct filesystems/devices may involve copies rather than atomic inode renames, mitigated by application-level rollback for handled exceptions.
