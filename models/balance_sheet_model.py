from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Generator

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
import pandas as pd


CATEGORIES = ("Income", "Expenses", "Assets", "Liabilities")
DEFAULT_DB_PATH = Path.home() / ".personal_finance_dashboard" / "balance_sheet.sqlite3"
LEGACY_COLUMNS = {
    "Income": (1, 2, 3),
    "Expenses": (5, 6, 7),
    "Assets": (9, 10, 11),
    "Liabilities": (13, 14, 15),
}
BALANCE_SHEET_SECTIONS = (
    ("INCOME", "Income"),
    ("EXPENSES", "Expenses"),
    ("ASSET", "Assets"),
    ("LIABILITY", "Liabilities"),
)
BALANCE_SHEET_FIELDS = ("DATE", "AMOUNT", "TYPE")


@dataclass(frozen=True)
class Transaction:
    id: int
    category: str
    transaction_date: str
    amount: float
    entry_type: str


class BalanceSheetModel:
    """Owns SQLite persistence and balance-sheet exports."""

    def __init__(self, database_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.database_path = Path(database_path).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL
                        CHECK (category IN ('Income', 'Expenses', 'Assets', 'Liabilities')),
                    transaction_date TEXT NOT NULL,
                    amount REAL NOT NULL CHECK (amount != 0),
                    entry_type TEXT NOT NULL CHECK (length(trim(entry_type)) > 0)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_date "
                "ON transactions (transaction_date, id)"
            )

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add_transaction(
        self,
        category: str,
        transaction_date: str,
        amount: float,
        entry_type: str,
    ) -> int:
        if category not in CATEGORIES:
            raise ValueError(f"Unknown balance-sheet category: {category}")
        try:
            parsed_date = date.fromisoformat(transaction_date)
        except ValueError as error:
            raise ValueError("Date must use the YYYY-MM-DD format.") from error
        if not math.isfinite(amount) or amount == 0:
            raise ValueError("Amount must be a non-zero, finite number.")
        if not entry_type.strip():
            raise ValueError("Type cannot be empty.")

        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transactions
                    (category, transaction_date, amount, entry_type)
                VALUES (?, ?, ?, ?)
                """,
                (category, parsed_date.isoformat(), amount, entry_type.strip()),
            )
            return int(cursor.lastrowid)

    def get_transactions(self) -> list[Transaction]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, category, transaction_date, amount, entry_type
                FROM transactions
                ORDER BY transaction_date DESC, id DESC
                """
            ).fetchall()
        return [
            Transaction(
                id=int(row["id"]),
                category=str(row["category"]),
                transaction_date=str(row["transaction_date"]),
                amount=float(row["amount"]),
                entry_type=str(row["entry_type"]),
            )
            for row in rows
        ]

    def get_transactions_dataframe(self) -> pd.DataFrame:
        with self._connection() as connection:
            return pd.read_sql_query(
                """
                SELECT id, category, transaction_date, amount, entry_type
                FROM transactions
                ORDER BY transaction_date DESC, id DESC
                """,
                connection,
            )

    def get_balance_sheet_dataframe(self) -> pd.DataFrame:
        """Return transactions in the four-section layout of the legacy workbook."""
        transactions = self.get_transactions()
        sections = [
            [
                transaction
                for transaction in transactions
                if transaction.category == category
            ]
            for _, category in BALANCE_SHEET_SECTIONS
        ]
        row_count = max((len(entries) for entries in sections), default=0)

        columns: list[str] = []
        column_data: list[pd.Series] = []
        for section_index, entries in enumerate(sections):
            columns.extend(BALANCE_SHEET_FIELDS)
            values = (
                [
                    date.fromisoformat(entry.transaction_date).strftime("%m/%d/%y")
                    for entry in entries
                ],
                [entry.amount for entry in entries],
                [entry.entry_type for entry in entries],
            )
            for field, field_values in zip(BALANCE_SHEET_FIELDS, values):
                padded_values = field_values + [None] * (row_count - len(entries))
                dtype = "float64" if field == "AMOUNT" else "object"
                column_data.append(pd.Series(padded_values, dtype=dtype))

            if section_index < len(sections) - 1:
                columns.append("")
                column_data.append(pd.Series([""] * row_count, dtype="object"))

        dataframe = pd.concat(column_data, axis=1)
        dataframe.columns = columns
        return dataframe

    def import_legacy_workbook(self, workbook_path: Path | str) -> int:
        """Import the old four-section workbook once, if the database is empty."""
        path = Path(workbook_path)
        if not path.is_file():
            return 0

        with self._connection() as connection:
            if connection.execute(
                "SELECT 1 FROM transactions LIMIT 1"
            ).fetchone():
                return 0

            workbook = load_workbook(path, read_only=True, data_only=True)
            imported = 0
            try:
                sheet = workbook.active
                for row in sheet.iter_rows(min_row=4, values_only=True):
                    for category, (date_column, amount_column, type_column) in (
                        LEGACY_COLUMNS.items()
                    ):
                        raw_date = row[date_column] if len(row) > date_column else None
                        raw_amount = (
                            row[amount_column] if len(row) > amount_column else None
                        )
                        raw_type = row[type_column] if len(row) > type_column else None
                        if raw_date is None and raw_amount is None and raw_type is None:
                            continue
                        if raw_date is None or raw_amount is None or raw_type is None:
                            continue

                        transaction_date = self._normalize_legacy_date(raw_date)
                        amount = float(raw_amount)
                        if not math.isfinite(amount) or amount == 0:
                            raise ValueError(
                                f"Invalid amount in legacy workbook: {raw_amount!r}"
                            )
                        connection.execute(
                            """
                            INSERT INTO transactions
                                (category, transaction_date, amount, entry_type)
                            VALUES (?, ?, ?, ?)
                            """,
                            (category, transaction_date, amount, str(raw_type).strip()),
                        )
                        imported += 1
            finally:
                workbook.close()
        return imported

    @staticmethod
    def _normalize_legacy_date(value: object) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        for date_format in ("%m/%d/%y", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, date_format).date().isoformat()
            except ValueError:
                continue
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError as error:
            raise ValueError(f"Unsupported date in legacy workbook: {value!r}") from error

    def export_balance_sheet(self, destination: Path | str) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Balance Sheet"
        sheet.append(("Category", "Date", "Amount", "Type"))
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F6AA5")

        for transaction in reversed(self.get_transactions()):
            sheet.append(
                (
                    transaction.category,
                    date.fromisoformat(transaction.transaction_date),
                    transaction.amount,
                    transaction.entry_type,
                )
            )
            sheet.cell(row=sheet.max_row, column=3).number_format = "#,##0.00"

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column, width in {"A": 18, "B": 16, "C": 18, "D": 24}.items():
            sheet.column_dimensions[column].width = width
        workbook.save(path)
        return path
