from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from core.config import CURRENCY_SYMBOL


class SummaryHeader(QFrame):
    """Bold summary bar shown above party ledgers / free account tables (SRS 20.4)."""

    def __init__(self, labels: list[str]):
        super().__init__()
        self.setObjectName("Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(28)
        self._value_labels: dict[str, QLabel] = {}
        for label in labels:
            box = QVBoxLayout()
            title = QLabel(label)
            title.setObjectName("CardTitle")
            value = QLabel("0")
            value.setObjectName("SummaryValue")
            box.addWidget(title)
            box.addWidget(value)
            layout.addLayout(box)
            self._value_labels[label] = value
        layout.addStretch()

    def set_value(self, label: str, text: str) -> None:
        if label in self._value_labels:
            self._value_labels[label].setText(text)

    def set_money(self, label: str, amount: float) -> None:
        self.set_value(label, f"{amount:,.0f} {CURRENCY_SYMBOL}")
