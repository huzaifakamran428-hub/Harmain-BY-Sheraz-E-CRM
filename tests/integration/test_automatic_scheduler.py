"""
End-to-end check of the AUTOMATIC background work, without pressing any button:

  * every scheduler tick moves pilgrims to the Free Account 6 hours after their permit
  * every scheduler tick emails the administrator once when a permit is within the reminder window

Runs the real BackgroundScheduler._tick() with the real services and a real (temporary)
database. Only the outgoing email is replaced by a recorder. If PyQt6 is not installed a tiny
stand-in is used, so the test still runs on a machine with no screen and no Qt.

Run with:  python tests/integration/test_automatic_scheduler.py
"""
import os
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path

os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
os.environ["HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import PyQt6.QtCore  # noqa: F401
except ImportError:                                   # headless stand-in for QObject / QTimer / pyqtSignal
    core = types.ModuleType("PyQt6.QtCore")

    class QObject:
        def __init__(self, parent=None):
            pass

    class _Signal:
        def __init__(self, *a):
            self.slots = []
        def connect(self, fn):
            self.slots.append(fn)
        def emit(self, *a):
            for fn in self.slots:
                fn(*a)

    class QTimer:
        def __init__(self, parent=None):
            self.timeout = _Signal()
        def setInterval(self, ms):
            self.ms = ms
        def start(self):
            pass
        def stop(self):
            pass

    def pyqtSignal(*a):
        return _Signal()

    core.QObject, core.QTimer, core.pyqtSignal = QObject, QTimer, pyqtSignal
    pkg = types.ModuleType("PyQt6")
    pkg.QtCore = core
    sys.modules["PyQt6"], sys.modules["PyQt6.QtCore"] = pkg, core

from domain.models import Gender, PilgrimStatus
from infrastructure.db import initialize_database, get_connection
import application.reminder_service as rs
from application.party_service import PartyService
from application.pilgrim_service import PilgrimService
from application.free_account_service import FreeAccountService
from application.reminder_service import ReminderService
from application.settings_service import SettingsService
from infrastructure.scheduler import BackgroundScheduler

initialize_database()

SENT = []


class FakeNotifier:
    def __init__(self, settings):
        pass

    def send_html(self, to_address, subject, html_body, plain_body, logo_path=None):
        SENT.append((to_address, subject))
        return True, ""


rs.EmailNotifier = FakeNotifier
SettingsService().set_many({
    "smtp_host": "smtp.example.com", "smtp_username": "u", "smtp_password": "p",
    "smtp_sender": "sender@gmail.com", "reminder_recipient": "admin@gmail.com",
})


class Ctx:
    free_accounts = FreeAccountService()
    reminders = ReminderService()


party = PartyService().create_party("Auto Party", "0300-0000000").id
pilgrims = PilgrimService()


def add(name, gender, delta):
    when = datetime.now() + delta
    return pilgrims.add_pilgrim(party, name, gender, when.date(), when.time().replace(microsecond=0)).id


ids = {
    "male_7h_ago": add("Male Seven", Gender.MALE, timedelta(hours=-7)),
    "female_7h_ago": add("Female Seven", Gender.FEMALE, timedelta(hours=-7)),
    "just_over_6h": add("Just Over Six", Gender.MALE, timedelta(hours=-6, minutes=-2)),
    "5h_ago": add("Five Hours", Gender.MALE, timedelta(hours=-5)),
    "in_30h": add("In Thirty Hours", Gender.FEMALE, timedelta(hours=30)),
    "in_47h": add("In Forty Seven", Gender.MALE, timedelta(hours=47)),
    "in_5_days": add("In Five Days", Gender.MALE, timedelta(days=5)),
}


def status(key):
    return pilgrims.get_pilgrim(ids[key]).status


moved_signals, reminder_signals = [], []
scheduler = BackgroundScheduler(Ctx, interval_minutes=1)
scheduler.transfer_completed.connect(moved_signals.append)
scheduler.reminders_sent.connect(reminder_signals.append)
scheduler.start()                       # what the app does at start-up: one tick immediately

results = []


def check(label, condition):
    results.append(condition)
    print(("PASS  " if condition else "FAIL  ") + label)


# ------------------------------------------------------------ 6-hour Free Account move
check("male, permit 7h ago -> moved to Free Male", status("male_7h_ago") == PilgrimStatus.FREE_MALE)
check("female, permit 7h ago -> moved to Free Female", status("female_7h_ago") == PilgrimStatus.FREE_FEMALE)
check("permit 6h02m ago -> moved", status("just_over_6h") == PilgrimStatus.FREE_MALE)
check("permit 5h ago -> NOT moved yet", status("5h_ago") == PilgrimStatus.ACTIVE)
check("future permits are not moved", status("in_30h") == status("in_5_days") == PilgrimStatus.ACTIVE)
check("scheduler reported 3 pilgrims moved", moved_signals == [3])

# ------------------------------------------------------------ automatic email reminder
subjects = " | ".join(s for _, s in SENT)
check("permit in 30h -> reminder emailed automatically", "In Thirty Hours" in subjects)
check("permit in 47h -> reminder emailed automatically", "In Forty Seven" in subjects)
check("permit in 5 days -> no reminder yet", "In Five Days" not in subjects)
check("every reminder went to the administrator only", all(to == "admin@gmail.com" for to, _ in SENT))
check("already-moved pilgrims are not reminded", "Male Seven" not in subjects and "Female Seven" not in subjects and "Just Over" not in subjects)

# ------------------------------------------------------------ next ticks change nothing
before = (len(SENT), len(moved_signals))
scheduler._tick()
scheduler._tick()
check("later ticks send no duplicate email and move nobody twice", (len(SENT), len(moved_signals)) == before)

# a permit that enters the window later is picked up by a later tick with no button pressed
late = add("Enters Window Later", Gender.MALE, timedelta(days=3))
scheduler._tick()
check("3 days out -> not reminded yet", "Enters Window Later" not in " ".join(s for _, s in SENT))
get_connection().execute("UPDATE pilgrims SET permit_date=?, permit_time=? WHERE id=?",
                         ((datetime.now() + timedelta(hours=40)).date().isoformat(),
                          (datetime.now() + timedelta(hours=40)).time().replace(microsecond=0).isoformat(), late))
get_connection().commit()
scheduler._tick()
check("once it is within 2 days, the next tick emails it by itself", "Enters Window Later" in " ".join(s for _, s in SENT))

# ------------------------------------------------ right after a pilgrim is saved (no waiting for the timer)
import infrastructure.scheduler as scheduler_module

count_before = len(SENT)
add("Just Added Now", Gender.FEMALE, timedelta(hours=20))
check("a new pilgrim is not emailed until a check runs", len(SENT) == count_before)
real_timer = scheduler_module.QTimer
scheduler_module.QTimer = types.SimpleNamespace(singleShot=lambda ms, fn: fn())   # the timer 'fires' at once
try:
    scheduler.run_soon()                                   # what the app does when the pilgrim dialog is saved
finally:
    scheduler_module.QTimer = real_timer
check("run_soon() emails the new pilgrim without pressing anything",
      "Just Added Now" in " ".join(s for _, s in SENT))

print(f"\n{'ALL PASSED' if all(results) else str(results.count(False)) + ' FAILED'}")
sys.exit(0 if all(results) else 1)
