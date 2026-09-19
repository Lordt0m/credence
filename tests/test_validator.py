import io
import pytest
from decimal import Decimal
from datetime import date

from credence.constants import (
    ERR_DUPLICATE_ID,
    ERR_INVALID_AMOUNT,
    ERR_INVALID_DATE,
    ERR_INVALID_TYPE,
    ERR_REQUIRED_FIELD,
    ERR_ROW_WIDTH_MISMATCH,
)
from credence.models import TransactionType
from credence.validator import (
    FileValidationError,
    read_source_rows,
    validate_cashbook,
    validate_header,
)


def test_validate_header_valid_canonical():
    header = ["transaction_id", "date", "type", "category", "description", "amount", "reference"]
    assert validate_header(header) == header


def test_validate_header_valid_permuted():
    header = ["amount", "description", "type", "date", "reference", "category", "transaction_id"]
    result = validate_header(header)
    assert set(result) == set(header)


@pytest.mark.parametrize(
    "invalid_header,err_snippet",
    [
        ([], "empty"),
        (["transaction_id", "date", "type", "category", "description", "amount"], "missing required columns"),
        (["transaction_id", "date", "type", "category", "description", "amount", "reference", "extra"], "unexpected columns"),
        (["transaction_id", "date", "type", "category", "description", "amount", "amount"], "duplicate columns"),
        (["Transaction_Id", "date", "type", "category", "description", "amount", "reference"], "missing required columns"),
        (["", "date", "type", "category", "description", "amount", "reference"], "empty column names"),
    ],
)
def test_validate_header_invalid(invalid_header, err_snippet):
    with pytest.raises(FileValidationError, match=err_snippet):
        validate_header(invalid_header)


def test_read_source_rows_preserves_physical_lines_and_ignores_blanks():
    csv_content = (
        "\n"  # line 1: blank
        "transaction_id,date,type,category,description,amount,reference\n"  # line 2: header
        "TX1,2026-01-01,income,Sales,Widget,100.00,REF1\n"  # line 3: data
        "\n"  # line 4: blank
        "   \n"  # line 5: blank with whitespace
        "TX2,2026-01-02,expense,Rent,Shop,500.00,REF2\n"  # line 6: data
    )
    stream = io.StringIO(csv_content)
    header, rows = read_source_rows(stream)

    assert len(rows) == 2
    assert rows[0].line_number == 3
    assert rows[0].raw_values["transaction_id"] == "TX1"
    assert rows[1].line_number == 6
    assert rows[1].raw_values["transaction_id"] == "TX2"


def test_read_source_rows_utf8_bom():
    csv_content = (
        "\ufefftransaction_id,date,type,category,description,amount,reference\n"
        "TX1,2026-01-01,income,Sales,Widget,100.00,REF1\n"
    )
    stream = io.StringIO(csv_content)
    header, rows = read_source_rows(stream)
    assert header[0] == "transaction_id"
    assert len(rows) == 1
    assert rows[0].line_number == 2


def test_row_width_mismatch():
    csv_content = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX1,2026-01-01,income,Sales,Too,Few\n"  # 6 cols
        "TX2,2026-01-02,expense,Rent,Shop,500.00,REF2\n"  # 7 cols (valid)
        "TX3,2026-01-03,income,Sales,Extra,Col,Too,Many\n"  # 8 cols
    )
    stream = io.StringIO(csv_content)
    header, rows = read_source_rows(stream)
    result, summary = validate_cashbook("test.csv", header, rows)

    assert result.processed_rows == 3
    assert result.valid_rows == 1
    assert result.invalid_rows == 2

    mismatch_issues = [i for i in result.issues if i.error_code == ERR_ROW_WIDTH_MISMATCH]
    assert len(mismatch_issues) == 2
    assert mismatch_issues[0].line_number == 2
    assert mismatch_issues[1].line_number == 4


def test_amount_validation_rules():
    valid_csv = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "T1,2026-01-01,income,Sales,Item 1,100,R1\n"
        "T2,2026-01-02,income,Sales,Item 2,100.5,R2\n"
        "T3,2026-01-03,income,Sales,Item 3,100.55,R3\n"
        "T4,2026-01-04,income,Sales,Item 4,0.05,R4\n"
    )
    header, rows = read_source_rows(io.StringIO(valid_csv))
    result, summary = validate_cashbook("test.csv", header, rows)
    assert result.valid_rows == 4
    assert result.invalid_rows == 0
    assert summary.total_income == Decimal("301.10")

    invalid_csv = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "T1,2026-01-01,income,Sales,Desc,0,\n"  # zero
        "T2,2026-01-02,income,Sales,Desc,0.00,\n"  # zero
        "T3,2026-01-03,income,Sales,Desc,-50.00,\n"  # negative
        "T4,2026-01-04,income,Sales,Desc,+50.00,\n"  # positive sign
        'T5,2026-01-05,income,Sales,Desc,"1,000.00",\n'  # comma
        "T6,2026-01-06,income,Sales,Desc,$50.00,\n"  # currency symbol
        "T7,2026-01-07,income,Sales,Desc,50.555,\n"  # 3 decimals
        "T8,2026-01-08,income,Sales,Desc,1e3,\n"  # scientific notation
        "T9,2026-01-09,income,Sales,Desc,abc,\n"  # non-numeric
        "T10,2026-01-10,income,Sales,Desc,,\n"  # empty
    )
    header, rows = read_source_rows(io.StringIO(invalid_csv))
    result, summary = validate_cashbook("test.csv", header, rows)
    assert result.valid_rows == 0
    assert result.invalid_rows == 10
    assert all(i.error_code == ERR_INVALID_AMOUNT for i in result.issues)


