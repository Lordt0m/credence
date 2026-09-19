# ADR 0002: Whole-file duplicate transaction validation

## Context

Financial transaction integrity requires that every record have a distinct, unambiguous identity. If two rows share a transaction identifier, neither row can be trusted: one might be an accidental re-entry, an altered duplicate, or a clash from disparate systems. Simply accepting the first occurrence and rejecting subsequent duplicates would risk accepting corrupted or arbitrary data.

Furthermore, duplicate checking cannot be completed in a single streaming pass without retaining prior identifiers in memory.

## Decision

Credence executes validation in two phases:
1. **Row-level phase**: Read rows sequentially, track physical line numbers, and check individual field integrity (date format, type, positive decimal amount, required fields).
2. **Whole-file duplicate pass**: Collect all non-blank, trimmed transaction identifiers in a case-insensitive index mapping normalized IDs to their occurrences across the file. If an identifier appears more than once:
   - **All** rows associated with that identifier are marked invalid.
   - Each associated row receives a `ValidationIssue` with error code `ERR_DUPLICATE_ID`.
   - None of the duplicate rows are emitted to `clean-transactions.csv` or factored into `summary.json`.

## Consequences

### Positive
- Strict financial correctness: prevents arbitrary first-come-first-served acceptance of corrupted records.
- Complete explainability: every duplicate row is flagged with its exact physical line number in `validation-errors.csv`.
- Case-insensitivity prevents subtle bypasses (e.g., `TX101` vs `tx101`).

### Negative
- Requires loading row metadata / identifiers into memory during validation, precluding single-pass unlimited streaming. For the small-business cashbook target domain (files typically thousands of rows), memory consumption is negligible (< 10 MB).
