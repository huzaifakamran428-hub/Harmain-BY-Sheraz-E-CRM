from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal

from presentation.app_context import AppContext, handle_error
from presentation.widgets.summary_header import SummaryHeader
from presentation.widgets.inputs import StyledComboBox
from presentation.widgets.pilgrim_table import (
    build_table, populate_pilgrim_rows, LEDGER_COLUMNS, LEDGER_ACTION_LABELS,
)
from presentation.dialogs.pilgrim_dialog import PilgrimDialog
from presentation.dialogs.payment_dialog import PaymentDialog
from domain.models import Gender


class PartyDetailPage(QWidget):
    back_requested = pyqtSignal()
    pilgrim_saved = pyqtSignal()      # a pilgrim was added or edited - check reminders right away

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.party_id: int | None = None
        self.party_name: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        back_btn = QPushButton("←  Back to Parties")
        back_btn.setMinimumWidth(160)
        back_btn.setObjectName("SecondaryButton")
        back_btn.clicked.connect(self.back_requested.emit)
        self.title_label = QLabel("Party")
        self.title_label.setObjectName("SectionTitle")
        header_row.addWidget(back_btn)
        header_row.addWidget(self.title_label)
        header_row.addStretch()
        bill_btn = QPushButton("Generate A6 Bill (PDF)")
        bill_btn.setMinimumWidth(190)
        bill_btn.setToolTip("Permit slip - shows serial, date, time, gender and totals only (no names)")
        bill_btn.clicked.connect(self._generate_bill)
        export_btn = QPushButton("Export to Excel")
        export_btn.setObjectName("SecondaryButton")
        export_btn.setMinimumWidth(160)
        export_btn.setToolTip("Save this party's full pilgrim list, with the party's name, as an .xlsx file")
        export_btn.clicked.connect(self._export_excel)
        add_btn = QPushButton("+ Add Pilgrim")
        add_btn.setMinimumWidth(140)
        add_btn.clicked.connect(self._add_pilgrim)
        header_row.addWidget(bill_btn)
        header_row.addWidget(export_btn)
        header_row.addWidget(add_btn)
        layout.addLayout(header_row)

        self.summary = SummaryHeader(["People", "Total Charge", "Total Received", "Total Remaining"])
        layout.addWidget(self.summary)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, passport or visa number...")
        self.search_input.textChanged.connect(self.refresh)
        self.gender_filter = StyledComboBox()
        self.gender_filter.addItems(["All Genders", Gender.MALE.value, Gender.FEMALE.value])
        self.gender_filter.currentIndexChanged.connect(self.refresh)
        self.gender_filter.setMinimumWidth(150)
        self.mask_toggle = QPushButton("Show Passwords")
        self.mask_toggle.setMinimumWidth(150)
        self.mask_toggle.setObjectName("SecondaryButton")
        self.mask_toggle.setCheckable(True)
        self.mask_toggle.toggled.connect(self._toggle_mask)
        filter_row.addWidget(self.search_input)
        filter_row.addWidget(self.gender_filter)
        filter_row.addWidget(self.mask_toggle)
        layout.addLayout(filter_row)

        self.table = build_table(LEDGER_COLUMNS, with_actions=True, action_labels=LEDGER_ACTION_LABELS)
        layout.addWidget(self.table)

    def open_party(self, party_id: int, party_name: str):
        self.party_id = party_id
        self.party_name = party_name
        self.title_label.setText(f"Party: {party_name}")
        self.refresh()

    def _toggle_mask(self, checked: bool):
        self.mask_toggle.setText("Hide Passwords" if checked else "Show Passwords")
        self.refresh()

    def refresh(self):
        if self.party_id is None:
            return
        try:
            party = self.ctx.parties.get_party_with_totals(self.party_id)
            gender_text = self.gender_filter.currentText()
            gender = Gender(gender_text) if gender_text != "All Genders" else None
            pilgrims = self.ctx.pilgrims.list_party_ledger(
                self.party_id, self.search_input.text().strip(), gender
            )
        except Exception as e:
            handle_error(self, e, "Party Ledger")
            return

        self.summary.set_value("People", str(party.total_people))
        self.summary.set_money("Total Charge", party.total_charge)
        self.summary.set_money("Total Received", party.total_received)
        self.summary.set_money("Total Remaining", party.total_remaining)

        populate_pilgrim_rows(
            self.table, pilgrims, LEDGER_COLUMNS,
            mask_password=not self.mask_toggle.isChecked(),
            on_edit=self._edit_pilgrim,
            on_pay=self._open_payment,
            extra_action=("Move to Free", self._manual_transfer),
            on_delete=self._delete_pilgrim,
            upcoming_color=self.ctx.settings.upcoming_color(),
            reminder_days=self.ctx.settings.reminder_days(),
        )

    def _add_pilgrim(self):
        dialog = PilgrimDialog(self.ctx, self.party_id, parent=self)
        if dialog.exec():
            self.refresh()
            self.pilgrim_saved.emit()

    def _edit_pilgrim(self, pilgrim):
        dialog = PilgrimDialog(self.ctx, self.party_id, pilgrim=pilgrim, parent=self)
        if dialog.exec():
            self.refresh()
            self.pilgrim_saved.emit()

    def _open_payment(self, pilgrim):
        dialog = PaymentDialog(self.ctx, pilgrim, parent=self)
        dialog.exec()
        if dialog.changed:
            self.refresh()

    def _manual_transfer(self, pilgrim):
        choice = QMessageBox.question(
            self, "Move to Free Account",
            f"Move {pilgrim.name} to the Free Account now, ahead of the automatic 6-hour rule?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.free_accounts.transfer_to_free(pilgrim.id, actor=self.ctx.current_username)
            self.refresh()
        except Exception as e:
            handle_error(self, e, "Move to Free Account")

    def _delete_pilgrim(self, pilgrim):
        choice = QMessageBox.warning(
            self, "Delete Pilgrim",
            f"Permanently delete {pilgrim.name}? Their payment history goes with them.\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.pilgrims.delete_pilgrim(pilgrim.id, actor=self.ctx.current_username)
            self.refresh()
        except Exception as e:
            handle_error(self, e, "Delete Pilgrim")

    def _export_excel(self):
        if self.party_id is None:
            return
        default_name = f"{self.party_name or 'party'}_pilgrims.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", default_name, "Excel Files (*.xlsx)"
        )
        if not file_path:
            return
        try:
            self.ctx.exports.export_party_to_excel(self.party_id, Path(file_path))
            QMessageBox.information(self, "Export to Excel", f"Saved to:\n{file_path}")
        except Exception as e:
            handle_error(self, e, "Export to Excel")

    def _generate_bill(self):
        default_name = f"{self.party_name or 'party'}_bill.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Bill As", default_name, "PDF Files (*.pdf)")
        if not file_path:
            return
        try:
            self.ctx.bills.generate_bill_for_party(self.party_id, Path(file_path))
            QMessageBox.information(self, "Bill Generated", f"Bill saved to:\n{file_path}")
        except Exception as e:
            handle_error(self, e, "Generate Bill")
