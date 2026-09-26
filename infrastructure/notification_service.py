"""
Notification delivery (SRS 8 + 20.6). Three channels:

- Desktop: system tray balloon notification (always available, works on
  Windows and macOS via Qt's native tray icon support).
- Email: standard SMTP, configured by the administrator in Settings.
  Off by default until SMTP settings are filled in.
- WhatsApp: the SRS requires an "authorized provider or official
  WhatsApp Business API" and explicitly forbids unauthorized
  automation/scraping. There is no such official API this application
  can be wired to out of the box - it requires a business account,
  provider credentials and approved message templates that only the
  business owner can obtain. This module therefore exposes a clean
  WhatsAppProvider interface (send/…) with a safe no-op default
  implementation; plugging in a real provider (e.g. Twilio WhatsApp,
  Meta Cloud API, 360dialog) later is a one-file change here, not an
  application rewrite.

Every send attempt is recorded through NotificationRepository so
failures never crash the app and delivery status is always visible in
the Notifications screen (FR-REM, 20.6 acceptance criteria).
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText
from dataclasses import dataclass
from pathlib import Path

from core.logging_setup import get_logger

logger = get_logger(__name__)


def _build_ssl_context() -> ssl.SSLContext:
    """
    Builds the TLS context used for SMTP. Prefers certifi's bundled CA
    certificates over the OS default store: on macOS, Python installed
    via python.org (and PyInstaller-built apps) often can't see the
    system's trusted certificates, which makes every TLS connection fail
    with CERTIFICATE_VERIFY_FAILED even though nothing is actually wrong.
    Falls back to the normal default context if certifi isn't installed.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        logger.info("certifi not installed; using system default certificate store for SMTP TLS.")
        return ssl.create_default_context()


@dataclass
class SmtpSettings:
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    sender: str = ""
    use_tls: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.sender)


class DesktopNotifier:
    """Thin wrapper so presentation code doesn't import QSystemTrayIcon directly everywhere."""

    def __init__(self, tray_icon=None):
        self._tray_icon = tray_icon  # a QSystemTrayIcon instance, set by main_window at startup

    def set_tray_icon(self, tray_icon) -> None:
        self._tray_icon = tray_icon

    def notify(self, title: str, message: str) -> bool:
        if self._tray_icon is None:
            logger.info("Desktop notification (no tray icon yet): %s - %s", title, message)
            return False
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon
            self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 8000)
            return True
        except Exception as e:
            logger.warning("Desktop notification failed: %s", e)
            return False


class EmailNotifier:
    def __init__(self, settings: SmtpSettings):
        self.settings = settings

    def send(self, to_address: str, subject: str, body: str) -> tuple[bool, str]:
        """Plain-text send - kept for simple/system messages."""
        return self._send(to_address, subject, plain_body=body, html_body=None, logo_path=None)

    def send_html(self, to_address: str, subject: str, html_body: str, plain_body: str,
                   logo_path=None) -> tuple[bool, str]:
        """Rich HTML send used for the branded booking-confirmation reminder."""
        return self._send(to_address, subject, plain_body=plain_body, html_body=html_body, logo_path=logo_path)

    def _send(self, to_address: str, subject: str, plain_body: str,
               html_body: str | None, logo_path) -> tuple[bool, str]:
        if not self.settings.configured:
            return False, "Email is not configured in Settings."
        if not to_address:
            return False, "No recipient email address."
        try:
            if html_body:
                from email.mime.multipart import MIMEMultipart
                from email.mime.image import MIMEImage

                msg = MIMEMultipart("related")
                msg["Subject"] = subject
                msg["From"] = self.settings.sender
                msg["To"] = to_address

                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(plain_body, "plain"))
                alt.attach(MIMEText(html_body, "html"))
                msg.attach(alt)

                if logo_path is not None:
                    try:
                        with open(logo_path, "rb") as f:
                            image = MIMEImage(f.read())
                        image.add_header("Content-ID", "<brand_logo>")
                        image.add_header("Content-Disposition", "inline", filename=Path(logo_path).name)
                        msg.attach(image)
                    except OSError as e:
                        logger.warning("Could not attach logo %s: %s", logo_path, e)
            else:
                msg = MIMEText(plain_body)
                msg["Subject"] = subject
                msg["From"] = self.settings.sender
                msg["To"] = to_address

            context = _build_ssl_context()
            with smtplib.SMTP(self.settings.host, self.settings.port, timeout=15) as server:
                if self.settings.use_tls:
                    server.starttls(context=context)
                server.login(self.settings.username, self.settings.password)
                server.sendmail(self.settings.sender, [to_address], msg.as_string())
            return True, ""
        except Exception as e:
            logger.warning("Email send failed to %s: %s", to_address, e)
            return False, str(e)


class WhatsAppProvider:
    """
    Interface for an authorized WhatsApp Business provider. Replace
    `send` with a real HTTP call to your provider (Meta Cloud API,
    Twilio, 360dialog, etc.) using credentials from Settings. The
    default implementation intentionally does nothing but report itself
    as unconfigured, so the app never pretends a message was delivered.
    """

    def __init__(self, api_url: str = "", api_token: str = "", sender_id: str = ""):
        self.api_url = api_url
        self.api_token = api_token
        self.sender_id = sender_id

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_token)

    def send(self, to_number: str, message: str) -> tuple[bool, str]:
        if not self.configured:
            return False, "WhatsApp provider is not configured in Settings."
        if not to_number:
            return False, "No WhatsApp number on file for this pilgrim."
        # --- Wire up your authorized provider's HTTP API here. ---
        # Example (Meta Cloud API pseudo-code):
        #   requests.post(self.api_url, headers={"Authorization": f"Bearer {self.api_token}"},
        #                 json={"to": to_number, "type": "text", "text": {"body": message}}, timeout=15)
        logger.info("WhatsApp send skipped (no provider wired up) -> %s", to_number)
        return False, "No WhatsApp provider is wired up yet. See infrastructure/notification_service.py."
