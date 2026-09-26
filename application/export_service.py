"""
Excel export (SRS-style addition: administrator wants a party's ledger,
or the Free Account, as an .xlsx file they can open outside the app).
"""
from __future__ import annotations

from pathlib import Path

from core.exceptions import NotFoundError
from core.config import get_documents_export_dir
from domain.models import PilgrimStatus
from infrastructure.repositories import PartyRepository, PilgrimRepository, PaymentRepository
from infrastructure.excel_export import export_party_excel, export_free_account_excel


class ExportService:
    def __init__(self):
        self.parties = PartyRepository()
        self.pilgrims = PilgrimRepository()
        self.payments = PaymentRepository()

    def _with_balance(self, pilgrim):
        pilgrim.total_received = round(self.payments.total_received_for_pilgrim(pilgrim.id), 2)
        pilgrim.remaining = round(pilgrim.charge - pilgrim.total_received, 2)
        return pilgrim

    def export_party_to_excel(self, party_id: int, output_path: Path | None = None) -> Path:
        party = self.parties.get(party_id)
        if not party:
            raise NotFoundError("Party not found.")
        pilgrims = [self._with_balance(p) for p in self.pilgrims.list_by_party(party_id)]
        if output_path is None:
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in party.name).strip() or "party"
            output_path = get_documents_export_dir() / f"{safe_name}_pilgrims.xlsx"
        return export_party_excel(party.name, pilgrims, output_path)

    def export_free_account_to_excel(self, output_path: Path | None = None) -> Path:
        male = [self._with_balance(p) for p in self.pilgrims.list_free(PilgrimStatus.FREE_MALE)]
        female = [self._with_balance(p) for p in self.pilgrims.list_free(PilgrimStatus.FREE_FEMALE)]
        if output_path is None:
            output_path = get_documents_export_dir() / "free_account.xlsx"
        return export_free_account_excel(male, female, output_path)
