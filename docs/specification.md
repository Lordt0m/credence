# Credence functional specification

This document specifies the functional behavior, data contracts, validation rules, output artifacts, and error handling of Credence.

## 1. Product overview

Credence is a deterministic Python command-line utility for small businesses and bookkeepers. It parses a cashbook CSV file, runs row-level and whole-file validation passes, writes clean transaction data, logs all validation errors with source line locations, and computes a financial summary in Nigerian Naira (NGN).

## 2. Command line interface

### Primary syntax

```bash
credence check INPUT.csv --output-dir OUTPUT_DIR
```

Credence can also be invoked via Python's module interface:

```bash
python -m credence check INPUT.csv --output-dir OUTPUT_DIR
```

### Arguments

- `INPUT.csv` (positional, required): Path to the source CSV cashbook file.
- `--output-dir` (required, option `-o` or `--output-dir`): Directory path where generated artifacts will be written.

### Operational behavior

1. Validates the command arguments.
2. Checks input file existence and file type (must be regular file).
3. Verifies output directory safety: if any target artifact (`clean-transactions.csv`, `validation-errors.csv`, `summary.json`) already exists in `--output-dir`, execution halts immediately before processing with exit code `2`.
4. Reads and validates the CSV header.
5. Processes all data rows, accumulating validation errors across the entire file.
6. Performs a whole-file pass to flag duplicate transaction identifiers.
7. Stages output artifact files in a temporary location.
8. Safely publishes staged artifacts to `--output-dir` once processing finishes.
9. Prints a concise summary to terminal and terminates with the appropriate exit code.

## 3. Input file contract

### 3.1 File encoding and structure

- **Encoding**: UTF-8 encoded text. An optional UTF-8 Byte Order Mark (BOM: `\ufeff`) at the beginning of the file is accepted and stripped.
- **Line endings**: Both Unix LF (`\n`) and Windows CRLF (`\r\n`) are supported.
- **Blank lines**: Completely blank lines (or lines containing only whitespace) are skipped and do not increment processed row counters or generate validation errors.
- **Physical line numbers**: Error reporting tracks original 1-indexed line numbers in the source file, taking blank lines and the header row into account.

### 3.2 Header contract

The first non-blank line of the CSV must be the header. The header must contain exactly the following 7 column names in lowercase ASCII, in any order:
- `transaction_id`
- `date`
- `type`
- `category`
- `description`
- `amount`
- `reference`

**File-level failure conditions**:
- Header column names contain leading or trailing whitespace (names must match canonical lowercase ASCII names exactly).
- Structurally unparseable or malformed CSV quoting (e.g., unclosed quotes or syntax violations).
- Header contains missing required columns.
- Header contains unknown/extra columns.
- Header contains duplicate column names.
- File is empty (zero bytes or only blank lines).

Any header violation or structural quoting failure halts execution before or during row ingestion, produces no output artifacts, and returns exit code `2`.

## 4. Row validation semantics

Every non-blank row following the header is evaluated independently for field-level errors, followed by a whole-file uniqueness check for transaction identifiers. All detectable errors on a row are collected (validation does not stop at the first error).

### 4.1 Field rules

| Field | Invariant / Validation Rule | Stable Error Code |
|---|---|---|
| Column count | Row column count must match header column count. | `ERR_ROW_WIDTH_MISMATCH` |
| `transaction_id` | Required. Must be non-empty after trimming whitespace. | `ERR_REQUIRED_FIELD` |
| `transaction_id` (uniqueness) | Must be unique across the entire file using case-insensitive comparison. If duplicated, **all** rows sharing that identifier (including the first occurrence) are marked invalid. | `ERR_DUPLICATE_ID` |
| `date` | Required. Must be an ISO 8601 calendar date (`YYYY-MM-DD`). Must represent a real, valid calendar date (e.g., handles leap years). | `ERR_INVALID_DATE` |
| `type` | Required. Must equal `income` or `expense` (case-insensitive). Normalized to lowercase. | `ERR_INVALID_TYPE` |
| `category` | Required. Non-empty string after trimming whitespace. | `ERR_REQUIRED_FIELD` |
| `description` | Required. Non-empty string after trimming whitespace. | `ERR_REQUIRED_FIELD` |
| `amount` | Required. Positive decimal number with at most 2 fractional digits. Leading/trailing whitespace is stripped. Strictly positive (`> 0`). Currency symbols (e.g., `₦`, `$`), signs (`+`, `-`), thousands commas (`,`), and exponential notation are prohibited. | `ERR_INVALID_AMOUNT` |
| `reference` | Optional text. Whitespace is trimmed; an empty value is valid. | None |

