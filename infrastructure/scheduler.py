"""
Background scheduler (SRS 4.9, 4.10, 16.7). Runs on the Qt event loop
via QTimer (no separate OS service required - works identically on
Windows and macOS as long as the app itself is running), periodically:

1. Sweeping for pilgrims eligible for automatic 6-hour transfer.
2. Checking for pilgrims entering the 2-day reminder window and
   dispatching notifications across all configured channels.
3. Mirroring the database and uploaded files into any cloud-sync
   folder (iCloud Drive / Google Drive) the administrator has enabled
   in Settings -> Backup & Sync.

All three operations are already idempotent/duplicate-safe (see
application/free_account_service.py, reminder_service.py, and
infrastructure/backup_service.py, which always overwrites the same
backup files rather than accumulating new ones), so re-running this
timer at any interval is always safe.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.logging_setup import get_logger

logger = get_logger(__name__)


class BackgroundScheduler(QObject):
    transfer_completed = pyqtSignal(int)     # number of pilgrims moved
    reminders_sent = pyqtSignal(int)         # number of reminders dispatched
    backup_finished = pyqtSignal(list)       # list[BackupResult]
    tick_failed = pyqtSignal(str)

    def __init__(self, ctx, interval_minutes: int = 5, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.set_interval(interval_minutes)

    def set_interval(self, minutes: int) -> None:
        minutes = max(1, int(minutes))
        self.timer.setInterval(minutes * 60 * 1000)

    def start(self) -> None:
        self.timer.start()
        # run once immediately on startup as well
        self._tick()

    def stop(self) -> None:
        self.timer.stop()

    def run_soon(self, delay_ms: int = 800) -> None:
        """
        Do a check right after something changed (a pilgrim was added or edited, the email
        settings were saved) instead of waiting for the next timer tick. The short delay lets
        the dialog close first, so the screen never freezes while a window is still open.
        The regular timer keeps running unchanged.
        """
        QTimer.singleShot(delay_ms, self._tick)

    def _tick(self) -> None:
        try:
            moved = self.ctx.free_accounts.run_six_hour_transfer_sweep(actor="system")
            if moved:
                logger.info("Background sweep moved %d pilgrim(s) to Free Account", moved)
                self.transfer_completed.emit(moved)
        except Exception as e:
            logger.error("Background transfer sweep failed: %s", e)
            self.tick_failed.emit(str(e))

        try:
            sent = self.ctx.reminders.check_and_send_reminders()
            if sent:
                logger.info("Background sweep sent %d reminder(s)", sent)
                self.reminders_sent.emit(sent)
        except Exception as e:
            logger.error("Background reminder check failed: %s", e)
            self.tick_failed.emit(str(e))

        try:
            # only_enabled=True: a path saved but left unchecked in Settings
            # is never used automatically - the administrator must switch it on.
            results = self.ctx.backups.backup_now(only_enabled=True)
            if results:
                self.backup_finished.emit(results)
                for r in results:
                    if not r.success:
                        logger.warning("Automatic backup to %s failed: %s", r.label, r.message)
        except Exception as e:
            logger.error("Background backup failed: %s", e)
            self.tick_failed.emit(str(e))
