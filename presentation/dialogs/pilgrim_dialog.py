from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QLabel,
    QDateEdit, QTimeEdit, QDoubleSpinBox, QFileDialog, QMessageBox,
    QFrame, QScrollArea, QWidget, QApplication,
)
from PyQt6.QtCore import QDate, QTime, Qt

from domain.models import Pilgrim, Gender
from domain.rules import generate_pilgrim_password, normalize_first_name, check_email
from presentation.app_context import AppContext, handle_error
from presentation.widgets.avatars import circular_pixmap_from_path
from presentation.widgets.inputs import StyledComboBox
from core.exceptions import ApplicationError, ValidationError
from core.config import DEFAULT_CHARGE_PKR, CURRENCY_SYMBOL

# Every readable format, offered in one filter so nothing looks "rejected".
FILE_FILTER = (
    "Passport / Visa documents (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.heic *.heif);;"
    "PDF files (*.pdf);;"
    "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;"
    "All files (*)"
)

PHOTO_FILE_FILTER = "Photos (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)"
PHOTO_PREVIEW_DIAMETER = 64


GENDER_PLACEHOLDER = "Select gender..."


class PilgrimDialog(QDialog):
    def __init__(self, ctx: AppContext, party_id: int, pilgrim: Optional[Pilgrim] = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.party_id = party_id
        self.pilgrim = pilgrim
        self._stored_document_path = pilgrim.passport_document_path if pilgrim else ""
        self._stored_photo_path = pilgrim.photo_path if pilgrim else ""
        self._last_raw_text = ""
        self.setWindowTitle("Edit Pilgrim" if pilgrim else "Add Pilgrim")
        self.setMinimumWidth(560)
        self.setMinimumHeight(640)
        self.result_pilgrim: Optional[Pilgrim] = None
        self._build_ui()

    # -------------------------------------------------------------- build
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title = QLabel("Edit Pilgrim" if self.pilgrim else "Add Pilgrim")
        title.setObjectName("SectionTitle")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        layout.addWidget(self._build_upload_panel())
        layout.addWidget(self._build_form_panel())

        # -------- footer buttons, always visible outside the scroll area
        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)
        outer.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.setMinimumWidth(120)
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Pilgrim")
        save_btn.setMinimumWidth(150)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        outer.addLayout(buttons)

    def _build_upload_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("GlassPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        heading = QLabel("PASSPORT / VISA DOCUMENT")
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.upload_button = QPushButton("Upload Document")
        self.upload_button.setMinimumWidth(160)
        self.upload_button.setToolTip("Attach a passport or visa photo, scan or PDF and read it automatically")
        self.upload_button.clicked.connect(self._upload_and_read)

        self.reread_button = QPushButton("Read Again")
        self.reread_button.setObjectName("SecondaryButton")
        self.reread_button.setMinimumWidth(120)
        self.reread_button.setEnabled(bool(self._stored_document_path))
        self.reread_button.setToolTip("Run the reader again on the attached document")
        self.reread_button.clicked.connect(self._reread)

        self.raw_text_button = QPushButton("Show Read Text")
        self.raw_text_button.setObjectName("SecondaryButton")
        self.raw_text_button.setMinimumWidth(140)
        self.raw_text_button.setEnabled(False)
        self.raw_text_button.setToolTip("See exactly what the reader got out of the document")
        self.raw_text_button.clicked.connect(self._show_raw_text)

        row.addWidget(self.upload_button)
        row.addWidget(self.reread_button)
        row.addWidget(self.raw_text_button)
        row.addStretch()
        layout.addLayout(row)

        self.attached_label = QLabel(
            f"Attached: {Path(self._stored_document_path).name}" if self._stored_document_path
            else "No document attached yet. Uploading one fills the fields below automatically."
        )
        self.attached_label.setObjectName("HintText")
        self.attached_label.setWordWrap(True)
        layout.addWidget(self.attached_label)

        photo_row = QHBoxLayout()
        photo_row.setSpacing(10)
        self.photo_preview_label = QLabel()
        self.photo_preview_label.setFixedSize(PHOTO_PREVIEW_DIAMETER, PHOTO_PREVIEW_DIAMETER)
        self.set_photo_button = QPushButton("Set Photo")
        self.set_photo_button.setObjectName("SecondaryButton")
        self.set_photo_button.setMinimumWidth(120)
        self.set_photo_button.setToolTip(
            "Uploading a document above picks up the pilgrim's photo automatically where possible. "
            "Use this to choose the picture yourself instead."
        )
        self.set_photo_button.clicked.connect(self._set_photo_manually)
        photo_row.addWidget(self.photo_preview_label)
        photo_row.addWidget(self.set_photo_button)
        photo_row.addStretch()
        layout.addLayout(photo_row)
        self._refresh_photo_preview()

        self.photo_hint_label = QLabel("")
        self.photo_hint_label.setObjectName("HintText")
        self.photo_hint_label.setWordWrap(True)
        layout.addWidget(self.photo_hint_label)

        self.ocr_status_label = QLabel("")
        self.ocr_status_label.setObjectName("HintText")
        self.ocr_status_label.setWordWrap(True)
        layout.addWidget(self.ocr_status_label)

        # If this machine cannot read images at all, say so up front rather
        # than after the user has already picked a file.
        hint = self.ctx.documents.setup_hint()
        if hint:
            warning = QLabel(hint)
            warning.setObjectName("ErrorText")
            warning.setWordWrap(True)
            layout.addWidget(warning)

        return panel

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("GlassPanel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(10)

        heading = QLabel("PILGRIM DETAILS")
        heading.setObjectName("CardTitle")
        outer.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        p = self.pilgrim

        self.name_input = QLineEdit(p.name if p else "")
        self.name_input.setPlaceholderText("Full name as printed on the passport")
        self.name_input.textChanged.connect(self._refresh_password_preview)
        self.name_input.textChanged.connect(self._refresh_photo_preview)

        # Index 0 is "not chosen yet": a new pilgrim is never silently saved as
        # Male just because nobody touched the box.
        self.gender_input = StyledComboBox()
        self.gender_input.addItems([GENDER_PLACEHOLDER, Gender.MALE.value, Gender.FEMALE.value])
        if p:
            self.gender_input.setCurrentText(p.gender.value)
        self.gender_hint = QLabel("")
        self.gender_hint.setObjectName("SuccessText")
        self.gender_hint.setWordWrap(True)
        self.gender_hint.setVisible(False)
        gender_row = QVBoxLayout()
        gender_row.setSpacing(4)
        gender_row.addWidget(self.gender_input)
        gender_row.addWidget(self.gender_hint)

        self.date_input = QDateEdit(calendarPopup=True)
        self.date_input.setDisplayFormat("dd-MMM-yyyy")
        self.date_input.setDate(QDate(p.permit_date) if (p and p.permit_date) else QDate.currentDate())
        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("hh:mm AP")
        self.time_input.setTime(
            QTime(p.permit_time.hour, p.permit_time.minute) if (p and p.permit_time) else QTime(9, 0)
        )

        self.batch_input = QLineEdit(p.batch if p else "")
        self.passport_input = QLineEdit(p.passport_number if p else "")
        self.visa_input = QLineEdit(p.visa_number if p else "")
        self.email_input = QLineEdit(p.email if p else "")
        self.email_input.setPlaceholderText("The Gmail on which the booking code arrives")
        self.whatsapp_input = QLineEdit(p.whatsapp_number if p else "")
        self.whatsapp_input.setPlaceholderText("e.g. +92 300 1234567")

        self.charge_input = QDoubleSpinBox()
        self.charge_input.setRange(0, 10_000_000)
        self.charge_input.setDecimals(0)
        self.charge_input.setSuffix(f" {CURRENCY_SYMBOL}")
        self.charge_input.setValue(p.charge if p else self._default_charge())

        self.password_input = QLineEdit(p.password if p else "")
        self.password_input.setPlaceholderText("Auto-generated from the first name (editable)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.reveal_button = QPushButton("Show")
        self.reveal_button.setObjectName("SecondaryButton")
        self.reveal_button.setCheckable(True)
        self.reveal_button.setMaximumWidth(90)
        self.reveal_button.toggled.connect(self._toggle_password_visibility)
        password_row = QHBoxLayout()
        password_row.setSpacing(8)
        password_row.addWidget(self.password_input, 1)
        password_row.addWidget(self.reveal_button)

        form.addRow("Full Name *", self.name_input)
        form.addRow("Gender *", gender_row)
        form.addRow("Permit Date", self.date_input)
        form.addRow("Permit Time", self.time_input)
        form.addRow("Batch", self.batch_input)
        form.addRow("Passport Number", self.passport_input)
        form.addRow("Visa Number", self.visa_input)
        form.addRow("Gmail (code arrives here)", self.email_input)
        form.addRow("WhatsApp Number", self.whatsapp_input)
        form.addRow("Charge", self.charge_input)
        form.addRow("Password", password_row)
        outer.addLayout(form)

        rule = QLabel(
            "Password rule: first letter of the first name in capital, the rest in small "
            "letters, followed by 111@  (for example: Muhammad111@)."
        )
        rule.setObjectName("HintText")
        rule.setWordWrap(True)
        outer.addWidget(rule)

        if not self.pilgrim:
            self._refresh_password_preview()
        return panel

    def _default_charge(self) -> float:
        try:
            return float(self.ctx.settings.get("default_charge") or DEFAULT_CHARGE_PKR)
        except (TypeError, ValueError):
            return DEFAULT_CHARGE_PKR

    # --------------------------------------------------------- password UI
    def _toggle_password_visibility(self, checked: bool):
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.reveal_button.setText("Hide" if checked else "Show")

    def _refresh_password_preview(self):
        """Keep the preview in step with the name, without clobbering a
        password the administrator has typed in by hand."""
        if self.pilgrim is not None:
            return
        current = self.password_input.text()
        if current and not current.endswith("111@"):
            return          # manually edited - leave it alone
        self.password_input.setText(generate_pilgrim_password(self.name_input.text()))

    # ------------------------------------------------------ document flow
    def _upload_and_read(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Passport / Visa Document", "", FILE_FILTER,
        )
        if not file_path:
            return
        try:
            stored_path = self.ctx.documents.store_document(Path(file_path))
        except ApplicationError as e:
            self.ocr_status_label.setObjectName("ErrorText")
            self.ocr_status_label.setText(e.user_message)
            self._restyle(self.ocr_status_label)
            return
        except Exception as e:
            handle_error(self, e, "Upload Document")
            return

        self._stored_document_path = str(stored_path)
        self.attached_label.setText(f"Attached: {Path(file_path).name}")
        self.reread_button.setEnabled(True)
        self._run_reader(stored_path)
        self._extract_photo(stored_path)

    def _reread(self):
        if self._stored_document_path:
            stored_path = Path(self._stored_document_path)
            self._run_reader(stored_path)
            self._extract_photo(stored_path)

    def _run_reader(self, stored_path: Path):
        """
        Read the document and fill whatever it found. The file stays
        attached whether or not the reading succeeds - a failed read is
        never a reason to reject the upload.
        """
        self.ocr_status_label.setObjectName("HintText")
        self.ocr_status_label.setText("Reading document, please wait...")
        self._restyle(self.ocr_status_label)
        QApplication.processEvents()

        try:
            result = self.ctx.documents.run_ocr(stored_path)
        except ApplicationError as e:
            self.ocr_status_label.setObjectName("ErrorText")
            self.ocr_status_label.setText(
                f"{e.user_message} The file is still attached to this pilgrim."
            )
            self._restyle(self.ocr_status_label)
            return
        except Exception as e:
            handle_error(self, e, "Read Document")
            return

        self._last_raw_text = result.raw_text or ""
        self.raw_text_button.setEnabled(bool(self._last_raw_text.strip()))

        filled = []
        if result.name and not self.name_input.text().strip():
            self.name_input.setText(result.name)
            filled.append("name")
        if result.passport_number:
            self.passport_input.setText(result.passport_number)
            filled.append("passport number")
        if result.visa_number:
            self.visa_input.setText(result.visa_number)
            filled.append("visa number")

        # ---- gender: picked up automatically, and always say where it came from
        gender_missing = False
        if result.gender is not None:
            self.gender_input.setCurrentText(result.gender.value)
            source = result.gender_source
            if source == "name (guess)":
                self._set_gender_hint(
                    f"{result.gender.value} - only GUESSED from the name. Please check it.", "ErrorText")
            elif source == "MRZ code":
                self._set_gender_hint(
                    f"auto-detected: {result.gender.value} (from the code line at the bottom of the document)",
                    "SuccessText")
            else:
                self._set_gender_hint(f"auto-detected: {result.gender.value}", "SuccessText")
            filled.append("gender")
        elif self.gender_input.currentIndex() == 0:
            gender_missing = True
            self._set_gender_hint(
                "Gender is not written on this document - please choose it.", "ErrorText")
        else:
            self.gender_hint.setVisible(False)

        if filled:
            method = f" via {result.method}" if result.method else ""
            message = f"Read{method}: {', '.join(filled)}. Please check every field before saving."
            if gender_missing:
                message += "  Gender was not found - please choose it."
            if result.warning:
                message += f"  {result.warning}"
            self.ocr_status_label.setObjectName("SuccessText")
            self.ocr_status_label.setText(message)
        else:
            self.ocr_status_label.setObjectName("ErrorText")
            self.ocr_status_label.setText(
                result.warning or "Nothing could be read from this document - please type the "
                                  "details in below. The file has still been attached."
            )
        self._restyle(self.ocr_status_label)

    def _set_gender_hint(self, text: str, object_name: str):
        self.gender_hint.setText(text)
        self.gender_hint.setObjectName(object_name)
        self._restyle(self.gender_hint)
        self.gender_hint.setVisible(True)

    # --------------------------------------------------------- photo flow
    def _extract_photo(self, stored_path: Path):
        """
        Try to pick the pilgrim's picture out of the document that was
        just uploaded - the embedded photo in a digital visa PDF, or a
        detected face in a plain photo upload. Never blocks saving: a
        miss just leaves "Set Photo" for the administrator to use.
        """
        result = self.ctx.documents.extract_photo(stored_path)
        if result.image_bytes:
            try:
                photo_path = self.ctx.documents.store_photo_bytes(result.image_bytes)
            except ApplicationError as e:
                self._set_photo_hint(e.user_message, "ErrorText")
                return
            self._stored_photo_path = str(photo_path)
            self._refresh_photo_preview()
            self._set_photo_hint(f"Photo picked up automatically ({result.method}).", "SuccessText")
        else:
            self._set_photo_hint(
                result.warning or 'No photo could be picked up automatically - use "Set Photo" to add one.',
                "HintText",
            )

    def _set_photo_manually(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Pilgrim Photo", "", PHOTO_FILE_FILTER,
        )
        if not file_path:
            return
        try:
            photo_path = self.ctx.documents.store_photo_file(Path(file_path))
        except ApplicationError as e:
            self._set_photo_hint(e.user_message, "ErrorText")
            return
        except Exception as e:
            handle_error(self, e, "Set Photo")
            return
        self._stored_photo_path = str(photo_path)
        self._refresh_photo_preview()
        self._set_photo_hint("Photo set.", "SuccessText")

    def _refresh_photo_preview(self):
        self.photo_preview_label.setPixmap(
            circular_pixmap_from_path(
                self._stored_photo_path, PHOTO_PREVIEW_DIAMETER, self._current_name_for_avatar()
            )
        )

    def _current_name_for_avatar(self) -> str:
        if hasattr(self, "name_input"):
            return self.name_input.text()
        return self.pilgrim.name if self.pilgrim else ""

    def _set_photo_hint(self, text: str, object_name: str):
        self.photo_hint_label.setText(text)
        self.photo_hint_label.setObjectName(object_name)
        self._restyle(self.photo_hint_label)

    def _show_raw_text(self):
        box = QMessageBox(self)
        box.setWindowTitle("Text read from the document")
        box.setText("This is exactly what the reader extracted. If a field came out wrong, "
                    "correct it in the form before saving.")
        box.setDetailedText(self._last_raw_text or "(nothing)")
        box.exec()

    def _restyle(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    # ---------------------------------------------------------------- save
    def _save(self):
        self.error_label.setText("")
        if not self.name_input.text().strip():
            self.error_label.setText("Full name is required.")
            return
        if self.gender_input.currentIndex() == 0:
            self.error_label.setText("Please choose the gender (Male or Female).")
            self.gender_input.setFocus()
            return
        level, message = check_email(self.email_input.text())
        if level == "error":
            self.error_label.setText(message)
            self.email_input.setFocus()
            return
        if level == "warning":
            choice = QMessageBox.question(
                self, "Check the email address",
                f"{message}\n\nA wrong Gmail means you will not find the booking code in it.\n\n"
                "Save with this address anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self.email_input.setFocus()
                return
        if level == "ok" and not self.email_input.text().strip():
            choice = QMessageBox.question(
                self, "No Gmail added",
                "No Gmail has been added for this pilgrim.\n\nYour permit reminder email will then show "
                "\"NOT ADDED\" instead of the Gmail on which the code arrives.\n\nSave without a Gmail?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self.email_input.setFocus()
                return
        permit_date = self.date_input.date().toPyDate()
        permit_time = self.time_input.time().toPyTime()
        try:
            self._persist(permit_date, permit_time, allow_duplicate=False)
            self.accept()
        except ValidationError as e:
            if "already exists" in str(e):
                choice = QMessageBox.question(
                    self, "Possible Duplicate", f"{e}\n\nSave anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if choice == QMessageBox.StandardButton.Yes:
                    try:
                        self._persist(permit_date, permit_time, allow_duplicate=True)
                        self.accept()
                    except ApplicationError as inner:
                        self.error_label.setText(inner.user_message)
                    except Exception as inner:
                        handle_error(self, inner, "Save Pilgrim")
                    return
            self.error_label.setText(e.user_message)
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Save Pilgrim")

    def _persist(self, permit_date, permit_time, allow_duplicate: bool):
        password = self.password_input.text().strip() or generate_pilgrim_password(self.name_input.text())

        if self.pilgrim:
            self.pilgrim.name = self.name_input.text().strip()
            self.pilgrim.gender = Gender(self.gender_input.currentText())
            self.pilgrim.permit_date = permit_date
            self.pilgrim.permit_time = permit_time
            self.pilgrim.batch = self.batch_input.text().strip()
            self.pilgrim.passport_number = self.passport_input.text().strip()
            self.pilgrim.visa_number = self.visa_input.text().strip()
            self.pilgrim.email = self.email_input.text().strip()
            self.pilgrim.whatsapp_number = self.whatsapp_input.text().strip()
            self.pilgrim.charge = self.charge_input.value()
            self.pilgrim.password = password
            if self._stored_document_path:
                self.pilgrim.passport_document_path = self._stored_document_path
            self.pilgrim.photo_path = self._stored_photo_path
            self.result_pilgrim = self.ctx.pilgrims.update_pilgrim(
                self.pilgrim, actor=self.ctx.current_username, allow_duplicate=allow_duplicate,
            )
            return

        self.result_pilgrim = self.ctx.pilgrims.add_pilgrim(
            party_id=self.party_id,
            name=self.name_input.text(),
            gender=Gender(self.gender_input.currentText()),
            permit_date=permit_date,
            permit_time=permit_time,
            batch=self.batch_input.text(),
            passport_number=self.passport_input.text(),
            visa_number=self.visa_input.text(),
            email=self.email_input.text(),
            whatsapp_number=self.whatsapp_input.text(),
            charge=self.charge_input.value(),
            passport_document_path=self._stored_document_path,
            photo_path=self._stored_photo_path,
            actor=self.ctx.current_username,
            allow_duplicate=allow_duplicate,
        )
        if password != self.result_pilgrim.password:
            self.result_pilgrim.password = password
            self.ctx.pilgrims.update_pilgrim(
                self.result_pilgrim, actor=self.ctx.current_username, allow_duplicate=True,
            )
