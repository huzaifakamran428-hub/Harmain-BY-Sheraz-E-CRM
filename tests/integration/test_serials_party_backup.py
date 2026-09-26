"""
Checks for: unique serial numbers (party ledger + Free Account), the party shown in the
Dashboard "upcoming" list and in the reminder email, and the Google Drive backup that used to
fail with "disk I/O error".

Runs on a real temporary database, no Qt needed.
Run with:  python tests/integration/test_serials_party_backup.py
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
os.environ["HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from domain.models import Gender, PilgrimStatus
from infrastructure.db import initialize_database, get_connection, repair_serial_numbers
import application.reminder_service as rs
from application.party_service import PartyService
from application.pilgrim_service import PilgrimService
from application.free_account_service import FreeAccountService
from application.reminder_service import ReminderService
from application.report_service import ReportService
from application.settings_service import SettingsService
from infrastructure.email_templates import build_reminder_email
from infrastructure.backup_service import BackupService

initialize_database()
results = []


def check(label, condition):
    results.append(condition)
    print(("PASS  " if condition else "FAIL  ") + label)


parties, pilgrims, free = PartyService(), PilgrimService(), FreeAccountService()
alpha = parties.create_party("Alpha Travels", "0300-1111111").id
beta = parties.create_party("Beta Group", "0300-2222222").id


def serials(party_id):
    return [p.serial_number for p in pilgrims.list_party_ledger(party_id)]


# ---------------------------------------------------------------- party serials
a = [pilgrims.add_pilgrim(alpha, f"A{i}", Gender.MALE).id for i in range(1, 8)]      # serials 1..7
b = [pilgrims.add_pilgrim(beta, f"B{i}", Gender.FEMALE).id for i in range(1, 4)]     # serials 1..3
check("every party starts at 1", serials(alpha) == [1, 2, 3, 4, 5, 6, 7] and serials(beta) == [1, 2, 3])

# pilgrims 3 and 4 finish and go to the Free Account; the ledger keeps the other numbers
free.transfer_to_free(a[2]); free.transfer_to_free(a[3])
check("serials stay put when someone moves to Free", serials(alpha) == [1, 2, 5, 6, 7])

# returning takes the party's NEXT number, never a repeat (this was the 1,2,2,5,... bug)
returned = free.return_to_party(a[2], alpha, actor="test")
check("returned pilgrim gets the next serial (8)", returned.serial_number == 8)
check("no serial repeats after the return", len(set(serials(alpha))) == len(serials(alpha)))
new = pilgrims.add_pilgrim(alpha, "New After", Gender.MALE)
check("a new pilgrim continues after that (9)", new.serial_number == 9)
other = free.return_to_party(a[3], beta, actor="test")
check("returning into another party uses THAT party's next serial (4)", other.serial_number == 4)
check("both parties are still unique", len(set(serials(alpha))) == len(serials(alpha)) and len(set(serials(beta))) == len(serials(beta)))

# ---------------------------------------------------------------- Free Account serials
males = [pilgrims.add_pilgrim(alpha, f"FM{i}", Gender.MALE).id for i in range(3)]
females = [pilgrims.add_pilgrim(beta, f"FF{i}", Gender.FEMALE).id for i in range(2)]
for pid in males + females:
    free.transfer_to_free(pid)
fm = pilgrims.list_free(PilgrimStatus.FREE_MALE)
ff = pilgrims.list_free(PilgrimStatus.FREE_FEMALE)
check("Free Male counts 1,2,3", [p.free_serial for p in fm] == [1, 2, 3])
check("Free Female counts 1,2 on its own", [p.free_serial for p in ff] == [1, 2])
free.return_to_party(males[1], alpha, actor="test")
check("others keep their Free number after one returns", [p.free_serial for p in pilgrims.list_free(PilgrimStatus.FREE_MALE)] == [1, 3])
free.transfer_to_free(males[1])
check("moving back to Free continues after the highest (4)", pilgrims.get_pilgrim(males[1]).free_serial == 4)

# ---------------------------------------------------------------- repair of old duplicate data
conn = get_connection()
conn.execute("UPDATE pilgrims SET serial_number=2 WHERE id=?", (a[4],))       # pilgrim 5 wrongly shows 2
conn.execute("UPDATE pilgrims SET free_serial=0 WHERE status='FreeFemale'")   # as in an old database
conn.commit()
check("duplicate present before repair", serials(alpha).count(2) == 2)
repair_serial_numbers(conn); conn.commit()
check("start-up repair removes the duplicate", len(set(serials(alpha))) == len(serials(alpha)))
check("start-up repair numbers old Free Account people from 1",
      [p.free_serial for p in pilgrims.list_free(PilgrimStatus.FREE_FEMALE)] == [1, 2])

# ---------------------------------------------------------------- party name: dashboard + email
soon = datetime.now() + timedelta(hours=20)
p_soon = pilgrims.add_pilgrim(beta, "Soon Person", Gender.FEMALE, soon.date(), soon.time().replace(microsecond=0))
upcoming = ReportService().upcoming_pilgrims()
mine = [r for r in upcoming if r["pilgrim"].id == p_soon.id]
check("dashboard upcoming list names the party", bool(mine) and mine[0]["party_name"] == "Beta Group" and mine[0]["party_id"] == beta)
check("dashboard count matches the list", ReportService().count_upcoming() == len(upcoming))

html, plain = build_reminder_email(p_soon, "0300", include_logo=False, party_name="Beta Group")
check("email body (html + text) shows the party name", "Beta Group" in html and "Party: Beta Group" in plain)
html2, _ = build_reminder_email(p_soon, "0300", include_logo=False)
check("email without a party still builds", "Soon Person" in html2)

SENT = []


class FakeNotifier:
    def __init__(self, settings):
        pass

    def send_html(self, to_address, subject, html_body, plain_body, logo_path=None):
        SENT.append((to_address, subject, html_body))
        return True, ""


rs.EmailNotifier = FakeNotifier
SettingsService().set_many({"smtp_host": "smtp.example.com", "smtp_username": "u", "smtp_password": "p",
                            "smtp_sender": "s@gmail.com", "reminder_recipient": "admin@gmail.com"})
ReminderService().check_and_send_reminders()
sent = [s for s in SENT if "Soon Person" in s[1]]
check("reminder subject carries the party name", bool(sent) and "Beta Group" in sent[0][1])
check("reminder body carries the party name", bool(sent) and "Beta Group" in sent[0][2])

# ---------------------------------------------------------------- backup to a 'virtual drive'
drive = Path(tempfile.mkdtemp()) / "My Drive"
drive.mkdir()
real_connect = sqlite3.connect


def picky_connect(path, *args, **kwargs):
    # Google Drive (Stream) cannot host SQLite files: opening one there = "disk I/O error"
    if str(drive) in str(path):
        raise sqlite3.OperationalError("disk I/O error")
    return real_connect(path, *args, **kwargs)


sqlite3.connect = picky_connect
try:
    svc = BackupService()
    svc.save_destination("gdrive", enabled=True, path=str(drive))
    result = [r for r in svc.backup_now(only_enabled=True) if r.key == "gdrive"][0]
    check("backup to the drive folder now succeeds (" + result.message[:60] + ")", result.success)
    copy = drive / "HaramaIn Backup" / "harmain.db"
    check("database copy exists on the drive", copy.exists() and copy.stat().st_size > 0)
    leftovers = [p.name for p in (drive / "HaramaIn Backup").iterdir() if p.name.endswith((".uploading", ".tmp", "-journal"))]
    check("no temporary files left behind", not leftovers)
    again = [r for r in svc.backup_now(only_enabled=True) if r.key == "gdrive"][0]
    check("a second backup (nothing changed) also succeeds", again.success)

    # restore into the live database from the drive copy
    get_connection().execute("DELETE FROM pilgrims"); get_connection().commit()
    restored = svc.restore_now("gdrive")
    check("restore from the drive succeeds", restored.success)
    check("restore brought the pilgrims back", get_connection().execute("SELECT COUNT(*) c FROM pilgrims").fetchone()["c"] > 10)
finally:
    sqlite3.connect = real_connect

print(f"\n{'ALL PASSED' if all(results) else str(results.count(False)) + ' FAILED'}")
sys.exit(0 if all(results) else 1)
