"""
Glass theme system (SRS 7.6).

Qt's stylesheet engine has no backdrop-blur, so the "glass" look is built
the way native apps faked it before blur existed, and it reads the same:

  * a soft diagonal gradient behind the whole window
  * translucent card surfaces (rgba) so the gradient shows through
  * a light 1px top/edge highlight on every panel
  * heavier, rounded, high-contrast controls that float above it

Red is reserved for urgent/upcoming-permit warnings and validation errors
and is never used as a theme accent. Green is reserved for the "payment
clear" badge.
"""
from __future__ import annotations

from core.config import DEFAULT_THEME_NAME as DEFAULT_THEME

WARNING_RED = "#e0455c"
SUCCESS_GREEN = "#1f9d5b"
SUCCESS_GREEN_SOFT = "rgba(31, 157, 91, 0.18)"

# glass  - rgba fill for cards / panels
# edge   - rgba colour of the 1px highlight around glass
# hover  - rgba overlay used on hover states
_THEMES = {
    "Glass Gold": dict(
        bg_from="#101218", bg_to="#1c1a12", surface="#191b22", sidebar="rgba(12,13,18,0.86)",
        glass="rgba(255,255,255,0.055)", edge="rgba(255,255,255,0.13)", hover="rgba(255,255,255,0.09)",
        text="#f3f4f7", subtext="#a9aeba", accent="#d8b45a", accent_text="#14161c",
        border="rgba(255,255,255,0.10)", input_bg="rgba(255,255,255,0.05)", dark=True,
        sidebar_text="#f3f4f7", sidebar_subtext="#a9aeba", sidebar_hover="rgba(255,255,255,0.09)",
    ),
    "Glass Midnight": dict(
        bg_from="#0b1020", bg_to="#161c33", surface="#161b2b", sidebar="rgba(9,12,24,0.86)",
        glass="rgba(255,255,255,0.06)", edge="rgba(255,255,255,0.14)", hover="rgba(255,255,255,0.10)",
        text="#eef2fb", subtext="#a6b0c8", accent="#5b8dfb", accent_text="#0a0f1e",
        border="rgba(255,255,255,0.10)", input_bg="rgba(255,255,255,0.05)", dark=True,
        sidebar_text="#eef2fb", sidebar_subtext="#a6b0c8", sidebar_hover="rgba(255,255,255,0.10)",
    ),
    "Glass Emerald": dict(
        bg_from="#07160f", bg_to="#11291d", surface="#102319", sidebar="rgba(6,18,12,0.86)",
        glass="rgba(255,255,255,0.055)", edge="rgba(255,255,255,0.13)", hover="rgba(255,255,255,0.09)",
        text="#ecf7f0", subtext="#9dc0ac", accent="#2ecc86", accent_text="#06150d",
        border="rgba(255,255,255,0.10)", input_bg="rgba(255,255,255,0.05)", dark=True,
        sidebar_text="#ecf7f0", sidebar_subtext="#9dc0ac", sidebar_hover="rgba(255,255,255,0.09)",
    ),
    "Glass Royal": dict(
        bg_from="#140d22", bg_to="#241638", surface="#1d1430", sidebar="rgba(15,9,26,0.86)",
        glass="rgba(255,255,255,0.06)", edge="rgba(255,255,255,0.14)", hover="rgba(255,255,255,0.10)",
        text="#f1ecfb", subtext="#bcaad8", accent="#a56cf0", accent_text="#12091f",
        border="rgba(255,255,255,0.10)", input_bg="rgba(255,255,255,0.05)", dark=True,
        sidebar_text="#f1ecfb", sidebar_subtext="#bcaad8", sidebar_hover="rgba(255,255,255,0.10)",
    ),
    "Glass Teal": dict(
        bg_from="#07171a", bg_to="#0f2c31", surface="#0f2429", sidebar="rgba(5,17,20,0.86)",
        glass="rgba(255,255,255,0.055)", edge="rgba(255,255,255,0.13)", hover="rgba(255,255,255,0.09)",
        text="#e9fbf9", subtext="#97c2bd", accent="#25c2ad", accent_text="#05161a",
        border="rgba(255,255,255,0.10)", input_bg="rgba(255,255,255,0.05)", dark=True,
        sidebar_text="#e9fbf9", sidebar_subtext="#97c2bd", sidebar_hover="rgba(255,255,255,0.09)",
    ),
    "Glass Maroon": dict(
        bg_from="#170a0f", bg_to="#2b1119", surface="#20101a", sidebar="rgba(18,7,11,0.86)",
        glass="rgba(255,255,255,0.055)", edge="rgba(255,255,255,0.13)", hover="rgba(255,255,255,0.09)",
        text="#f7ebef", subtext="#cca3b0", accent="#d1547a", accent_text="#170a0f",
        border="rgba(255,255,255,0.10)", input_bg="rgba(255,255,255,0.05)", dark=True,
        sidebar_text="#f7ebef", sidebar_subtext="#cca3b0", sidebar_hover="rgba(255,255,255,0.09)",
    ),
    "Frosted Light": dict(
        bg_from="#eef1f7", bg_to="#e4e9f5", surface="#ffffff", sidebar="rgba(20,22,30,0.93)",
        glass="rgba(255,255,255,0.72)", edge="rgba(255,255,255,0.95)", hover="rgba(20,22,30,0.06)",
        text="#1b1f2a", subtext="#5d6577", accent="#3d5afe", accent_text="#ffffff",
        border="rgba(20,22,30,0.12)", input_bg="rgba(255,255,255,0.85)", dark=False,
        # The sidebar itself is always a dark panel (by design, even in a
        # "light" theme), so its text/hover must be light regardless of the
        # theme's own (dark) text colour - otherwise nav labels read as
        # near-invisible dark-on-dark, which is the bug being fixed here.
        sidebar_text="#f3f5fb", sidebar_subtext="#aab1c4", sidebar_hover="rgba(255,255,255,0.08)",
    ),
    "Frosted Sand": dict(
        bg_from="#f7f3ea", bg_to="#efe7d7", surface="#ffffff", sidebar="rgba(32,28,22,0.93)",
        glass="rgba(255,255,255,0.74)", edge="rgba(255,255,255,0.95)", hover="rgba(32,28,22,0.06)",
        text="#241f16", subtext="#6a6053", accent="#b08430", accent_text="#ffffff",
        border="rgba(36,31,22,0.13)", input_bg="rgba(255,255,255,0.88)", dark=False,
        sidebar_text="#f6f0e4", sidebar_subtext="#c8bcaa", sidebar_hover="rgba(255,255,255,0.08)",
    ),
    "Frosted Emerald": dict(
        bg_from="#f3f8f4", bg_to="#e8f3ea", surface="#ffffff", sidebar="rgba(8,20,14,0.94)",
        glass="rgba(255,255,255,0.74)", edge="rgba(255,255,255,0.95)", hover="rgba(15,80,50,0.07)",
        text="#132018", subtext="#59705f", accent="#1f9d5b", accent_text="#ffffff",
        border="rgba(15,80,50,0.14)", input_bg="rgba(255,255,255,0.88)", dark=False,
        sidebar_text="#eefaf1", sidebar_subtext="#9fc4ac", sidebar_hover="rgba(255,255,255,0.08)",
    ),
}

