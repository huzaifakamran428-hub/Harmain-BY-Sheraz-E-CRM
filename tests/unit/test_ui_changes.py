"""
Tests for the interface changes: party Edit, highlight colour setting,
gender placeholder / auto-detection in the pilgrim dialog, button sizes.

Runs without a screen (Qt 'offscreen'). Skipped if PyQt6 is not installed.
Run with:  python tests/unit/test_ui_changes.py
"""
import os
import sys
import tempfile
from datetime import date, time, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
os.environ["HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton
    from PyQt6.QtGui import QColor
except ImportError:
    print("SKIPPED (PyQt6 not installed)")
    sys.exit(0)

app = QApplication(sys.argv)

from infrastructure.db import initialize_database
from domain.models import Gender
from infrastructure.ocr_service import OcrResult

initialize_database()
from presentation.app_context import AppContext
from presentation.themes import build_stylesheet

ctx = AppContext()
ctx.auth.create_first_admin("admin", "secret1")
ctx.auth.login("admin", "secret1")
app.setStyleSheet(build_stylesheet(ctx.settings.get("theme")))
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)


def _party():
    return ctx.parties.create_party("Test Party", "0300-1111111", "Lahore", "35202-0000000-1")


# ------------------------------------------------------------ party edit
def test_party_edit_dialog_saves_all_fields():
    from presentation.dialogs.party_dialog import PartyDialog
    party = _party()
    dialog = PartyDialog(ctx, party=party)
    assert dialog.name_input.text() == "Test Party"
    dialog.name_input.setText("Renamed Party")
    dialog.phone_input.setText("0321-2222222")
    dialog.address_input.setText("Karachi")
    dialog.cnic_input.setText("42101-9999999-9")
    dialog._save()
    saved = ctx.parties.get_party_with_totals(party.id)
    assert (saved.name, saved.phone, saved.address, saved.cnic) == (
        "Renamed Party", "0321-2222222", "Karachi", "42101-9999999-9")


def test_party_edit_cancel_does_not_touch_the_list_object():
    from presentation.dialogs.party_dialog import PartyDialog
    party = _party()
    dialog = PartyDialog(ctx, party=party)
    dialog.name_input.setText("Changed but cancelled")
    assert party.name == "Test Party"          # dialog works on a copy


def test_parties_page_has_edit_button():
    from presentation.pages.parties_page import PartiesPage
    _party()
    page = PartiesPage(ctx)
    page.resize(1000, 500); page.show(); app.processEvents()
    labels = [b.text() for b in page.table.cellWidget(0, 6).findChildren(QPushButton)]
    assert labels == ["Open Ledger", "Edit"], labels


# --------------------------------------------------- buttons never clipped
def test_row_buttons_are_wide_enough_for_their_text():
    from presentation.widgets.buttons import make_row_button
    from PyQt6.QtGui import QFontMetrics
    for text in ("Edit", "Pay", "Closed", "Clear", "Move to Free", "Return to Party", "Open Ledger"):
        button = make_row_button(text)
        button.show(); app.processEvents()
        needed = QFontMetrics(button.font()).horizontalAdvance(text) + 22
        assert button.width() >= needed, (text, button.width(), needed)


def test_ledger_actions_column_holds_all_buttons():
    from presentation.widgets.pilgrim_table import (
        build_table, populate_pilgrim_rows, LEDGER_COLUMNS, ACTIONS_FIRST,
    )
    party = _party()
    p = ctx.pilgrims.add_pilgrim(party.id, "Row Test", Gender.MALE,
                                 date.today() + timedelta(days=30), time(9, 0))
    table = build_table(LEDGER_COLUMNS)
    table.resize(1100, 300); table.show()
    populate_pilgrim_rows(table, [p], LEDGER_COLUMNS, True, on_edit=lambda x: None,
                          on_pay=lambda x: None, extra_action=("Move to Free", lambda x: None))
    app.processEvents()
    actions_col = 0 if ACTIONS_FIRST else len(LEDGER_COLUMNS)
    assert table.horizontalHeaderItem(actions_col).text() == "Actions"
    cell = table.cellWidget(0, actions_col)
    buttons = cell.findChildren(QPushButton)
    assert [b.text() for b in buttons] == ["Edit", "Pay", "Move to Free"]
    # every button fits inside the column (cell padding is 8px each side)
    right_edge = max(b.geometry().right() for b in buttons)
    assert right_edge <= table.columnWidth(actions_col) - 16, (right_edge, table.columnWidth(actions_col))


def test_long_names_are_shown_in_full():
    from presentation.widgets.pilgrim_table import (
        build_table, populate_pilgrim_rows, LEDGER_COLUMNS, ACTIONS_FIRST,
    )
    from PyQt6.QtGui import QFontMetrics
    party = _party()
    long_name = "Dostmuhammad Saidrahman Muhammadyar Khan"
    p = ctx.pilgrims.add_pilgrim(party.id, long_name, Gender.MALE,
                                 date.today() + timedelta(days=30), time(9, 0))
    table = build_table(LEDGER_COLUMNS)
    table.resize(1100, 300); table.show()
    populate_pilgrim_rows(table, [p], LEDGER_COLUMNS, True)
    app.processEvents()
    col = LEDGER_COLUMNS.index("Name") + (1 if ACTIONS_FIRST else 0)
    needed = QFontMetrics(table.font()).horizontalAdvance(long_name)
    assert table.columnWidth(col) >= needed, (table.columnWidth(col), needed)
    assert table.item(0, col).toolTip() == long_name


