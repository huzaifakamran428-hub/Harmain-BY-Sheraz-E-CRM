"""
A6 bill generation (SRS 9.3). Branding (business name, footer line,
contact number, logo) is pulled from Settings so the administrator can
change it without touching any code.
"""
from __future__ import annotations

from pathlib import Path

from core.exceptions import NotFoundError
from core.config import get_documents_export_dir, get_logo_path, APP_VENDOR
from infrastructure.repositories import PartyRepository, PilgrimRepository
from infrastructure.pdf_generator import generate_a6_bill
from application.settings_service import SettingsService


class BillService:
    def __init__(self):
        self.parties = PartyRepository()
        self.pilgrims = PilgrimRepository()
        self.settings = SettingsService()

    def generate_bill_for_party(self, party_id: int, output_path: Path | None = None) -> Path:
        party = self.parties.get(party_id)
        if not party:
            raise NotFoundError("Party not found.")
        pilgrims = self.pilgrims.list_by_party(party_id)

        if output_path is None:
            output_path = get_documents_export_dir() / f"permit_slip_{party_id}.pdf"

        s = self.settings.get_all()
        return generate_a6_bill(
            party,
            pilgrims,
            output_path,
            brand_name=s.get("business_name") or APP_VENDOR,
            subtitle=s.get("bill_subtitle") or "Riyazul Jannah Permit Slip",
            footer_text=s.get("bill_footer_text") or "Thank you for choosing HaramaIn",
            contact=s.get("business_contact_number", ""),
            logo_path=get_logo_path(),
        )
