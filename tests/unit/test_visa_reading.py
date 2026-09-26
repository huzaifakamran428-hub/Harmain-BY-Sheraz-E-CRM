"""
Regression tests for the visa reading bugs:

  * visa number came out as one number repeated 3 times (the PDF draws
    every character several times on top of itself),
  * the visa number is printed BEFORE its 'Visa No.' label on the Saudi
    e-visa, so a 'label then value' pattern grabbed the wrong text,
  * gender stayed 'Male' because the Saudi e-visa has no sex field - only a
    number inside the MRZ line.

All names / numbers below are invented.

Run with:  python tests/unit/test_visa_reading.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from domain.models import Gender
from infrastructure.ocr_service import (
    OcrResult, _parse_document, _collapse_overprint, _find_visa_number,
    extract_passport_data,
)


def parse(text: str) -> OcrResult:
    result = OcrResult()
    _parse_document(text, result)
    return result


def visa_mrz(sex_digit: str) -> str:
    return (
        "1<PAKPERSON<<TEST<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
        f"AB12345676PAK15011985" + "2" + sex_digit + "14122031" + "9" + "<" * 10 + "06\n"
    )


# ----------------------------------------------------------- overprint
def test_collapse_tripled_and_doubled():
    assert _collapse_overprint("111222333444555666777888999000") == "1234567890"
    assert _collapse_overprint("11223344556677889900") == "1234567890"


def test_real_number_is_never_altered():
    # only tokens longer than a real number are collapsed
    assert _find_visa_number("Visa No. 1122334455") == "1122334455"


# ---------------------------------------------- value BEFORE / AFTER label
def test_visa_value_before_label():
    text = "XX 1234567890 Visa No.\n18/09/2026 Date of Issue\nAB1234567 Passport No.\n"
    assert parse(text).visa_number == "1234567890"


def test_visa_value_after_label():
    assert parse("Visa Number : 4210987654\n").visa_number == "4210987654"


def test_application_number_is_not_the_visa_number():
    text = (
        "1234567890 Visa No.\n"
        "Visa No.\n1234567890\n"
        "Application No.\nE555555555\n"
    )
    assert parse(text).visa_number == "1234567890"


def test_tripled_caption_under_barcode():
    text = "Visa No.\n111222333444555666777888999000\nApplication No.\nEEE555\n"
    # 30 characters, each x3 -> 10 digits
    assert parse(text).visa_number == "1234567890"


def test_passport_value_before_label():
    assert parse("AB1234567 Passport No.\n").passport_number == "AB1234567"


def test_name_before_label():
    assert parse("Zubaida Bi Name\n").name == "Zubaida Bi"


# --------------------------------------------------------------- gender
def test_saudi_visa_mrz_number_female():
    r = parse(visa_mrz("2"))
    assert r.gender == Gender.FEMALE and r.gender_source == "MRZ code"
    assert r.passport_number == "AB1234567"


def test_saudi_visa_mrz_number_male():
    assert parse(visa_mrz("1")).gender == Gender.MALE


def test_name_guess_is_flagged():
    r = parse("Name: AYESHA BIBI\nPassport No: EF1122334\n")
    assert r.gender == Gender.FEMALE and r.gender_source == "name (guess)"


def test_gender_left_undecided_when_nothing_says():
    r = parse("Name: AHMED KHAN\nPassport No: EF1122334\nVisa No: 1234567890\n")
    assert r.gender is None


def test_explicit_label_beats_name_guess():
    r = parse("Name: BEGUM ALI\nSex: M\n")
    assert r.gender == Gender.MALE and r.gender_source == "label"


def test_arabic_reversed_presentation_forms():
    # 'أنثى' as a PDF reader hands it back: visually reversed ('ىثنأ')
    assert parse("Name: TEST\nsex \u0649\u062b\u0646\u0623\n").gender == Gender.FEMALE
    # ...and 'ذكر' reversed ('ركذ')
    assert parse("Name: TEST\nsex \u0631\u0643\u0630\n").gender == Gender.MALE


def test_ocr_damaged_mrz_line_is_repaired():
    text = (
        "1<PAKPERSON<<TEST<K<<<K<K<K<<<<<<s<K<ssK<ss<<<<<<\n"
        "AB12345676PAK150119852214122031" "9<<<<<<<<<<06 ;\n"
    )
    r = parse(text)
    assert r.name == "Test Person" and r.gender == Gender.FEMALE


# ------------------------------------------------- real overprinted PDF
def _make_overprinted_pdf(path: Path, sex_digit: str) -> None:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4

    def bold(x, y, text, size=11, font="Helvetica"):
        c.setFont(font, size)
        for _ in range(3):                       # same spot, 3 times = fake bold
            c.drawString(x, y, text)

    bold(80, h - 100, "1234567890")
    bold(430, h - 100, "Visa No.")
    bold(80, h - 130, "AB1234567")
    bold(430, h - 130, "Passport No.")
    bold(80, h - 160, "Test Person")
    bold(430, h - 160, "Name")
    bold(430, h - 200, "Visa No.")
    bold(80, h - 215, "1234567890")
    bold(430, h - 240, "Application No.")
    bold(80, h - 255, "E123456789")
    mrz = visa_mrz(sex_digit).splitlines()
    c.setFont("Courier", 9)
    c.drawString(60, 90, mrz[0])
    c.drawString(60, 78, mrz[1])
    c.save()


def test_overprinted_pdf_female():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "visa.pdf"
        _make_overprinted_pdf(pdf, "2")
        r = extract_passport_data(pdf)
        assert r.visa_number == "1234567890", r.visa_number
        assert r.passport_number == "AB1234567", r.passport_number
        assert r.gender == Gender.FEMALE, r.gender


def test_overprinted_pdf_male():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "visa.pdf"
        _make_overprinted_pdf(pdf, "1")
        r = extract_passport_data(pdf)
        assert r.visa_number == "1234567890", r.visa_number
        assert r.gender == Gender.MALE, r.gender


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
