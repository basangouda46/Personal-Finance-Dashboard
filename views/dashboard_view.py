from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from tkinter import Canvas, Frame, filedialog, messagebox
from typing import Callable, Sequence

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from pandastable import Table
import pandas as pd

from models.balance_sheet_model import (
    BALANCE_SHEET_SECTIONS,
    Transaction,
)
from views.dashboard_export import export_dashboard_image as create_dashboard_image


FORM_TYPES = {
    "Income": ("Salary", "Loan", "Assets", "Splitwise", "Tax Rebate", "Gift"),
    "Expenses": ("Rent", "Credit Card", "Splitwise"),
    "Assets": ("Stocks", "Gold", "Land", "Savings"),
    "Liabilities": ("Student Loan", "Car Loan", "Home Loan"),
}
ADD_BUTTON_LABELS = {
    "Income": "Add Income",
    "Expenses": "Add Expense",
    "Assets": "Add Asset",
    "Liabilities": "Add Liability",
}
MAX_BALANCE_SHEET_ROWS = 50


class DashboardView(ctk.CTk):
    """Tkinter widgets for the dashboard and balance-sheet tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Personal Finance Dashboard")
        self.geometry("1500x900")
        self.minsize(1100, 700)

        self._add_handler: Callable[[str, str, str, bool], None] | None = None
        self._export_handler: Callable[[], None] | None = None
        self._amount_entries: dict[str, ctk.CTkEntry] = {}
        self._chart_canvases: list[FigureCanvasTkAgg] = []
        self._figures: dict[str, Figure] = {}

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=16)
        self.dashboard_tab = self.tabs.add("Dashboard")
        self.balance_sheet_tab = self.tabs.add("Balance Sheet")
        self._build_dashboard()
        self._build_balance_sheet()

    def set_handlers(
        self,
        add_handler: Callable[[str, str, str, bool], None],
        export_handler: Callable[[], None],
    ) -> None:
        self._add_handler = add_handler
        self._export_handler = export_handler

    def _build_dashboard(self) -> None:
        self.dashboard_tab.grid_columnconfigure(0, weight=1, minsize=360)
        self.dashboard_tab.grid_columnconfigure(1, weight=2, minsize=600)
        self.dashboard_tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.dashboard_tab, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 12))
        ctk.CTkLabel(
            header, text="Transactions", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left")
        self.export_button = ctk.CTkButton(
            header,
            text="Download Balance Sheet & Graphs",
            command=self._export,
        )
        self.export_button.pack(side="right")

        forms = ctk.CTkFrame(self.dashboard_tab)
        forms.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        for index in range(2):
            forms.grid_columnconfigure(index, weight=1, uniform="form-columns")
            forms.grid_rowconfigure(index, weight=1, uniform="form-rows")
        for index, (category, choices) in enumerate(FORM_TYPES.items()):
            self._build_form(
                forms,
                category,
                choices,
                row=index // 2,
                column=index % 2,
            )

        charts = ctk.CTkFrame(self.dashboard_tab, fg_color="transparent")
        charts.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        charts.grid_columnconfigure(0, weight=1)
        for index in range(2):
            charts.grid_rowconfigure(index, weight=1)
        self.chart_frames = []
        for row in range(2):
            chart_frame = ctk.CTkFrame(charts)
            chart_frame.grid(row=row, column=0, sticky="nsew", padx=4, pady=4)
            self.chart_frames.append(chart_frame)

    def _build_form(
        self,
        parent: ctk.CTkFrame,
        category: str,
        choices: Sequence[str],
        row: int,
        column: int,
    ) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            frame, text=category, font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))
        ctk.CTkLabel(frame, text="Date").grid(
            row=1, column=0, sticky="w", padx=10, pady=4
        )
        ctk.CTkLabel(frame, text=date.today().strftime("%m/%d/%Y")).grid(
            row=1, column=1, sticky="w", padx=10, pady=4
        )
        ctk.CTkLabel(frame, text="Amount").grid(
            row=2, column=0, sticky="w", padx=10, pady=4
        )
        amount_entry = ctk.CTkEntry(frame, placeholder_text="Amount")
        amount_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=4)
        self._amount_entries[category] = amount_entry
        ctk.CTkLabel(frame, text="Type").grid(
            row=3, column=0, sticky="w", padx=10, pady=4
        )
        type_menu = ctk.CTkOptionMenu(frame, values=list(choices))
        type_menu.grid(row=3, column=1, sticky="ew", padx=10, pady=4)

        button_row = ctk.CTkFrame(frame, fg_color="transparent")
        button_row.grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=8
        )
        ctk.CTkButton(
            button_row,
            text=ADD_BUTTON_LABELS[category],
            command=lambda: self._submit(category, type_menu, False),
        ).pack(fill="x", padx=4, pady=4)
        if category == "Assets":
            ctk.CTkButton(
                button_row,
                text="Sell Asset",
                command=lambda: self._submit(category, type_menu, True),
            ).pack(fill="x", padx=4, pady=4)

    def _build_balance_sheet(self) -> None:
        self.balance_sheet_tab.grid_columnconfigure(0, weight=1)
        self.balance_sheet_tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            self.balance_sheet_tab,
            text="Balance Sheet",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        table_frame = ctk.CTkFrame(self.balance_sheet_tab)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)

        self.balance_sheet_header = Canvas(
            table_frame,
            height=32,
            highlightthickness=0,
            background="#90EE90",
        )
        self.balance_sheet_header.grid(row=0, column=0, sticky="ew")
        header_content = Frame(self.balance_sheet_header, height=32)
        header_content.grid_propagate(False)
        self.balance_sheet_header.create_window(
            (0, 0), window=header_content, anchor="nw"
        )

        column_widths = (95, 100, 135)
        spacer_width = 20
        section_column = 0
        header_width = 0
        for section_index, (heading, _) in enumerate(BALANCE_SHEET_SECTIONS):
            for offset, width in enumerate(column_widths):
                header_content.grid_columnconfigure(
                    section_column + offset, minsize=width
                )
            ctk.CTkLabel(
                header_content,
                text=heading,
                fg_color="#90EE90",
                text_color="#000000",
                corner_radius=0,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(
                row=0,
                column=section_column,
                columnspan=len(column_widths),
                sticky="nsew",
            )
            section_column += len(column_widths)
            header_width += sum(column_widths)
            if section_index < len(BALANCE_SHEET_SECTIONS) - 1:
                header_content.grid_columnconfigure(
                    section_column, minsize=spacer_width
                )
                section_column += 1
                header_width += spacer_width
        header_content.configure(width=header_width)
        self.balance_sheet_header.configure(
            scrollregion=(0, 0, header_width, 32)
        )

        # PandasTable calls bind_all on its container's master.
        table_binding_frame = Frame(table_frame)
        table_binding_frame.grid(row=1, column=0, sticky="nsew")
        table_binding_frame.grid_columnconfigure(0, weight=1)
        table_binding_frame.grid_rowconfigure(0, weight=1)
        table_container = Frame(table_binding_frame)
        table_container.grid(row=0, column=0, sticky="nsew")
        table_container.grid_columnconfigure(1, weight=1)
        table_container.grid_rowconfigure(1, weight=1)
        self.balance_table = Table(
            table_container,
            dataframe=pd.DataFrame(),
            showtoolbar=False,
            showstatusbar=False,
            editable=False,
            enable_menus=False,
        )
        self.balance_table.colheaderbgcolor = "#FFFF00"
        self.balance_table.colheaderfgcolor = "#000000"
        self.balance_table.columnwidths = {
            "DATE": column_widths[0],
            "AMOUNT": column_widths[1],
            "TYPE": column_widths[2],
            "": spacer_width,
        }
        self.balance_table.floatprecision = 2
        self.balance_table.thousandseparator = ","
        self.balance_table.show()
        self.balance_table.hideRowHeader()
        self.balance_table.rowheight = 22
        self.balance_table.columnwidths.update(
            {
                "DATE": column_widths[0],
                "AMOUNT": column_widths[1],
                "TYPE": column_widths[2],
                "": spacer_width,
            }
        )
        self.balance_table.Xscrollbar.configure(
            command=self._scroll_balance_sheet
        )
        self.balance_table.Yscrollbar.configure(
            command=self.balance_table.set_yviews
        )
        self.balance_table.bind(
            "<MouseWheel>", self._mousewheel_balance_sheet
        )
        self.balance_table.bind(
            "<Button-4>", self._mousewheel_balance_sheet
        )
        self.balance_table.bind(
            "<Button-5>", self._mousewheel_balance_sheet
        )
        self.balance_table.redraw()

    def _submit(
        self, category: str, type_menu: ctk.CTkOptionMenu, is_sale: bool
    ) -> None:
        if self._add_handler is not None:
            self._add_handler(
                category,
                self._amount_entries[category].get(),
                type_menu.get(),
                is_sale,
            )

    def _export(self) -> None:
        if self._export_handler is not None:
            self._export_handler()

    def clear_amount(self, category: str) -> None:
        self._amount_entries[category].delete(0, "end")

    def update_balance_sheet(self, transactions: pd.DataFrame) -> None:
        row_count = max(len(transactions), MAX_BALANCE_SHEET_ROWS)
        displayed_transactions = transactions.reindex(
            range(row_count)
        )
        self.balance_table.model.df = displayed_transactions
        self.balance_table.redraw()

    def _scroll_balance_sheet(self, *args: str) -> None:
        self.balance_table.set_xviews(*args)
        self.balance_sheet_header.xview(*args)

    def _mousewheel_balance_sheet(self, event: object) -> str:
        delta = getattr(event, "delta", 0)
        if delta:
            units = -1 if delta > 0 else 1
        else:
            units = -1 if getattr(event, "num", 0) == 4 else 1
        self.balance_table.set_yviews("scroll", units, "units")
        return "break"

    def update_dashboard(self, transactions: Sequence[Transaction]) -> None:
        for canvas in self._chart_canvases:
            canvas.get_tk_widget().destroy()
        self._chart_canvases.clear()
        self._figures.clear()

        monthly_expenses = [0.0] * 12
        totals: dict[str, float] = defaultdict(float)
        for transaction in transactions:
            totals[transaction.category] += transaction.amount
            if transaction.category == "Expenses":
                transaction_month = date.fromisoformat(
                    transaction.transaction_date
                ).month
                monthly_expenses[transaction_month - 1] += transaction.amount

        expenses_figure = Figure(figsize=(7, 3.2), dpi=100)
        expenses_axes = expenses_figure.add_subplot(111)
        expenses_axes.bar(
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
            monthly_expenses,
            color="#1f6aa5",
        )
        expenses_axes.set_title("Monthly Expenses")
        expenses_axes.set_ylabel("Amount")
        expenses_axes.grid(axis="y", alpha=0.25)
        expenses_figure.tight_layout()
        self._figures["Monthly Expenses.png"] = expenses_figure

        allocation_figure = Figure(figsize=(7, 3.2), dpi=100)
        allocation_axes = allocation_figure.add_subplot(111)
        labels = ("Income", "Expenses", "Assets", "Liabilities")
        values = [max(totals[label], 0) for label in labels]
        if sum(values) > 0:
            wedges, _, _ = allocation_axes.pie(
                values,
                autopct="%1.0f%%",
                startangle=90,
            )
            allocation_axes.set_title("Balance Sheet Totals")
            allocation_axes.legend(
                wedges,
                labels,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
            )
        else:
            allocation_axes.text(
                0.5,
                0.5,
                "Add transactions to see the balance sheet graph",
                ha="center",
                va="center",
                wrap=True,
            )
            allocation_axes.set_axis_off()
        allocation_figure.tight_layout(rect=(0, 0, 0.8, 1))
        self._figures["Balance Sheet Totals.png"] = allocation_figure

        for frame, figure in zip(self.chart_frames, self._figures.values()):
            canvas = FigureCanvasTkAgg(figure, master=frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)
            self._chart_canvases.append(canvas)

    def choose_export_directory(self) -> str:
        return filedialog.askdirectory(
            parent=self,
            title="Choose where to save the balance sheet and graphs image",
        )

    def export_dashboard_image(
        self, destination: Path, balance_sheet: pd.DataFrame
    ) -> Path:
        return create_dashboard_image(destination, balance_sheet, self._figures)

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self)
