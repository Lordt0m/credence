import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TextIO

from credence.constants import (
    CANONICAL_COLUMNS,
    ERR_DUPLICATE_ID,
    ERR_INVALID_AMOUNT,
    ERR_INVALID_DATE,
    ERR_INVALID_TYPE,
    ERR_REQUIRED_FIELD,
    ERR_ROW_WIDTH_MISMATCH,
)
from credence.models import (
    FinancialSummary,
    SourceRow,
    Transaction,
    TransactionType,
    ValidationIssue,
    ValidationResult,
)


class FileValidationError(Exception):
    """File-level or operational error preventing normal reporting (Exit code 2)."""
    pass


DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AMOUNT_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")


def validate_header(header: list[str]) -> list[str]:
    """
    Validate the CSV header line.
    Must contain exactly the 7 canonical column names in lowercase ASCII.
    Can be in any column order. Whitespace around column names is rejected.
    """
    if not header:
        raise FileValidationError("CSV file is empty or has no header.")

    # Check for empty column names
    if any(not col.strip() for col in header):
        raise FileValidationError("CSV header contains empty column names.")

    # Check for duplicates
    if len(header) != len(set(header)):
        duplicates = [col for col in header if header.count(col) > 1]
        raise FileValidationError(f"CSV header contains duplicate columns: {', '.join(set(duplicates))}")

    header_set = set(header)
    canonical_set = set(CANONICAL_COLUMNS)

    missing = canonical_set - header_set
    if missing:
        raise FileValidationError(f"CSV header is missing required columns: {', '.join(sorted(missing))}")

    extra = header_set - canonical_set
    if extra:
        raise FileValidationError(f"CSV header contains unexpected columns: {', '.join(sorted(extra))}")

    return list(header)


def read_source_rows(stream: TextIO) -> tuple[list[str], list[SourceRow]]:
    """
    Read header and source data rows while retaining 1-indexed physical line numbers.
    Fully blank lines are ignored and omitted from record counting.
    """
    raw_lines = stream.readlines()
    if not raw_lines:
        raise FileValidationError("CSV file is empty.")

    # Check and strip UTF-8 BOM if present on the first line
    if raw_lines and raw_lines[0].startswith("\ufeff"):
        raw_lines[0] = raw_lines[0].lstrip("\ufeff")

    header: list[str] = []
    header_line_index = -1

    # Find the header row (first non-blank line)
    for idx, line in enumerate(raw_lines, start=1):
        if line.strip():
            header_line_index = idx
            try:
                parsed_header = list(csv.reader([line], strict=True))
            except csv.Error as e:
                raise FileValidationError(f"Malformed CSV: {e}") from e
            if not parsed_header or not parsed_header[0]:
                raise FileValidationError("Unable to parse CSV header.")
            header = validate_header(parsed_header[0])
            break

    if header_line_index == -1:
        raise FileValidationError("CSV file contains only blank lines.")

    # Parse remaining rows
    source_rows: list[SourceRow] = []
    for line_number in range(header_line_index + 1, len(raw_lines) + 1):
        line = raw_lines[line_number - 1]
        if not line.strip():
            # Fully blank row ignored
            continue

        try:
            parsed = list(csv.reader([line], strict=True))
        except csv.Error as e:
            raise FileValidationError(f"Malformed CSV: {e}") from e
        if not parsed:
            continue
        row_values = parsed[0]

        if len(row_values) != len(header):
            # Record mismatch with dummy raw_values to preserve physical line
            source_rows.append(
                SourceRow(
                    line_number=line_number,
                    raw_values={"__raw_list__": row_values},
                )
            )
        else:
            raw_dict = {header[i]: row_values[i] for i in range(len(header))}
            source_rows.append(
                SourceRow(
                    line_number=line_number,
                    raw_values=raw_dict,
                )
            )

    return header, source_rows


