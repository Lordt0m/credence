from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True)
class SourceRow:
    line_number: int
    raw_values: dict[str, str]


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    date: date
    type: TransactionType
    category: str
    description: str
    amount: Decimal
    reference: str = ""


@dataclass(frozen=True)
class ValidationIssue:
    line_number: int
    transaction_id: str
    field: str
    error_code: str
    message: str


@dataclass
class ValidationResult:
    valid_transactions: list[Transaction] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    processed_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0

    @property
    def total_errors(self) -> int:
        return len(self.issues)


@dataclass(frozen=True)
class FinancialSummary:
    source_file: str
    processed_rows: int
    valid_rows: int
    invalid_rows: int
    error_count: int
    earliest_date: Optional[str]
    latest_date: Optional[str]
    total_income: Decimal
    total_expenses: Decimal
    net_cash_movement: Decimal
    income_by_category: dict[str, Decimal]
    expenses_by_category: dict[str, Decimal]
    currency: str = "NGN"

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "currency": self.currency,
            "processed_rows": self.processed_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
            "error_count": self.error_count,
            "earliest_date": self.earliest_date,
            "latest_date": self.latest_date,
            "total_income": f"{self.total_income:.2f}",
            "total_expenses": f"{self.total_expenses:.2f}",
            "net_cash_movement": f"{self.net_cash_movement:.2f}",
            "income_by_category": {
                k: f"{v:.2f}" for k, v in sorted(self.income_by_category.items(), key=lambda x: x[0].lower())
            },
            "expenses_by_category": {
                k: f"{v:.2f}" for k, v in sorted(self.expenses_by_category.items(), key=lambda x: x[0].lower())
            },
        }
