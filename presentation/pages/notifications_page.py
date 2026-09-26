from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtGui import QColor

from presentation.app_context import AppContext, handle_error
from presentation.themes import WARNING_RED


class NotificationsPage(QWidget):
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
        title = QLabel("Notifications")
        title.setObjectName("SectionTitle")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        check_now_btn = QPushButton("Check Reminders Now")
        check_now_btn.clicked.connect(self._check_now)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(refresh_btn)
        header_row.addWidget(check_now_btn)
        layout.addLayout(header_row)

        interval = self._interval_minutes()
        note = QLabel(
            f"Reminders are sent to you automatically by email - checked right after you save a pilgrim and "
            f"every {interval} minute(s) while the app is running (it keeps running in the tray when the window is closed). "
            "You never need to press the button; it only forces a check right now."
        )
        note.setWordWrap(True)
        note.setObjectName("HintText")
        layout.addWidget(note)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Pilgrim", "Type", "Channel", "Scheduled For", "Status", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def _interval_minutes(self) -> int:
        try:
            return max(1, int(self.ctx.settings.get("scheduler_interval_minutes") or 1))
        except (TypeError, ValueError):
            return 1

    def refresh(self):
        try:
            records = self.ctx.reminders.notifications.list_recent(200)
        except Exception as e:
            handle_error(self, e, "Notifications")
            return
        self.table.setRowCount(0)
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                getattr(record, "pilgrim_name", "-"), record.type, record.channel.value,
                record.scheduled_for.strftime("%d-%b-%Y %H:%M") if record.scheduled_for else "-",
                record.status.value, record.failure_reason or "-",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if record.status.value == "Failed":
                    item.setForeground(QColor(WARNING_RED))
                self.table.setItem(row, col, item)

    def _check_now(self):
        try:
            sent = self.ctx.reminders.check_and_send_reminders(force=True)
            self.refresh()
        except Exception as e:
            handle_error(self, e, "Notifications")