def validate_cashbook(
    source_file_name: str,
    header: list[str],
    source_rows: list[SourceRow],
) -> tuple[ValidationResult, FinancialSummary]:
    """
    Execute row-level and whole-file validation passes and compute the financial summary.
    """
    result = ValidationResult(processed_rows=len(source_rows))
    expected_col_count = len(header)

    # Temporary storage for candidate valid rows
    candidate_transactions: list[tuple[SourceRow, Transaction]] = []
    rows_with_errors: set[int] = set()

    # Index for whole-file duplicate checking: normalized_id -> list of (line_number, raw_id)
    id_occurrences: dict[str, list[tuple[int, str]]] = {}

    for row in source_rows:
        line_num = row.line_number
        raw = row.raw_values

        # Check for column width mismatch
        if "__raw_list__" in raw:
            actual_count = len(raw["__raw_list__"])
            result.issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id="",
                    field="row",
                    error_code=ERR_ROW_WIDTH_MISMATCH,
                    message=f"Row has {actual_count} columns; expected {expected_col_count}.",
                )
            )
            rows_with_errors.add(line_num)
            continue

        row_issues: list[ValidationIssue] = []

        # 1. transaction_id
        raw_tx_id = raw.get("transaction_id", "").strip()
        if not raw_tx_id:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id="",
                    field="transaction_id",
                    error_code=ERR_REQUIRED_FIELD,
                    message="Transaction ID is required.",
                )
            )
        else:
            norm_id = raw_tx_id.lower()
            id_occurrences.setdefault(norm_id, []).append((line_num, raw_tx_id))

        # 2. date
        raw_date = raw.get("date", "").strip()
        parsed_date: date | None = None
        if not raw_date:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="date",
                    error_code=ERR_INVALID_DATE,
                    message="Date is required.",
                )
            )
        elif not DATE_REGEX.match(raw_date):
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="date",
                    error_code=ERR_INVALID_DATE,
                    message=f"Date '{raw_date}' must be in YYYY-MM-DD format.",
                )
            )
        else:
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError:
                row_issues.append(
                    ValidationIssue(
                        line_number=line_num,
                        transaction_id=raw_tx_id,
                        field="date",
                        error_code=ERR_INVALID_DATE,
                        message=f"Date '{raw_date}' is not a valid calendar date.",
                    )
                )

        # 3. type
        raw_type = raw.get("type", "").strip().lower()
        parsed_type: TransactionType | None = None
        if not raw_type:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="type",
                    error_code=ERR_INVALID_TYPE,
                    message="Type is required (income or expense).",
                )
            )
        elif raw_type in ("income", "expense"):
            parsed_type = TransactionType(raw_type)
        else:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="type",
                    error_code=ERR_INVALID_TYPE,
                    message=f"Type '{raw.get('type', '')}' must be 'income' or 'expense'.",
                )
            )

        # 4. category
        raw_cat = raw.get("category", "").strip()
        if not raw_cat:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="category",
                    error_code=ERR_REQUIRED_FIELD,
                    message="Category is required and cannot be empty.",
                )
            )

        # 5. description
        raw_desc = raw.get("description", "").strip()
        if not raw_desc:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="description",
                    error_code=ERR_REQUIRED_FIELD,
                    message="Description is required and cannot be empty.",
                )
            )

        # 6. amount
        raw_amount = raw.get("amount", "").strip()
        parsed_amount: Decimal | None = None
        if not raw_amount:
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="amount",
                    error_code=ERR_INVALID_AMOUNT,
                    message="Amount is required.",
                )
            )
        elif not AMOUNT_REGEX.match(raw_amount):
            row_issues.append(
                ValidationIssue(
                    line_number=line_num,
                    transaction_id=raw_tx_id,
                    field="amount",
                    error_code=ERR_INVALID_AMOUNT,
                    message=(
                        f"Amount '{raw_amount}' must be a positive decimal with at most 2 decimal places "
                        "and no currency signs, commas, or symbols."
                    ),
                )
            )
        else:
            try:
                dec_val = Decimal(raw_amount)
                if dec_val <= 0:
                    row_issues.append(
                        ValidationIssue(
                            line_number=line_num,
                            transaction_id=raw_tx_id,
                            field="amount",
                            error_code=ERR_INVALID_AMOUNT,
                            message=f"Amount '{raw_amount}' must be strictly positive (> 0).",
                        )
                    )
                else:
                    parsed_amount = dec_val
            except InvalidOperation:
                row_issues.append(
                    ValidationIssue(
                        line_number=line_num,
                        transaction_id=raw_tx_id,
                        field="amount",
                        error_code=ERR_INVALID_AMOUNT,
                        message=f"Amount '{raw_amount}' is not a valid decimal.",
                    )
                )

        # 7. reference
        raw_ref = raw.get("reference", "").strip()

        if row_issues:
            result.issues.extend(row_issues)
            rows_with_errors.add(line_num)
        else:
            # Candidate valid transaction
            assert parsed_date is not None
            assert parsed_type is not None
            assert parsed_amount is not None
            candidate = Transaction(
                transaction_id=raw_tx_id,
                date=parsed_date,
                type=parsed_type,
                category=raw_cat,
                description=raw_desc,
                amount=parsed_amount,
                reference=raw_ref,
            )
            candidate_transactions.append((row, candidate))

    # Whole-file duplicate pass: check all id_occurrences
    duplicate_lines: set[int] = set()
    for norm_id, occurrences in id_occurrences.items():
        if len(occurrences) > 1:
            for line_num, original_id in occurrences:
                duplicate_lines.add(line_num)
                rows_with_errors.add(line_num)
                result.issues.append(
                    ValidationIssue(
                        line_number=line_num,
                        transaction_id=original_id,
                        field="transaction_id",
                        error_code=ERR_DUPLICATE_ID,
                        message=f"Duplicate transaction ID '{original_id}' (case-insensitive) appears {len(occurrences)} times.",
                    )
                )

    # Filter candidate transactions to retain only those without any row issues or duplicate issues
    for src_row, candidate in candidate_transactions:
        if src_row.line_number not in duplicate_lines and src_row.line_number not in rows_with_errors:
            result.valid_transactions.append(candidate)

    # Sort all issues deterministically: line_number ascending, then field name
    result.issues.sort(key=lambda issue: (issue.line_number, issue.field, issue.error_code))

    result.valid_rows = len(result.valid_transactions)
    result.invalid_rows = len(rows_with_errors)

    # Calculate financial summary
    summary = calculate_summary(source_file_name, result)
    return result, summary