# ----------------------------------------------------- highlight colour
def test_upcoming_colour_default_and_custom():
    from core.config import DEFAULT_UPCOMING_COLOR
    assert ctx.settings.upcoming_color() == DEFAULT_UPCOMING_COLOR
    ctx.settings.set("upcoming_color", "#12ab34")
    assert ctx.settings.upcoming_color() == "#12ab34"
    ctx.settings.set("upcoming_color", "not-a-colour")          # bad value -> safe default
    assert ctx.settings.upcoming_color() == DEFAULT_UPCOMING_COLOR


def test_settings_page_saves_colour_and_ledger_uses_it():
    from presentation.pages.settings_page import SettingsPage
    from presentation.widgets.pilgrim_table import (
        build_table, populate_pilgrim_rows, LEDGER_COLUMNS, ACTIONS_FIRST,
    )
    page = SettingsPage(ctx)
    page._set_upcoming_color("#2255ff")
    page._save_general()
    assert ctx.settings.upcoming_color() == "#2255ff"

    party = _party()
    soon = ctx.pilgrims.add_pilgrim(party.id, "Soon Person", Gender.FEMALE,
                                    date.today() + timedelta(days=1), time(23, 0))
    later = ctx.pilgrims.add_pilgrim(party.id, "Later Person", Gender.FEMALE,
                                     date.today() + timedelta(days=30), time(9, 0))
    table = build_table(LEDGER_COLUMNS)
    populate_pilgrim_rows(table, [soon, later], LEDGER_COLUMNS, True,
                          upcoming_color=ctx.settings.upcoming_color(),
                          reminder_days=ctx.settings.reminder_days())
    name_col = LEDGER_COLUMNS.index("Name") + (1 if ACTIONS_FIRST else 0)
    assert table.item(0, name_col).foreground().color() == QColor("#2255ff")
    assert table.item(1, name_col).foreground().color() != QColor("#2255ff")

    page._set_upcoming_color("#e0455c"); page._save_general()   # put default back


# ------------------------------------------------------- email address check
def _fill_valid(dialog, name, email):
    dialog.name_input.setText(name)
    dialog.gender_input.setCurrentIndex(1)
    dialog.email_input.setText(email)


def test_broken_email_blocks_save_in_dialog():
    dialog = _dialog()
    _fill_valid(dialog, "Mail Test One", "not-an-email")
    dialog._save()
    assert dialog.result_pilgrim is None
    assert "@" in dialog.error_label.text(), dialog.error_label.text()


def test_suspicious_email_asks_and_no_means_not_saved():
    dialog = _dialog()
    _fill_valid(dialog, "Mail Test Two", "sakjfsajkfjskdfjsakdjfklasjdfks@gmail.com")
    asked = []
    QMessageBox.question = staticmethod(
        lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.No)
    dialog._save()
    assert asked and "Address not found" in asked[0]
    assert dialog.result_pilgrim is None


def test_suspicious_email_yes_saves():
    dialog = _dialog()
    _fill_valid(dialog, "Mail Test Three", "ahmed@gmial.com")
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._save()
    assert dialog.result_pilgrim is not None and dialog.result_pilgrim.email == "ahmed@gmial.com"


# --------------------------------------------------------------- gender
def _dialog():
    from presentation.dialogs.pilgrim_dialog import PilgrimDialog
    return PilgrimDialog(ctx, _party().id)


def test_new_pilgrim_gender_starts_unchosen_and_blocks_save():
    dialog = _dialog()
    assert dialog.gender_input.currentIndex() == 0
    dialog.name_input.setText("No Gender Yet")
    dialog._save()
    assert "gender" in dialog.error_label.text().lower()
    assert dialog.result_pilgrim is None


def test_document_result_sets_female_and_says_where_from():
    dialog = _dialog()
    result = OcrResult(name="Zubaida Bi", passport_number="AB1234567",
                       visa_number="1234567890", gender=Gender.FEMALE, gender_source="MRZ code")
    ctx.documents.run_ocr = lambda path: result
    dialog._run_reader(Path("x.pdf"))
    assert dialog.gender_input.currentText() == "Female"
    assert dialog.visa_input.text() == "1234567890"
    assert "auto-detected" in dialog.gender_hint.text()


def test_guessed_gender_is_flagged_as_guess():
    dialog = _dialog()
    result = OcrResult(name="Ayesha Bibi", gender=Gender.FEMALE, gender_source="name (guess)")
    ctx.documents.run_ocr = lambda path: result
    dialog._run_reader(Path("x.pdf"))
    assert "GUESSED" in dialog.gender_hint.text()


def test_missing_gender_asks_user_to_choose():
    dialog = _dialog()
    ctx.documents.run_ocr = lambda path: OcrResult(name="Some One", visa_number="1234567890")
    dialog._run_reader(Path("x.pdf"))
    assert dialog.gender_input.currentIndex() == 0
    assert "choose" in dialog.gender_hint.text().lower()


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
