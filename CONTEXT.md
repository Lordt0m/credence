# Domain context and vocabulary

This document defines the canonical domain models, terminology, and invariants for Credence.

## Domain vocabulary

### Cashbook
A simple income-and-expense ledger exported or assembled by a small business in CSV format. A cashbook records chronological transactions with dates, categories, descriptions, amounts, and optional references.

### SourceRow
An unvalidated row parsed from an input cashbook CSV. It preserves:
- The physical 1-indexed source line number in the CSV file.
- The raw text strings parsed from the file columns.
- Any blank row status (fully blank rows are ignored and omitted from record counting).

### Transaction
A fully validated, normalized business transaction record consisting of:
- `transaction_id`: Cleaned non-empty unique identifier string.
- `date`: Valid calendar date (`datetime.date`).
- `type`: Either `TransactionType.INCOME` or `TransactionType.EXPENSE`.
- `category`: Non-empty trimmed text.
- `description`: Non-empty trimmed text.
- `amount`: Positive `decimal.Decimal` value with up to 2 decimal places.
- `reference`: Optional trimmed text (empty string if omitted or blank).

### ValidationIssue
A structured defect record detected in a `SourceRow`. It includes:
- `line_number`: 1-indexed source file line where the error occurred.
- `transaction_id`: The raw or parsed identifier (or empty string if missing or unrecoverable).
- `field`: The specific field associated with the issue (e.g., `amount`, `date`, `transaction_id`, or `header`/`row`).
- `error_code`: A stable uppercase identifier (e.g., `ERR_INVALID_AMOUNT`, `ERR_DUPLICATE_ID`).
- `message`: A clear, actionable explanation of why the value failed validation.

### ValidationResult
The holistic outcome of validating an entire cashbook file:
- `valid_transactions`: List of valid `Transaction` records in original input order.
- `issues`: List of all detected `ValidationIssue` instances, ordered deterministically by line number and field.
- `processed_rows`: Count of non-blank data rows read from the source file.
- `valid_rows`: Count of rows with zero validation issues.
- `invalid_rows`: Count of rows with one or more validation issues.
- `total_errors`: Total count of individual validation issues across all rows.

### FinancialSummary
Calculated financial aggregates derived exclusively from valid `Transaction` instances:
- `source_file`: The filename of the input cashbook.
- `currency`: Constant `"NGN"` (Nigerian Naira).
- Row and error counts (`processed_rows`, `valid_rows`, `invalid_rows`, `error_count`).
- `earliest_date`: ISO string of earliest transaction date, or `null` if no valid rows exist.
- `latest_date`: ISO string of latest transaction date, or `null` if no valid rows exist.
- `total_income`: Sum of all valid income amounts (`Decimal`).
- `total_expenses`: Sum of all valid expense amounts (`Decimal`).
- `net_cash_movement`: `total_income - total_expenses` (`Decimal`).
- `income_by_category`: Dictionary mapping category names to total income (`Decimal`), sorted case-insensitively.
- `expenses_by_category`: Dictionary mapping category names to total expenses (`Decimal`), sorted case-insensitively.

## Canonical input columns

An input cashbook CSV header must contain exactly these 7 lowercase ASCII field names (in any column order):
1. `transaction_id`: Identifier, trimmed, non-empty, case-insensitively unique across the file.
2. `date`: Calendar date in ISO 8601 format (`YYYY-MM-DD`).
3. `type`: Case-insensitive `income` or `expense`, normalized to lowercase.
4. `category`: Non-empty trimmed text.
5. `description`: Non-empty trimmed text.
6. `amount`: Positive decimal number with at most 2 decimal places (strictly `> 0`).
7. `reference`: Optional free-form text.

## Target output artifacts

When row processing completes (whether rows are valid or invalid), Credence writes exactly three artifacts to `--output-dir`:
1. `clean-transactions.csv`: Canonical column order with all valid normalized rows, amounts formatted with two fractional digits.
2. `validation-errors.csv`: Structured CSV listing every detected issue (`line_number`, `transaction_id`, `field`, `error_code`, `message`). Header-only if no errors were found.
3. `summary.json`: JSON payload containing file metadata, row counts, and financial totals serialized as two-decimal numeric strings (e.g., `"12500.00"`).

## CLI exit codes

- `0`: Valid run. All data rows passed validation; outputs written.
- `1`: Invalid row run. One or more rows had validation errors; outputs written.
- `2`: File or operational error. Missing file, unreadable encoding, header contract violation, argument error, or existing output file conflict. No report artifacts written.
