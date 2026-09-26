"""
HaramaIn by Sheraz - Riyazul Jannah Permit & Pilgrim Management System

Entry point. Run with:  python main.py
"""
from __future__ import annotations

import sys
import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from core.config import get_logo_path
from core.logging_setup import setup_logging, get_logger, new_error_reference
from infrastructure.db import initialize_database
from presentation.app_context import AppContext
from presentation.themes import build_stylesheet
from presentation.login_window import LoginWindow, FirstRunSetupWindow
from presentation.main_window import MainWindow

logger = get_logger("main")


def install_global_exception_hook(app: QApplication):
    """
    SRS 16.1 / 16.10: an unexpected error anywhere must never crash the
    whole application silently - it is logged with a reference id and
    shown to the user as a safe, generic message.
    """
    def hook(exc_type, exc_value, exc_tb):
        ref = new_error_reference()
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Unhandled exception [ref=%s]:\n%s", ref, details)
        try:
            QMessageBox.critical(
                None, "Unexpected Error",
                f"Something went wrong and the last action may not have completed.\n\n"
                f"Your data has not been lost. Please restart if the application seems stuck.\n\n"
                f"Error ID: {ref}",
            )
        except Exception:
            pass

    sys.excepthook = hook


def main():
    setup_logging()
    initialize_database()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    install_global_exception_hook(app)

    # SRS branding: use the business logo as the app icon (taskbar / dock /
    # alt-tab / title bar) instead of Qt's generic default icon. Falls back
    # silently to the platform default if no logo has been provided yet.
    logo_path = get_logo_path()
    if logo_path:
        app_icon = QIcon(str(logo_path))
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)

    ctx = AppContext()
    app.setStyleSheet(build_stylesheet(ctx.settings.get("theme")))

    def backup_on_quit():
        # Best-effort final safety net if the app is actually exiting
        # (e.g. "Quit" from the tray menu) rather than just minimizing.
        try:
            ctx.backups.backup_now(only_enabled=True)
        except Exception:
            logger.exception("Backup on quit failed")

    app.aboutToQuit.connect(backup_on_quit)

    windows = {}  # keep references alive

    def show_main_window():
        main_window = MainWindow(ctx, app)
        windows["main"] = main_window
        main_window.show()
        for key in ("login", "setup"):
            if key in windows:
                windows[key].close()

    if ctx.auth.needs_first_run_setup():
        setup_window = FirstRunSetupWindow(ctx)
        setup_window.setup_complete.connect(lambda _user: show_main_window())
        windows["setup"] = setup_window
        setup_window.show()
    else:
        login_window = LoginWindow(ctx)
        login_window.login_succeeded.connect(lambda _user: show_main_window())
        windows["login"] = login_window
        login_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
