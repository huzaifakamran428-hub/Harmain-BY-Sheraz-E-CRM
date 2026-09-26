from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QLineEdit, QPushButton,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt

from domain.models import Pilgrim, PilgrimStatus
from presentation.app_context import AppContext, handle_error
from core.exceptions import ApplicationError
from core.config import CURRENCY_SYMBOL

FREE_STATUSES = (PilgrimStatus.FREE_MALE, PilgrimStatus.FREE_FEMALE)


class PaymentDialog(QDialog):
    """
    Payments ledger for one pilgrim.

    Behaviour the administrator asked for:
      * Several part-payments can be recorded one after another; the
        dialog stays open and the history updates after each one.
      * The moment the total received covers the charge, a bold green
        "PAYMENT CLEAR" badge appears and the record button turns into a
        disabled "Payment is Clear".
      * A pilgrim sitting in a Free Account cannot be paid against at
        all - the whole form locks with the reason shown.
    """

    def __init__(self, ctx: AppContext, pilgrim: Pilgrim, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.pilgrim = pilgrim
        self.setWindowTitle(f"Payments - {pilgrim.name}")
        self.setMinimumWidth(500)
        self.changed = False
        self._build_ui()
        self._refresh_all()

    # ------------------------------------------------------------- build
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel(self.pilgrim.name or "Pilgrim")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = QLabel("")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.status_badge)
        layout.addLayout(header)

        # ---- money summary tiles
        summary_card = QFrame()
        summary_card.setObjectName("GlassPanel")
        grid = QGridLayout(summary_card)
        grid.setContentsMargins(18, 14, 18, 14)
        grid.setHorizontalSpacing(26)
        self._tiles: dict[str, QLabel] = {}
        for column, label in enumerate(("Total Charge", "Received", "Remaining")):
            caption = QLabel(label.upper())
            caption.setObjectName("CardTitle")
            value = QLabel("0")
            value.setObjectName("SummaryValue")
            grid.addWidget(caption, 0, column)
            grid.addWidget(value, 1, column)
            self._tiles[label] = value
        layout.addWidget(summary_card)

        # ---- new payment form
        form = QFormLayout()
        form.setSpacing(10)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.0, 10_000_000)
        self.amount_input.setDecimals(0)
        self.amount_input.setSingleStep(100)
        self.amount_input.setSuffix(f" {CURRENCY_SYMBOL}")
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional note / reference (e.g. cash, bank transfer)")
        form.addRow("Amount Received *", self.amount_input)
        form.addRow("Note", self.note_input)
        layout.addLayout(form)

        quick_row = QHBoxLayout()
        self.full_amount_btn = QPushButton("Pay Full Remaining")
        self.full_amount_btn.setObjectName("SecondaryButton")
        self.full_amount_btn.clicked.connect(self._fill_remaining)
        quick_row.addWidget(self.full_amount_btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.record_btn = QPushButton("Record Payment")
        self.record_btn.clicked.connect(self._record)
        layout.addWidget(self.record_btn)

        history_label = QLabel("Payment History")
        history_label.setObjectName("CardTitle")
        layout.addWidget(history_label)
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(140)
        layout.addWidget(self.history_list)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    # ------------------------------------------------------------ refresh
    def _refresh_all(self):
        received, remaining = self.ctx.payments.balance(self.pilgrim.id, self.pilgrim.charge)
        self.pilgrim.total_received = received
        self.pilgrim.remaining = remaining

        self._tiles["Total Charge"].setText(f"{self.pilgrim.charge:,.0f} {CURRENCY_SYMBOL}")
        self._tiles["Received"].setText(f"{received:,.0f} {CURRENCY_SYMBOL}")
        self._tiles["Remaining"].setText(f"{max(remaining, 0):,.0f} {CURRENCY_SYMBOL}")

        in_free_account = self.pilgrim.status in FREE_STATUSES
        is_clear = remaining <= 0 and self.pilgrim.charge > 0

        # ---- badge
        if in_free_account:
            self.status_badge.setObjectName("FreeBadge")
            self.status_badge.setText(f"IN FREE ACCOUNT ({self.pilgrim.gender.value.upper()})")
        elif is_clear:
            self.status_badge.setObjectName("ClearBadge")
            self.status_badge.setText("PAYMENT CLEAR")
        else:
            self.status_badge.setObjectName("DueBadge")
            self.status_badge.setText(f"DUE  {remaining:,.0f} {CURRENCY_SYMBOL}")
        self._restyle(self.status_badge)

        # ---- controls
        if in_free_account:
            self.record_btn.setText("Payments Closed - In Free Account")
            self.record_btn.setEnabled(False)
            self.record_btn.setObjectName("")
            self.amount_input.setEnabled(False)
            self.note_input.setEnabled(False)
            self.full_amount_btn.setEnabled(False)
            self.error_label.setText(
                "This pilgrim has moved to the Free Account, so their ledger is closed. "
                "Return them to a party first if a payment is still outstanding."
            )
        elif is_clear:
            self.record_btn.setText("Payment is Clear")
            self.record_btn.setEnabled(False)
            self.record_btn.setObjectName("SuccessButton")
            self.amount_input.setEnabled(False)
            self.note_input.setEnabled(False)
            self.full_amount_btn.setEnabled(False)
        else:
            self.record_btn.setText("Record Payment")
            self.record_btn.setEnabled(True)
            self.record_btn.setObjectName("")
            self.amount_input.setEnabled(True)
            self.note_input.setEnabled(True)
            self.full_amount_btn.setEnabled(True)
            self.amount_input.setMaximum(max(remaining, 1))
            self.amount_input.setValue(remaining)
        self._restyle(self.record_btn)

        self._refresh_history()

    def _restyle(self, widget):
        """Force Qt to re-apply the stylesheet after an objectName change."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _refresh_history(self):
        self.history_list.clear()
        payments = self.ctx.payments.history(self.pilgrim.id)
        if not payments:
            item = QListWidgetItem("No payments recorded yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.history_list.addItem(item)
            return
        running = 0.0
        for index, payment in enumerate(payments, start=1):
            running += payment.amount
            text = (f"{index}.  {payment.paid_at.strftime('%d-%b-%Y  %I:%M %p')}   "
                    f"+{payment.amount:,.0f} {CURRENCY_SYMBOL}   "
                    f"(total {running:,.0f} {CURRENCY_SYMBOL})")
            if payment.note:
                text += f"   -  {payment.note}"
            self.history_list.addItem(QListWidgetItem(text))

    # ------------------------------------------------------------- actions
    def _fill_remaining(self):
        _, remaining = self.ctx.payments.balance(self.pilgrim.id, self.pilgrim.charge)
        if remaining > 0:
            self.amount_input.setValue(remaining)

    def _record(self):
        self.error_label.setText("")
        amount = self.amount_input.value()
        if amount <= 0:
            self.error_label.setText("Enter an amount greater than zero.")
            return
        try:
            self.ctx.payments.record_payment(
                self.pilgrim.id, amount, self.note_input.text().strip(),
                actor=self.ctx.current_username,
            )
            self.changed = True
            self.note_input.clear()
            self._refresh_all()
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Record Payment")
