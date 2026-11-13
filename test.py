import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from matplotlib.figure import Figure
from openpyxl import Workbook, load_workbook

from models.balance_sheet_model import BalanceSheetModel
from views.dashboard_export import export_dashboard_image


class BalanceSheetModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database_path = self.directory / "nested" / "finance.sqlite3"
        self.model = BalanceSheetModel(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_transactions_persist_when_model_is_reopened(self) -> None:
        self.model.add_transaction("Income", "2026-11-13", 1250, "Salary")

        reopened_model = BalanceSheetModel(self.database_path)

        self.assertEqual(len(reopened_model.get_transactions()), 1)
        self.assertEqual(reopened_model.get_transactions()[0].amount, 1250)
        dataframe = reopened_model.get_transactions_dataframe()
        self.assertEqual(dataframe.loc[0, "category"], "Income")
        self.assertEqual(dataframe.loc[0, "amount"], 1250)

    def test_balance_sheet_dataframe_matches_workbook_sections(self) -> None:
        self.assertEqual(self.model.get_balance_sheet_dataframe().shape, (0, 15))

        self.model.add_transaction("Income", "2026-11-13", 1250, "Salary")
        self.model.add_transaction("Income", "2026-11-10", 100, "Gift")
        self.model.add_transaction("Expenses", "2026-11-12", 55.5, "Rent")
        self.model.add_transaction("Assets", "2026-11-11", -100, "Stocks")

        dataframe = self.model.get_balance_sheet_dataframe()

        self.assertEqual(
            dataframe.columns.tolist(),
            [
                "DATE", "AMOUNT", "TYPE", "",
                "DATE", "AMOUNT", "TYPE", "",
                "DATE", "AMOUNT", "TYPE", "",
                "DATE", "AMOUNT", "TYPE",
            ],
        )
        self.assertEqual(dataframe.shape, (2, 15))
        self.assertEqual(dataframe.iloc[0, 0], "11/13/26")
        self.assertEqual(dataframe.iloc[0, 1], 1250)
        self.assertEqual(dataframe.iloc[0, 4], "11/12/26")
        self.assertEqual(dataframe.iloc[0, 5], 55.5)
        self.assertEqual(dataframe.iloc[0, 9], -100)
        self.assertEqual(dataframe.iloc[1, 0], "11/10/26")
        self.assertIsNone(dataframe.iloc[1, 4])

    def test_rejects_zero_amount_and_unknown_category(self) -> None:
        with self.assertRaises(ValueError):
            self.model.add_transaction("Income", "2026-11-13", 0, "Salary")
        with self.assertRaises(ValueError):
            self.model.add_transaction("Other", "2026-11-13", 10, "Other")

    def test_imports_legacy_workbook_once_when_database_is_empty(self) -> None:
        workbook_path = self.directory / "legacy.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.cell(row=4, column=2, value=date(2026, 11, 13))
        sheet.cell(row=4, column=3, value=1200)
        sheet.cell(row=4, column=4, value="Salary")
        workbook.save(workbook_path)

        self.assertEqual(self.model.import_legacy_workbook(workbook_path), 1)
        self.assertEqual(self.model.import_legacy_workbook(workbook_path), 0)
        transaction = self.model.get_transactions()[0]
        self.assertEqual(transaction.category, "Income")
        self.assertEqual(transaction.transaction_date, "2026-11-13")
        self.assertEqual(transaction.amount, 1200)

    def test_exports_balance_sheet_as_excel(self) -> None:
        self.model.add_transaction("Expenses", "2026-11-13", 55.5, "Rent")
        destination = self.directory / "exports" / "Balance Sheet.xlsx"

        result = self.model.export_balance_sheet(destination)

        self.assertEqual(result, destination)
        workbook = load_workbook(destination, read_only=True, data_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        workbook.close()
        self.assertEqual(rows[0], ("Category", "Date", "Amount", "Type"))
        self.assertEqual(
            rows[1], ("Expenses", datetime(2026, 11, 13), 55.5, "Rent")
        )

    def test_exports_balance_sheet_and_charts_as_one_png(self) -> None:
        self.model.add_transaction("Income", "2026-11-13", 1250, "Salary")
        charts = {}
        for chart_name in ("Monthly Expenses.png", "Balance Sheet Totals.png"):
            figure = Figure(figsize=(2, 1))
            figure.add_subplot(111).plot((0, 1), (0, 1))
            charts[chart_name] = figure
        destination = self.directory / "exports" / "Dashboard.png"

        result = export_dashboard_image(
            destination,
            self.model.get_balance_sheet_dataframe(),
            charts,
        )

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(list(destination.parent.iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
