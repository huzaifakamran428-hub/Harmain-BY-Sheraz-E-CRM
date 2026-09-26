# HaramaIn — Riyazul Jannah Permit & Pilgrim Management System

A desktop application for managing Riyazul Jannah permit bookings: parties,
pilgrims, payments, automatic permit reminders, gender-routed Free Accounts,
and printable A6 permit slips.

Runs on **Windows**, **macOS** and **Linux**. Everything is stored in a single
local database file — no server to install, no internet connection required for
day-to-day use.

---

## Table of contents

1. [What's new in this version](#1-whats-new-in-this-version)
2. [Quick start](#2-quick-start)
3. [Installing Tesseract (for reading photos and scans)](#3-installing-tesseract)
4. [Adding your logo](#4-adding-your-logo)
5. [The screens, one by one](#5-the-screens-one-by-one)
6. [Business rules in plain language](#6-business-rules-in-plain-language)
7. [Uploading a passport or visa](#7-uploading-a-passport-or-visa)
8. [Payments and the "Payment Clear" badge](#8-payments-and-the-payment-clear-badge)
9. [The Free Account and the 6-hour rule](#9-the-free-account-and-the-6-hour-rule)
10. [The A6 permit slip (bill)](#10-the-a6-permit-slip-bill)
11. [Reminders: email to you only](#11-reminders-email-to-you-only)
12. [Settings reference](#12-settings-reference)
13. [Where your data lives, and how to back it up](#13-where-your-data-lives)
14. [Troubleshooting](#14-troubleshooting)
15. [For developers: architecture](#15-for-developers-architecture)
16. [Running the tests](#16-running-the-tests)
17. [Building a Windows .exe / macOS .app](#17-building-an-installer)

---

## 1. What's new in this version

| Area | What changed |
|---|---|
| **Pilgrim photo** | Uploading a document now also picks up a circular photo of the pilgrim automatically - the embedded picture in a digital visa PDF, or (with `opencv-python` installed) a detected face in a plain photo upload. Shown as the first column, **Photo**, before **SR**, in the Party Ledger and Free Account. Use **Set Photo** in the pilgrim form to choose it by hand when nothing is picked up automatically. |
| **Visa number fix** | Some PDFs (the Saudi e-visa) print every character 2–3 times on top of itself, which made the visa number come out as `111222333444…`. The reader now removes the duplicates, finds the number whether it is printed before or after the words "Visa No.", and ignores the Application No. |
| **Gender from the visa** | The Saudi e-visa has no Sex field. The reader now uses the number in the code line at the bottom (`1` = male, `2` = female), then any Sex/Gender label, then — only as a flagged guess — the name (Bibi, Begum, Khatoon, "Bi"). If nothing is found the box stays on **Select gender...** instead of silently saying Male. |
| **Logo in emails** | Reminder emails go only to you, so they have **no logo by default** (a plain text header). Tick **Settings -> Email -> Include my logo in reminder emails** to bring it back. |
| **Email address check** | Broken addresses are refused when saving a pilgrim; suspicious ones ask "Save anyway?", so a made-up address no longer causes a silent "Address not found" bounce. |
| **Edit party** | **Parties → Edit** changes name, phone, address and CNIC. |
| **Buttons and dropdowns** | Row buttons are sized from their text, so "Move to Free" is never cut. The **Actions column is the last column** in both the Party Ledger and the Free Account (scroll right, or enlarge the window, to reach it). Every dropdown, date box, time box and number box now shows a visible arrow, and the lists open readable on macOS. |
| **Upcoming-permit colour** | **Settings → General → Upcoming Permit Colour** chooses the colour of pilgrims inside the reminder window (red by default, **Reset to Red** brings it back). The ledger now also follows the *Reminder Window (days)* setting. |
| **Document upload** | Uploads no longer bounce with "enter values manually". The reader now tries four different methods and picks the first that works — including reading digital PDF visas with no OCR engine at all. |
| **Automatic gender** | Gender is now picked up from passport MRZ codes, English labels (`Sex`, `Gender`, `M`, `F`, `MALE`, `FEMALE`), Arabic wording (`ذكر`, `أنثى`), honorifics, and form layouts where the letter sits on the next line. |
| **Password rule** | Now always *first letter capital, rest small*, then `111@` — `MUHAMMAD ALI` → `Muhammad111@`. |
| **Buttons** | Every button has a real minimum width, larger padding and a visible border. Table rows are taller and the Actions column is sized from the number of buttons in it, so nothing is clipped. |
| **Bill** | Completely redesigned. **No pilgrim names.** Shows serial, date, time, gender, and male/female/total counts, with a proper header band (logo + business name) and footer band (footer line, reference, contact, page number). |
| **Logo** | Appears in the sidebar, on the A6 bill header and as the tray/app icon. Imported from **Settings → Branding & Bill**. |
| **Payments** | Multiple part-payments per pilgrim; a bold green **PAYMENT CLEAR** badge and a disabled **"Payment is Clear"** button once the balance reaches zero. |
| **Free Account** | Payments are locked while a pilgrim sits in a Free Account. Returning them to a party removes them from the Free Account and re-opens payments. |
| **Look and feel** | New glass (frosted) theme system with 8 palettes, translucent cards, soft gradients, rounded controls and modern tables. |

---

## 2. Quick start

### Requirements

* **Python 3.10 or newer** — <https://www.python.org/downloads/>
  On Windows, tick **"Add Python to PATH"** during install.

### Install

```bash
# 1. go into the project folder
cd haramain

# 2. (recommended) create an isolated environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. install the libraries
pip install -r requirements.txt

# 4. run
python main.py
```

### First run

The first time it starts, the app asks you to create the **administrator
account**. Choose a username and a password (at least 6 characters) and keep
them safe — there is no "forgot password" e-mail, because the database lives
only on your own computer.

---

## 3. Installing Tesseract

**You only need this for photos and scanned documents.** Digital PDF visas
(Saudi e-visa, Nusuk permits, most e-tickets) are read without it.

| System | How |
|---|---|
| **Windows** | Download the installer from <https://github.com/UB-Mannheim/tesseract/wiki>, install it, and make sure "Add to PATH" is selected. Restart the app. |
| **macOS** | `brew install tesseract` |
| **Ubuntu / Debian** | `sudo apt install tesseract-ocr` |

To confirm it worked, open **Settings → Document Reading**. You should see a
green tick next to *"Photos and image scans"*.

> If Tesseract is installed but the app cannot find it, add this at the top of
> `infrastructure/ocr_service.py`, pointing at your own install path:
> ```python
> import pytesseract
> pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
> ```

---

## 4. Adding your logo

1. Open **Settings → Branding & Bill**.
2. Click **Import Logo…** and choose your image (PNG, JPG, WEBP, BMP or ICO).
3. The logo appears immediately in the sidebar, on the app icon, and in the
   header of every new bill.

A **PNG with a transparent background** looks best, because the bill header is
dark. Square or slightly wide images work well; very tall images get scaled
down and may look small.

The file is **copied into the app's own folder**, so it keeps working even if
you later move or delete the original. A placeholder logo ships in `assets/logo.png` —
importing your own replaces it everywhere.

On the same tab you can also set:

* **Business Name** — sidebar title and bill header (e.g. *HaramaIn by Sheraz*)
* **Bill Subtitle** — the small gold line under it (e.g. *Riyazul Jannah Permit Slip*)
* **Bill Footer Line** — the bold line in the footer band (e.g. *Thank you for choosing HaramaIn*)

---

## 5. The screens, one by one

### Dashboard
Live totals: active pilgrims, Free Account male/female counts, total visited,
permits coming up in the next two days, and total charges / received /
remaining across every party.

### Parties
Every travel party with its people count and money totals. **Open Ledger**
(or double-click a row) opens that party's pilgrim list. **Edit** changes the
party's name, phone, address and CNIC.

### Party Ledger
The working screen. Search by name, passport or visa number, filter by gender,
show or hide passwords, and per row: **Edit**, **Pay**, **Move to Free**
(these buttons are in the last column, on the right).
Pilgrims whose permit is within the reminder window are shown in the
*Upcoming Permit Colour* from Settings (bold red by default).

* **+ Add Pilgrim** — opens the pilgrim form with document upload.
* **Generate A6 Bill (PDF)** — the printable permit slip.

### Free Account
Two tabs, **Male** and **Female**. Pilgrims arrive here automatically six hours
after their permit time, routed by gender. Full details stay visible, including
gender. One action per row: **Return to Party**.

### Reports
Party-wise totals, and a visited/completed list.

### Notifications
Every reminder the app has tried to send, with channel, status and failure
reason. **Check Reminders Now** runs the check immediately.

### Settings
General, Branding & Bill, Document Reading, Email, WhatsApp, Account.

---

## 6. Business rules in plain language

| Rule | Behaviour |
|---|---|
| **Password** | First name, first letter capital and the rest small, then `111@`. `MUHAMMAD ALI` → `Muhammad111@`, `aYeSHa` → `Ayesha111@`. Editable per pilgrim. |
| **Serial number** | Numbered from 1 within each party. |
| **Charge** | Defaults to the value in Settings (200 PKR out of the box); changeable per pilgrim. |
| **Remaining** | `Charge − total received`. |
| **Payment clear** | When remaining reaches 0, a bold green badge shows and the record button locks. |
| **Free Account transfer** | 6 hours after the permit date/time, automatically — males to Male, females to Female. |
| **Payments in Free Account** | Blocked. Return the pilgrim to a party first. |
| **Return to party** | Removes them from the Free Account, sets them Active on the chosen party, re-opens payments, and is written to the return history. |
| **Reminder window** | 2 days before the permit date/time (configurable). |
| **Duplicates** | Warns if a passport or visa number already exists; you can still save after confirming. |
| **Bill privacy** | No names, no passport/visa numbers, no money. |

All of these are pure functions in `domain/rules.py` and covered by tests.

---

## 7. Uploading a passport or visa

In **Add / Edit Pilgrim**, click **Upload Document**. Accepted:
`.pdf .png .jpg .jpeg .webp .bmp .tif .tiff .heic .heif`, up to 15 MB.

The reader tries these in order and stops at the first that works:

1. **PDF text layer** — for digital visas. Exact, instant, **no OCR needed**.
2. **PDF page rendering + OCR** — for scanned PDFs (PyMuPDF, no extra program).
3. **Image OCR** — photos and scans. Images are converted to greyscale,
   auto-contrasted, upscaled and sharpened, then read with three different
   Tesseract page modes; the best result wins.
4. **EasyOCR** — used only if you have installed it.

It fills **name, passport number, visa number and gender**, and tells you which
fields it filled and by which method. When gender is detected you see a small
green *"auto-detected: Male/Female"* note beside the dropdown.

**Everything stays editable.** Reading is never assumed correct — always check
the fields before saving.

Two buttons help when a read goes wrong:

* **Read Again** — re-runs the reader on the attached file.
* **Show Read Text** — shows exactly what came out of the document, so you can
  see whether the photo was the problem.

> **The file is always attached, even if nothing could be read.** A failed read
> never blocks saving the pilgrim.

### Getting better results from photos

* Lay the document flat and fill the frame with it.
* Even lighting, no flash glare across the text.
* Shoot straight on, not at an angle.
* For passports, include the two lines of `<<<<` codes at the bottom — that
  machine-readable zone gives the most accurate name, number and gender.

---

## 8. Payments and the "Payment Clear" badge

Click **Pay** on a ledger row.

* Record as many part-payments as you like; each appears in the history with a
  running total.
* **Pay Full Remaining** fills the outstanding amount in one click.
* The badge at the top shows **DUE <amount>** while money is outstanding.
* The moment the balance reaches zero, the badge turns into a bold green
  **PAYMENT CLEAR**, the button changes to a disabled **"Payment is Clear"**,
  and the amount fields lock. Trying to record more is refused.
* In the ledger, that row's button reads **Clear** and the Status column shows
  **Clear** in green.
* For a pilgrim in a Free Account, the button reads **Closed** and the dialog
  explains that the ledger is shut until they are returned to a party.

---

## 9. The Free Account and the 6-hour rule

A background check runs when the app starts and then every minute (configurable
in **Settings → General → Background Check Interval**). It looks for **Active**
pilgrims whose permit date and time passed **6 hours or more** ago, and moves
each one into the Free Account:

* **Male** pilgrims → **Male** tab
* **Female** pilgrims → **Female** tab

The move is atomic and idempotent — a pilgrim is moved exactly once, and a
failure never leaves someone half-moved. A tray notification tells you when
pilgrims have been moved, and the open screens refresh themselves.

**Move to Free** on a ledger row does the same thing immediately, ahead of the
6-hour mark. **Run 6-Hour Check Now** on the Free Account page forces the sweep.

**Returning someone:** click **Return to Party**, choose the destination party
and optionally a reason. They disappear from the Free Account, reappear on that
party's ledger as Active, and payments re-open. The move is recorded in the
return history with who did it and when.

> The app must be **running** (it can be minimised to the tray) for the
> automatic check to happen. Closing the window keeps it running in the
> background; use **Quit** in the tray menu to stop it completely.

---

## 10. The A6 permit slip (bill)

From a party ledger, click **Generate A6 Bill (PDF)** and choose where to save.

**What the bill shows**

* Header band: your logo, business name, subtitle, print date and time
* Reference strip: booking reference (e.g. `RJ-0012-1809`) and permit day
* Table: **SR · DATE · TIME · GENDER**
* Totals strip: **MALE · FEMALE · TOTAL PERSONS**, in large bold figures
* Note line about arriving 30 minutes early
* Footer band: your footer line, reference, contact number, page number

**What the bill never shows**

* Pilgrim names
* Passport or visa numbers
* Email addresses or passwords
* Charges, payments or balances

This is deliberate: the slip is handed over in public, so it carries only what
identifies a booking slot.

Paper size is A6 (105 × 148 mm). Print at **100% / Actual size** — don't let the
printer "fit to page", or the layout will shrink.

---

## 11. Reminders: email to you only

Two days before a permit (configurable), the app sends **one email to you, the
administrator** - you are the one who accepts and confirms the booking, so you
are the one who is reminded. **Nothing is sent to the pilgrim**, and there is
no desktop pop-up and no WhatsApp message for reminders.

The email names the pilgrim and shows their gender, **Gmail (the one the booking
code arrives on)**, password, permit date and time, so you have everything needed
to confirm the booking. If no Gmail was added for that pilgrim, the email says
**NOT ADDED** - open the pilgrim (**Party Ledger -> Edit**) and type it in; the app
then sends you one corrected reminder by itself. Reminder emails carry no logo
unless you tick **Include my logo in reminder emails** in **Settings -> Email**. A reminder is
never sent twice for the same pilgrim and permit, and every attempt is logged on
the Notifications page.

**It is automatic.** You never press anything: the app checks **right after you
save a pilgrim** (or the email settings), and again every minute
(**Settings -> General -> Background Check Interval**), and emails you the
moment a permit is within the reminder window. The **Check Reminders Now**
button only forces an immediate check. The app must be running for this - closing
the window keeps it running in the tray; **Quit** in the tray menu stops it.
If an email cannot be sent (no internet, wrong app password) the same row on the
Notifications page shows the reason, and the app retries by itself about every
10 minutes until it goes through.

Set it up in **Settings -> Email**:

* **SMTP details** - for Gmail use an
  [App Password](https://support.google.com/accounts/answer/185833), host
  `smtp.gmail.com`, port `587`, TLS on.
* **Send Reminders To (you)** - your own email address. If left empty, the
  Sender Email Address is used, so the reminder still lands in your inbox.

The pilgrim's Gmail is only stored and shown to you in the reminder; the app
never writes to it.

---

## 12. Settings reference

### General
| Setting | Meaning |
|---|---|
| Theme | One of 8 glass palettes (below) |
| Default Charge | Pre-filled charge for a new pilgrim |
| Your Contact Number | Shown on reminder emails and in the bill footer |
| Reminder Window | Days before the permit to start reminding and highlighting (default 2) |
| Upcoming Permit Colour | Colour of pilgrims inside the reminder window. Red by default; **Choose Colour** to change, **Reset to Red** to undo |
| Auto-transfer After | Hours after the permit before moving to Free Account (default 6) |
| Background Check Interval | Minutes between automatic checks (default 1) |

**Themes:** Glass Gold, Glass Midnight, Glass Emerald, Glass Royal, Glass Teal,
Glass Maroon, Frosted Light, Frosted Sand.
Red is reserved for urgent permits and errors; green is reserved for
payment-clear. Older theme names in an existing database are mapped
automatically.

### Branding & Bill
Business name, bill subtitle, bill footer line, logo import/remove.

### Document Reading
A live check of what this computer can read, with exactly what to install if
something is missing, the exact error for each missing part, and the path of
the Python that is running the app (useful when libraries were installed into a
different Python than the one running the app).

### Email / WhatsApp / Account
SMTP details, WhatsApp provider details, and changing your own password.

---

## 13. Where your data lives

| System | Folder |
|---|---|
| Windows | `%APPDATA%\HaramaIn` |
| macOS | `~/Library/Application Support/HaramaIn` |
| Linux | `~/.local/share/HaramaIn` |

Inside it:

```
harmain.db      the database — parties, pilgrims, payments, everything
documents/      uploaded passport/visa files, stored under random names
branding/       your imported logo
logs/           application logs (useful when reporting a problem)
backups/        backup destination
```

### Backing up

**Automatic (recommended):** open **Settings → Backup & Sync** and switch on
iCloud Drive and/or Google Drive. From then on the app copies `harmain.db`,
`documents/`, `photos/` and `branding/` into a `HaramaIn Backup` folder inside
whichever cloud folder you pick, automatically — at startup, every few minutes,
right after any change, and again when you quit. The cloud app (iCloud for
Windows / Google Drive for desktop) then carries that copy off the computer on
its own. The path there must be a **local folder that app keeps in sync** —
use **Auto-Detect** or **Browse** rather than typing a `drive.google.com` /
`icloud.com` web link, which is not a real folder on disk and will be
rejected.

**Manual (extra safety, or if you don't use either cloud service):** close the
app, then copy the whole `HaramaIn` folder above to a USB drive or cloud
folder. To restore, copy it back to the same place. That single folder is your
entire system — database, documents and logo. Do this **weekly at minimum** if
you rely on it instead of the automatic option — the data is not stored
anywhere else.

### Restoring after a Windows reinstall (or on a new computer)

If you were using the automatic cloud backup above, your data survives a full
Windows reinstall. After reinstalling Windows:

1. **Reinstall the cloud app first** — Google Drive for desktop and/or iCloud
   for Windows — and sign in with the same account you backed up with. Give it
   time to fully sync back down to this computer; for Google Drive, watch its
   tray icon until it shows "up to date" rather than "syncing."
2. Confirm the `HaramaIn Backup` folder has reappeared inside your synced
   Google Drive / iCloud Drive folder, with `harmain.db` inside it.
3. **Install HaramaIn** (run `HaramaIn_Setup.exe`, or reinstall Python and the
   requirements if running from source) and **launch it once**, then close it
   again. This step just creates the fresh `%APPDATA%\HaramaIn` folder the app
   expects to find — it's fine that it's empty/new at this point.
4. Open `%APPDATA%\HaramaIn` in File Explorer (type that path directly into
   the address bar). With the app **closed**, copy these from the
   `HaramaIn Backup` folder into it, replacing what's there:
   - `harmain.db`
   - the `documents/` folder
   - the `photos/` folder
   - the `branding/` folder
5. Start HaramaIn. Your parties, pilgrims, payments and settings should all be
   exactly as they were.

Don't skip step 3 (launching once first) — it's what creates the `%APPDATA%`
folder in the right place before you copy anything into it.

### Security notes

* Your administrator password is stored as a PBKDF2-HMAC-SHA256 hash with a
  random salt — never in plain text.
* **Pilgrim passwords are stored as readable text on purpose**, because you
  need to read them out to pilgrims. They are masked in tables until you press
  **Show Passwords**. Anyone with access to the database file can read them, so
  protect the computer with an account password and full-disk encryption
  (BitLocker on Windows, FileVault on macOS).

---

## 14. Troubleshooting

**"It says enter values manually when I upload a visa."**
Open **Settings → Document Reading**. If *"Photos and image scans"* has a red
cross, install Tesseract ([section 3](#3-installing-tesseract)). Digital PDF
visas should work regardless — if they don't, run `pip install -r requirements.txt`
again.

**"Gender is not picked up."**
Use **Show Read Text** in the pilgrim form to see what the reader got. If the
text is garbled, the photo is the problem — retake it flat and well lit. If the
text is clean but gender is missing, the document may write it in a form not yet
recognised; set it manually and it saves normally.

**"Nothing happens when I click Upload."**
Check the file is under 15 MB and one of the accepted types. HEIC photos from
an iPhone may need `pip install pillow-heif`; alternatively export as JPG.

**"Pilgrims are not moving to the Free Account."**
The app must be running (tray counts). Check the permit time really is 6+ hours
ago, check **Auto-transfer After** in Settings, and press **Run 6-Hour Check
Now** on the Free Account page to force it.

**"Reminder emails are not sending."**
Check the Notifications page for the failure reason. For Gmail, an ordinary
account password will not work — you need an App Password.

**"I got an 'Address not found' / 'Mail Delivery Subsystem' message in Gmail."**
Reminders now go only to the address in **Settings -> Email -> Send Reminders To**
(or the Sender address). If you see this message, that address has a typing
mistake - correct it there. Pilgrims' own addresses are no longer emailed, so
they can no longer cause a bounce.

**"The bill prints too small."**
Set the printer to **Actual size / 100%**, not "Fit to page", and select A6 or
a 4×6 label if your printer supports it.

**"I forgot the administrator password."**
There is no recovery. The only route is deleting `harmain.db` from the data
folder, which starts a new empty database — so keep backups.

**"The app looks wrong / buttons overlap."**
Set display scaling to 100% or 125% and restart. Report anything that still
misbehaves, along with the newest file in `logs/`.

**"Something went wrong. Error ID: ABC123."**
That ID is in the log file for that day. Send the matching lines when reporting
the problem.

---

## 15. For developers: architecture

Four layers, each depending only on the one beneath it:

```
presentation/   PyQt6 windows, pages, dialogs, widgets, themes
       ↓
application/    services — the use cases (add pilgrim, record payment, ...)
       ↓
domain/         entities + pure business rules (no Qt, no SQL, no PDF)
       ↓
infrastructure/ SQLite, repositories, OCR, PDF, email, scheduler
core/           config, exceptions, logging, password hashing
```

```
haramain/
├── main.py                       entry point, global exception hook
├── core/
│   ├── config.py                 paths, constants, logo lookup
│   ├── exceptions.py             ApplicationError hierarchy
│   ├── logging_setup.py          rotating logs + error reference IDs
│   └── security.py               PBKDF2 password hashing
├── domain/
│   ├── models.py                 dataclasses: Party, Pilgrim, Payment, ...
│   └── rules.py                  password, balance, reminder, 6-hour, routing
├── application/
│   ├── auth_service.py           login, first-run setup, password change
│   ├── party_service.py          parties + aggregate totals
│   ├── pilgrim_service.py        pilgrims, serials, duplicates, balances
│   ├── payment_service.py        payments + free-account/clear guards
│   ├── free_account_service.py   6-hour sweep, return-to-party (atomic)
│   ├── document_service.py       upload, validation, reader capabilities
│   ├── bill_service.py           bill generation with branding
│   ├── report_service.py         dashboard and report queries
│   ├── reminder_service.py       2-day reminders across channels
│   └── settings_service.py       settings with defaults
├── infrastructure/
│   ├── db.py                     SQLite schema, connections, transactions
│   ├── repositories.py           all SQL lives here
│   ├── ocr_service.py            multi-backend reader + gender detection
│   ├── photo_service.py          pilgrim photo: PDF embedded photo + face detection
│   ├── pdf_generator.py          A6 bill
│   ├── notification_service.py   desktop / SMTP / WhatsApp senders
│   ├── email_templates.py        HTML reminder email
│   └── scheduler.py              QTimer background sweeps
├── presentation/
│   ├── themes.py                 glass palettes + stylesheet builder
│   ├── login_window.py           sign-in + first-run setup
│   ├── main_window.py            sidebar, navigation, tray, scheduler
│   ├── app_context.py            one instance of each service + error handler
│   ├── pages/                    dashboard, parties, ledger, free account,
│   │                             reports, notifications, settings
│   ├── dialogs/                  party, pilgrim, payment, return
│   └── widgets/                  pilgrim table, summary header, photo avatars
├── assets/logo.png               default logo (replace via Settings)
├── tests/                        unit + integration
└── deployment/                   PyInstaller specs
```

**Design notes**

* The domain layer imports nothing from PyQt6, sqlite3, reportlab or OCR
  libraries, so the rules can be tested in isolation.
* All SQL is in `repositories.py`; the UI never writes a query.
* Multi-step writes run inside `infrastructure.db.transaction()` and roll back
  as one unit.
* Unexpected errors are logged with a short reference ID; the user only ever
  sees a safe message, never a stack trace.
* SQLite is used instead of a server database so the app "just works" on a
  single machine. Because everything goes through the repositories, swapping in
  Django ORM + MySQL for a multi-computer deployment touches only `db.py` and
  `repositories.py`.

---

## 16. Running the tests

```bash
python tests/unit/test_domain_rules.py        # password, balance, 6-hour, routing
python tests/unit/test_document_reading.py    # MRZ, English/Arabic gender parsing
python tests/unit/test_visa_reading.py        # visa number (overprinted PDFs, value before label), gender from code line
python tests/unit/test_photo_extraction.py    # picks the portrait photo over square seals/QR codes in a visa PDF
python tests/unit/test_ui_changes.py          # party Edit, colour setting, gender box, button sizes (no screen needed)
python tests/integration/test_automatic_scheduler.py   # scheduler ticks: 6-hour move + automatic reminder email, no button pressed
python tests/integration/test_full_flow.py    # login → party → pilgrim → pay → transfer → return → bill
```

Each script prints a PASS/FAIL line per check and exits non-zero on failure, so
they work in CI without pytest installed.

---

## 17. Building an installer

PyInstaller specs are in `deployment/`.

**Windows**
```bash
pip install pyinstaller
pyinstaller deployment/windows/harmain.spec
```
Result: `dist/HaramaIn/HaramaIn.exe`

**macOS**
```bash
pip install pyinstaller
pyinstaller deployment/macos/harmain.spec
```
Result: `dist/HaramaIn.app`

Put `icon.ico` (Windows) and/or `icon.icns` (macOS) in `assets/` to have the
build pick them up automatically.

> **Tesseract is not bundled.** If the people using the build need to read
> photos and scans, they must install Tesseract separately
> ([section 3](#3-installing-tesseract)), or you must add it to the spec as a
> bundled binary. Digital PDF visas work without it.

---

## Support

When reporting a problem, include: what you clicked, what you expected, what
happened, any Error ID shown, and the newest file from the `logs/` folder.
