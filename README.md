# Credence

Credence turns small-business cashbook CSV files into an explainable validation report, a clean transaction file, and a trustworthy financial summary in Nigerian Naira (NGN).

Small-business owners, bookkeepers, and analysts frequently export or assemble cashbooks in spreadsheets. Before these records are used for financial reporting or tax preparation, three critical questions must be answered:
1. **Can this file be processed safely?** (Are encoding, column names, and row widths structurally intact?)
2. **Which records are invalid, and why?** (Are dates malformed, amounts signed or negative, categories missing, or transaction IDs duplicated?)
3. **What do the valid records say about income, expenses, and net cash movement?**

Credence answers these questions deterministically through a single local command—requiring no accounts, databases, cloud APIs, internet connectivity, or spreadsheet software.

---

## Quickstart demonstration

Clone the repository and run the demonstration cashbook using Python 3.13:

### Windows PowerShell

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install Credence in editable mode with development tools
pip install -e .[dev]

# 3. Run the demonstration against the fictional mixed cashbook
credence check fixtures/mixed_cashbook.csv --output-dir demo_output
```

### POSIX Shell (Linux / macOS)

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Credence in editable mode with development tools
pip install -e .[dev]

# 3. Run the demonstration against the fictional mixed cashbook
credence check fixtures/mixed_cashbook.csv --output-dir demo_output
```

Alternatively, invoke Credence as a Python module:

```bash
python -m credence check fixtures/mixed_cashbook.csv --output-dir demo_output
```

### Terminal output

When executed against `fixtures/mixed_cashbook.csv`, Credence outputs:

```text
Source: mixed_cashbook.csv
Processed rows: 10 (Valid: 4, Invalid: 6, Errors: 7)
Artifacts written to: demo_output
Financial summary (valid records, NGN):
  Total income:             75,000.00
  Total expenses:           59,500.50
  Net cash movement:        15,499.50
```

Because invalid rows were encountered, the command returns exit code `1`.

> **Note on demonstration data**: All fixtures in `fixtures/` represent entirely fictional small-business scenarios created for automated verification and demonstration. They do not represent real persons, businesses, or transactions.

---

## Input CSV contract

Credence accepts UTF-8 encoded CSV files (with an optional UTF-8 Byte Order Mark). Header column order may vary, but the header must contain exactly these 7 lowercase ASCII field names:

| Field | Invariant / Validation Rule | Error Code on Failure |
|---|---|---|
| `transaction_id` | Required after trimming. Must be unique across the entire file (case-insensitive). If duplicated, **all** rows sharing that identifier are rejected. | `ERR_REQUIRED_FIELD` / `ERR_DUPLICATE_ID` |
| `date` | Required ISO 8601 calendar date in `YYYY-MM-DD` format. Validated as a real calendar date (handles leap years). | `ERR_INVALID_DATE` |
| `type` | Required. Must be `income` or `expense` (case-insensitive); normalized to lowercase. | `ERR_INVALID_TYPE` |
| `category` | Required non-empty string after trimming leading and trailing whitespace. | `ERR_REQUIRED_FIELD` |
| `description` | Required non-empty string after trimming leading and trailing whitespace. | `ERR_REQUIRED_FIELD` |
| `amount` | Required positive decimal with at most two fractional digits (strictly `> 0`). Currency symbols (`₦`, `$`), signs (`+`, `-`), thousands separators (`,`), and exponential notation are prohibited. | `ERR_INVALID_AMOUNT` |
| `reference` | Optional free-form string. An empty or omitted value is valid. | None |

### Structural rules
- **Header and structural errors**: Missing, extra, whitespace-padded, or duplicated header columns, as well as structurally unparseable CSV quoting, halt execution immediately with exit code `2`.
- **Blank lines**: Empty or whitespace-only lines are ignored and do not affect record counts or physical line tracking.
- **Physical line numbers**: Error diagnostics track 1-indexed physical file lines.
- **Row width mismatch**: If a row contains more or fewer columns than the header, it is flagged with `ERR_ROW_WIDTH_MISMATCH`, excluded from valid transactions, and companion valid rows remain eligible for reporting.

---

## Generated artifacts

When row validation completes, Credence writes exactly three artifacts into `--output-dir`:

### 1. `clean-transactions.csv`
Contains all valid, normalized records in original source order, rendered with canonical columns and 2-decimal amounts:
```csv
transaction_id,date,type,category,description,amount,reference
TX-MIX-001,2026-01-04,income,Sales,Retail clothing sales,75000.00,INV-001
TX-MIX-002,2026-01-07,expense,Rent,Shop space rental,40000.00,REC-001
TX-MIX-006,2026-02-02,expense,Utilities,Water bill payment,12000.00,REC-002
TX-MIX-008,2026-02-19,expense,Logistics,Courier delivery dispatch,7500.50,DISP-88
```

