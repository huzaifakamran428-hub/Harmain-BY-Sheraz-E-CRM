"""
Core business rules, kept as pure functions with no side effects so
they can be unit tested directly (SRS 17: "Business rules, balance
calculation, 2-day reminder calculation, 6-hour transfer eligibility,
gender routing and password generation").
"""
from __future__ import annotations

import re
from datetime import datetime, date, time, timedelta
from typing import Optional

from domain.models import Gender, PilgrimStatus
from core.config import DEFAULT_TRANSFER_HOURS, DEFAULT_REMINDER_DAYS, PASSWORD_SUFFIX


def calculate_remaining(charge: float, total_received: float) -> float:
    """Remaining = Charge - Received (FR-PAY-06)."""
    return round((charge or 0.0) - (total_received or 0.0), 2)


def normalize_first_name(full_name: str) -> str:
    """
    Take the first word of a full name and normalise its capitalisation:
    first letter upper-case, every other letter lower-case.

        'MUHAMMAD ALI'  -> 'Muhammad'
        'aYesha khan'   -> 'Ayesha'
        'MUHAMMAD<<ALI' -> 'Muhammad'   (MRZ leftovers are stripped)
    """
    raw = (full_name or "").strip()
    if not raw:
        return ""
    raw = raw.replace("<", " ").replace(".", " ").replace(",", " ")
    first = raw.split()[0] if raw.split() else ""
    letters = re.sub(r"[^A-Za-z]", "", first)
    if not letters:
        return ""
    return letters[0].upper() + letters[1:].lower()


def generate_pilgrim_password(first_name: str) -> str:
    """
    FR-PASS-01/02: password = First name (first letter capital, the rest
    lower-case) + '111@'

        'MUHAMMAD ALI' -> 'Muhammad111@'
        'ayesha'       -> 'Ayesha111@'
        'bilal ahmed'  -> 'Bilal111@'
    """
    cleaned = normalize_first_name(first_name)
    if not cleaned:
        return ""
    return f"{cleaned}{PASSWORD_SUFFIX}"


def permit_datetime(permit_date: Optional[date], permit_time: Optional[time]) -> Optional[datetime]:
    if not permit_date:
        return None
    t = permit_time or time(0, 0)
    return datetime.combine(permit_date, t)


def is_within_reminder_window(
    permit_date: Optional[date],
    permit_time: Optional[time],
    now: Optional[datetime] = None,
    reminder_days: int = DEFAULT_REMINDER_DAYS,
) -> bool:
    """
    FR-REM-02 / 8.1: two calendar days before the permit date/time, the
    pilgrim enters the "upcoming, needs attention" red-warning state.
    True from (permit_datetime - reminder_days) up to the permit datetime itself.
    """
    pdt = permit_datetime(permit_date, permit_time)
    if pdt is None:
        return False
    now = now or datetime.now()
    reminder_point = pdt - timedelta(days=reminder_days)
    return reminder_point <= now <= pdt


def is_eligible_for_transfer(
    permit_date: Optional[date],
    permit_time: Optional[time],
    now: Optional[datetime] = None,
    hours: int = DEFAULT_TRANSFER_HOURS,
) -> bool:
    """
    FR-MOVE-01: six hours or more have passed since permit date/time.
    A pilgrim with no permit date/time is never auto-transferred.
    """
    pdt = permit_datetime(permit_date, permit_time)
    if pdt is None:
        return False
    now = now or datetime.now()
    return now >= pdt + timedelta(hours=hours)


def route_free_status(gender: Gender) -> PilgrimStatus:
    """FR-MOVE-02: gender-based routing into Free Male / Free Female."""
    if gender == Gender.FEMALE:
        return PilgrimStatus.FREE_FEMALE
    return PilgrimStatus.FREE_MALE


def free_status_label(status: PilgrimStatus) -> str:
    return {
        PilgrimStatus.FREE_MALE: "Male",
        PilgrimStatus.FREE_FEMALE: "Female",
    }.get(status, "")


# --------------------------------------------------------------------- email
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'\-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$")

# A mistyped provider name is the most common reason an address bounces.
_DOMAIN_TYPOS = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gamil.com": "gmail.com",
    "gnail.com": "gmail.com", "gmail.con": "gmail.com", "gmail.co": "gmail.com",
    "gmail.cm": "gmail.com", "gmail.om": "gmail.com", "gmaill.com": "gmail.com",
    "gmail.comm": "gmail.com", "hotmial.com": "hotmail.com", "hotmal.com": "hotmail.com",
    "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com", "yahoo.con": "yahoo.com",
    "outlok.com": "outlook.com", "outllook.com": "outlook.com",
}


def check_email(address: str) -> tuple[str, str]:
    """
    Check an e-mail address BEFORE it is saved. Returns (level, message):

      ("ok", "")       - nothing wrong (also returned for an empty address,
                         because the e-mail field is optional)
      ("error", ...)   - cannot possibly be delivered: refuse to save
      ("warning", ...) - format is fine but it very likely does not exist
                         (e.g. a Gmail name longer than Gmail allows): ask first

    The program can NOT know whether a mailbox really exists - Gmail only
    reports that later, by sending a "Mail Delivery Subsystem / Address not
    found" message back to the sending account. These checks catch the
    typical typing mistakes early.
    """
    address = (address or "").strip()
    if not address:
        return "ok", ""

    if any(ch.isspace() for ch in address):
        return "error", "The email address must not contain spaces."
    if address.count("@") != 1:
        return "error", "The email address must contain exactly one @ sign."
    local, domain = address.split("@")
    if not local or not domain:
        return "error", "The email address is incomplete."
    if len(address) > 254 or len(local) > 64:
        return "error", "The email address is too long."
    if ".." in address or local.startswith(".") or local.endswith("."):
        return "error", "The email address has misplaced dots."
    if not _EMAIL_RE.match(address):
        return "error", "This does not look like a valid email address (example: name@gmail.com)."

    domain_lower = domain.lower()
    if domain_lower in _DOMAIN_TYPOS:
        return "warning", (f"'{domain}' looks like a typing mistake. "
                           f"Did you mean {local}@{_DOMAIN_TYPOS[domain_lower]}?")

    if domain_lower in ("gmail.com", "googlemail.com"):
        name = local.split("+", 1)[0]
        if len(name) > 30:
            return "warning", ("Gmail names can be at most 30 characters, so this address "
                               "cannot exist. Please check it.")
        if not re.fullmatch(r"[A-Za-z0-9.]+", name):
            return "warning", ("Gmail names can only contain letters, numbers and dots. "
                               "Please check it.")
    return "ok", ""
