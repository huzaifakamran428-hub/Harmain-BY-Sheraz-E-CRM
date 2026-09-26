import sys
import os
import tempfile
from pathlib import Path
from datetime import date, time, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Point the app at a throwaway temp database before importing anything
# that opens a connection.
_tmp_dir = tempfile.mkdtemp(prefix="haramain_test_")
_db_path = Path(_tmp_dir) / "test.db"

import core.config as config
config.get_db_path = lambda: _db_path  # monkeypatch for the test run

from infrastructure.db import initialize_database, get_connection
from application.auth_service import AuthService
from application.party_service import PartyService
from application.pilgrim_service import PilgrimService
from application.payment_service import PaymentService
from application.free_account_service import FreeAccountService
from application.report_service import ReportService
from application.bill_service import BillService
from domain.models import Gender, PilgrimStatus
from core.exceptions import ValidationError, DuplicateRecordError, NotFoundError

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"FAIL: {msg}")
    else:
        print(f"PASS: {msg}")


def run():
    initialize_database(_db_path)

    auth = AuthService()
    party_svc = PartyService()
    pilgrim_svc = PilgrimService()
    payment_svc = PaymentService()
    free_svc = FreeAccountService()
    report_svc = ReportService()
    bill_svc = BillService()

    # --- Auth ---
    check(auth.needs_first_run_setup() is True, "fresh db needs first-run setup")
    admin = auth.create_first_admin("admin", "adminpass123")
    check(admin.id is not None, "admin account created")
    check(auth.needs_first_run_setup() is False, "no longer needs first-run setup")
    logged_in = auth.login("admin", "adminpass123")
    check(logged_in.username == "admin", "login succeeds with correct password")
    try:
        auth.login("admin", "wrongpass")
        check(False, "login with wrong password should raise")
    except Exception as e:
        check(type(e).__name__ == "AuthenticationError", "login with wrong password raises AuthenticationError")

    # --- Party ---
    party = party_svc.create_party("Ali Traders", "0300-1111111", actor="admin")
    check(party.id is not None, "party created")
    try:
        party_svc.create_party("", "0300-1111111", actor="admin")
        check(False, "party without name should fail")
    except ValidationError:
        check(True, "party without name raises ValidationError")

    # --- Pilgrim add, default charge, password generation ---
    p1 = pilgrim_svc.add_pilgrim(
        party_id=party.id, name="Muhammad Ali", gender=Gender.MALE,
        permit_date=date.today() + timedelta(days=10), permit_time=time(9, 0), actor="admin",
    )
    check(p1.password == "Muhammad111@", f"auto-generated password correct: {p1.password}")
    check(p1.charge == 200.0, "default charge is 200 PKR")
    check(p1.serial_number == 1, "first pilgrim in party gets serial 1")

    p2 = pilgrim_svc.add_pilgrim(
        party_id=party.id, name="Ayesha Khan", gender=Gender.FEMALE,
        permit_date=date.today() + timedelta(days=10), permit_time=time(9, 0),
        passport_number="AB123456", actor="admin",
    )
    check(p2.serial_number == 2, "second pilgrim gets serial 2")

    # duplicate passport should be rejected
    try:
        pilgrim_svc.add_pilgrim(party_id=party.id, name="Someone Else", gender=Gender.MALE,
                                 passport_number="AB123456", actor="admin")
        check(False, "duplicate passport number should be rejected")
    except ValidationError:
        check(True, "duplicate passport number raises ValidationError")

    # --- Payments & party totals ---
    payment_svc.record_payment(p1.id, 100, note="advance", actor="admin")
    party_with_totals = party_svc.get_party_with_totals(party.id)
    check(party_with_totals.total_people == 2, "party has 2 active pilgrims")
    check(party_with_totals.total_charge == 400.0, "party total charge = 400")
    check(party_with_totals.total_received == 100.0, "party total received = 100")
    check(party_with_totals.total_remaining == 300.0, "party total remaining = 300")

    # --- Ledger search/filter ---
    results = pilgrim_svc.list_party_ledger(party.id, search="ayesha")
    check(len(results) == 1 and results[0].name == "Ayesha Khan", "search by name works")
    results = pilgrim_svc.list_party_ledger(party.id, gender=Gender.FEMALE)
    check(len(results) == 1, "gender filter works")

    # --- Six-hour transfer sweep (idempotency) ---
    p3 = pilgrim_svc.add_pilgrim(
        party_id=party.id, name="Bilal Ahmed", gender=Gender.MALE,
        permit_date=date.today() - timedelta(days=1), permit_time=time(9, 0), actor="admin",
    )  # permit was 24h+ ago -> eligible for transfer
    moved_count = free_svc.run_six_hour_transfer_sweep(actor="system")
    check(moved_count == 1, f"exactly one pilgrim transferred, got {moved_count}")
    moved_count_2 = free_svc.run_six_hour_transfer_sweep(actor="system")
    check(moved_count_2 == 0, "second sweep is idempotent - nothing left to move")

    free_male = pilgrim_svc.list_free(PilgrimStatus.FREE_MALE)
    check(len(free_male) == 1 and free_male[0].name == "Bilal Ahmed", "transferred pilgrim appears in Free Male")
    active_ledger = pilgrim_svc.list_party_ledger(party.id)
    check(all(p.name != "Bilal Ahmed" for p in active_ledger), "transferred pilgrim no longer in active ledger")

    # --- Return to party ---
    party2 = party_svc.create_party("Sara Travels", "0300-2222222", actor="admin")
    returned = free_svc.return_to_party(free_male[0].id, party2.id, actor="admin", reason="rebooked")
    check(returned.status == PilgrimStatus.ACTIVE, "returned pilgrim is Active again")
    check(returned.party_id == party2.id, "returned pilgrim linked to new party")
    free_male_after = pilgrim_svc.list_free(PilgrimStatus.FREE_MALE)
    check(len(free_male_after) == 0, "Free Male list empty after return")

    # --- Reminder window ---
    upcoming = pilgrim_svc.is_upcoming(p1)  # 10 days out -> should not be in 2-day window yet
    check(upcoming is False, "pilgrim 10 days out is not yet in reminder window")

    # --- Reports ---
    summary = report_svc.dashboard_summary()
    check(summary["total_active"] >= 2, f"dashboard shows active pilgrims: {summary}")
    check(summary["free_male"] == 0, "free male count is 0 after return")

    # --- PDF bill generation ---
    bill_path = bill_svc.generate_bill_for_party(party.id, Path(_tmp_dir) / "bill.pdf")
    check(bill_path.exists() and bill_path.stat().st_size > 0, "PDF bill file created and non-empty")

    # --- Not found handling ---
    try:
        pilgrim_svc.get_pilgrim(999999)
        check(False, "getting nonexistent pilgrim should raise NotFoundError")
    except NotFoundError:
        check(True, "getting nonexistent pilgrim raises NotFoundError")

    print(f"\n{len(failures)} failing checks out of full flow.")
    return len(failures) == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
