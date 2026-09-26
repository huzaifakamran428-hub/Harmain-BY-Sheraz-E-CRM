"""
Quick standalone test for your saved Email (SMTP) settings.

Run from the project folder:
    python test_email.py your-address@example.com

It reads whatever you saved in Settings -> Email inside the app and
tries to send one real test email to the address you give it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from infrastructure.db import initialize_database
from application.settings_service import SettingsService
from infrastructure.notification_service import EmailNotifier, SmtpSettings
from infrastructure.email_templates import build_reminder_email, find_logo_path
from domain.models import Pilgrim, Gender, PilgrimStatus
from datetime import date, time, timedelta


def _sample_pilgrim() -> Pilgrim:
    return Pilgrim(
        id=None, party_id=None, serial_number=1,
        permit_date=date.today() + timedelta(days=1), permit_time=time(9, 30),
        name="Test Pilgrim", gender=Gender.MALE, email="test@example.com",
        password="Test111@", charge=200.0, status=PilgrimStatus.ACTIVE,
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_email.py your-address@example.com")
        sys.exit(1)

    to_address = sys.argv[1]

    initialize_database()
    settings = SettingsService().get_all()

    smtp = SmtpSettings(
        host=settings["smtp_host"],
        port=int(settings["smtp_port"] or 587),
        username=settings["smtp_username"],
        password=settings["smtp_password"],
        sender=settings["smtp_sender"],
        use_tls=settings["smtp_use_tls"] == "1",
    )

    print(f"Host:     {smtp.host}")
    print(f"Port:     {smtp.port}")
    print(f"Username: {smtp.username}")
    print(f"Sender:   {smtp.sender}")
    print(f"TLS:      {smtp.use_tls}")
    print(f"Configured: {smtp.configured}")
    print()

    if not smtp.configured:
        print("Email settings are incomplete. Fill in Settings -> Email in the app first.")
        sys.exit(1)

    print(f"Sending test email to {to_address} ...")
    pilgrim = _sample_pilgrim()
    with_logo = SettingsService().reminder_email_logo()
    html_body, plain_body = build_reminder_email(
        pilgrim, contact_number=settings.get("business_contact_number", ""),
        brand_name=settings.get("business_name") or "HaramaIn by Sheraz",
        include_logo=with_logo,
    )
    logo = find_logo_path() if with_logo else None
    print(f"Logo found: {logo if logo else '(none - using text header)'}")
    ok, reason = EmailNotifier(smtp).send_html(
        to_address,
        "HaramaIn by Sheraz - Test Reminder Email",
        html_body, plain_body, logo_path=logo,
    )

    if ok:
        print("SUCCESS - check the inbox (and spam folder) of", to_address)
    else:
        print("FAILED:", reason)
        print()
        print("Common causes:")
        print("- Wrong app password (must be the 16-character Gmail App Password, not your normal password)")
        print("- 2-Step Verification not enabled on the Gmail account")
        print("- Wrong host/port (Gmail: smtp.gmail.com, port 587, TLS on)")
        print("- Firewall/antivirus blocking outbound port 587")


if __name__ == "__main__":
    main()