THEME_NAMES = list(_THEMES.keys())

# Older databases may still hold a pre-glass theme name.
_LEGACY_ALIASES = {
    "Dark Gold": "Glass Gold", "Emerald": "Glass Emerald", "Blue": "Glass Midnight",
    "Purple": "Glass Royal", "Teal": "Glass Teal", "Royal Maroon": "Glass Maroon",
    "Slate": "Glass Midnight", "Sunset": "Glass Gold", "Ocean": "Glass Teal",
    "Light Gold": "Frosted Sand", "Ivory": "Frosted Sand", "Neutral Light": "Frosted Light",
}


def resolve_theme_name(name: str) -> str:
    if name in _THEMES:
        return name
    return _LEGACY_ALIASES.get(name, DEFAULT_THEME if DEFAULT_THEME in _THEMES else THEME_NAMES[0])


def theme_palette(name: str) -> dict:
    return _THEMES[resolve_theme_name(name)]


def window_gradient(name: str) -> tuple[str, str]:
    t = theme_palette(name)
    return t["bg_from"], t["bg_to"]


def build_stylesheet(theme_name: str) -> str:
    t = theme_palette(theme_name)
    from presentation.icons import arrow_urls
    arrows = arrow_urls(t["text"])
    down = arrows.get("down", "none")
    up = arrows.get("up", "none")
    return f"""
    /* ---------------------------------------------------------- base */
    QWidget {{
        color: {t['text']};
        font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
        background: transparent;
    }}
    QMainWindow, QDialog, #GlassRoot {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                     stop:0 {t['bg_from']}, stop:1 {t['bg_to']});
    }}
    QToolTip {{
        background-color: {t['surface']};
        color: {t['text']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 6px 8px;
    }}

    /* ------------------------------------------------------- sidebar */
    #Sidebar {{
        background-color: {t['sidebar']};
        border-right: 1px solid {t['edge']};
    }}
    #Sidebar QPushButton {{
        text-align: left;
        padding: 11px 16px;
        border: 1px solid transparent;
        border-radius: 10px;
        color: {t['sidebar_text']};
        background: transparent;
        font-size: 13px;
        font-weight: 500;
        min-height: 20px;
    }}
    #Sidebar QPushButton:hover {{
        background-color: {t['sidebar_hover']};
        color: {t['sidebar_text']};
        border: 1px solid {t['edge']};
    }}
    #Sidebar QPushButton:checked {{
        background-color: {t['accent']};
        color: {t['accent_text']};
        font-weight: 700;
        border: 1px solid {t['accent']};
    }}
    #BrandLabel {{
        color: {t['accent']}; font-size: 17px; font-weight: 800;
        padding: 16px 16px 2px 16px; background: transparent;
    }}
    #BrandSubLabel {{
        color: {t['sidebar_subtext']}; font-size: 11px;
        padding: 0 16px 12px 16px; background: transparent;
    }}
    #LogoHolder {{ background: transparent; padding: 14px 16px 0 16px; }}
    #CreditLabel {{
        color: {t['accent']};
        font-family: "Segoe UI Semibold", "SF Pro Display", "Poppins", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1.4px;
        padding: 12px 16px 14px 16px;
        margin-top: 4px;
        border-top: 1px solid {t['edge']};
        background: transparent;
    }}

    /* --------------------------------------------------- glass cards */
    QFrame#Card, QWidget#Card {{
        background-color: {t['glass']};
        border: 1px solid {t['edge']};
        border-radius: 16px;
    }}
    QFrame#GlassPanel {{
        background-color: {t['glass']};
        border: 1px solid {t['edge']};
        border-radius: 14px;
    }}
    QLabel#CardTitle {{
        color: {t['subtext']}; font-size: 11px; font-weight: 600;
        letter-spacing: 0.6px; background: transparent;
    }}
    QLabel#CardValue {{
        color: {t['text']}; font-size: 25px; font-weight: 800; background: transparent;
    }}
    QLabel#SectionTitle {{
        font-size: 21px; font-weight: 800; color: {t['text']}; background: transparent;
    }}
    QLabel#PageSubtitle {{ color: {t['subtext']}; font-size: 12px; background: transparent; }}
    QLabel#SummaryValue {{
        font-size: 16px; font-weight: 800; color: {t['accent']}; background: transparent;
    }}

    /* ------------------------------------------------------- buttons */
    /* Every button gets a real minimum size, generous padding and a
       visible border, so no action is ever clipped or hard to see. */
    QPushButton {{
        background-color: {t['accent']};
        color: {t['accent_text']};
        border: 1px solid {t['accent']};
        border-radius: 9px;
        padding: 9px 18px;
        font-weight: 700;
        font-size: 13px;
        min-height: 20px;
        min-width: 86px;
    }}
    QPushButton:hover   {{ background-color: {t['accent']}; border: 1px solid {t['text']}; }}
    QPushButton:pressed {{ padding-top: 10px; padding-bottom: 8px; }}
    QPushButton:disabled {{
        background-color: {t['glass']};
        color: {t['subtext']};
        border: 1px solid {t['border']};
    }}
    QPushButton#SecondaryButton {{
        background-color: {t['glass']};
        border: 1px solid {t['edge']};
        color: {t['text']};
        font-weight: 600;
    }}
    QPushButton#SecondaryButton:hover {{ background-color: {t['hover']}; border: 1px solid {t['accent']}; }}
    QPushButton#SecondaryButton:checked {{
        background-color: {t['accent']}; color: {t['accent_text']}; border: 1px solid {t['accent']};
    }}
    QPushButton#DangerButton {{
        background-color: {WARNING_RED}; color: #ffffff; border: 1px solid {WARNING_RED};
    }}
    QPushButton#SuccessButton {{
        background-color: {SUCCESS_GREEN}; color: #ffffff; border: 1px solid {SUCCESS_GREEN};
    }}
    /* Compact buttons living inside table rows - smaller, still legible. */
    QPushButton#RowButton {{
        padding: 0px 10px;
        font-size: 12px;
        font-weight: 700;
        min-width: 0px;
        min-height: 0px;
        border-radius: 8px;
    }}
    QPushButton#RowButtonGhost {{
        padding: 0px 10px;
        font-size: 12px;
        font-weight: 600;
        min-width: 0px;
        min-height: 0px;
        border-radius: 8px;
        background-color: {t['glass']};
        border: 1px solid {t['edge']};
        color: {t['text']};
    }}
    QPushButton#RowButtonGhost:hover {{ background-color: {t['hover']}; border: 1px solid {t['accent']}; }}
    QPushButton#RowButtonGhost:disabled {{ color: {t['subtext']}; border: 1px solid {t['border']}; }}
    QPushButton#RowButtonDanger {{
        padding: 0px 10px;
        font-size: 12px;
        font-weight: 700;
        min-width: 0px;
        min-height: 0px;
        border-radius: 8px;
        background-color: {WARNING_RED};
        border: 1px solid {WARNING_RED};
        color: #ffffff;
    }}
    QPushButton#RowButtonDanger:hover {{ background-color: #c33249; border: 1px solid #c33249; }}
    QPushButton#RowButtonDanger:disabled {{ background-color: {t['glass']}; color: {t['subtext']}; border: 1px solid {t['border']}; }}

    /* -------------------------------------------------------- inputs */
    QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit, QDoubleSpinBox, QSpinBox {{
        background-color: {t['input_bg']};
        border: 1px solid {t['border']};
        border-radius: 9px;
        padding: 8px 10px;
        color: {t['text']};
        min-height: 20px;
        selection-background-color: {t['accent']};
        selection-color: {t['accent_text']};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus,
    QTextEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
        border: 1px solid {t['accent']};
        background-color: {t['hover']};
    }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {t['subtext']}; }}

    /* Dropdown boxes: a visible arrow button on the right, and a themed
       list that is always opaque (never see-through, never native). */
    QComboBox {{ padding-right: 36px; combobox-popup: 0; }}
    QComboBox::drop-down, QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 30px;
        border: none;
        border-left: 1px solid {t['border']};
        border-top-right-radius: 9px;
        border-bottom-right-radius: 9px;
        background: transparent;
    }}
    QComboBox::down-arrow, QDateEdit::down-arrow {{
        image: {down};
        width: 14px;
        height: 14px;
    }}
    QComboBoxPrivateContainer {{
        background-color: {t['surface']};
        border: 1px solid {t['edge']};
        border-radius: 8px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['surface']};
        color: {t['text']};
        border: 1px solid {t['edge']};
        border-radius: 8px;
        selection-background-color: {t['accent']};
        selection-color: {t['accent_text']};
        outline: 0;
        padding: 4px;
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 30px;
        padding: 2px 10px;
        border-radius: 6px;
        color: {t['text']};
        background-color: transparent;
    }}
    QComboBox QAbstractItemView::item:selected,
    QComboBox QAbstractItemView::item:hover {{
        background-color: {t['accent']};
        color: {t['accent_text']};
    }}

    /* Date / time / number boxes: real up-down buttons with arrows. */
    QDateEdit {{ padding-right: 36px; }}
    QTimeEdit, QSpinBox, QDoubleSpinBox {{ padding-right: 34px; }}
    QTimeEdit::up-button, QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 28px;
        border: none;
        border-left: 1px solid {t['border']};
        border-top-right-radius: 9px;
        background: transparent;
    }}
    QTimeEdit::down-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 28px;
        border: none;
        border-left: 1px solid {t['border']};
        border-bottom-right-radius: 9px;
        background: transparent;
    }}
    QTimeEdit::up-button:hover, QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QTimeEdit::down-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {t['hover']};
    }}
    QTimeEdit::up-arrow, QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: {up}; width: 12px; height: 12px;
    }}
    QTimeEdit::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: {down}; width: 12px; height: 12px;
    }}

    /* Calendar that pops out of the date box. */
    QCalendarWidget QWidget {{
        background-color: {t['surface']};
        color: {t['text']};
    }}
    QCalendarWidget QToolButton {{
        background-color: transparent;
        color: {t['text']};
        border: none;
        border-radius: 6px;
        padding: 6px 10px;
        font-weight: 700;
        min-width: 0px;
        min-height: 0px;
    }}
    QCalendarWidget QToolButton:hover {{ background-color: {t['hover']}; }}
    QCalendarWidget QMenu {{ background-color: {t['surface']}; color: {t['text']}; }}
    QCalendarWidget QSpinBox {{ padding: 2px 6px; min-height: 0px; }}
    QCalendarWidget QAbstractItemView:enabled {{
        background-color: {t['surface']};
        color: {t['text']};
        selection-background-color: {t['accent']};
        selection-color: {t['accent_text']};
        outline: 0;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {t['subtext']}; }}
    QCalendarWidget QTableView {{
        alternate-background-color: {t['surface']};
        background-color: {t['surface']};
    }}
    QCalendarWidget #qt_calendar_navigationbar {{
        background-color: {t['surface']};
        border-bottom: 1px solid {t['edge']};
        min-height: 34px;
    }}
    QCalendarWidget QToolButton::menu-indicator {{ image: {down}; width: 10px; height: 10px; }}
    QCheckBox {{ spacing: 8px; background: transparent; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px; border-radius: 5px;
        border: 1px solid {t['border']}; background: {t['input_bg']};
    }}
    QCheckBox::indicator:checked {{ background: {t['accent']}; border: 1px solid {t['accent']}; }}

    /* -------------------------------------------------------- tables */
    QTableWidget {{
        background-color: {t['glass']};
        alternate-background-color: {t['hover']};
        gridline-color: {t['border']};
        border: 1px solid {t['edge']};
        border-radius: 14px;
        padding: 2px;
    }}
    QTableWidget::item {{ padding: 6px 8px; border: none; }}
    QHeaderView {{ background: transparent; }}
    QHeaderView::section {{
        background-color: {t['sidebar']};
        color: {t['sidebar_subtext']};
        padding: 10px 8px;
        border: none;
        border-bottom: 1px solid {t['edge']};
        font-weight: 700;
        font-size: 11px;
        letter-spacing: 0.4px;
    }}
    QHeaderView::section:first {{ border-top-left-radius: 12px; }}
    QHeaderView::section:last  {{ border-top-right-radius: 12px; }}
    QTableWidget::item:selected {{ background-color: {t['accent']}; color: {t['accent_text']}; }}
    QTableCornerButton::section {{ background-color: {t['sidebar']}; border: none; }}

    /* ---------------------------------------------------------- tabs */
    QTabWidget::pane {{
        border: 1px solid {t['edge']};
        border-radius: 14px;
        background-color: {t['glass']};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t['subtext']};
        padding: 9px 20px;
        border: 1px solid transparent;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        margin-right: 4px;
        font-weight: 600;
        min-width: 80px;
    }}
    QTabBar::tab:hover {{ background: {t['hover']}; color: {t['text']}; }}
    QTabBar::tab:selected {{
        background: {t['accent']};
        color: {t['accent_text']};
        font-weight: 700;
        border: 1px solid {t['accent']};
    }}

    /* ------------------------------------------------------- badges */
    QLabel#WarningBadge {{
        background-color: {WARNING_RED}; color: #ffffff;
        border-radius: 8px; padding: 4px 10px; font-weight: 800; font-size: 11px;
    }}
    QLabel#ClearBadge {{
        background-color: {SUCCESS_GREEN}; color: #ffffff;
        border: 1px solid {SUCCESS_GREEN};
        border-radius: 9px; padding: 6px 14px;
        font-weight: 800; font-size: 13px; letter-spacing: 0.5px;
    }}
    QLabel#DueBadge {{
        background-color: {t['glass']}; color: {t['text']};
        border: 1px solid {t['edge']};
        border-radius: 9px; padding: 6px 14px; font-weight: 700; font-size: 13px;
    }}
    QLabel#FreeBadge {{
        background-color: {t['glass']}; color: {t['subtext']};
        border: 1px solid {t['edge']};
        border-radius: 8px; padding: 3px 10px; font-weight: 700; font-size: 11px;
    }}
    QLabel#ErrorText   {{ color: {WARNING_RED}; font-size: 12px; background: transparent; }}
    QLabel#SuccessText {{ color: {SUCCESS_GREEN}; font-size: 12px; font-weight: 700; background: transparent; }}
    QLabel#HintText    {{ color: {t['subtext']}; font-size: 11px; background: transparent; }}

    /* ------------------------------------------------------ scrollbars */
    QScrollBar:vertical {{
        background: transparent; width: 11px; margin: 4px 2px 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['edge']}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t['accent']}; }}
    QScrollBar:horizontal {{
        background: transparent; height: 11px; margin: 2px 4px 2px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t['edge']}; border-radius: 5px; min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {t['accent']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ------------------------------------------------------ list/misc */
    QListWidget {{
        background-color: {t['glass']};
        border: 1px solid {t['edge']};
        border-radius: 12px;
        padding: 4px;
    }}
    QListWidget::item {{ padding: 7px 10px; border-radius: 8px; }}
    QListWidget::item:selected {{ background: {t['accent']}; color: {t['accent_text']}; }}
    QMenu {{
        background-color: {t['surface']}; border: 1px solid {t['edge']};
        border-radius: 10px; padding: 6px;
    }}
    QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background-color: {t['accent']}; color: {t['accent_text']}; }}
    QMessageBox {{ background-color: {t['surface']}; }}
    QMessageBox QPushButton {{ min-width: 92px; }}
    QProgressBar {{
        border: 1px solid {t['edge']}; border-radius: 8px;
        background: {t['glass']}; text-align: center; height: 16px;
    }}
    QProgressBar::chunk {{ background-color: {t['accent']}; border-radius: 7px; }}
    """
