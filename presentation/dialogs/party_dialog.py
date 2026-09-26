from __future__ import annotations

import copy
from typing import Optional

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QLabel

from domain.models import Party
from presentation.app_context import AppContext, handle_error
from core.exceptions import ApplicationError


class PartyDialog(QDialog):
    def __init__(self, ctx: AppContext, party: Optional[Party] = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.party = copy.copy(party) if party else None   # edit a copy
        self.setWindowTitle("Edit Party" if party else "Add Party")
        self.setMinimumWidth(460)
        self.result_party: Optional[Party] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit(self.party.name if self.party else "")
        self.phone_input = QLineEdit(self.party.phone if self.party else "")
        self.address_input = QLineEdit(self.party.address if self.party else "")
        self.cnic_input = QLineEdit(self.party.cnic if self.party else "")

        form.addRow("Party Name *", self.name_input)
        form.addRow("Phone Number *", self.phone_input)
        form.addRow("Address", self.address_input)
        form.addRow("CNIC", self.cnic_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def _save(self):
        self.error_label.setText("")
        try:
            if self.party:
                self.party.name = self.name_input.text().strip()
                self.party.phone = self.phone_input.text().strip()
                self.party.address = self.address_input.text().strip()
                self.party.cnic = self.cnic_input.text().strip()
                self.result_party = self.ctx.parties.update_party(self.party, actor=self.ctx.current_username)
            else:
                self.result_party = self.ctx.parties.create_party(
                    self.name_input.text(), self.phone_input.text(),
                    self.address_input.text(), self.cnic_input.text(),
                    actor=self.ctx.current_username,
                )
            self.accept()
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Save Party")
