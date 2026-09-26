from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core.exceptions import ValidationError, NotFoundError
from core.config import DEFAULT_CHARGE_PKR
from domain.models import Party, AuditEntry
from domain.rules import calculate_remaining
from infrastructure.repositories import PartyRepository, PilgrimRepository, PaymentRepository, AuditRepository
from infrastructure.db import transaction


class PartyService:
    def __init__(self):
        self.parties = PartyRepository()
        self.pilgrims = PilgrimRepository()
        self.payments = PaymentRepository()
        self.audit = AuditRepository()

    def create_party(self, name: str, phone: str, address: str = "", cnic: str = "",
                      actor: str = "") -> Party:
        name = (name or "").strip()
        phone = (phone or "").strip()
        if not name:
            raise ValidationError("Party Name is required.", field="name")
        if not phone:
            raise ValidationError("Phone Number is required.", field="phone")
        party = Party(id=None, name=name, phone=phone, address=(address or "").strip(),
                      cnic=(cnic or "").strip())
        party = self.parties.create(party)
        self.audit.log(AuditEntry(id=None, user=actor, action="Create", entity="Party",
                                   entity_id=party.id, timestamp=datetime.now(),
                                   details=f"Created party '{party.name}'"))
        return party

    def update_party(self, party: Party, actor: str = "") -> Party:
        if not party.name.strip():
            raise ValidationError("Party Name is required.", field="name")
        if not party.phone.strip():
            raise ValidationError("Phone Number is required.", field="phone")
        self.parties.update(party)
        self.audit.log(AuditEntry(id=None, user=actor, action="Update", entity="Party",
                                   entity_id=party.id, timestamp=datetime.now(), details="Party details updated"))
        return party

    def archive_party(self, party_id: int, actor: str = "") -> None:
        self.parties.archive(party_id)
        self.audit.log(AuditEntry(id=None, user=actor, action="Archive", entity="Party",
                                   entity_id=party_id, timestamp=datetime.now(), details=""))

    def count_party_pilgrims(self, party_id: int) -> int:
        """Every pilgrim still linked to this party, whatever their status - used to
        warn the administrator before a delete that removes them too."""
        return len(self.pilgrims.list_all_by_party(party_id))

    def delete_party(self, party_id: int, actor: str = "") -> None:
        """
        Permanently delete a party AND every pilgrim still linked to it (active
        ledger or Free Account), with their payments and notifications. Runs as
        one transaction so a failure partway through never leaves pilgrims
        orphaned (party_id set to NULL by the foreign key) instead of removed.
        """
        with transaction() as conn:
            party = self.parties.get(party_id, conn=conn)
            if not party:
                raise NotFoundError("Party not found.")
            pilgrims = self.pilgrims.list_all_by_party(party_id, conn=conn)
            for pilgrim in pilgrims:
                self.pilgrims.delete(pilgrim.id, conn=conn)
            self.parties.delete(party_id, conn=conn)
            self.audit.log(
                AuditEntry(id=None, user=actor, action="Delete", entity="Party",
                           entity_id=party_id, timestamp=datetime.now(),
                           details=f"Deleted party '{party.name}' and {len(pilgrims)} pilgrim(s)"),
                conn=conn,
            )

    def get_party_with_totals(self, party_id: int) -> Party:
        party = self.parties.get(party_id)
        if not party:
            raise NotFoundError("Party not found.")
        return self._with_totals(party)

    def list_parties(self, search: str = "") -> List[Party]:
        parties = self.parties.list_active(search)
        return [self._with_totals(p) for p in parties]

    def search_parties(self, search: str = "") -> List[Party]:
        """Lightweight version for pickers (no per-party totals query)."""
        return self.parties.list_active(search)

    def _with_totals(self, party: Party) -> Party:
        pilgrims = self.pilgrims.list_by_party(party.id)
        party.total_people = len(pilgrims)
        party.total_charge = round(sum(p.charge for p in pilgrims), 2)
        party.total_received = round(self.payments.totals_for_party(party.id), 2)
        party.total_remaining = calculate_remaining(party.total_charge, party.total_received)
        return party
