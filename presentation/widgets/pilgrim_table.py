from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QHBoxLayout, QWidget, QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from domain.models import Pilgrim, PilgrimStatus
from domain.rules import is_within_reminder_window, calculate_remaining
from core.config import CURRENCY_SYMBOL
from presentation.themes import WARNING_RED, SUCCESS_GREEN
from presentation.widgets.avatars import circular_pixmap_from_path
from presentation.widgets.buttons import (
    actions_column_width, make_row_button, ROW_BUTTON_SPACING, ROW_CELL_MARGIN,
)

# Diameter of the pilgrim's circular photo shown before the SR column.
PHOTO_AVATAR_DIAMETER = 38

# Where the Actions column sits. False = last column (the owner's choice).
# True puts it first, so it is visible without scrolling sideways.
ACTIONS_FIRST = False

# Labels of the buttons a row can show (used to size the Actions column).
LEDGER_ACTION_LABELS = ["Edit", "Pay", "Move to Free", "Delete"]
FREE_ACTION_LABELS = ["Return to Party", "Delete"]
_PAY_SLOT_LABELS = ["Pay", "Closed", "Clear"]     # one slot, never resizes

LEDGER_COLUMNS = ["Photo", "SR", "Date", "Time", "Batch", "Name", "Gender", "Passport No.", "Visa No.",
                  "Email", "Password", "Charge", "Received", "Remaining", "Status"]
FREE_COLUMNS = ["Photo", "SR", "Date", "Time", "Batch", "Name", "Gender", "Passport No.", "Visa No.",
                "Email", "Password", "Charge", "Received", "Remaining", "Status"]

# Columns that grow to fit their longest value (see _fit_columns_to_text).
_FIT_TO_TEXT_COLUMNS = ("Name", "Email")
_FIT_MAX_WIDTH = 460

# The Photo column is a fixed-size circular avatar, not resizable text.
_FIXED_WIDTH_COLUMNS = ("Photo",)

_COLUMN_WIDTHS = {
    "Photo": 60, "SR": 58, "Date": 130, "Time": 90, "Batch": 92, "Name": 180, "Gender": 92,
    "Passport No.": 140, "Visa No.": 140, "Email": 210, "Password": 138,
    "Charge": 112, "Received": 112, "Remaining": 118, "Status": 118,
}

FREE_STATUSES = (PilgrimStatus.FREE_MALE, PilgrimStatus.FREE_FEMALE)


def build_table(columns: Sequence[str], with_actions: bool = True,
                action_labels: Sequence[str] = LEDGER_ACTION_LABELS) -> QTableWidget:
    """
    Build a ledger table.

    The Actions column is sized from the real labels of its buttons
    (`action_labels`), so every button is fully visible - the previous fixed
    280px squeezed three buttons together and cut "Move to Free" in half.
    """
    table = QTableWidget()
    columns = list(columns)
    offset = 1 if (with_actions and ACTIONS_FIRST) else 0
    table.setColumnCount(len(columns) + (1 if with_actions else 0))
    headers = list(columns)
    if with_actions:
        if ACTIONS_FIRST:
            headers.insert(0, "Actions")
        else:
            headers.append("Actions")
    table.setHorizontalHeaderLabels(headers)

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(58)
    header.setHighlightSections(False)

    for index, name in enumerate(columns):
        mode = (QHeaderView.ResizeMode.Fixed if name in _FIXED_WIDTH_COLUMNS
                else QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(index + offset, mode)
        table.setColumnWidth(index + offset, _COLUMN_WIDTHS.get(name, 110))

    if with_actions:
        actions_index = 0 if ACTIONS_FIRST else len(columns)
        header.setSectionResizeMode(actions_index, QHeaderView.ResizeMode.Fixed)
        # the Pay slot can show Pay / Closed / Clear - reserve the widest
        table.setColumnWidth(actions_index,
                             actions_column_width(_slot_widths_labels(list(action_labels))))

    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)                          # dates / names never wrap to 2 lines
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(52)   # room for real buttons
    return table


def _slot_widths_labels(labels: Sequence[str]) -> List[str]:
    """Replace the 'Pay' slot by its widest possible label, keep the others."""
    out = []
    for label in labels:
        out.append(max(_PAY_SLOT_LABELS, key=len) if label == "Pay" else label)
    return out


def populate_pilgrim_rows(
    table: QTableWidget,
    pilgrims: List[Pilgrim],
    columns: Sequence[str],
    mask_password: bool,
    on_edit: Optional[Callable[[Pilgrim], None]] = None,
    on_pay: Optional[Callable[[Pilgrim], None]] = None,
    extra_action: Optional[tuple[str, Callable[[Pilgrim], None]]] = None,
    on_delete: Optional[Callable[[Pilgrim], None]] = None,
    upcoming_color: str = WARNING_RED,
    reminder_days: int = 2,
) -> None:
    columns = list(columns)
    offset = 1 if ACTIONS_FIRST else 0
    with_actions = bool(on_edit or on_pay or extra_action or on_delete)
    table.setRowCount(0)
    table.setSortingEnabled(False)

    for pilgrim in pilgrims:
        row = table.rowCount()
        table.insertRow(row)

        upcoming = is_within_reminder_window(
            pilgrim.permit_date, pilgrim.permit_time, reminder_days=reminder_days)
        remaining = calculate_remaining(pilgrim.charge, pilgrim.total_received)
        is_clear = remaining <= 0 and pilgrim.charge > 0
        in_free = pilgrim.status in FREE_STATUSES

        for column_index, column_name in enumerate(columns):
            if column_name == "Photo":
                table.setCellWidget(row, column_index + offset, _photo_avatar_widget(pilgrim))
                continue

            text = _cell_value(pilgrim, column_name, mask_password, remaining, is_clear, in_free)
            item = QTableWidgetItem(text)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | (
                    Qt.AlignmentFlag.AlignRight
                    if column_name in ("Charge", "Received", "Remaining")
                    else Qt.AlignmentFlag.AlignLeft
                )
            )
            # Pilgrims inside the reminder window are shown in the colour chosen in
            # Settings (red by default). Status keeps its own Clear/Due colours.
            if upcoming and column_name not in ("Status", "Remaining"):
                item.setForeground(QColor(upcoming_color))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if column_name == "Status":
                item.setForeground(QColor(SUCCESS_GREEN if is_clear else WARNING_RED))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if column_name == "Remaining" and is_clear:
                item.setForeground(QColor(SUCCESS_GREEN))
            if column_name in _FIT_TO_TEXT_COLUMNS or column_name in ("Passport No.", "Visa No."):
                item.setToolTip(text)                      # full value on hover
            table.setItem(row, column_index + offset, item)

        if with_actions:
            table.setCellWidget(
                row, 0 if ACTIONS_FIRST else len(columns),
                _build_actions(pilgrim, on_edit, on_pay, extra_action, on_delete, is_clear, in_free),
            )

    _fit_columns_to_text(table, columns, offset)


