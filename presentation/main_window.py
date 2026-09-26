from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QStackedWidget, QSystemTrayIcon, QMenu, QDialog, QFormLayout, QLineEdit, QMessageBox,
)
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt

from presentation.app_context import AppContext, handle_error
from presentation.themes import build_stylesheet, resolve_theme_name
from presentation.pages.dashboard_page import DashboardPage
from presentation.pages.parties_page import PartiesPage
from presentation.pages.party_detail_page import PartyDetailPage
from presentation.pages.free_account_page import FreeAccountPage
from presentation.pages.reports_page import ReportsPage
from presentation.pages.settings_page import SettingsPage
from presentation.pages.notifications_page import NotificationsPage
from infrastructure.scheduler import BackgroundScheduler
from core.config import APP_VENDOR, get_logo_path
from core.exceptions import ApplicationError


def _make_tray_icon() -> QIcon:
    logo = get_logo_path()
    if logo:
        icon = QIcon(str(logo))
        if not icon.isNull():
            return icon
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor("#d4af37"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor("#141414"))
    font = QFont("Arial", 26, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "H")
    painter.end()
    return QIcon(pixmap)


class ChangePasswordDialog(QDialog):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("New Password", self.new_password)
        form.addRow("Confirm Password", self.confirm_password)
        layout.addLayout(form)
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        layout.addWidget(self.error_label)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _save(self):
        if self.new_password.text() != self.confirm_password.text():
            self.error_label.setText("Passwords do not match.")
            return
        try:
            self.ctx.auth.change_password(self.ctx.auth.current_user, self.new_password.text())
            self.accept()
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Change Password")


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, app):
        super().__init__()
        self.ctx = ctx
        self.app = app
        self.setWindowTitle(f"{APP_VENDOR} - Riyazul Jannah Permit Management")
        self.resize(1180, 760)

        self._build_ui()
        self._apply_theme(self.ctx.settings.get("theme"))
        self._setup_tray()
        self._setup_scheduler()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("GlassRoot")
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 12)
        sidebar_layout.setSpacing(2)

        # ---- logo (when the administrator has provided one)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("LogoHolder")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sidebar_layout.addWidget(self.logo_label)
        self.refresh_logo()

        self.brand_label = QLabel(self._business_name())
        self.brand_label.setObjectName("BrandLabel")
        self.brand_label.setWordWrap(True)
        sub = QLabel("Riyazul Jannah Permits")
        sub.setObjectName("BrandSubLabel")
        sidebar_layout.addWidget(self.brand_label)
        sidebar_layout.addWidget(sub)

        self.nav_buttons: dict[str, QPushButton] = {}
        nav_items = [
            ("dashboard", "Dashboard"),
            ("parties", "Parties"),
            ("free_account", "Free Account"),
            ("reports", "Reports"),
            ("notifications", "Notifications"),
            ("settings", "Settings"),
        ]
        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._navigate(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn
        sidebar_layout.addStretch()

        logout_btn = QPushButton("Logout")
        logout_btn.setMinimumHeight(38)
        logout_btn.setObjectName("SecondaryButton")
        logout_btn.clicked.connect(self._logout)
        sidebar_layout.addWidget(logout_btn)

        credit_label = QLabel("DEVELOPED BY HUZAIFA")
        credit_label.setObjectName("CreditLabel")
        credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(credit_label)

        root_layout.addWidget(sidebar)

        # Stacked pages
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage(self.ctx)
        self.parties_page = PartiesPage(self.ctx)
        self.party_detail_page = PartyDetailPage(self.ctx)
        self.free_account_page = FreeAccountPage(self.ctx)
        self.reports_page = ReportsPage(self.ctx)
        self.settings_page = SettingsPage(self.ctx)
        self.notifications_page = NotificationsPage(self.ctx)

        self.parties_page.party_opened.connect(self._open_party_detail)
        self.dashboard_page.party_requested.connect(self._open_party_detail)
        self.party_detail_page.back_requested.connect(lambda: self._navigate("parties"))
        self.settings_page.theme_changed.connect(self._apply_theme)
        self.settings_page.password_change_requested.connect(self._change_password)
        self.settings_page.branding_changed.connect(self.refresh_branding)
        self.settings_page.scheduler_interval_changed.connect(self._update_scheduler_interval)

        for page in (self.dashboard_page, self.parties_page, self.party_detail_page,
                     self.free_account_page, self.reports_page, self.settings_page,
                     self.notifications_page):
            self.stack.addWidget(page)

        root_layout.addWidget(self.stack, 1)

        self._navigate("dashboard")

    def _navigate(self, key: str):
        page_map = {
            "dashboard": self.dashboard_page,
            "parties": self.parties_page,
            "free_account": self.free_account_page,
            "reports": self.reports_page,
            "settings": self.settings_page,
            "notifications": self.notifications_page,
        }
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        page = page_map.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            if hasattr(page, "refresh"):
                page.refresh()

    def _open_party_detail(self, party_id: int, party_name: str):
        self.party_detail_page.open_party(party_id, party_name)
        for btn in self.nav_buttons.values():
            btn.setChecked(False)
        self.stack.setCurrentWidget(self.party_detail_page)

    def _apply_theme(self, theme_name: str):
        self.app.setStyleSheet(build_stylesheet(resolve_theme_name(theme_name)))

    def _business_name(self) -> str:
        try:
            return self.ctx.settings.get("business_name") or APP_VENDOR
        except Exception:
            return APP_VENDOR

    def refresh_logo(self):
        """Redraw the sidebar logo - called at start-up and after an import."""
        logo = get_logo_path()
        if not logo:
            self.logo_label.clear()
            self.logo_label.setFixedHeight(0)
            return
        pixmap = QPixmap(str(logo))
        if pixmap.isNull():
            self.logo_label.clear()
            self.logo_label.setFixedHeight(0)
            return
        self.logo_label.setFixedHeight(76)
        self.logo_label.setPixmap(pixmap.scaled(
            176, 62,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def refresh_branding(self):
        """Re-read business name + logo after Settings -> Branding is saved."""
        self.refresh_logo()
        self.brand_label.setText(self._business_name())
        self.tray_icon.setIcon(_make_tray_icon())
        self.tray_icon.setToolTip(self._business_name())

    def _change_password(self):
        dialog = ChangePasswordDialog(self.ctx, parent=self)
        if dialog.exec():
            QMessageBox.information(self, "Password Changed", "Your password has been updated.")

    def _logout(self):
        choice = QMessageBox.question(
            self, "Logout", "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if choice == QMessageBox.StandardButton.Yes:
            self.ctx.auth.logout()
            self.app.quit()

    # --------------------------------------------------------- Tray/Scheduler
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(_make_tray_icon(), self)
        self.tray_icon.setToolTip(self._business_name())
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        self.ctx.desktop_notifier.set_tray_icon(self.tray_icon)

    def _update_scheduler_interval(self, minutes: int):
        if hasattr(self, "scheduler"):
            self.scheduler.set_interval(minutes)

    def _setup_scheduler(self):
        interval = int(self.ctx.settings.get("scheduler_interval_minutes") or 1)
        self.scheduler = BackgroundScheduler(self.ctx, interval_minutes=interval, parent=self)
        self.scheduler.transfer_completed.connect(self._on_auto_transfer)
        self.scheduler.reminders_sent.connect(lambda n: self.notifications_page.refresh())
        self.scheduler.backup_finished.connect(self._on_backup_finished)
        # Do not wait for the next timer tick: check as soon as a pilgrim is saved or the email settings change.
        self.party_detail_page.pilgrim_saved.connect(self.scheduler.run_soon)
        self.settings_page.email_settings_saved.connect(self._on_email_settings_saved)
        self.scheduler.start()

    def _on_email_settings_saved(self):
        self.ctx.reminders.clear_retry_throttle()
        self.scheduler.run_soon()

    def _on_auto_transfer(self, moved: int):
        """A background sweep moved pilgrims - keep every open view honest."""
        self.dashboard_page.refresh()
        self.free_account_page.refresh()
        current = self.stack.currentWidget()
        if current is self.party_detail_page:
            self.party_detail_page.refresh()
        if moved and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                self._business_name(),
                f"{moved} pilgrim(s) moved to the Free Account after the 6-hour rule.",
                QSystemTrayIcon.MessageIcon.Information, 4000,
            )

    def _on_backup_finished(self, results):
        """Only surface a tray notice when a backup actually fails - a silent
        success in the background is the whole point of "automatic"."""
        failed = [r for r in results if not r.success]
        if failed and self.tray_icon.isVisible():
            names = ", ".join(r.label for r in failed)
            self.tray_icon.showMessage(
                self._business_name(),
                f"Backup to {names} failed - check Settings -> Backup & Sync.",
                QSystemTrayIcon.MessageIcon.Warning, 6000,
            )
        if hasattr(self, "settings_page"):
            self.settings_page.refresh_backup_status()

    def closeEvent(self, event):
        # Minimize to tray instead of quitting, so the background scheduler
        # keeps checking reminders/transfers while the app is "running".
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                self._business_name(),
                "Still running in the background for reminders and auto-transfers.",
                QSystemTrayIcon.MessageIcon.Information, 4000,
            )
            event.ignore()
        else:
            event.accept()
