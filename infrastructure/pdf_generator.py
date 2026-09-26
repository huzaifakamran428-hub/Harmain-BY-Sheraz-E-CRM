"""
A6 permit bill generation (SRS 9.3 / FR-PDF-*).

PRIVACY RULES BAKED INTO THIS FILE
----------------------------------
The bill is handed to a party representative in public, so it carries the
minimum needed to identify a booking slot and nothing more:

  SHOWN    serial number, permit date, permit time, gender,
           male/female counts and the total number of persons
  NEVER    pilgrim names, passport numbers, visa numbers, e-mail
           addresses, passwords, charges, payments or balances

Layout is a modern ticket: a coloured header band carrying the logo and
business name, a clean zebra-striped table, a bold totals strip, and a
footer band with the reference, print timestamp and page number.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from core.exceptions import PDFGenerationError
from core.logging_setup import get_logger
from core.config import get_logo_path, APP_VENDOR
from domain.models import Party, Pilgrim, Gender

logger = get_logger(__name__)

INK = colors.HexColor("#14161c")
GOLD = colors.HexColor("#c9a227")
GOLD_SOFT = colors.HexColor("#f6efd9")
MUTED = colors.HexColor("#7a7f8c")
LINE = colors.HexColor("#d9dce3")
ZEBRA = colors.HexColor("#fafbfd")

PAGE_WIDTH, PAGE_HEIGHT = A6
MARGIN = 7 * mm
HEADER_HEIGHT = 20 * mm
FOOTER_HEIGHT = 13 * mm


# --------------------------------------------------------- page furniture

class _BillCanvas:
    """
    Draws the fixed header band and footer band on every page, then the
    page number once the total page count is known.
    """

    def __init__(self, brand_name: str, subtitle: str, footer_text: str,
                 contact: str, reference: str, logo_path: Optional[Path]):
        self.brand_name = brand_name
        self.subtitle = subtitle
        self.footer_text = footer_text
        self.contact = contact
        self.reference = reference
        self.logo_path = logo_path
        self.printed_at = datetime.now()

    def __call__(self, canvas, doc):
        canvas.saveState()
        self._header(canvas)
        self._footer(canvas, doc)
        canvas.restoreState()

    def _header(self, canvas):
        top = PAGE_HEIGHT - HEADER_HEIGHT
        canvas.setFillColor(INK)
        canvas.rect(0, top, PAGE_WIDTH, HEADER_HEIGHT, stroke=0, fill=1)

        # Gold hairline under the band - the "modern ticket" cue.
        canvas.setFillColor(GOLD)
        canvas.rect(0, top - 1.1 * mm, PAGE_WIDTH, 1.1 * mm, stroke=0, fill=1)

        text_x = MARGIN
        logo_drawn = False
        if self.logo_path:
            try:
                image = ImageReader(str(self.logo_path))
                iw, ih = image.getSize()
                box = 13 * mm
                scale = min(box / iw, box / ih)
                width, height = iw * scale, ih * scale
                canvas.drawImage(
                    image, MARGIN, top + (HEADER_HEIGHT - height) / 2,
                    width=width, height=height, mask="auto",
                    preserveAspectRatio=True,
                )
                text_x = MARGIN + width + 3 * mm
                logo_drawn = True
            except Exception as e:
                logger.warning("Logo could not be drawn on the bill: %s", e)

        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(text_x, top + HEADER_HEIGHT - 8 * mm, self.brand_name[:34])
        canvas.setFillColor(GOLD)
        canvas.setFont("Helvetica", 6.6)
        canvas.drawString(text_x, top + HEADER_HEIGHT - 12 * mm, self.subtitle[:52])
        if self.contact and not logo_drawn:
            canvas.setFillColor(colors.HexColor("#9aa0ad"))
            canvas.drawString(text_x, top + HEADER_HEIGHT - 15.4 * mm, self.contact[:40])

        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 6.2)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, top + HEADER_HEIGHT - 8 * mm,
                               self.printed_at.strftime("%d-%b-%Y"))
        canvas.setFillColor(colors.HexColor("#9aa0ad"))
        canvas.drawRightString(PAGE_WIDTH - MARGIN, top + HEADER_HEIGHT - 11.2 * mm,
                               self.printed_at.strftime("%H:%M"))

    def _footer(self, canvas, doc):
        canvas.setFillColor(colors.HexColor("#f2f3f6"))
        canvas.rect(0, 0, PAGE_WIDTH, FOOTER_HEIGHT, stroke=0, fill=1)
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(0.9)
        canvas.line(0, FOOTER_HEIGHT, PAGE_WIDTH, FOOTER_HEIGHT)

        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 6.4)
        canvas.drawString(MARGIN, FOOTER_HEIGHT - 5 * mm, self.footer_text[:56])

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 5.6)
        line = f"Ref {self.reference}"
        if self.contact:
            line += f"   |   {self.contact}"
        canvas.drawString(MARGIN, FOOTER_HEIGHT - 8.6 * mm, line[:66])
        canvas.drawRightString(PAGE_WIDTH - MARGIN, FOOTER_HEIGHT - 8.6 * mm,
                               f"Page {canvas.getPageNumber()}")


# --------------------------------------------------------------- the bill

def generate_a6_bill(
    party: Party,
    pilgrims: List[Pilgrim],
    output_path: Path,
    brand_name: str = APP_VENDOR,
    footer_text: str = "Thank you for choosing HaramaIn",
    subtitle: str = "Riyazul Jannah Permit Slip",
    contact: str = "",
    logo_path: Optional[Path] = None,
    show_party_name: bool = False,
) -> Path:
    """
    Build the A6 bill.

    `show_party_name` stays False by default: the bill identifies a booking
    by reference number and slot, never by person. Names of pilgrims are
    never included under any setting.
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        reference = _reference_for(party)
        logo = logo_path or get_logo_path()

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A6,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=HEADER_HEIGHT + 4 * mm,
            bottomMargin=FOOTER_HEIGHT + 3 * mm,
            title=f"Permit Slip {reference}",
            author=brand_name,
        )

        styles = getSampleStyleSheet()
        meta = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=6.6,
                              textColor=MUTED, leading=9)
        meta_right = ParagraphStyle("MetaR", parent=meta, alignment=TA_RIGHT)
        note = ParagraphStyle("Note", parent=styles["Normal"], fontSize=5.8,
                              textColor=MUTED, alignment=TA_CENTER, leading=8)

        elements = []

        # ---- reference strip (no personal data)
        permit_day = _common_permit_day(pilgrims)
        meta_table = Table(
            [[Paragraph(f"<b>REFERENCE</b><br/>{reference}", meta),
              Paragraph(f"<b>PERMIT DAY</b><br/>{permit_day}", meta_right)]],
            colWidths=[(PAGE_WIDTH - 2 * MARGIN) / 2] * 2,
        )
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GOLD_SOFT),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 3.5 * mm))

        # ---- the slot table: SR / Date / Time / Gender only
        data = [["SR", "DATE", "TIME", "GENDER"]]
        male_count = female_count = 0
        for pilgrim in pilgrims:
            if pilgrim.gender == Gender.FEMALE:
                female_count += 1
            else:
                male_count += 1
            data.append([
                str(pilgrim.serial_number),
                pilgrim.permit_date.strftime("%d-%b-%Y") if pilgrim.permit_date else "-",
                pilgrim.permit_time.strftime("%I:%M %p").lstrip("0") if pilgrim.permit_time else "-",
                pilgrim.gender.value,
            ])

        usable = PAGE_WIDTH - 2 * MARGIN
        table = Table(
            data,
            colWidths=[usable * 0.14, usable * 0.36, usable * 0.26, usable * 0.24],
            repeatRows=1,
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 6.4),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("TEXTCOLOR", (0, 1), (-1, -1), INK),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 4 * mm))

        # ---- bold totals strip at the bottom
        totals = Table(
            [["MALE", "FEMALE", "TOTAL PERSONS"],
             [str(male_count), str(female_count), str(len(pilgrims))]],
            colWidths=[usable * 0.3, usable * 0.3, usable * 0.4],
        )
        totals.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eceef3")),
            ("BACKGROUND", (0, 1), (-1, 1), INK),
            ("BACKGROUND", (2, 1), (2, 1), GOLD),
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
            ("TEXTCOLOR", (0, 1), (1, 1), colors.white),
            ("TEXTCOLOR", (2, 1), (2, 1), INK),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 5.8),
            ("FONTSIZE", (0, 1), (-1, 1), 11),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ]))
        elements.append(KeepTogether(totals))
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph(
            "Please arrive at the gate 30 minutes before the permit time and "
            "carry your original passport.", note,
        ))

        page_furniture = _BillCanvas(
            brand_name=brand_name, subtitle=subtitle, footer_text=footer_text,
            contact=contact, reference=reference, logo_path=logo,
        )
        doc.build(elements, onFirstPage=page_furniture, onLaterPages=page_furniture)
        return output_path
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        raise PDFGenerationError() from e


def _reference_for(party: Party) -> str:
    """Short, non-identifying booking reference, e.g. RJ-0007-1809."""
    party_id = party.id or 0
    return f"RJ-{party_id:04d}-{datetime.now().strftime('%d%m')}"


def _common_permit_day(pilgrims: List[Pilgrim]) -> str:
    dates = {p.permit_date for p in pilgrims if p.permit_date}
    if not dates:
        return "-"
    if len(dates) == 1:
        return next(iter(dates)).strftime("%d-%b-%Y")
    return f"{len(dates)} different dates"
