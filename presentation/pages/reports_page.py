from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QTabWidget,
)

from presentation.app_context import AppContext, handle_error
from core.config import CURRENCY_SYMBOL


class ReportsPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        title = QLabel("Reports")
        title.setObjectName("SectionTitle")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.tabs = QTabWidget()

        self.party_table = QTableWidget()
        self.party_table.setColumnCount(5)
        self.party_table.setHorizontalHeaderLabels(["Party", "People", "Charge", "Received", "Remaining"])
        self._style_table(self.party_table)
        self.tabs.addTab(self.party_table, "Party-wise Totals")

        self.visited_table = QTableWidget()
        self.visited_table.setColumnCount(4)
        self.visited_table.setHorizontalHeaderLabels(["Name", "Gender", "Passport No.", "Moved to Free On"])
        self._style_table(self.visited_table)
        self.tabs.addTab(self.visited_table, "Visited / Completed")

        layout.addWidget(self.tabs)

    @staticmethod
    def _style_table(table: QTableWidget):
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

    def refresh(self):
        try:
            party_totals = self.ctx.reports.party_wise_totals()
            visited = self.ctx.reports.visited_report()
        except Exception as e:
            handle_error(self, e, "Reports")
            return

        self.party_table.setRowCount(0)
        for row_data in party_totals:
            row = self.party_table.rowCount()
            self.party_table.insertRow(row)
            values = [
                row_data["party"], str(row_data["people"]),
                f"{row_data['charge']:,.0f} {CURRENCY_SYMBOL}",
                f"{row_data['received']:,.0f} {CURRENCY_SYMBOL}",
                f"{row_data['remaining']:,.0f} {CURRENCY_SYMBOL}",
            ]
            for col, text in enumerate(values):
                self.party_table.setItem(row, col, QTableWidgetItem(text))

        self.visited_table.setRowCount(0)
        for entry in visited:
            row = self.visited_table.rowCount()
            self.visited_table.insertRow(row)
            moved = entry.get("moved_to_free_at") or "-"
            values = [entry.get("name", ""), entry.get("gender", ""), entry.get("passport_number", "-"), moved]
            for col, text in enumerate(values):
                self.visited_table.setItem(row, col, QTableWidgetItem(str(text)))
