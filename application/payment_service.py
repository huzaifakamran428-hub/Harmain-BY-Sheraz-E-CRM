from __future__ import annotations

from datetime import datetime
from typing import List

from core.exceptions import ValidationError, NotFoundError
from domain.models import Payment, AuditEntry, PilgrimStatus
from domain.rules import calculate_remaining
from infrastructure.repositories import PaymentRepository, PilgrimRepository, AuditRepository
from infrastructure.db import transaction


class PaymentService:
    def __init__(self):
        self.payments = PaymentRepository()
        self.pilgrims = PilgrimRepository()
        self.audit = AuditRepository()

    FREE_ACCOUNT_STATUSES = (PilgrimStatus.FREE_MALE, PilgrimStatus.FREE_FEMALE)

    def record_payment(self, pilgrim_id: int, amount: float, note: str = "", actor: str = "") -> Payment:
        if amount is None or amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.", field="amount")
        pilgrim = self.pilgrims.get(pilgrim_id)
        if not pilgrim:
            raise NotFoundError("Pilgrim not found.")

        # A pilgrim sitting in a Free Account has finished their visit and
        # their ledger is closed. Payments can only be recorded again once
        # an administrator returns them to a party.
        if pilgrim.status in self.FREE_ACCOUNT_STATUSES:
            raise ValidationError(
                "This pilgrim is in the Free Account, so no further payment can be "
                "recorded. Return them to a party first if a payment is still due.",
                field="amount",
            )

        # Already settled in full - the ledger is clear.
        received = self.payments.total_received_for_pilgrim(pilgrim_id)
        if calculate_remaining(pilgrim.charge, received) <= 0:
            raise ValidationError(
                "Payment for this pilgrim is already clear - nothing is outstanding.",
                field="amount",
            )

        with transaction() as conn:
            payment = Payment(id=None, pilgrim_id=pilgrim_id, amount=round(amount, 2),
                               paid_at=datetime.now(), note=note or "", created_by=actor)
            payment = self.payments.create(payment, conn=conn)
            self.audit.log(
                AuditEntry(id=None, user=actor, action="Payment", entity="Pilgrim", entity_id=pilgrim_id,
                           timestamp=datetime.now(), details=f"Recorded payment of {amount} for {pilgrim.name}"),
                conn=conn,
            )
        return payment

    def history(self, pilgrim_id: int) -> List[Payment]:
        return self.payments.history_for_pilgrim(pilgrim_id)

    def balance(self, pilgrim_id: int, charge: float) -> tuple[float, float]:
        received = self.payments.total_received_for_pilgrim(pilgrim_id)
        return received, calculate_remaining(charge, received)

    def is_clear(self, pilgrim_id: int, charge: float) -> bool:
        """True when nothing is outstanding for this pilgrim."""
        received, remaining = self.balance(pilgrim_id, charge)
        return remaining <= 0 and charge > 0

    def can_record(self, pilgrim) -> tuple[bool, str]:
        """
        Whether the Record Payment button should be active, plus the reason
        to show the user when it is not. Keeps the rule in one place so the
        dialog and the ledger table never disagree.
        """
        if pilgrim.status in self.FREE_ACCOUNT_STATUSES:
            return False, "In Free Account - payments are closed"
        received, remaining = self.balance(pilgrim.id, pilgrim.charge)
        if remaining <= 0 and pilgrim.charge > 0:
            return False, "Payment is clear"
        return True, ""
