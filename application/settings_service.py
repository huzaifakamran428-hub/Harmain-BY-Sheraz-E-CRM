from __future__ import annotations

from infrastructure.repositories import SettingsRepository, AuditRepository
import re

from core.config import (
    DEFAULT_CHARGE_PKR, DEFAULT_TRANSFER_HOURS, DEFAULT_REMINDER_DAYS, DEFAULT_THEME_NAME,
    DEFAULT_UPCOMING_COLOR,
)

_DEFAULTS = {
    "theme": DEFAULT_THEME_NAME,
    "default_charge": str(DEFAULT_CHARGE_PKR),
    "transfer_hours": str(DEFAULT_TRANSFER_HOURS),
    "reminder_days": str(DEFAULT_REMINDER_DAYS),
    "upcoming_color": DEFAULT_UPCOMING_COLOR,
    "business_contact_number": "",
    "business_name": "HaramaIn by Sheraz",
    "bill_subtitle": "Riyazul Jannah Permit Slip",
    "bill_footer_text": "Thank you for choosing HaramaIn",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_username": "",
    "smtp_password": "",
    "smtp_sender": "",
    "reminder_recipient": "",
    "reminder_email_logo": "0",
    "smtp_use_tls": "1",
    "whatsapp_api_url": "",
    "whatsapp_api_token": "",
    "whatsapp_sender_id": "",
    "scheduler_interval_minutes": "1",
}


class SettingsService:
    def __init__(self):
        self.repo = SettingsRepository()
        self.audit = AuditRepository()

    def get_all(self) -> dict:
        stored = self.repo.get_all()
        merged = dict(_DEFAULTS)
        merged.update(stored)
        return merged

    def get(self, key: str) -> str:
        return self.repo.get(key, _DEFAULTS.get(key, ""))

    def upcoming_color(self) -> str:
        """Highlight colour for pilgrims inside the reminder window (#rrggbb)."""
        value = (self.get("upcoming_color") or "").strip()
        return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else DEFAULT_UPCOMING_COLOR

    def reminder_recipient(self) -> str:
        """
        Where permit reminders are sent: the administrator's OWN address
        (Settings -> Email -> "Send Reminders To"). Reminders are never sent
        to pilgrims. If that box is empty, the sender address is used, so
        the reminder lands in the administrator's own inbox.
        """
        return ((self.get("reminder_recipient") or "").strip()
                or (self.get("smtp_sender") or "").strip())

    def reminder_email_logo(self) -> bool:
        """Whether reminder emails carry the logo. Off by default - they only go to the administrator."""
        return (self.get("reminder_email_logo") or "0") == "1"

    def reminder_days(self) -> int:
        try:
            return max(0, int(float(self.get("reminder_days"))))
        except (TypeError, ValueError):
            return DEFAULT_REMINDER_DAYS

    def set(self, key: str, value: str, actor: str = "") -> None:
        self.repo.set(key, value)
        if actor:
            from domain.models import AuditEntry
            from datetime import datetime
            self.audit.log(AuditEntry(id=None, user=actor, action="Update", entity="Settings",
                                       entity_id=None, timestamp=datetime.now(), details=f"{key} updated"))

    def set_many(self, values: dict, actor: str = "") -> None:
        for k, v in values.items():
            self.repo.set(k, str(v))
        if actor:
            from domain.models import AuditEntry
            from datetime import datetime
            self.audit.log(AuditEntry(id=None, user=actor, action="Update", entity="Settings",
                                       entity_id=None, timestamp=datetime.now(),
                                       details=f"Updated: {', '.join(values.keys())}"))