def _fit_columns_to_text(table: QTableWidget, columns: Sequence[str], offset: int) -> None:
    """
    Names (and e-mails) vary a lot in length. A fixed width cut long ones
    off with "...". Grow these columns to show the longest value in full -
    never narrower than the normal width, and capped so one absurdly long
    value cannot push everything else off screen (hover shows it in full).
    """
    for index, name in enumerate(columns):
        if name not in _FIT_TO_TEXT_COLUMNS:
            continue
        column = index + offset
        table.resizeColumnToContents(column)
        wanted = table.columnWidth(column) + 16          # breathing room for bold text
        table.setColumnWidth(
            column, min(_FIT_MAX_WIDTH, max(_COLUMN_WIDTHS.get(name, 110), wanted)))


def _photo_avatar_widget(pilgrim: Pilgrim) -> QWidget:
    """The pilgrim's photo (or an initials placeholder) as a small circle,
    centred in the cell - same picture that was picked up automatically
    or set by hand when the pilgrim was added/edited."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label = QLabel()
    label.setFixedSize(PHOTO_AVATAR_DIAMETER, PHOTO_AVATAR_DIAMETER)
    label.setPixmap(circular_pixmap_from_path(pilgrim.photo_path, PHOTO_AVATAR_DIAMETER, pilgrim.name))
    layout.addWidget(label)
    return container


def _build_actions(pilgrim, on_edit, on_pay, extra_action, on_delete, is_clear, in_free) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(ROW_CELL_MARGIN, 6, ROW_CELL_MARGIN, 6)
    layout.setSpacing(ROW_BUTTON_SPACING)

    if on_edit:
        button = make_row_button("Edit", ghost=True)
        button.setToolTip("Edit this pilgrim's details")
        button.clicked.connect(lambda _, p=pilgrim: on_edit(p))
        layout.addWidget(button)

    if on_pay:
        if in_free:
            button = make_row_button("Closed", ghost=True, width_for=_PAY_SLOT_LABELS)
            button.setEnabled(False)
            button.setToolTip("In the Free Account - payments are closed for this pilgrim")
        elif is_clear:
            button = make_row_button("Clear", ghost=True, width_for=_PAY_SLOT_LABELS)
            button.setEnabled(False)
            button.setToolTip("Payment is clear - nothing outstanding")
        else:
            button = make_row_button("Pay", width_for=_PAY_SLOT_LABELS)
            button.setToolTip("Record a payment")
            button.clicked.connect(lambda _, p=pilgrim: on_pay(p))
        layout.addWidget(button)

    if extra_action:
        label, handler = extra_action
        button = make_row_button(label)
        button.clicked.connect(lambda _, p=pilgrim: handler(p))
        layout.addWidget(button)

    if on_delete:
        button = make_row_button("Delete", danger=True)
        button.setToolTip("Permanently delete this pilgrim")
        button.clicked.connect(lambda _, p=pilgrim: on_delete(p))
        layout.addWidget(button)

    layout.addStretch()
    return container


def _cell_value(pilgrim: Pilgrim, column: str, mask_password: bool,
                remaining: float, is_clear: bool, in_free: bool) -> str:
    if column == "Status":
        if in_free:
            return "Free / Clear" if is_clear else "Free"
        return "Clear" if is_clear else "Due"

    mapping = {
        # Free Account counts from 1 on its own; a party ledger shows the party serial.
        "SR": str(pilgrim.free_serial if (in_free and pilgrim.free_serial) else pilgrim.serial_number),
        "Date": pilgrim.permit_date.strftime("%d-%b-%Y") if pilgrim.permit_date else "-",
        "Time": pilgrim.permit_time.strftime("%I:%M %p").lstrip("0") if pilgrim.permit_time else "-",
        "Batch": pilgrim.batch or "-",
        "Name": pilgrim.name,
        "Gender": pilgrim.gender.value,
        "Passport No.": pilgrim.passport_number or "-",
        "Visa No.": pilgrim.visa_number or "-",
        "Email": pilgrim.email or "-",
        "Password": ("•" * len(pilgrim.password)) if (mask_password and pilgrim.password) else (pilgrim.password or "-"),
        "Charge": f"{pilgrim.charge:,.0f} {CURRENCY_SYMBOL}",
        "Received": f"{pilgrim.total_received:,.0f} {CURRENCY_SYMBOL}",
        "Remaining": f"{max(remaining, 0):,.0f} {CURRENCY_SYMBOL}",
    }
    return mapping.get(column, "-")