### 4.2 Error accumulation and recovery

- If a row has a column count mismatch (`ERR_ROW_WIDTH_MISMATCH`), field-by-field validation cannot safely align values; the row is marked invalid immediately.
- If a row has matching column width, all 6 required fields are evaluated and all failing fields record separate `ValidationIssue` entries.
- If `transaction_id` cannot be parsed or is empty, the issue's `transaction_id` field is logged as empty (`""`).

## 5. Output artifacts contract

When row validation completes, three files are written to `--output-dir`.

### 5.1 `clean-transactions.csv`

Contains all valid, normalized rows in their original source file order.
- **Header**: Canonical column order:
  `transaction_id,date,type,category,description,amount,reference`
- **Normalization**:
  - `transaction_id`: trimmed string.
  - `date`: `YYYY-MM-DD`.
  - `type`: lowercase (`income` or `expense`).
  - `category`: trimmed string.
  - `description`: trimmed string.
  - `amount`: formatted to exactly two decimal places (e.g., `1500.00`).
  - `reference`: trimmed string (or empty).
- Rows with any validation issue are excluded.

### 5.2 `validation-errors.csv`

Contains all detected validation issues, sorted deterministically by source `line_number` ascending, then by `field`.
- **Columns**:
  `line_number,transaction_id,field,error_code,message`
- If no errors were detected in the file, this file is still written containing only the header line.

### 5.3 `summary.json`

JSON payload summarizing file metrics and financial totals derived exclusively from valid rows.
- **Fields**:
  - `source_file`: string (basename or path of input file).
  - `currency`: `"NGN"`.
  - `processed_rows`: integer.
  - `valid_rows`: integer.
  - `invalid_rows`: integer.
  - `error_count`: integer.
  - `earliest_date`: ISO date string (`"YYYY-MM-DD"`), or `null` if 0 valid rows.
  - `latest_date`: ISO date string (`"YYYY-MM-DD"`), or `null` if 0 valid rows.
  - `total_income`: string with 2 decimal places (e.g., `"250000.00"`).
  - `total_expenses`: string with 2 decimal places (e.g., `"140200.50"`).
  - `net_cash_movement`: string with 2 decimal places (`total_income - total_expenses`).
  - `income_by_category`: object mapping category names to 2-decimal string amounts, sorted case-insensitively by category name.
  - `expenses_by_category`: object mapping category names to 2-decimal string amounts, sorted case-insensitively by category name.

## 6. Output safety and staged publication

1. **Collision prevention**: Before reading or processing rows, Credence checks if any of the target filenames already exist in the target `--output-dir`. If any target artifact exists, the command terminates with an error message and exit code `2`.
2. **Staged writes and publication rollback**: During processing, artifacts are written to a temporary staging directory. Only after all rows are processed and all files written successfully are the artifacts moved to `--output-dir`. If publication of any target artifact fails due to a handled exception, Credence executes best-effort rollback, removing any target files newly published during that execution while preserving any pre-existing unrelated files in `--output-dir`.
3. **Safety boundary**: Application-level guarantees cover handled exceptions and collision prevention. The CLI does not provide multi-file POSIX filesystem-level crash consistency across sudden power outages, OS crashes, or SIGKILL signals.

## 7. Terminal reporting and exit codes

### Terminal summary

On completion, Credence prints a concise status report to stdout:
```text
Source: input.csv
Processed rows: 25 (Valid: 22, Invalid: 3, Errors: 4)
Artifacts written to: output_dir/
Financial summary (valid records, NGN):
  Total income:        250,000.00
  Total expenses:      140,200.50
  Net cash movement:   109,799.50
```

### Exit codes

| Exit Code | Condition |
|---|---|
| `0` | Success. All data rows valid, all artifacts generated. |
| `1` | Validation issues detected. Outputs generated, but 1 or more rows were invalid. |
| `2` | File, argument, header, or safety error. No artifacts generated. |

Operational errors write a clear, single-line error message to stderr without Python tracebacks.

## 8. Explicit exclusions

- No support for Excel (`.xlsx`), PDF, JSON, or SQL ingestion.
- No interactive editing or in-place file modification.
- No network connections, database connections, or external API calls.
- No multi-currency conversion or tax calculations.
- No configurable schema or plugin architecture.
