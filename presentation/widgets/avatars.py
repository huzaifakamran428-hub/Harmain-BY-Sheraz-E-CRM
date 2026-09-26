"""
Circular pilgrim-photo avatars.

Used both in the pilgrim table (the small circle in front of the SR
column) and in the Add/Edit Pilgrim form (the preview next to "Set
Photo"), so the cropping/masking logic lives in one place.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPixmap

PLACEHOLDER_BG = "#3a4258"
PLACEHOLDER_FG = "#c9cedb"


def circular_pixmap_from_path(photo_path: str, diameter: int, name: str = "") -> QPixmap:
    """A `diameter`x`diameter` circular pixmap: the pilgrim's photo if one is
    stored and loadable, otherwise a plain initials placeholder."""
    if photo_path and Path(photo_path).exists():
        loaded = QPixmap(photo_path)
        if not loaded.isNull():
            return _mask_circle(loaded, diameter)
    return _placeholder(name, diameter)


def _mask_circle(source: QPixmap, diameter: int) -> QPixmap:
    scaled = source.scaled(
        QSize(diameter, diameter),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - diameter) // 2)
    y = max(0, (scaled.height() - diameter) // 2)
    cropped = scaled.copy(x, y, diameter, diameter)

    result = QPixmap(diameter, diameter)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, diameter, diameter)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return result


def _placeholder(name: str, diameter: int) -> QPixmap:
    result = QPixmap(diameter, diameter)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(PLACEHOLDER_BG)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, diameter, diameter)

    initials = "".join(part[0].upper() for part in (name or "").split()[:2]) or "?"
    painter.setPen(QColor(PLACEHOLDER_FG))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(max(7, diameter // 3))
    painter.setFont(font)
    painter.drawText(result.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return result
