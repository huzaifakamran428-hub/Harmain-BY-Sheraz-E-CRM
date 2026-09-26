from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTabWidget, QPushButton,
    QMessageBox, QFileDialog,
)

from presentation.app_context import AppContext, handle_error
from presentation.widgets.pilgrim_table import (
    build_table, populate_pilgrim_rows, FREE_COLUMNS, FREE_ACTION_LABELS,
)
from presentation.widgets.summary_header import SummaryHeader
from presentation.dialogs.return_dialog import ReturnToPartyDialog
from domain.models import PilgrimStatus


class FreeAccountPage(QWidget):
    """
    Pilgrims who have finished their Riyazul Jannah visit.

    They arrive here automatically six hours after their permit time,
    routed by gender - males into the Male tab, females into the Female
    tab. Their full record (including gender) stays visible. Payments are
    closed while a pilgrim sits here; returning them to a party removes
    them from this page and puts them back on that party's ledger.
    """

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
        title = QLabel("Free Account")
        title.setObjectName("SectionTitle")
        subtitle = QLabel(
            "Pilgrims move here automatically 6 hours after their permit time - "
            "males into Male, females into Female."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header_row.addLayout(heading)
        header_row.addStretch()

        check_now_btn = QPushButton("Run 6-Hour Check Now")
        check_now_btn.setMinimumWidth(190)
        check_now_btn.setToolTip("Immediately move every pilgrim whose permit time passed 6 hours ago")
        check_now_btn.clicked.connect(self._run_sweep)
        export_btn = QPushButton("Export to Excel")
        export_btn.setObjectName("SecondaryButton")
        export_btn.setMinimumWidth(160)
        export_btn.setToolTip("Save the Free Account as an .xlsx file with separate Male and Female sheets")
        export_btn.clicked.connect(self._export_excel)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.setMinimumWidth(120)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(check_now_btn)
        header_row.addWidget(export_btn)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.summary = SummaryHeader(["Male", "Female", "Total in Free Account"])
        layout.addWidget(self.summary)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, passport or visa number...")
        self.search_input.textChanged.connect(self.refresh)
        layout.addWidget(self.search_input)

        self.tabs = QTabWidget()
        # One action button per row here (Return to Party), so the Actions
        # column is sized for exactly one.
        self.male_table = build_table(FREE_COLUMNS, with_actions=True, action_labels=FREE_ACTION_LABELS)
        self.female_table = build_table(FREE_COLUMNS, with_actions=True, action_labels=FREE_ACTION_LABELS)
        self.tabs.addTab(self.male_table, "Male")
        self.tabs.addTab(self.female_table, "Female")
        layout.addWidget(self.tabs)

    def refresh(self):
        search = self.search_input.text().strip()
        try:
            male = self.ctx.pilgrims.list_free(PilgrimStatus.FREE_MALE, search)
            female = self.ctx.pilgrims.list_free(PilgrimStatus.FREE_FEMALE, search)
        except Exception as e:
            handle_error(self, e, "Free Account")
            return

        self.summary.set_value("Male", str(len(male)))
        self.summary.set_value("Female", str(len(female)))
        self.summary.set_value("Total in Free Account", str(len(male) + len(female)))
        self.tabs.setTabText(0, f"Male ({len(male)})")
        self.tabs.setTabText(1, f"Female ({len(female)})")

        # No pay handler: payments are closed while a pilgrim is in a Free Account.
        for table, pilgrims in ((self.male_table, male), (self.female_table, female)):
            populate_pilgrim_rows(
                table, pilgrims, FREE_COLUMNS, mask_password=True,
                extra_action=("Return to Party", self._return_pilgrim),
                on_delete=self._delete_pilgrim,
            )

    def _run_sweep(self):
        try:
            moved = self.ctx.free_accounts.run_six_hour_transfer_sweep(
                actor=self.ctx.current_username
            )
        except Exception as e:
            handle_error(self, e, "Free Account")
            return
        self.refresh()
        QMessageBox.information(
            self, "6-Hour Check",
            f"{moved} pilgrim(s) moved to the Free Account." if moved
            else "No pilgrim has passed the 6-hour mark yet.",
        )

    def _export_excel(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", "free_account.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return
        try:
            self.ctx.exports.export_free_account_to_excel(Path(file_path))
            QMessageBox.information(self, "Export to Excel", f"Saved to:\n{file_path}")
        except Exception as e:
            handle_error(self, e, "Export to Excel")

    def _return_pilgrim(self, pilgrim):
        dialog = ReturnToPartyDialog(self.ctx, pilgrim, parent=self)
        if dialog.exec():
            self.refresh()

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
