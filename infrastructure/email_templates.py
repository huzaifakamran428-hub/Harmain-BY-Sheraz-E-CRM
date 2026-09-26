"""
HTML email template for the two-day booking-confirmation reminder
(SRS 8 / FR-REM). Renders as a proper branded email: logo header,
business contact number, and the pilgrim's full details so the person
confirming the booking has everything in one place.

Uses a table-based HTML layout with inline CSS, which is what actually
renders correctly across Gmail, Outlook, and Apple Mail (email clients
ignore most <style> blocks and modern CSS).
"""
from __future__ import annotations

import hashlib
from html import escape as _esc
import logging
from pathlib import Path
from typing import Optional

from domain.models import Pilgrim
from core.config import get_logo_path, get_app_data_dir

logger = logging.getLogger(__name__)

GOLD = "#b8860b"
DARK = "#1a1a1a"
LIGHT_BG = "#f7f5f0"
BORDER = "#e0dcd0"

_EMAIL_LOGO_MAX_WIDTH = 520      # pixels; shown at ~240px wide, doubled for sharp phone screens
_EMAIL_LOGO_DISPLAY_WIDTH = 240


def _corner_colour(image) -> tuple:
    """Average colour of the four corners = the logo's own background colour."""
    from PIL import Image
    width, height = image.size
    n = max(2, min(12, width // 20, height // 20))
    samples = []
    for x, y in ((0, 0), (width - n, 0), (0, height - n), (width - n, height - n)):
        samples.append(image.crop((x, y, x + n, y + n)).resize((1, 1), Image.BOX).getpixel((0, 0)))
    return tuple(sum(px[i] for px in samples) // len(samples) for i in range(3))


def _edge_colour(image) -> tuple:
    """Average colour of the whole outer edge - what the header band must match to blend in."""
    from PIL import Image
    width, height = image.size
    n = max(2, min(10, width // 30, height // 30))
    strips = [
        image.crop((0, 0, width, n)), image.crop((0, height - n, width, height)),
        image.crop((0, 0, n, height)), image.crop((width - n, 0, width, height)),
    ]
    samples = [strip.resize((1, 1), Image.BOX).getpixel((0, 0)) for strip in strips]
    return tuple(sum(px[i] for px in samples) // len(samples) for i in range(3))


def _trim_and_shrink(source: Path, target: Path) -> None:
    """
    Make an email-sized copy of the logo: cut away the empty margin around it
    (a logo drawn on a large square canvas would otherwise take the whole
    screen of a phone), then shrink it. A 300 KB photo becomes about 40 KB.
    """
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    image = ImageOps.exif_transpose(Image.open(source))
    has_alpha = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info

    if has_alpha:
        image = image.convert("RGBA")
        mask = image.getchannel("A").point(lambda v: 255 if v > 16 else 0)
    else:
        image = image.convert("RGB")
        background = Image.new("RGB", image.size, _corner_colour(image))
        difference = ImageChops.difference(image, background).convert("L")
        # median filter removes stray specks of background texture
        mask = difference.point(lambda v: 255 if v > 70 else 0).filter(ImageFilter.MedianFilter(7))

    box = mask.getbbox()
    if box:
        width, height = image.size
        pad = int(0.05 * max(box[2] - box[0], box[3] - box[1]))
        image = image.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                            min(width, box[2] + pad), min(height, box[3] + pad)))

    if image.width > _EMAIL_LOGO_MAX_WIDTH:
        ratio = _EMAIL_LOGO_MAX_WIDTH / image.width
        image = image.resize((_EMAIL_LOGO_MAX_WIDTH, max(1, round(image.height * ratio))), Image.LANCZOS)

    target.parent.mkdir(parents=True, exist_ok=True)
    if has_alpha:
        image.save(target, "PNG", optimize=True)
    else:
        image.save(target, "JPEG", quality=88, optimize=True)


def find_logo_path() -> Optional[Path]:
    """
    The logo shown in reminder emails = the SAME logo as the rest of the app:
    the one imported in Settings -> Branding & Bill (or, if none was imported,
    the one shipped in assets/). It is trimmed and shrunk for email first.
    Returns None when there is no logo at all - the email then uses a text header.
    """
    source = get_logo_path()
    if source is None:
        return None
    try:
        stat = source.stat()
        key = hashlib.sha1(f"{source}|{stat.st_mtime_ns}|{stat.st_size}".encode()).hexdigest()[:12]
        ext = ".png" if source.suffix.lower() in (".png", ".webp", ".ico") else ".jpg"
        target = get_app_data_dir() / "ui_cache" / f"email_logo_{key}{ext}"
        if not target.exists():
            _trim_and_shrink(source, target)
        return target
    except Exception as e:                          # noqa: BLE001
        logger.warning("Could not prepare the email logo (%s); using the original file.", e)
        return source


def _logo_background(logo: Path) -> str:
    """Header band colour that blends into the logo's own background (#rrggbb)."""
    try:
        from PIL import Image
        with Image.open(logo) as image:
            if image.mode in ("RGBA", "LA", "PA"):
                return DARK
            r, g, b = _edge_colour(image.convert("RGB"))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:                               # noqa: BLE001
        return DARK


def _header_html(brand_name: str, tagline: str, logo: Optional[Path]) -> str:
    """
    With a logo: the logo IS the header (it already carries the business
    name), followed by the tagline. Without one: a styled text header.
    """
    brand = _esc(brand_name)
    tag = _esc(tagline)
    if logo is not None:
        band = _logo_background(logo)
        return f"""
    <tr>
      <td align="center" style="background-color:{band};padding:26px 20px 20px 20px;border-radius:10px 10px 0 0;">
        <img src="cid:brand_logo" alt="{brand}" width="{_EMAIL_LOGO_DISPLAY_WIDTH}"
             style="display:block;width:{_EMAIL_LOGO_DISPLAY_WIDTH}px;max-width:100%;height:auto;border:0;margin:0 auto;" />
        <div style="font-size:12px;color:#cccccc;margin-top:12px;letter-spacing:0.5px;">{tag}</div>
      </td>
    </tr>
    """
    return f"""
    <tr>
      <td align="center" style="background-color:{DARK};padding:26px 20px;border-radius:10px 10px 0 0;">
        <div style="font-size:20px;font-weight:700;color:{GOLD};letter-spacing:0.5px;">{brand}</div>
        <div style="font-size:12px;color:#cccccc;margin-top:4px;">{tag}</div>
      </td>
    </tr>
    """


def _detail_row(label: str, value: str) -> str:
    return f"""
    <tr>
      <td style="padding:8px 12px;border-bottom:1px solid {BORDER};color:#666666;font-size:13px;width:40%;">{_esc(label)}</td>
      <td style="padding:8px 12px;border-bottom:1px solid {BORDER};color:{DARK};font-size:13px;font-weight:600;">{_esc(str(value))}</td>
    </tr>
    """


def build_reminder_email(
    pilgrim: Pilgrim,
    contact_number: str,
    brand_name: str = "HaramaIn by Sheraz",
    tagline: str = "Riyazul Jannah Permit Booking",
    include_logo: bool = True,
    party_name: str = "",
) -> tuple[str, str]:
    """
    Returns (html_body, plain_text_fallback).
    ``include_logo=False`` gives a plain text header with no image at all.
    """
    logo = find_logo_path() if include_logo else None
    party_name = (party_name or "").strip()
    gmail = (pilgrim.email or "").strip() or "NOT ADDED - open the pilgrim and add the Gmail"
    date_str = pilgrim.permit_date.strftime("%d %B %Y") if pilgrim.permit_date else "-"
    time_str = pilgrim.permit_time.strftime("%I:%M %p") if pilgrim.permit_time else "-"
    days_left = "-"
    if pilgrim.permit_date:
        from datetime import date
        days_left = max(0, (pilgrim.permit_date - date.today()).days)

    contact_line = (
        f'<p style="font-size:13px;color:#555555;margin:16px 0 0 0;">'
        f'Contact number: <b>{_esc(contact_number)}</b></p>'
        if contact_number else ""
    )

    party_sentence_html = f" (party: <b>{_esc(party_name)}</b>)" if party_name else ""
    party_row = _detail_row("Party", party_name) if party_name else ""

    html = f"""
    <html>
    <body style="margin:0;padding:0;background-color:{LIGHT_BG};font-family:Arial,Helvetica,sans-serif;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0;">
        <tr>
          <td align="center">
            <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                   style="background-color:#ffffff;border:1px solid {BORDER};border-radius:10px;overflow:hidden;">
              {_header_html(brand_name, tagline, logo)}
              <tr>
                <td style="padding:22px 24px 6px 24px;">
                  <p style="font-size:15px;color:{DARK};margin:0 0 4px 0;">
                    Permit reminder
                  </p>
                  <p style="font-size:13px;color:#555555;margin:0 0 14px 0;line-height:1.5;">
                    The Riyazul Jannah permit for <b>{_esc(pilgrim.name)}</b>{party_sentence_html} is coming up in
                    <b>{days_left} day(s)</b>. Please confirm this booking as soon as possible.
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding:0 24px 20px 24px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                         style="border:1px solid {BORDER};border-radius:8px;overflow:hidden;">
                    {party_row}
                    {_detail_row("Name", pilgrim.name)}
                    {_detail_row("Gender", pilgrim.gender.value)}
                    {_detail_row("Gmail (code arrives here)", gmail)}
                    {_detail_row("Password", pilgrim.password or "-")}
                    {_detail_row("Permit Date", date_str)}
                    {_detail_row("Permit Time", time_str)}
                  </table>
                  {contact_line}
                </td>
              </tr>
              <tr>
                <td align="center" style="background-color:{LIGHT_BG};padding:14px;border-top:1px solid {BORDER};">
                  <span style="font-size:11px;color:#999999;">Thank you for choosing {_esc(brand_name)}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    plain = (
        f"Permit reminder\n\n"
        f"The Riyazul Jannah permit for {pilgrim.name}"
        + (f" (party: {party_name})" if party_name else "")
        + f" is coming up in {days_left} day(s). "
        f"Please confirm this booking as soon as possible.\n\n"
        + (f"Party: {party_name}\n" if party_name else "")
        + f"Name: {pilgrim.name}\n"
        f"Gender: {pilgrim.gender.value}\n"
        f"Gmail (code arrives here): {gmail}\n"
        f"Password: {pilgrim.password or '-'}\n"
        f"Permit Date: {date_str}\n"
        f"Permit Time: {time_str}\n\n"
        + (f"Contact number: {contact_number}\n\n" if contact_number else "")
        + f"Thank you for choosing {brand_name}"
    )
    return html, plain
