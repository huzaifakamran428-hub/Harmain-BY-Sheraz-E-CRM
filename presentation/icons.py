"""
Small arrow images for dropdowns, date/time pickers and spin boxes.

Qt's stylesheet engine removes the built-in arrow as soon as a control's
drop-down is restyled, and it cannot draw one itself. So the arrows are
drawn once (a simple chevron in the theme's text colour), saved as PNG in
the app's cache folder and referenced from the stylesheet with url(...).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from core.config import get_app_data_dir

logger = logging.getLogger(__name__)

_SIZE = 32          # drawn large, shown small -> crisp on Retina screens


def _draw(direction: str, colour: str, target: Path) -> None:
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QImage, QPainter, QPen, QColor, QPolygonF

    image = QImage(_SIZE, _SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(colour))
    pen.setWidthF(3.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if direction == "down":
        points = [QPointF(8, 12), QPointF(16, 20), QPointF(24, 12)]
    else:
        points = [QPointF(8, 20), QPointF(16, 12), QPointF(24, 20)]
    painter.drawPolyline(QPolygonF(points))
    painter.end()
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target), "PNG")


def arrow_urls(colour: str) -> Dict[str, str]:
    """Return {'down': 'url(...)', 'up': 'url(...)'} or {} if drawing fails."""
    try:
        folder = get_app_data_dir() / "ui_cache"
        safe = colour.lstrip("#").lower()
        urls = {}
        for direction in ("down", "up"):
            path = folder / f"arrow_{direction}_{safe}.png"
            if not path.exists():
                _draw(direction, colour, path)
            urls[direction] = f'url("{path.as_posix()}")'
        return urls
    except Exception as e:                          # noqa: BLE001
        logger.warning("Could not create arrow icons: %s", e)
        return {}
