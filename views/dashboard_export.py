from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.image import imread
import pandas as pd

from models.balance_sheet_model import BALANCE_SHEET_FIELDS, BALANCE_SHEET_SECTIONS


CHART_FILENAMES = ("Monthly Expenses.png", "Balance Sheet Totals.png")
SECTION_COLOR = "#90EE90"
FIELD_COLOR = "#FFFF00"


def export_dashboard_image(
    destination: Path,
    balance_sheet: pd.DataFrame,
    charts: Mapping[str, Figure],
) -> Path:
    missing_charts = [name for name in CHART_FILENAMES if name not in charts]
    if missing_charts:
        raise ValueError("Dashboard charts are not ready to export.")

    column_widths: list[float] = []
    section_row: list[str] = []
    field_row: list[str] = []
    for section_index, (heading, _) in enumerate(BALANCE_SHEET_SECTIONS):
        column_widths.extend((95, 100, 135))
        section_row.extend(("", "", ""))
        field_row.extend(BALANCE_SHEET_FIELDS)
        if section_index < len(BALANCE_SHEET_SECTIONS) - 1:
            column_widths.append(20)
            section_row.append("")
            field_row.append("")

    total_column_width = sum(column_widths)
    column_widths = [width / total_column_width for width in column_widths]
    amount_columns = {
        section_index * 4 + 1
        for section_index in range(len(BALANCE_SHEET_SECTIONS))
    }
    spacer_columns = {
        section_index * 4 + len(BALANCE_SHEET_FIELDS)
        for section_index in range(len(BALANCE_SHEET_SECTIONS) - 1)
    }

    data_rows = []
    for row in balance_sheet.itertuples(index=False, name=None):
        formatted_row = []
        for column_index, value in enumerate(row):
            if pd.isna(value):
                formatted_row.append("")
            elif column_index in amount_columns:
                formatted_row.append(f"{float(value):,.2f}")
            else:
                formatted_row.append(str(value))
        data_rows.append(formatted_row)

    cell_rows = [section_row, field_row, *data_rows]
    table_height = max(2.2, 0.22 * len(cell_rows))
    chart_height = 3.4
    figure = Figure(
        figsize=(16, table_height + chart_height + 0.8),
        facecolor="white",
    )
    grid = figure.add_gridspec(
        2,
        2,
        height_ratios=(table_height, chart_height),
        left=0.035,
        right=0.965,
        top=0.95,
        bottom=0.04,
        wspace=0.1,
        hspace=0.24,
    )
    figure.suptitle("Balance Sheet & Graphs", fontsize=16, fontweight="bold")

    table_axes = figure.add_subplot(grid[0, :])
    table_axes.set_axis_off()
    table = table_axes.table(
        cellText=cell_rows,
        colWidths=column_widths,
        cellLoc="center",
        bbox=(0, 0, 1, 1),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    for (row_index, column_index), cell in table.get_celld().items():
        cell.set_edgecolor("#B7B7B7")
        cell.set_linewidth(0.5)
        if column_index in spacer_columns:
            cell.set_facecolor("white")
        elif row_index == 0:
            cell.set_facecolor(SECTION_COLOR)
            cell.get_text().set_fontweight("bold")
        elif row_index == 1:
            cell.set_facecolor(FIELD_COLOR)
            cell.get_text().set_fontweight("bold")
        elif column_index in amount_columns:
            cell.get_text().set_ha("right")

    for section_index, (heading, _) in enumerate(BALANCE_SHEET_SECTIONS):
        first_column = section_index * 4
        left = sum(column_widths[:first_column])
        group_width = sum(column_widths[first_column : first_column + 3])
        table_axes.text(
            left + group_width / 2,
            1 - 0.5 / len(cell_rows),
            heading,
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            transform=table_axes.transAxes,
        )

    for chart_index, filename in enumerate(CHART_FILENAMES):
        chart_axes = figure.add_subplot(grid[1, chart_index])
        with BytesIO() as image_buffer:
            charts[filename].savefig(
                image_buffer, format="png", dpi=180, bbox_inches="tight"
            )
            image_buffer.seek(0)
            chart_axes.imshow(imread(image_buffer))
        chart_axes.set_axis_off()

    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, format="png", dpi=180, bbox_inches="tight")
    return destination
