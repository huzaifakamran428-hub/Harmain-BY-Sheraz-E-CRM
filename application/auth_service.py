from __future__ import annotations

from datetime import datetime

from core.exceptions import AuthenticationError, ValidationError
from core.security import hash_password, verify_password
from core.logging_setup import get_logger
from domain.models import User, AuditEntry
from infrastructure.repositories import UserRepository, AuditRepository

logger = get_logger(__name__)


class AuthService:
    def __init__(self):
        self.users = UserRepository()
        self.audit = AuditRepository()
        self.current_user: User | None = None

    def needs_first_run_setup(self) -> bool:
        return not self.users.any_exist()

    def create_first_admin(self, username: str, password: str, display_name: str = "Administrator") -> User:
        username = (username or "").strip()
        if not username or not password:
            raise ValidationError("Username and password are required.")
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters.", field="password")
        password_hash, salt = hash_password(password)
        user = User(id=None, username=username, password_hash=password_hash, salt=salt,
                    display_name=display_name, is_admin=True)
        user = self.users.create(user)
        self.audit.log(AuditEntry(id=None, user=username, action="Create", entity="User",
                                   entity_id=user.id, timestamp=datetime.now(), details="First admin account created"))
        return user

    def login(self, username: str, password: str) -> User:
        username = (username or "").strip()
        if not username or not password:
            raise ValidationError("Please enter both username and password.")
        user = self.users.get_by_username(username)
        if not user or not verify_password(password, user.password_hash, user.salt):
            logger.info("Failed login attempt for username=%s", username)
            raise AuthenticationError()
        self.current_user = user
        self.audit.log(AuditEntry(id=None, user=username, action="Login", entity="User",
                                   entity_id=user.id, timestamp=datetime.now(), details=""))
        return user

    def change_password(self, user: User, new_password: str) -> None:
        if len(new_password) < 6:
            raise ValidationError("Password must be at least 6 characters.", field="password")
        password_hash, salt = hash_password(new_password)
        self.users.update_password(user.id, password_hash, salt)
        self.audit.log(AuditEntry(id=None, user=user.username, action="ChangePassword", entity="User",
                                   entity_id=user.id, timestamp=datetime.now(), details=""))

    def logout(self) -> None:
        if self.current_user:
            self.audit.log(AuditEntry(id=None, user=self.current_user.username, action="Logout",
                                       entity="User", entity_id=self.current_user.id,
                                       timestamp=datetime.now(), details=""))
        self.current_user = None
