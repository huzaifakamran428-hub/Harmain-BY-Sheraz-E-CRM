from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QHBoxLayout, QLabel,
)

from domain.models import Pilgrim
from presentation.app_context import AppContext, handle_error
from core.exceptions import ApplicationError

from presentation.widgets.inputs import StyledComboBox


class ReturnToPartyDialog(QDialog):
    def __init__(self, ctx: AppContext, pilgrim: Pilgrim, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.pilgrim = pilgrim
        self.setWindowTitle(f"Return to Party - {pilgrim.name}")
        self.setMinimumWidth(380)
        self.result_pilgrim: Pilgrim | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        info = QLabel(f"Currently in Free Account ({self.pilgrim.status.value}). Select the party to return them to:")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.party_combo = StyledComboBox()
        self._parties = self.ctx.parties.search_parties()
        for party in self._parties:
            self.party_combo.addItem(f"{party.name} ({party.phone})", party.id)
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Optional reason / note")
        form.addRow("Destination Party *", self.party_combo)
        form.addRow("Reason", self.reason_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("Confirm Return")
        confirm_btn.clicked.connect(self._confirm)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(confirm_btn)
        layout.addLayout(buttons)

    def _confirm(self):
        self.error_label.setText("")
        if not self._parties:
            self.error_label.setText("No active parties available. Please create a party first.")
            return
        destination_id = self.party_combo.currentData()
        try:
            self.result_pilgrim = self.ctx.free_accounts.return_to_party(
                self.pilgrim.id, destination_id, actor=self.ctx.current_username,
                reason=self.reason_input.text().strip(),
            )
            self.accept()
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Return to Party")
