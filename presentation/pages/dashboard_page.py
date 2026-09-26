from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QFrame, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from presentation.app_context import AppContext, handle_error
from core.config import CURRENCY_SYMBOL
from presentation.dialogs.upcoming_dialog import UpcomingPermitsDialog


class DashboardPage(QWidget):
    party_requested = pyqtSignal(int, str)     # open this party (id, name)

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Live totals across every party and free account.")
        subtitle.setObjectName("PageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addLayout(heading)
        header_row.addStretch()
        refresh_btn.setMinimumWidth(120)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        grid = QGridLayout()
        grid.setSpacing(16)
        self.cards: dict[str, QLabel] = {}
        card_defs = [
            ("total_active", "Active Pilgrims"),
            ("free_male", "Free Account - Male"),
            ("free_female", "Free Account - Female"),
            ("total_visited", "Total Visited (Umrah Completed)"),
            ("upcoming_permits", "Upcoming Permits (Next 2 Days)"),
            ("total_charge", "Total Charges"),
            ("total_received", "Total Received"),
            ("total_remaining", "Total Remaining"),
        ]
        for i, (key, label) in enumerate(card_defs):
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(6)
            title_label = QLabel(label)
            title_label.setObjectName("CardTitle")
            value_label = QLabel("0")
            value_label.setObjectName("CardValue")
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            if key == "upcoming_permits":
                # The number alone does not say WHOSE people they are - this shows each
                # pilgrim with his/her party, and can open that party.
                view_btn = QPushButton("View Pilgrims && Parties")
                view_btn.setObjectName("SecondaryButton")
                view_btn.setToolTip("See who is coming up in the next 2 days and which party they belong to")
                view_btn.clicked.connect(self._show_upcoming)
                card_layout.addWidget(view_btn)
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.mousePressEvent = lambda _event: self._show_upcoming()
            grid.addWidget(card, i // 3, i % 3)
            self.cards[key] = value_label
        layout.addLayout(grid)
        layout.addStretch()

    def _show_upcoming(self):
        dialog = UpcomingPermitsDialog(self.ctx, parent=self)
        if dialog.exec() and dialog.selected_party:
            party_id, party_name = dialog.selected_party
            self.party_requested.emit(party_id, party_name)

    def refresh(self):
        try:
            summary = self.ctx.reports.dashboard_summary()
        except Exception as e:
            handle_error(self, e, "Dashboard")
            return
        self.cards["total_active"].setText(str(summary["total_active"]))
        self.cards["free_male"].setText(str(summary["free_male"]))
        self.cards["free_female"].setText(str(summary["free_female"]))
        self.cards["total_visited"].setText(str(summary["total_visited"]))
        self.cards["upcoming_permits"].setText(str(summary["upcoming_permits"]))
        self.cards["total_charge"].setText(f"{summary['total_charge']:,.0f} {CURRENCY_SYMBOL}")
        self.cards["total_received"].setText(f"{summary['total_received']:,.0f} {CURRENCY_SYMBOL}")
        self.cards["total_remaining"].setText(f"{summary['total_remaining']:,.0f} {CURRENCY_SYMBOL}")
