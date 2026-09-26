from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from presentation.app_context import AppContext, handle_error
from core.exceptions import ApplicationError
from core.config import APP_VENDOR


class LoginWindow(QWidget):
    login_succeeded = pyqtSignal(object)  # emits the logged-in User

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("HaramaIn by Sheraz - Sign In")
        self.setMinimumSize(420, 420)
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("GlassRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(380)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)

        brand = QLabel(APP_VENDOR)
        brand.setObjectName("BrandLabel")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Riyazul Jannah Permit & Pilgrim Management")
        subtitle.setObjectName("BrandSubLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.returnPressed.connect(self._attempt_login)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._attempt_login)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)

        self.login_button = QPushButton("Sign In")
        self.login_button.setMinimumHeight(42)
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._attempt_login)

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Username"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(self.password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.login_button)

        outer.addWidget(card)

    def _attempt_login(self):
        self.error_label.setText("")
        username = self.username_input.text().strip()
        password = self.password_input.text()
        try:
            user = self.ctx.auth.login(username, password)
            self.login_succeeded.emit(user)
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Sign In")


class FirstRunSetupWindow(QWidget):
    """Shown only when the database has no user accounts yet."""
    setup_complete = pyqtSignal(object)

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("HaramaIn by Sheraz - Initial Setup")
        self.setMinimumSize(440, 460)
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("GlassRoot")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(400)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        title = QLabel("Welcome - Create Administrator Account")
        title.setObjectName("SectionTitle")
        title.setWordWrap(True)
        info = QLabel("This is a one-time setup. Create the first administrator account to start using the system.")
        info.setWordWrap(True)
        info.setObjectName("BrandSubLabel")

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Full name (e.g. Sheraz Ahmed)")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Choose a username")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Choose a password (min. 6 characters)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm password")
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)

        create_button = QPushButton("Create Account & Continue")
        create_button.setMinimumHeight(42)
        create_button.clicked.connect(self._create_account)

        for w in (title, info, self.display_name_input, self.username_input,
                  self.password_input, self.confirm_input, self.error_label, create_button):
            layout.addWidget(w)

        outer.addWidget(card)

    def _create_account(self):
        self.error_label.setText("")
        display_name = self.display_name_input.text().strip() or "Administrator"
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        if password != confirm:
            self.error_label.setText("Passwords do not match.")
            return
        try:
            self.ctx.auth.create_first_admin(username, password, display_name)
            user = self.ctx.auth.login(username, password)
            self.setup_complete.emit(user)
        except ApplicationError as e:
            self.error_label.setText(e.user_message)
        except Exception as e:
            handle_error(self, e, "Setup")