def calculate_summary(source_file_name: str, result: ValidationResult) -> FinancialSummary:
    """Compute financial summary strictly from valid transactions."""
    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")
    income_by_cat: dict[str, Decimal] = {}
    expenses_by_cat: dict[str, Decimal] = {}
    earliest: str | None = None
    latest: str | None = None

    if result.valid_transactions:
        sorted_by_date = sorted(result.valid_transactions, key=lambda t: t.date)
        earliest = sorted_by_date[0].date.isoformat()
        latest = sorted_by_date[-1].date.isoformat()

        for tx in result.valid_transactions:
            if tx.type == TransactionType.INCOME:
                total_income += tx.amount
                income_by_cat[tx.category] = income_by_cat.get(tx.category, Decimal("0.00")) + tx.amount
            elif tx.type == TransactionType.EXPENSE:
                total_expenses += tx.amount
                expenses_by_cat[tx.category] = expenses_by_cat.get(tx.category, Decimal("0.00")) + tx.amount

    net_movement = total_income - total_expenses

    return FinancialSummary(
        source_file=source_file_name,
        currency="NGN",
        processed_rows=result.processed_rows,
        valid_rows=result.valid_rows,
        invalid_rows=result.invalid_rows,
        error_count=result.total_errors,
        earliest_date=earliest,
        latest_date=latest,
        total_income=total_income,
        total_expenses=total_expenses,
        net_cash_movement=net_movement,
        income_by_category=income_by_cat,
        expenses_by_category=expenses_by_cat,
    )
