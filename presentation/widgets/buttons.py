"""
Row buttons with a guaranteed-enough width.

The old code let the layout squeeze three buttons into a fixed column, so
long labels such as "Move to Free" were cut off and buttons overlapped.
Here the width of every button is measured from its own text (plus a safety
margin for different fonts on Windows / macOS) and then FIXED, so a button
can never be squeezed smaller than its label.
"""
from __future__ import annotations

from typing import Iterable

from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import QPushButton

ROW_BUTTON_HEIGHT = 32
ROW_BUTTON_SPACING = 8
ROW_CELL_MARGIN = 8

_QSS_EXTRA_W = 22     # 2 x 10px horizontal padding + 2 x 1px border (QSS sizes exclude them)
_QSS_EXTRA_H = 2      # 2 x 1px border
_PADDING = 44        # 2 x 12px stylesheet padding + border + ~18px font safety margin
_MIN_WIDTH = 72


def row_button_width(text: str) -> int:
    font = QFont()
    font.setPixelSize(12)
    font.setBold(True)
    return max(_MIN_WIDTH, QFontMetrics(font).horizontalAdvance(text) + _PADDING)


def actions_column_width(labels: Iterable[str]) -> int:
    """Width of a table column that must hold one button per label."""
    widths = [row_button_width(label) for label in labels]
    if not widths:
        return 0
    # + 2 x 8px: the table stylesheet pads every cell, which shrinks a cell widget
    return sum(widths) + ROW_BUTTON_SPACING * (len(widths) - 1) + 2 * ROW_CELL_MARGIN + 2 * 8 + 6


def make_row_button(text: str, ghost: bool = False, danger: bool = False,
                     width_for: Iterable[str] = ()) -> QPushButton:
    """`width_for` = every label this button slot can ever show (so it never resizes).

    `danger=True` draws the red "Delete" style; takes priority over `ghost`.
    """
    button = QPushButton(text)
    button.setObjectName("RowButtonDanger" if danger else ("RowButtonGhost" if ghost else "RowButton"))
    labels = list(width_for) or [text]
    width = max(row_button_width(label) for label in labels)
    button.setFixedSize(width, ROW_BUTTON_HEIGHT)
    # A Qt stylesheet's min-/max-width beats setFixedSize(), so the size is
    # ALSO written into the button's own stylesheet - otherwise the theme's
    # generic button rules could shrink it back to the text width.
    inner_w = width - _QSS_EXTRA_W
    inner_h = ROW_BUTTON_HEIGHT - _QSS_EXTRA_H
    button.setStyleSheet(
        f"min-width: {inner_w}px; max-width: {inner_w}px; "
        f"min-height: {inner_h}px; max-height: {inner_h}px;"
    )
    return button