### 2. `validation-errors.csv`
Contains every detected error, sorted deterministically by source `line_number` and `field`. Always written upon completion (header-only if 0 errors):
```csv
line_number,transaction_id,field,error_code,message
5,TX-MIX-003,amount,ERR_INVALID_AMOUNT,Amount '0.00' must be strictly positive (> 0).
6,TX-MIX-004,transaction_id,ERR_DUPLICATE_ID,Duplicate transaction ID 'TX-MIX-004' (case-insensitive) appears 2 times.
7,,row,ERR_ROW_WIDTH_MISMATCH,Row has 6 columns; expected 7.
9,TX-MIX-007,description,ERR_REQUIRED_FIELD,Description is required and cannot be empty.
9,TX-MIX-007,type,ERR_INVALID_TYPE,Type 'transfer' must be 'income' or 'expense'.
10,tx-mix-004,transaction_id,ERR_DUPLICATE_ID,Duplicate transaction ID 'tx-mix-004' (case-insensitive) appears 2 times.
12,TX-MIX-009,date,ERR_INVALID_DATE,Date '2026-02-29' is not a valid calendar date.
```

### 3. `summary.json`
Provides machine-readable file metrics and reconciled financial aggregates:
```json
{
  "source_file": "mixed_cashbook.csv",
  "currency": "NGN",
  "processed_rows": 10,
  "valid_rows": 4,
  "invalid_rows": 6,
  "error_count": 7,
  "earliest_date": "2026-01-04",
  "latest_date": "2026-02-19",
  "total_income": "75000.00",
  "total_expenses": "59500.50",
  "net_cash_movement": "15499.50",
  "income_by_category": {
    "Sales": "75000.00"
  },
  "expenses_by_category": {
    "Logistics": "7500.50",
    "Rent": "40000.00",
    "Utilities": "12000.00"
  }
}
```

---

## Example: Tracing an invalid row

Consider source row line 9 from `fixtures/mixed_cashbook.csv`:
```csv
TX-MIX-007,2026-02-08,transfer,Finance,,25000.00,
```

Credence accumulates all detectable defects on this row instead of stopping at the first failure:
1. `type`: Value `'transfer'` is neither `'income'` nor `'expense'` &rarr; flags `ERR_INVALID_TYPE`.
2. `description`: Field is empty &rarr; flags `ERR_REQUIRED_FIELD`.

Both issues appear in `validation-errors.csv`:
```csv
9,TX-MIX-007,description,ERR_REQUIRED_FIELD,Description is required and cannot be empty.
9,TX-MIX-007,type,ERR_INVALID_TYPE,Type 'transfer' must be 'income' or 'expense'.
```
Because line 9 has issues, it is excluded from `clean-transactions.csv` and its `25000.00` amount is not included in any totals in `summary.json`.

---

## Exit codes

| Exit Code | Meaning | Output Artifacts |
|---|---|---|
| `0` | Clean validation: all rows passed; full reports generated. | Written |
| `1` | Row issues detected: one or more rows were invalid; diagnostics and valid row summaries generated. | Written |
| `2` | File, argument, header, malformed CSV quoting, or safety collision error: execution halted; no output artifacts generated. | Not written |

---

## Architecture and design decisions

- **Zero runtime dependencies**: Built exclusively on the Python 3.13 standard library (`argparse`, `csv`, `dataclasses`, `datetime`, `decimal`, `enum`, `json`, `pathlib`, `tempfile`, `shutil`). See [ADR 0001](docs/adr/0001-standard-library-runtime.md).
- **Exact decimal arithmetic**: Never uses `float` for money. Amounts and totals are parsed and aggregated using `decimal.Decimal` and serialized as two-decimal strings (`"0.00"`).
- **Whole-file duplicate rejection**: Duplicate transaction IDs cannot be safely resolved by accepting the first record. All instances sharing an ID are rejected. See [ADR 0002](docs/adr/0002-whole-file-duplicate-validation.md).
- **Staged output safety, collision refusal, and publication rollback**: Target reports are completely generated in an isolated temporary staging directory before publication. Pre-flight checks refuse to overwrite existing target files in `--output-dir`. If an operational failure occurs during publication, Credence triggers best-effort rollback of newly published files while preserving pre-existing unrelated files. Multi-file filesystem crash consistency across power loss, OS crashes, or SIGKILL is not guaranteed. See [ADR 0003](docs/adr/0003-safe-deterministic-staged-output.md).

---

## Running the test suite

Credence uses `pytest` for unit and integration testing:

```bash
pytest -v
```

The test suite covers:
- Exact header schema permutations, missing headers, duplicate headers, and empty files.
- UTF-8 BOM handling and CRLF/LF line ending compatibility.
- Physical source line number preservation across interleaved blank lines.
- Row width mismatches and error accumulation.
- Boundary conditions for decimal amounts, dates (including leap years), transaction types, and required text fields.
- Whole-file duplicate ID invalidation.
- Staged output generation, collision refusal (exit code `2`), publication rollback on handled operational errors, and preserving unrelated files.
- Deterministic repeated execution and byte-for-byte reconciliation against canonical fixtures.

---

## Explicit exclusions

Credence intentionally excludes:
- Excel (`.xlsx`), PDF, JSON, or SQL database ingestion.
- Modifying or repairing the user's source file in place.
- External banking APIs, payment gateways, or web scrapers.
- Multi-currency conversions, exchange rates, tax calculations, or double-entry ledgers.
- User accounts, authentication, graphical user interfaces, or cloud dependencies.
