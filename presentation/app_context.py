"""
Holds one instance of every application service so screens don't each
construct their own repositories, plus small UI helper functions for
translating ApplicationError -> user-friendly dialogs (SRS 16.1/16.10).
"""
from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QWidget

from core.exceptions import ApplicationError
from core.logging_setup import get_logger, new_error_reference
from application.auth_service import AuthService
from application.party_service import PartyService
from application.pilgrim_service import PilgrimService
from application.payment_service import PaymentService
from application.free_account_service import FreeAccountService
from application.report_service import ReportService
from application.bill_service import BillService
from application.settings_service import SettingsService
from application.document_service import DocumentService
from application.reminder_service import ReminderService
from application.export_service import ExportService
from infrastructure.notification_service import DesktopNotifier
from infrastructure.backup_service import BackupService

logger = get_logger("ui")


class AppContext:
    def __init__(self):
        self.auth = AuthService()
        self.parties = PartyService()
        self.pilgrims = PilgrimService()
        self.payments = PaymentService()
        self.free_accounts = FreeAccountService()
        self.reports = ReportService()
        self.bills = BillService()
        self.settings = SettingsService()
        self.documents = DocumentService()
        self.exports = ExportService()
        self.backups = BackupService()
        self.desktop_notifier = DesktopNotifier()
        self.reminders = ReminderService(desktop_notifier=self.desktop_notifier)

    @property
    def current_username(self) -> str:
        user = self.auth.current_user
        return user.username if user else "system"


def handle_error(parent: QWidget, error: Exception, title: str = "Error") -> None:
    """
    Central place that maps a known ApplicationError to its safe
    user_message, or - for anything unexpected - logs full details
    under a short reference id and shows only a generic message
    (SRS 16.10 / 16.4: never expose raw stack traces to the user).
    """
    if isinstance(error, ApplicationError):
        logger.warning("%s: %s", type(error).__name__, error)
        QMessageBox.warning(parent, title, error.user_message)
    else:
        ref = new_error_reference()
        logger.error("Unexpected error [ref=%s]: %s", ref, error, exc_info=True)
        QMessageBox.critical(
            parent, title,
            f"Something went wrong. Your data was not intentionally changed. "
            f"Please try again. Error ID: {ref}",
        )
