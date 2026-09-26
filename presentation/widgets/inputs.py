"""Input widgets that behave the same on Windows, macOS and Linux."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QListView


class StyledComboBox(QComboBox):
    """
    A QComboBox whose dropdown list is a plain QListView.

    On macOS a stylesheet-styled QComboBox otherwise opens the native
    popup, which ignores the theme (list can appear empty, transparent or
    unclickable). Giving it its own list view makes the themed popup used
    everywhere, so every dropdown opens and can be picked from.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setView(QListView())
        self.setMaxVisibleItems(12)
