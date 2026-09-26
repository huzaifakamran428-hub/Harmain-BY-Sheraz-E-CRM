import sys
import os
from datetime import date, time, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from domain.rules import (
    calculate_remaining,
    generate_pilgrim_password,
    is_within_reminder_window,
    is_eligible_for_transfer,
    route_free_status,
)
from domain.models import Gender, PilgrimStatus


def test_calculate_remaining():
    assert calculate_remaining(200, 0) == 200
    assert calculate_remaining(200, 150) == 50
    assert calculate_remaining(200, 200) == 0
    assert calculate_remaining(200, 250) == -50  # overpaid


def test_generate_pilgrim_password():
    assert generate_pilgrim_password("Muhammad") == "Muhammad111@"
    assert generate_pilgrim_password("Muhammad Ali") == "Muhammad111@"
    assert generate_pilgrim_password("  Ayesha  ") == "Ayesha111@"
    assert generate_pilgrim_password("") == ""
    assert generate_pilgrim_password(None) == ""
    # First letter capital, every other letter small (whatever was typed).
    assert generate_pilgrim_password("MUHAMMAD ALI") == "Muhammad111@"
    assert generate_pilgrim_password("aYeSHa") == "Ayesha111@"
    assert generate_pilgrim_password("bILAL ahmed") == "Bilal111@"
    # MRZ leftovers and punctuation are stripped.
    assert generate_pilgrim_password("MUHAMMAD<<ALI") == "Muhammad111@"


def test_reminder_window():
    permit_date = date(2026, 10, 10)
    permit_time = time(9, 0)
    # exactly 2 days before -> inside window
    now = datetime(2026, 10, 8, 9, 0)
    assert is_within_reminder_window(permit_date, permit_time, now) is True
    # 3 days before -> not yet
    now_early = datetime(2026, 10, 7, 9, 0)
    assert is_within_reminder_window(permit_date, permit_time, now_early) is False
    # after permit datetime -> no longer "upcoming"
    now_late = datetime(2026, 10, 10, 9, 1)
    assert is_within_reminder_window(permit_date, permit_time, now_late) is False
    # no permit date at all
    assert is_within_reminder_window(None, None, now) is False


def test_transfer_eligibility():
    permit_date = date(2026, 10, 10)
    permit_time = time(9, 0)
    not_yet = datetime(2026, 10, 10, 14, 59)
    exactly_six = datetime(2026, 10, 10, 15, 0)
    after = datetime(2026, 10, 11, 9, 0)
    assert is_eligible_for_transfer(permit_date, permit_time, not_yet) is False
    assert is_eligible_for_transfer(permit_date, permit_time, exactly_six) is True
    assert is_eligible_for_transfer(permit_date, permit_time, after) is True
    assert is_eligible_for_transfer(None, None, after) is False


def test_gender_routing():
    assert route_free_status(Gender.MALE) == PilgrimStatus.FREE_MALE
    assert route_free_status(Gender.FEMALE) == PilgrimStatus.FREE_FEMALE


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
