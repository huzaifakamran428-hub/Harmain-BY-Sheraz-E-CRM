from __future__ import annotations

from datetime import datetime, date, time
from typing import List, Optional

from core.exceptions import ValidationError, NotFoundError
from core.config import DEFAULT_CHARGE_PKR
from domain.models import Pilgrim, Gender, PilgrimStatus, AuditEntry
from domain.rules import (
    generate_pilgrim_password, calculate_remaining, is_within_reminder_window, check_email,
)
from infrastructure.repositories import (
    PilgrimRepository, PaymentRepository, AuditRepository, NotificationRepository,
)
from domain.models import NotificationChannel


class PilgrimService:
    def __init__(self):
        self.pilgrims = PilgrimRepository()
        self.payments = PaymentRepository()
        self.audit = AuditRepository()
        self.notifications = NotificationRepository()

    def add_pilgrim(
        self, party_id: int, name: str, gender: Gender,
        permit_date: Optional[date] = None, permit_time: Optional[time] = None,
        batch: str = "", passport_number: str = "", visa_number: str = "",
        email: str = "", whatsapp_number: str = "", charge: Optional[float] = None,
        passport_document_path: str = "", photo_path: str = "", actor: str = "",
        allow_duplicate: bool = False,
    ) -> Pilgrim:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Pilgrim name is required.", field="name")
        email = self._clean_email(email)

        if not allow_duplicate and (passport_number or visa_number):
            dupes = self.pilgrims.find_duplicates(passport_number, visa_number)
            if dupes:
                raise ValidationError(
                    f"A pilgrim with this passport/visa number already exists ({dupes[0].name}). "
                    "Review the existing record, or save again to add anyway.",
                    field="passport_number",
                )

        serial = self.pilgrims.next_serial_number(party_id)
        password = generate_pilgrim_password(name)
        pilgrim = Pilgrim(
            id=None, party_id=party_id, serial_number=serial, permit_date=permit_date,
            permit_time=permit_time, batch=batch, name=name, passport_number=passport_number,
            visa_number=visa_number, gender=gender, email=email, whatsapp_number=whatsapp_number,
            password=password, charge=charge if charge is not None else DEFAULT_CHARGE_PKR,
            passport_document_path=passport_document_path, photo_path=photo_path, status=PilgrimStatus.ACTIVE,
            original_party_id=party_id,
        )
        pilgrim = self.pilgrims.create(pilgrim)
        self.audit.log(AuditEntry(id=None, user=actor, action="Create", entity="Pilgrim",
                                   entity_id=pilgrim.id, timestamp=datetime.now(),
                                   details=f"Added pilgrim '{pilgrim.name}' to party {party_id}"))
        return self._with_balance(pilgrim)

    def update_pilgrim(self, pilgrim: Pilgrim, actor: str = "", allow_duplicate: bool = False) -> Pilgrim:
        if not pilgrim.name.strip():
            raise ValidationError("Pilgrim name is required.", field="name")
        pilgrim.email = self._clean_email(pilgrim.email)
        if not allow_duplicate and (pilgrim.passport_number or pilgrim.visa_number):
            dupes = self.pilgrims.find_duplicates(pilgrim.passport_number, pilgrim.visa_number, exclude_id=pilgrim.id)
            if dupes:
                raise ValidationError(
                    f"A pilgrim with this passport/visa number already exists ({dupes[0].name}).",
                    field="passport_number",
                )
        previous = self.pilgrims.get(pilgrim.id)
        # permit date/time changed -> audit + reminder recalculates automatically next scheduler tick
        self.pilgrims.update(pilgrim)
        if (previous and pilgrim.email and previous.email != pilgrim.email
                and pilgrim.status == PilgrimStatus.ACTIVE):
            # The Gmail was added or corrected AFTER a reminder went out with the old (or missing) one:
            # let the next automatic check send a fresh reminder that shows the right Gmail.
            from application.reminder_service import REMINDER_TYPE
            self.notifications.supersede_sent(pilgrim.id, REMINDER_TYPE, NotificationChannel.EMAIL)
        self.audit.log(AuditEntry(id=None, user=actor, action="Update", entity="Pilgrim",
                                   entity_id=pilgrim.id, timestamp=datetime.now(), details="Pilgrim details updated"))
        return self._with_balance(pilgrim)

    def delete_pilgrim(self, pilgrim_id: int, actor: str = "") -> None:
        """Permanently remove a pilgrim, from a party ledger or the Free Account.
        Their payment history and notification records go with them."""
        pilgrim = self.pilgrims.get(pilgrim_id)
        if not pilgrim:
            raise NotFoundError("Pilgrim not found.")
        self.pilgrims.delete(pilgrim_id)
        self.audit.log(AuditEntry(id=None, user=actor, action="Delete", entity="Pilgrim",
                                   entity_id=pilgrim_id, timestamp=datetime.now(),
                                   details=f"Deleted pilgrim '{pilgrim.name}'"))

    @staticmethod
    def _clean_email(email: str) -> str:
        """Trim the address and refuse ones that cannot work (suspicious ones are the dialog's job)."""
        email = (email or "").strip()
        level, message = check_email(email)
        if level == "error":
            raise ValidationError(message, field="email")
        return email

    def get_pilgrim(self, pilgrim_id: int) -> Pilgrim:
        p = self.pilgrims.get(pilgrim_id)
        if not p:
            raise NotFoundError("Pilgrim not found.")
        return self._with_balance(p)

    def list_party_ledger(self, party_id: int, search: str = "", gender: Optional[Gender] = None) -> List[Pilgrim]:
        pilgrims = self.pilgrims.list_by_party(party_id, search, gender)
        return [self._with_balance(p) for p in pilgrims]

    def list_free(self, status: PilgrimStatus, search: str = "") -> List[Pilgrim]:
        pilgrims = self.pilgrims.list_free(status, search)
        return [self._with_balance(p) for p in pilgrims]

    def is_upcoming(self, pilgrim: Pilgrim, now: Optional[datetime] = None) -> bool:
        return is_within_reminder_window(pilgrim.permit_date, pilgrim.permit_time, now)

    def _with_balance(self, pilgrim: Pilgrim) -> Pilgrim:
        pilgrim.total_received = round(self.payments.total_received_for_pilgrim(pilgrim.id), 2)
        pilgrim.remaining = calculate_remaining(pilgrim.charge, pilgrim.total_received)
        return pilgrim
