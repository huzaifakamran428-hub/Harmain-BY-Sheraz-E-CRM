"""
"Upcoming Permits (Next 2 Days)" - who is coming up, and which party each person belongs to.

Opened from the Dashboard card. Every row names the party; the "Open Party" button (or a
double-click on the row) jumps straight to that party's ledger.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)

from presentation.app_context import AppContext, handle_error
from presentation.widgets.buttons import make_row_button

COLUMNS = ["Party", "SR", "Name", "Gender", "Permit Date", "Time"]


class UpcomingPermitsDialog(QDialog):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.selected_party: tuple[int, str] | None = None     # set when the user opens a party
        self._rows: list[dict] = []
        self.setWindowTitle("Upcoming Permits (Next 2 Days)")
        self.resize(900, 460)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.table = QTableWidget(0, len(COLUMNS) + 1)
        self.table.setHorizontalHeaderLabels(COLUMNS + ["Action"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)     # Party name in full
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)     # Name in full
        for col in (1, 3, 4, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(COLUMNS), QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(len(COLUMNS), 140)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.cellDoubleClicked.connect(lambda row, _col: self._open_party(row))
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("SecondaryButton")
        close_btn.setMinimumWidth(120)
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _load(self):
        try:
            self._rows = self.ctx.reports.upcoming_pilgrims()
        except Exception as e:                                   # noqa: BLE001
            handle_error(self, e, "Upcoming Permits")
            return

        parties = {r["party_id"] for r in self._rows}
        if self._rows:
            self.info.setText(
                f"{len(self._rows)} pilgrim(s) from {len(parties)} part{'y' if len(parties) == 1 else 'ies'} "
                "have a permit coming up. Double-click a row, or press Open Party, to see the whole party."
            )
        else:
            self.info.setText("No permit is coming up in the next 2 days.")

        self.table.setRowCount(0)
        for r in self._rows:
            p = r["pilgrim"]
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                r["party_name"],
                str(p.serial_number),
                p.name,
                p.gender.value,
                p.permit_date.strftime("%d-%b-%Y") if p.permit_date else "-",
                p.permit_time.strftime("%I:%M %p").lstrip("0") if p.permit_time else "-",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(row, col, item)
            button = make_row_button("Open Party")
            button.clicked.connect(lambda _, i=row: self._open_party(i))
            self.table.setCellWidget(row, len(COLUMNS), button)

    def _open_party(self, row: int):
        if 0 <= row < len(self._rows):
            r = self._rows[row]
            if r["party_id"] is not None:
                self.selected_party = (r["party_id"], r["party_name"])
                self.accept()
