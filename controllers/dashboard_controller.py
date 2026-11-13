from __future__ import annotations

import math
import sqlite3
from datetime import date
from pathlib import Path

from models.balance_sheet_model import BalanceSheetModel
from views.dashboard_view import DashboardView


class DashboardController:
    """Connects dashboard actions to the model and refreshes the view."""

    def __init__(self, model: BalanceSheetModel, view: DashboardView) -> None:
        self.model = model
        self.view = view
        self.view.set_handlers(self.add_transaction, self.export_dashboard)
        self.refresh()

    def refresh(self) -> None:
        transactions = self.model.get_transactions()
        self.view.update_dashboard(transactions)
        self.view.update_balance_sheet(self.model.get_balance_sheet_dataframe())

    def add_transaction(
        self, category: str, amount_text: str, entry_type: str, is_sale: bool
    ) -> None:
        try:
            amount = float(amount_text)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError("Enter an amount greater than zero.")
            if is_sale:
                amount = -amount
            self.model.add_transaction(
                category=category,
                transaction_date=date.today().isoformat(),
                amount=amount,
                entry_type=entry_type,
            )
        except (ValueError, sqlite3.Error) as error:
            self.view.show_error("Could not save transaction", str(error))
            return

        self.view.clear_amount(category)
        self.refresh()

    def export_dashboard(self) -> None:
        selected_directory = self.view.choose_export_directory()
        if not selected_directory:
            return

        destination = Path(selected_directory)
        try:
            image_path = self.view.export_dashboard_image(
                destination / "Balance Sheet & Graphs.png",
                self.model.get_balance_sheet_dataframe(),
            )
        except (OSError, ValueError, sqlite3.Error) as error:
            self.view.show_error("Could not export dashboard", str(error))
            return

        self.view.show_info(
            "Export complete",
            f"Saved:\n{image_path}",
        )
