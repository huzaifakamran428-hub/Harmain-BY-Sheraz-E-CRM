"""
Unit tests for passport/visa parsing - in particular the automatic
gender pick-up, which has to cope with MRZ codes, English labels and
Arabic wording.

Run with:  python tests/unit/test_document_reading.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from domain.models import Gender
from infrastructure.ocr_service import OcrResult, _parse_document


def parse(text: str) -> OcrResult:
    result = OcrResult()
    _parse_document(text, result)
    return result


def test_mrz_passport_female():
    r = parse(
        "P<PAKKHAN<<AYESHA<BIBI<<<<<<<<<<<<<<<<<<<<<<<\n"
        "AB12345671PAK9203074F3005128<<<<<<<<<<<<<<04\n"
    )
    assert r.gender == Gender.FEMALE
    assert r.passport_number == "AB1234567"
    assert "Ayesha" in r.name


def test_mrz_passport_male():
    r = parse(
        "P<PAKALI<<MUHAMMAD<<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
        "CD98765431PAK8807114M3101015<<<<<<<<<<<<<<02\n"
    )
    assert r.gender == Gender.MALE


def test_english_visa_labels():
    r = parse(
        "Full Name : MUHAMMAD BILAL AHMED\n"
        "Passport Number : CD9876543\n"
        "Visa Number : 4210987654\n"
        "Gender : MALE\n"
    )
    assert r.gender == Gender.MALE
    assert r.visa_number == "4210987654"
    assert r.passport_number == "CD9876543"


def test_arabic_gender_female():
    r = parse("Name: FATIMA NOOR\nPassport No: EF1122334\nالجنس: أنثى\n")
    assert r.gender == Gender.FEMALE


def test_arabic_gender_male():
    r = parse("Name: OMAR FAROOQ\nPassport No: GH1122334\nالجنس: ذكر\n")
    assert r.gender == Gender.MALE


def test_sex_on_following_line():
    r = parse("NAME              ZAINAB MALIK\nPASSPORT NO       GH5566778\nSEX\nF\n")
    assert r.gender == Gender.FEMALE


def test_female_not_mistaken_for_male():
    """'FEMALE' contains 'MALE' - the reader must not trip over it."""
    assert parse("Sex: FEMALE").gender == Gender.FEMALE


def test_no_gender_stays_none():
    assert parse("Some unrelated document text with no markers.").gender is None


def test_labels_do_not_swallow_next_line():
    r = parse("Name: FATIMA NOOR\nPassport No: EF1122334\n")
    assert r.name == "Fatima Noor"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}  {e}")
    print(f"\n{'ALL PASSED' if not failures else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
