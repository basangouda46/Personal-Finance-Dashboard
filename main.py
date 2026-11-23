#Author: Basangouda Patil
from __future__ import annotations

from datetime import date
from pathlib import Path

from controllers.dashboard_controller import DashboardController
from models.balance_sheet_model import BalanceSheetModel
from views.dashboard_view import DashboardView


def _find_legacy_workbook() -> Path | None:
    project_directory = Path(__file__).resolve().parent
    configuration_path = project_directory / "filepath.txt"
    if configuration_path.is_file():
        lines = configuration_path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 1 and lines[0].strip().lower() == "yes":
            legacy_directory = Path(lines[1].strip()).expanduser()
            configured_workbook = (
                legacy_directory
                / "Balance Sheet"
                / f"Balance Sheet - {date.today().year}.xlsx"
            )
            if configured_workbook.is_file():
                return configured_workbook

    bundled_workbook = (
        project_directory
        / "Balance Sheet"
        / f"Balance Sheet - {date.today().year}.xlsx"
    )
    return bundled_workbook if bundled_workbook.is_file() else None


def main() -> None:
    model = BalanceSheetModel()
    legacy_workbook = _find_legacy_workbook()
    if legacy_workbook is not None:
        model.import_legacy_workbook(legacy_workbook)

    view = DashboardView()
    DashboardController(model, view)
    view.mainloop()


if __name__ == "__main__":
    main()