def test_date_validation_rules():
    invalid_dates_csv = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "T1,2026/01/01,income,Sales,Desc,100.00,\n"  # slash
        "T2,01-01-2026,income,Sales,Desc,100.00,\n"  # DD-MM-YYYY
        "T3,2026-1-1,income,Sales,Desc,100.00,\n"  # not padded
        "T4,2026-02-29,income,Sales,Desc,100.00,\n"  # non-leap year
        "T5,2026-13-01,income,Sales,Desc,100.00,\n"  # month 13
        "T6,2026-04-31,income,Sales,Desc,100.00,\n"  # april has 30 days
        "T7,,income,Sales,Desc,100.00,\n"  # empty date
    )
    header, rows = read_source_rows(io.StringIO(invalid_dates_csv))
    result, summary = validate_cashbook("test.csv", header, rows)
    assert result.valid_rows == 0
    assert result.invalid_rows == 7
    assert all(i.error_code == ERR_INVALID_DATE for i in result.issues)


def test_type_validation_rules():
    csv_content = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "T1,2026-01-01,INCOME,Sales,Item 1,100.00,\n"  # uppercase income
        "T2,2026-01-02,Expense,Supplies,Item 2,50.00,\n"  # mixed case expense
        "T3,2026-01-03,transfer,Bank,Transfer,10.00,\n"  # invalid type
        "T4,2026-01-04,,Other,Empty,10.00,\n"  # empty type
    )
    header, rows = read_source_rows(io.StringIO(csv_content))
    result, summary = validate_cashbook("test.csv", header, rows)
    assert result.valid_rows == 2
    assert result.invalid_rows == 2

    # Check normalization
    assert result.valid_transactions[0].type == TransactionType.INCOME
    assert result.valid_transactions[1].type == TransactionType.EXPENSE

    type_issues = [i for i in result.issues if i.field == "type"]
    assert len(type_issues) == 2
    assert all(i.error_code == ERR_INVALID_TYPE for i in type_issues)


def test_duplicate_transaction_id_invalidation():
    # When an ID is duplicated (case-insensitive), all rows sharing that ID are invalid!
    csv_content = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX100,2026-01-01,income,Sales,First instance,100.00,\n"
        "TX200,2026-01-02,expense,Office,Unique record,50.00,\n"
        "tx100,2026-01-03,income,Sales,Second instance (lowercase),150.00,\n"
        "TX300,2026-01-04,expense,Rent,Unique record 2,200.00,\n"
        "Tx100,2026-01-05,expense,Supplies,Third instance (mixed case),25.00,\n"
    )
    header, rows = read_source_rows(io.StringIO(csv_content))
    result, summary = validate_cashbook("test.csv", header, rows)

    # Only TX200 and TX300 should be valid
    assert result.valid_rows == 2
    assert result.invalid_rows == 3
    valid_ids = [t.transaction_id for t in result.valid_transactions]
    assert valid_ids == ["TX200", "TX300"]

    dup_issues = [i for i in result.issues if i.error_code == ERR_DUPLICATE_ID]
    assert len(dup_issues) == 3
    dup_lines = [i.line_number for i in dup_issues]
    assert dup_lines == [2, 4, 6]


def test_error_accumulation_on_single_row():
    # A single row with multiple errors: bad date, bad type, bad amount, missing category and description
    csv_content = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "TX99,bad-date,invalid-type,,,-100,\n"
    )
    header, rows = read_source_rows(io.StringIO(csv_content))
    result, summary = validate_cashbook("test.csv", header, rows)

    assert result.valid_rows == 0
    assert result.invalid_rows == 1
    fields = [i.field for i in result.issues]
    assert "date" in fields
    assert "type" in fields
    assert "category" in fields
    assert "description" in fields
    assert "amount" in fields
    assert len(result.issues) == 5


def test_required_text_fields_and_optional_reference():
    csv_content = (
        "transaction_id,date,type,category,description,amount,reference\n"
        "T1,2026-01-01,income,   ,Valid description,100.00,\n"  # whitespace-only category
        "T2,2026-01-02,income,Sales,   ,100.00,\n"  # whitespace-only description
        "  ,2026-01-03,income,Sales,Valid description,100.00,\n"  # whitespace-only transaction_id
        "T4,2026-01-04,income,Sales,Valid description,100.00,   \n"  # empty reference (valid)
    )
    header, rows = read_source_rows(io.StringIO(csv_content))
    result, summary = validate_cashbook("test.csv", header, rows)

    assert result.processed_rows == 4
    assert result.valid_rows == 1
    assert result.invalid_rows == 3

    assert result.valid_transactions[0].transaction_id == "T4"
    assert result.valid_transactions[0].reference == ""

    req_issues = [i for i in result.issues if i.error_code == ERR_REQUIRED_FIELD]
    assert len(req_issues) == 3
    issue_fields = {i.field for i in req_issues}
    assert issue_fields == {"category", "description", "transaction_id"}
