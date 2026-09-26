# Changes in this version

## Serial numbers, party in reminders, Google Drive backup
* **Serial numbers never repeat.** Each party counts 1, 2, 3 ... on its own. A pilgrim who comes back from the Free
  Account now takes that party's **next** number (before, the old number came back with them and clashed - the bill
  showed 1, 2, 2, 5, 6, 7, 9). Numbers of pilgrims who moved to the Free Account are not handed out again.
  Existing duplicates are fixed automatically the next time the app starts (the pilgrim who was NOT returned keeps
  the number, the other gets the party's next one).
* **Free Account has its own numbering.** Male and Female each count 1, 2, 3 ... (shown in the SR column and in the
  Excel export). Pilgrims already in the Free Account are numbered in the order they were moved there.
* **Dashboard -> Upcoming Permits (Next 2 Days)**: the card now has **View Pilgrims & Parties** (clicking the card does
  the same). The list shows the **party name** for every pilgrim, and **Open Party** (or double-click) jumps to it.
* **Reminder email shows the party**: in the subject (`Permit Reminder - <name> - Party: <party> (<date>)`), in the
  sentence, and as the first row of the details table.
* **Google Drive backup no longer fails with "disk I/O error".** The database snapshot is now made in a local temporary
  folder and copied to Drive as a normal file (SQLite cannot run on a Google Drive / iCloud folder). Unchanged files are
  skipped, so Drive is not re-uploading everything every minute. Restore reads the same way.
* Test: `tests/integration/test_serials_party_backup.py`.

## Pilgrim photo, picked up automatically from the uploaded document
* Uploading a passport/visa document now also tries to pull out a picture of the pilgrim: for a digital visa PDF
  (Saudi e-visa, Nusuk permit) the embedded photo object is read directly off the page - the same picture printed
  next to the visa number - with no OCR or internet needed. For a plain photo upload (a phone picture of a document)
  the face is detected automatically if the optional `opencv-python` package is installed; otherwise (or if nothing
  could be found) use the new **Set Photo** button in the pilgrim form to choose the picture by hand.
* The photo appears as a small circle in the **Photo** column, now the first column in both the Party Ledger and the
  Free Account, before **SR**. A pilgrim with no photo yet shows their initials in a plain circle instead.
* Existing databases are upgraded automatically the next time the app starts - no data is lost, and pilgrims saved
  before this version simply show the initials placeholder until a document is uploaded or a photo is set by hand.

## Reminder is checked right after you save a pilgrim
* Before, a new pilgrim was only picked up on the next timer tick (every *Background Check Interval* minutes), so going
  straight to Notifications showed nothing until you pressed **Check Reminders Now**. Now saving (or editing) a pilgrim
  runs a check about a second later, and saving the Email settings does too (and retries failed reminders at once).
* The Notifications list refreshes itself when the automatic check sends something.

## Gmail in the reminder, and no logo
* The pilgrim form now says **Gmail (code arrives here)** and asks "Save without a Gmail?" when it is left empty
  (the old hint said it was used to email the pilgrim - it no longer is). The reminder shows that Gmail, or
  **NOT ADDED** if there is none.
* When you add or correct a pilgrim's Gmail **after** the reminder was sent, the old reminder is marked *Replaced*
  and the next automatic check sends you one corrected reminder (once).
* Reminder emails have **no logo** by default (plain text header). Settings -> Email -> *Include my logo in reminder
  emails* turns it back on.

## Reminders are email-only and go to the administrator
* The 2-day reminder is now sent **only by email, only to you** (Settings -> Email -> *Send Reminders To (you)*;
  falls back to the Sender address if empty). It is **no longer emailed to the pilgrim**, and works even when the
  pilgrim has no email address.
* **No desktop pop-up** and **no WhatsApp message** for reminders any more. (Tray messages for the automatic
  Free Account move and "still running in the background" are separate and unchanged.)
* The email is now written to you about the pilgrim ("The permit for <name> is coming up in N day(s)"), with the
  pilgrim's name in the subject. The details table is unchanged.
* **Automatic, verified.** `tests/integration/test_automatic_scheduler.py` runs the real scheduler tick and confirms,
  with no button pressed: pilgrims 6+ hours past their permit move to Free Male / Free Female by gender (5 hours: not
  yet), and a reminder email goes out once when a permit is within 2 days (not before). The Notifications page now says so.
* **Failed reminders no longer pile up.** A reminder that fails (no internet, bad password) keeps ONE row, retried about
  every 10 minutes and switched to Sent when it works - it used to add a new Failed row every minute. "Check Reminders
  Now" retries immediately.
* Tests: the reminder tests in `tests/unit/test_email_features.py` check recipient, no desktop call, email-only
  records, and once-only sending.

## Fixed
1. **Visa number written three times / wrong number.**
   The Saudi e-visa PDF draws every character 2-3 times on top of itself, and prints the
   visa number *before* the words "Visa No.". `infrastructure/ocr_service.py` now removes
   the stacked duplicates, scores every 8-12 digit number (next to "Visa No.", printed twice,
   not next to "Application No.") and picks the right one. Works for PDF text, scanned PDF
   and photos.
2. **Gender not detected / always Male.**
   The visa has no Sex field. Gender is now read from: the code line at the bottom
   (1 = male, 2 = female; ICAO letter M/F also supported), then Sex/Gender labels (English
   and Arabic, including reversed Arabic from PDFs), then a *flagged guess* from the name.
   The Gender box now starts on "Select gender..." and Save requires a choice; the hint
   under the box says where the value came from.
3. **Buttons clipped ("Move to Free" cut in half, overlapping buttons).**
   New `presentation/widgets/buttons.py` measures each button from its text and fixes its size;
   the Actions column is computed from the real labels. The Actions column stays LAST in the
   Party Ledger and Free Account; to move it to the front set `ACTIONS_FIRST = True` in
   `pilgrim_table.py`. Dates no longer wrap.
4. **Dropdowns not working / invisible.**
   Arrow images are drawn per theme (`presentation/icons.py`), date/time/number boxes have real
   up-down buttons, dropdown lists and the calendar are opaque and readable, and every
   dropdown uses `StyledComboBox` (a plain list view) so it opens correctly on macOS.
5. Settings tab title "Branding & Bill" showed as "Branding _Bill"; tab titles are no longer cut.
6. Theme "Glass Gold" had a typo colour (`#d8b martin`) patched at runtime; fixed at the source.
7. Settings -> Document Reading said "installed" even when PDF text readers were missing;
   it now reports it, shows each error and the Python path in use. PyMuPDF is imported as
   `pymupdf` first (falls back to `fitz`).

8. **Long names cut with "...".** The Name and Email columns now grow to show the longest value in
   full (capped at 460px; hovering shows the full value). Same table code, so it applies to the
   Party Ledger and the Free Account.

9. **Old logo in emails / imported logo ignored.** `find_logo_path()` in `infrastructure/email_templates.py`
   only looked in `assets/`. It now uses `get_logo_path()` (Settings -> Branding first, then `assets/`),
   trims the empty margin, shrinks it to 520px (~60 KB) and colours the header band to match. The logo
   already contains the business name, so the duplicate text title is dropped when a logo is present.
   `assets/logo.png` (placeholder) replaced by `assets/logo.jpg` (HaramaIn by Sheraz logo).
10. **"Address not found" bounces.** A non-existent address is only reported by Gmail afterwards, so it can
    not be detected at send time. `domain/rules.py: check_email()` now stops broken addresses (error) and
    asks about suspicious ones (warning: provider typos, Gmail name > 30 chars or with illegal characters)
    in the pilgrim dialog; the service also refuses broken ones, and the reminder skips them.
11. Email body: names, e-mail, contact number and business name are HTML-escaped; the business name from
    Settings is now used in the email (it was always the default text).

## Added
* **Parties -> Edit** (name, phone, address, CNIC). The dialog edits a copy, so cancelling
  changes nothing.
* **Settings -> General -> Upcoming Permit Colour** (default red, Choose Colour / Reset to Red).
  Stored as `upcoming_color`. The ledger also uses the *Reminder Window (days)* setting,
  which it ignored before.
* Tests: `tests/unit/test_visa_reading.py`, `tests/unit/test_ui_changes.py`.
  Test data is invented; no real passport data is included.

## Known, not changed
* A pilgrim returned from the Free Account keeps the old serial number, so a party can have
  two pilgrims with the same serial.
* `record_payment` does not stop a payment larger than the remaining balance (the dialog does).
* SMTP password / WhatsApp token are stored as plain text in the local database.
