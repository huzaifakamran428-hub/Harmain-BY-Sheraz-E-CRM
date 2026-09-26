"""
Two-day reminder orchestration (SRS 4.10, 8, 20.6). Called periodically
by the background scheduler. Reminders are EMAIL ONLY and go to the
administrator (Settings -> Email -> "Send Reminders To"), never to the
pilgrim and never as a desktop pop-up.
Duplicate-safe: one notification row per (pilgrim, type, channel) is
enough to prevent re-sending unless explicitly reset.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from domain.models import NotificationRecord, NotificationChannel, NotificationStatus
from domain.rules import is_within_reminder_window, permit_datetime, check_email
from infrastructure.repositories import PilgrimRepository, NotificationRepository, PartyRepository
from infrastructure.notification_service import DesktopNotifier, EmailNotifier, SmtpSettings
from infrastructure.email_templates import build_reminder_email, find_logo_path
from application.settings_service import SettingsService
from core.logging_setup import get_logger

logger = get_logger(__name__)

REMINDER_TYPE = "TwoDayReminder"

# A reminder that could not be sent (no internet, wrong SMTP password, ...) is retried
# automatically, but not on every 1-minute tick: at most this often, on the SAME row.
RETRY_FAILED_AFTER = timedelta(minutes=10)


class ReminderService:
    def __init__(self, desktop_notifier: Optional[DesktopNotifier] = None):
        self.pilgrims = PilgrimRepository()
        self.parties = PartyRepository()
        self.notifications = NotificationRepository()
        self.settings = SettingsService()
        self.desktop = desktop_notifier or DesktopNotifier()
        self._last_attempt: dict[int, datetime] = {}

    def check_and_send_reminders(self, now: Optional[datetime] = None, force: bool = False) -> int:
        """
        Email the ADMINISTRATOR once for every pilgrim whose permit is inside
        the reminder window. Nothing is sent to the pilgrim, and there is no
        desktop pop-up or WhatsApp message: the administrator is the one who
        accepts the booking, so the administrator is the one who is reminded.

        Runs by itself on every scheduler tick. ``force=True`` (the "Check Reminders
        Now" button) also retries a failed reminder straight away.
        """
        now = now or datetime.now()
        reminder_days = int(self.settings.get("reminder_days"))
        sent_count = 0
        for pilgrim in self.pilgrims.list_upcoming_active():
            if not is_within_reminder_window(pilgrim.permit_date, pilgrim.permit_time, now, reminder_days):
                continue
            pdt = permit_datetime(pilgrim.permit_date, pilgrim.permit_time)
            sent_count += self._send_email(pilgrim, pdt, now=now, force=force)
        return sent_count

    def clear_retry_throttle(self) -> None:
        """Forget earlier failed attempts so the next automatic check retries straight away."""
        self._last_attempt.clear()

    def _already_notified(self, pilgrim_id: int, channel: NotificationChannel, pdt) -> bool:
        return self.notifications.exists_pending_or_sent(pilgrim_id, REMINDER_TYPE, channel, pdt)

    def _send_email(self, pilgrim, pdt, now: Optional[datetime] = None, force: bool = False) -> int:
        now = now or datetime.now()
        if self._already_notified(pilgrim.id, NotificationChannel.EMAIL, pdt):
            return 0
        last = self._last_attempt.get(pilgrim.id)
        if not force and last is not None and now - last < RETRY_FAILED_AFTER:
            return 0                                   # failed a moment ago - try again later
        self._last_attempt[pilgrim.id] = now

        settings = self.settings.get_all()
        recipient = self.settings.reminder_recipient()
        record_id = self._record_for_attempt(pilgrim, pdt)

        if not recipient or check_email(recipient)[0] == "error":
            self.notifications.mark_failed(
                record_id, "No valid 'Send Reminders To' address in Settings -> Email.")
            logger.info("Reminder for pilgrim %s not sent: no valid administrator address.", pilgrim.id)
            return 0

        smtp = SmtpSettings(
            host=settings["smtp_host"], port=int(settings["smtp_port"] or 587),
            username=settings["smtp_username"], password=settings["smtp_password"],
            sender=settings["smtp_sender"], use_tls=settings["smtp_use_tls"] == "1",
        )
        with_logo = self.settings.reminder_email_logo()
        party = self.parties.get(pilgrim.party_id) if pilgrim.party_id is not None else None
        party_name = party.name if party else ""
        html_body, plain_body = build_reminder_email(
            pilgrim, contact_number=settings.get("business_contact_number", ""),
            brand_name=settings.get("business_name") or "HaramaIn by Sheraz",
            include_logo=with_logo, party_name=party_name,
        )
        when = pilgrim.permit_date.strftime("%d %b %Y") if pilgrim.permit_date else ""
        subject = f"Permit Reminder - {pilgrim.name}"
        if party_name:
            subject += f" - Party: {party_name}"
        subject += f" ({when})" if when else ""
        ok, reason = EmailNotifier(smtp).send_html(
            recipient,
            subject.strip(),
            html_body, plain_body, logo_path=find_logo_path() if with_logo else None,
        )
        if ok:
            self.notifications.mark_sent(record_id)
            self._last_attempt.pop(pilgrim.id, None)
            return 1
        self.notifications.mark_failed(record_id, reason)
        logger.info("Email reminder not sent for pilgrim %s: %s", pilgrim.id, reason)
        return 0

    def _record_for_attempt(self, pilgrim, pdt) -> int:
        """Reuse this reminder's earlier Failed row (a retry), or open a new one."""
        existing = self.notifications.latest_failed_id(pilgrim.id, REMINDER_TYPE, NotificationChannel.EMAIL)
        if existing:
            return existing
        return self.notifications.create(NotificationRecord(
            id=None, pilgrim_id=pilgrim.id, type=REMINDER_TYPE, channel=NotificationChannel.EMAIL,
            scheduled_for=pdt,
        )).id

    @staticmethod
    def _days_left(pdt) -> int:
        return max(0, (pdt.date() - datetime.now().date()).days)
