"""
Tests for: email address checking (the "Address not found" bounce), the logo in
reminder emails, and safe HTML in the email body. No screen needed.

Run with:  python tests/unit/test_email_features.py
"""
import os
import sys
import tempfile
from datetime import date, time, timedelta
from pathlib import Path

os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
os.environ["HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from core.exceptions import ValidationError
from domain.models import Gender, Pilgrim, PilgrimStatus
from domain.rules import check_email
from infrastructure.db import initialize_database, get_connection
from infrastructure.email_templates import build_reminder_email, find_logo_path

initialize_database()


def level(address: str) -> str:
    return check_email(address)[0]


# ------------------------------------------------------------ address checks
def test_good_addresses_pass():
    for address in ("name@gmail.com", "first.last+tag@gmail.com", "a_b@company.co.uk", "", "  "):
        assert level(address) == "ok", address


def test_broken_addresses_are_errors():
    for address in ("no-at-sign.com", "two@@gmail.com", "with space@gmail.com",
                    "name@", "@gmail.com", "name@gmail", "na..me@gmail.com", ".name@gmail.com"):
        assert level(address) == "error", address


def test_the_bounced_address_from_the_screenshot_is_flagged():
    # 31 letters before @gmail.com - Gmail names are at most 30, so it cannot exist
    bounced = "sakjfsajkfjskdfjsakdjfklasjdfks@gmail.com"
    assert len(bounced.split("@")[0]) == 31
    lvl, message = check_email(bounced)
    assert lvl == "warning" and "30" in message


def test_domain_typos_are_flagged_with_a_suggestion():
    lvl, message = check_email("ahmed@gmial.com")
    assert lvl == "warning" and "ahmed@gmail.com" in message
    assert level("ahmed@gmail.con") == "warning"


def test_gmail_only_allows_letters_numbers_dots():
    assert level("ahmed_khan@gmail.com") == "warning"
    assert level("ahmed.khan.786@gmail.com") == "ok"


# ------------------------------------------------------------------ service
def _party_id():
    from application.party_service import PartyService
    return PartyService().create_party("Mail Party", "0300-0000000").id


def test_service_refuses_broken_and_trims_good_addresses():
    from application.pilgrim_service import PilgrimService
    service, party_id = PilgrimService(), _party_id()
    try:
        service.add_pilgrim(party_id, "Bad Mail", Gender.MALE, email="not an address")
        raise AssertionError("broken address was accepted")
    except ValidationError:
        pass
    saved = service.add_pilgrim(party_id, "Good Mail", Gender.MALE, email="  good.one@gmail.com ")
    assert saved.email == "good.one@gmail.com"


class _Spy:
    """Records every email the reminder service tries to send."""
    def __init__(self):
        self.sent = []

    def install(self):
        import application.reminder_service as rs
        spy = self

        class FakeNotifier:
            def __init__(self, settings):
                pass

            def send_html(self, to_address, subject, html_body, plain_body, logo_path=None):
                spy.sent.append((to_address, subject, plain_body, html_body, logo_path))
                return True, ""
        self._rs, self._old = rs, rs.EmailNotifier
        rs.EmailNotifier = FakeNotifier

    def restore(self):
        self._rs.EmailNotifier = self._old


def _configure(recipient="admin@gmail.com"):
    from application.settings_service import SettingsService
    SettingsService().set_many({
        "smtp_host": "smtp.example.com", "smtp_username": "u", "smtp_password": "p",
        "smtp_sender": "sender@gmail.com", "reminder_recipient": recipient,
    })


def _upcoming_pilgrim(name, email):
    from application.pilgrim_service import PilgrimService
    return PilgrimService().add_pilgrim(_party_id(), name, Gender.FEMALE,
                                        date.today() + timedelta(days=1), time(9, 0), email=email)


def test_reminder_goes_to_the_administrator_never_to_the_pilgrim():
    from application.reminder_service import ReminderService
    _configure("admin@gmail.com")
    p = _upcoming_pilgrim("Only Admin Gets Mail", "pilgrim.person@gmail.com")
    spy = _Spy(); spy.install()
    try:
        assert ReminderService().check_and_send_reminders() >= 1
    finally:
        spy.restore()
    mine = [m for m in spy.sent if "Only Admin Gets Mail" in m[1]]
    assert len(mine) == 1, spy.sent
    assert mine[0][0] == "admin@gmail.com"
    assert all(m[0] != "pilgrim.person@gmail.com" for m in spy.sent)
    assert "Dear" not in mine[0][2]                      # not written to the pilgrim any more


def test_reminder_is_sent_even_when_the_pilgrim_has_no_email():
    from application.reminder_service import ReminderService
    _configure("admin@gmail.com")
    _upcoming_pilgrim("No Email Pilgrim", "")
    spy = _Spy(); spy.install()
    try:
        ReminderService().check_and_send_reminders()
    finally:
        spy.restore()
    assert any("No Email Pilgrim" in m[1] and m[0] == "admin@gmail.com" for m in spy.sent), spy.sent


def test_reminder_falls_back_to_the_sender_address_when_recipient_is_empty():
    from application.reminder_service import ReminderService
    _configure("")
    _upcoming_pilgrim("Fallback Recipient", "x@gmail.com")
    spy = _Spy(); spy.install()
    try:
        ReminderService().check_and_send_reminders()
    finally:
        spy.restore()
    assert any("Fallback Recipient" in m[1] and m[0] == "sender@gmail.com" for m in spy.sent), spy.sent


def test_reminder_makes_no_desktop_notification_and_records_only_email():
    from application.reminder_service import ReminderService

    class Loud:
        called = 0
        def notify(self, *a, **k):
            Loud.called += 1
            return True
    _configure("admin@gmail.com")
    p = _upcoming_pilgrim("Silent Desktop", "s@gmail.com")
    spy = _Spy(); spy.install()
    try:
        ReminderService(desktop_notifier=Loud()).check_and_send_reminders()
    finally:
        spy.restore()
    channels = {r[0] for r in get_connection().execute(
        "SELECT channel FROM notifications WHERE pilgrim_id=?", (p.id,)).fetchall()}
    assert Loud.called == 0
    assert channels == {"Email"}, channels


def test_reminder_is_sent_only_once_per_pilgrim():
    from application.reminder_service import ReminderService
    _configure("admin@gmail.com")
    _upcoming_pilgrim("Once Only", "o@gmail.com")
    spy = _Spy(); spy.install()
    try:
        service = ReminderService()
        service.check_and_send_reminders()
        service.check_and_send_reminders()
    finally:
        spy.restore()
    assert len([m for m in spy.sent if "Once Only" in m[1]]) == 1


def test_fixing_the_email_settings_retries_at_once():
    from datetime import datetime
    import application.reminder_service as rs
    from application.reminder_service import ReminderService
    _configure("admin@gmail.com")
    _upcoming_pilgrim("Settings Just Fixed", "x@gmail.com")
    state = {"ok": False}

    class Notifier:
        def __init__(self, settings):
            pass
        def send_html(self, *a, **k):
            return (True, "") if state["ok"] else (False, "Username and Password not accepted")

    old, rs.EmailNotifier = rs.EmailNotifier, Notifier
    try:
        service, t0 = ReminderService(), datetime.now()
        assert service.check_and_send_reminders(now=t0) == 0
        state["ok"] = True                                                   # you correct the app password...
        assert service.check_and_send_reminders(now=t0 + timedelta(minutes=1)) == 0   # ...still waiting
        service.clear_retry_throttle()                                       # ...and press Save Email Settings
        assert service.check_and_send_reminders(now=t0 + timedelta(minutes=1)) >= 1
    finally:
        rs.EmailNotifier = old


def test_failed_reminder_retries_by_itself_on_the_same_row_without_spamming():
    from datetime import datetime
    import application.reminder_service as rs
    from application.reminder_service import ReminderService
    _configure("admin@gmail.com")
    p = _upcoming_pilgrim("Flaky Network", "f@gmail.com")
    outcome = {"ok": False, "calls": 0}

    class Flaky:
        def __init__(self, settings):
            pass
        def send_html(self, *a, **k):
            outcome["calls"] += 1
            return (True, "") if outcome["ok"] else (False, "Network is unreachable")

    old, rs.EmailNotifier = rs.EmailNotifier, Flaky
    try:
        service, t0 = ReminderService(), datetime.now()
        rows = lambda: get_connection().execute(
            "SELECT status, retry_count FROM notifications WHERE pilgrim_id=?", (p.id,)).fetchall()
        service.check_and_send_reminders(now=t0)
        service.check_and_send_reminders(now=t0 + timedelta(minutes=1))     # next tick: too soon, no new attempt
        service.check_and_send_reminders(now=t0 + timedelta(minutes=2))
        assert outcome["calls"] == 1 and len(rows()) == 1, (outcome, rows())
        service.check_and_send_reminders(now=t0 + timedelta(minutes=11))    # retried, same row
        assert outcome["calls"] == 2 and len(rows()) == 1 and rows()[0]["retry_count"] == 2
        outcome["ok"] = True                                                # network is back
        service.check_and_send_reminders(now=t0 + timedelta(minutes=22))
        assert len(rows()) == 1 and rows()[0]["status"] == "Sent", [tuple(r) for r in rows()]
    finally:
        rs.EmailNotifier = old


def _mail_for(name, **settings):
    """Run the automatic reminder for one new pilgrim and return the single email it produced."""
    from application.reminder_service import ReminderService
    from application.settings_service import SettingsService
    _configure("admin@gmail.com")
    SettingsService().set_many(settings)
    pilgrim = _upcoming_pilgrim(name, settings.pop("pilgrim_email", ""))
    spy = _Spy(); spy.install()
    try:
        ReminderService().check_and_send_reminders()
    finally:
        spy.restore()
    mine = [m for m in spy.sent if name in m[1]]
    assert len(mine) == 1, spy.sent
    return pilgrim, mine[0]


def test_reminder_email_has_no_logo_by_default():
    _, (to, subject, plain, html_body, logo) = _mail_for("No Logo Please")
    assert logo is None and "cid:brand_logo" not in html_body
    assert "HaramaIn by Sheraz" in html_body                      # plain text header instead


def test_reminder_email_logo_can_be_switched_back_on():
    _, (to, subject, plain, html_body, logo) = _mail_for("Logo Wanted", reminder_email_logo="1")
    from application.settings_service import SettingsService
    SettingsService().set("reminder_email_logo", "0")
    assert logo is not None and "cid:brand_logo" in html_body


def test_reminder_shows_the_pilgrims_gmail_or_says_it_is_missing():
    from application.pilgrim_service import PilgrimService
    party_id = _party_id()
    with_gmail = PilgrimService().add_pilgrim(party_id, "Has Gmail", Gender.MALE, date.today() + timedelta(days=1),
                                              time(9, 0), email="code.inbox@gmail.com")
    without = PilgrimService().add_pilgrim(party_id, "Has No Gmail", Gender.MALE, date.today() + timedelta(days=1),
                                           time(9, 0))
    _configure("admin@gmail.com")
    spy = _Spy(); spy.install()
    try:
        from application.reminder_service import ReminderService
        ReminderService().check_and_send_reminders()
    finally:
        spy.restore()
    by_name = {m[1].split(" - ")[1].split(" (")[0]: m for m in spy.sent}
    assert "code.inbox@gmail.com" in by_name["Has Gmail"][2] and "code.inbox@gmail.com" in by_name["Has Gmail"][3]
    assert "NOT ADDED" in by_name["Has No Gmail"][2]


def test_adding_the_gmail_later_sends_a_corrected_reminder_once():
    from application.pilgrim_service import PilgrimService
    from application.reminder_service import ReminderService
    _configure("admin@gmail.com")
    service = PilgrimService()
    p = service.add_pilgrim(_party_id(), "Gmail Added Late", Gender.MALE, date.today() + timedelta(days=1), time(9, 0))
    spy = _Spy(); spy.install()
    try:
        reminders = ReminderService()
        reminders.check_and_send_reminders()
        first = [m for m in spy.sent if "Gmail Added Late" in m[1]]
        assert len(first) == 1 and "NOT ADDED" in first[0][2]
        reminders.check_and_send_reminders()                                   # nothing changed: no repeat
        assert len([m for m in spy.sent if "Gmail Added Late" in m[1]]) == 1

        p.email = "late.gmail@gmail.com"                                       # you add it in the ledger
        service.update_pilgrim(p)
        reminders.check_and_send_reminders()
        reminders.check_and_send_reminders()
        again = [m for m in spy.sent if "Gmail Added Late" in m[1]]
        assert len(again) == 2 and "late.gmail@gmail.com" in again[1][2], [m[2] for m in again]
    finally:
        spy.restore()
    statuses = [r[0] for r in get_connection().execute(
        "SELECT status FROM notifications WHERE pilgrim_id=? ORDER BY id", (p.id,)).fetchall()]
    assert statuses == ["Replaced", "Sent"], statuses


# ---------------------------------------------------------------- email body
def _pilgrim(name="Zubaida Bi"):
    return Pilgrim(id=1, party_id=1, serial_number=1, name=name, gender=Gender.FEMALE,
                   permit_date=date.today() + timedelta(days=1), permit_time=time(9, 0),
                   email="z@gmail.com", password="Zubaida111@", charge=200.0,
                   status=PilgrimStatus.ACTIVE)


def test_email_uses_the_logo_header_with_cid_image():
    html_body, _ = build_reminder_email(_pilgrim(), "0300-1234567")
    assert 'src="cid:brand_logo"' in html_body


def test_email_is_written_to_the_administrator_about_the_pilgrim():
    html_body, plain = build_reminder_email(_pilgrim("Zubaida Bi"), "0300-1234567")
    assert "Dear" not in html_body and "Dear" not in plain
    assert "permit for <b>Zubaida Bi</b>" in html_body
    assert "z@gmail.com" in html_body and "Zubaida111@" in html_body      # details still shown


def test_html_special_characters_are_escaped():
    html_body, _ = build_reminder_email(_pilgrim("A <b>Bold</b> & Name"), "0300")
    assert "A &lt;b&gt;Bold&lt;/b&gt; &amp; Name" in html_body
    assert "<b>Bold</b>" not in html_body


# --------------------------------------------------------------------- logo
def test_email_logo_is_trimmed_small_and_from_the_app_logo():
    from core.config import get_logo_path
    logo = find_logo_path()
    source = get_logo_path()
    assert logo is not None and source is not None
    with Image.open(logo) as small, Image.open(source) as big:
        assert small.width <= 520, small.size
        assert os.path.getsize(logo) < os.path.getsize(source)
        assert small.width * small.height < big.width * big.height


def test_logo_imported_in_settings_beats_the_bundled_one():
    from core.config import get_branding_dir
    before = find_logo_path()
    imported = get_branding_dir() / "logo.png"
    Image.new("RGBA", (300, 120), (200, 30, 30, 255)).save(imported)      # a plain red logo
    after = find_logo_path()
    assert after != before
    with Image.open(after) as image:
        assert image.getpixel((5, 5))[0] > 150                           # the red one, not the bundled gold/black
    imported.unlink()
    assert find_logo_path() == before


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except Exception as e:                      # noqa: BLE001
                failures += 1
                print(f"FAIL  {name}  {type(e).__name__}: {e}")
    print(f"\n{'ALL PASSED' if not failures else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
