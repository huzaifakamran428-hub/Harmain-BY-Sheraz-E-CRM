from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal

from presentation.app_context import AppContext, handle_error
from presentation.dialogs.party_dialog import PartyDialog
from presentation.widgets.buttons import (
    actions_column_width, make_row_button, ROW_BUTTON_SPACING, ROW_CELL_MARGIN,
)
from core.config import CURRENCY_SYMBOL

PARTY_ACTION_LABELS = ["Open Ledger", "Edit", "Delete"]


class PartiesPage(QWidget):
    party_opened = pyqtSignal(int, str)  # party_id, party_name

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Parties")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Open a party to manage its pilgrims, payments and permit slip.")
        subtitle.setObjectName("PageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header_row.addLayout(heading)
        header_row.addStretch()
        add_btn = QPushButton("+ Add Party")
        add_btn.setMinimumWidth(150)
        add_btn.clicked.connect(self._add_party)
        header_row.addWidget(add_btn)
        layout.addLayout(header_row)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by party name or phone...")
        self.search_input.textChanged.connect(self.refresh)
        search_row.addWidget(self.search_input)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Party Name", "Phone", "People", "Charge", "Received", "Remaining", "Actions"]
        )
        header = self.table.horizontalHeader()
        # Party Name takes the spare room; the other columns get a sensible fixed width
        header.setMinimumSectionSize(60)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 124), (2, 66), (3, 104), (4, 104), (5, 108)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, actions_column_width(PARTY_ACTION_LABELS))
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(52)   # room for real buttons
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self._row_double_clicked)
        layout.addWidget(self.table)

    def refresh(self):
        try:
            self._parties = self.ctx.parties.list_parties(self.search_input.text().strip())
        except Exception as e:
            handle_error(self, e, "Parties")
            return
        self.table.setRowCount(0)
        for party in self._parties:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                party.name, party.phone, str(party.total_people),
                f"{party.total_charge:,.0f} {CURRENCY_SYMBOL}",
                f"{party.total_received:,.0f} {CURRENCY_SYMBOL}",
                f"{party.total_remaining:,.0f} {CURRENCY_SYMBOL}",
            ]
            for col, text in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(text))

            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(ROW_CELL_MARGIN, 6, ROW_CELL_MARGIN, 6)
            cell_layout.setSpacing(ROW_BUTTON_SPACING)
            open_btn = make_row_button("Open Ledger")
            open_btn.setToolTip("Open this party's ledger")
            open_btn.clicked.connect(lambda _, p=party: self.party_opened.emit(p.id, p.name))
            edit_btn = make_row_button("Edit", ghost=True)
            edit_btn.setToolTip("Edit party name, phone, address and CNIC")
            edit_btn.clicked.connect(lambda _, p=party: self._edit_party(p))
            delete_btn = make_row_button("Delete", danger=True)
            delete_btn.setToolTip("Permanently delete this party and its pilgrims")
            delete_btn.clicked.connect(lambda _, p=party: self._delete_party(p))
            cell_layout.addWidget(open_btn)
            cell_layout.addWidget(edit_btn)
            cell_layout.addWidget(delete_btn)
            cell_layout.addStretch()
            self.table.setCellWidget(row, 6, cell)

    def _add_party(self):
        dialog = PartyDialog(self.ctx, parent=self)
        if dialog.exec():
            self.refresh()

    def _edit_party(self, party):
        dialog = PartyDialog(self.ctx, party=party, parent=self)
        if dialog.exec():
            self.refresh()

    def _row_double_clicked(self, row: int, _col: int):
        party = self._parties[row]
        self.party_opened.emit(party.id, party.name)

    def _delete_party(self, party):
        try:
            pilgrim_count = self.ctx.parties.count_party_pilgrims(party.id)
        except Exception as e:
            handle_error(self, e, "Delete Party")
            return
        warning = (
            f"This will permanently delete '{party.name}', along with its "
            f"{pilgrim_count} pilgrim(s) and all their payment records.\n\n"
            "This cannot be undone."
            if pilgrim_count
            else f"Permanently delete '{party.name}'?\n\nThis cannot be undone."
        )
        choice = QMessageBox.warning(
            self, "Delete Party", warning,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.parties.delete_party(party.id, actor=self.ctx.current_username)
            self.refresh()
        except Exception as e:
            handle_error(self, e, "Delete Party")
