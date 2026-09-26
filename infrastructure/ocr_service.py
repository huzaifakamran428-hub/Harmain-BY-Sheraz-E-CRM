"""
Passport / visa document reading (SRS 4.4 / 16.8).

WHY THIS FILE WAS REWRITTEN
---------------------------
The previous version had a single path: pytesseract -> Tesseract binary.
If the Tesseract binary was not installed on the computer (which is the
normal state of a fresh Windows or macOS machine, because Tesseract is a
separate program, not a Python package), `is_ocr_available()` returned
False and every upload immediately answered "please enter details
manually" - even for PDFs that contain real, selectable text and need no
OCR at all. That is the "it does not accept my visa picture/PDF" bug.

The reader now tries several backends in order of accuracy and falls
through to the next one automatically:

  1. EMBEDDED TEXT LAYER (PDF only)  - pdfplumber / PyMuPDF / pypdf.
     Saudi e-visas, Nusuk permits and most e-tickets are digital PDFs
     with a real text layer. This is 100% accurate, instant, and needs
     NO Tesseract at all.
  2. PDF PAGE RASTERISATION + OCR    - PyMuPDF (preferred, pure pip
     install) or pdf2image (needs Poppler). Used for scanned PDFs.
  3. IMAGE OCR                       - Pillow pre-processing (greyscale,
     auto-contrast, upscale, sharpen) then Tesseract, trying several
     page-segmentation modes and keeping the best result.
  4. EasyOCR                         - optional pure-Python fallback if
     it happens to be installed.

Every extracted field is still returned for the administrator to review
and edit before saving (FR-OCR-05/06/08) - OCR is treated as
probabilistic and is never assumed correct.
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from core.exceptions import DocumentProcessingError
from core.logging_setup import get_logger
from domain.models import Gender

logger = get_logger(__name__)

# A GUI app launched by double-clicking (Finder/Dock, or a PyInstaller
# .app bundle) does NOT inherit the PATH a Terminal shell has - it gets a
# much barer default PATH. So `tesseract` can work perfectly in Terminal
# (because Homebrew's `brew shellenv` added its bin dir to your shell's
# PATH via .zprofile) while the same binary is invisible to the app,
# which is exactly the "brew says it's installed but the app still says
# not found" situation. To make this work regardless of how the app was
# launched, we search the well-known install locations directly instead
# of relying on PATH, and tell pytesseract exactly where the binary is.
_TESSERACT_CANDIDATES = (
    "/opt/homebrew/bin/tesseract",   # Homebrew on Apple Silicon Macs
    "/usr/local/bin/tesseract",      # Homebrew on Intel Macs / some Linux
    "/usr/bin/tesseract",            # Linux package managers
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _configure_tesseract_path() -> None:
    """
    Point pytesseract at the Tesseract binary directly, checked once at
    import time, so detection works the same whether the app was started
    from a Terminal, a Dock icon, or a built .app/.exe.
    """
    try:
        import pytesseract
    except Exception:
        return

    # Already resolvable via PATH (e.g. running "python main.py" from a
    # Terminal that has it) - nothing to do.
    if shutil.which(pytesseract.pytesseract.tesseract_cmd):
        return

    for candidate in _TESSERACT_CANDIDATES:
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            logger.info("Tesseract binary found at %s (not on PATH)", candidate)
            return


_configure_tesseract_path()

_MRZ_LINE_RE = re.compile(r"^[A-Z0-9<]{28,50}$")

# Words that must never be mistaken for a name or a document number.
_STOPWORDS = {
    "PLATFORM", "NUMBER", "VISA", "PASSPORT", "NAME", "SURNAME", "GIVEN",
    "REPUBLIC", "ISLAMIC", "KINGDOM", "SAUDI", "ARABIA", "PAKISTAN",
    "NATIONALITY", "GENDER", "SEX", "TYPE", "ISSUE", "EXPIRY", "DATE",
    "BIRTH", "AUTHORITY", "HOLDER", "UMRAH", "HAJJ", "PILGRIM", "PERMIT",
    "MALE", "FEMALE", "UNKNOWN", "SPECIMEN", "SAMPLE", "NO", "NUM", "OF",
    "DOCUMENT", "DOC", "CODE", "PLACE", "SIGNATURE", "VALID", "ENTRIES",
}


# ---------------------------------------------------------------- results

@dataclass
class OcrResult:
    """What the reader managed to pull out of one document."""
    name: str = ""
    passport_number: str = ""
    visa_number: str = ""
    gender: Optional[Gender] = None
    raw_text: str = ""
    available: bool = True          # was ANY reading backend usable?
    warning: str = ""               # user-facing note, may be empty
    method: str = ""                # which backend actually produced text
    fields_found: List[str] = field(default_factory=list)
    gender_source: str = ""         # "MRZ", "MRZ code", "label", "name (guess)"

    @property
    def found_anything(self) -> bool:
        return bool(self.name or self.passport_number or self.visa_number or self.gender)


# ------------------------------------------------------- backend detection

def _has(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def _import_error(*modules: str) -> str:
    """'' when at least one of the modules imports, else the last error."""
    last = ""
    for module in modules:
        try:
            __import__(module)
            return ""
        except Exception as e:                      # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
    return last


def _pymupdf():
    """PyMuPDF is 'pymupdf' in new releases and 'fitz' in old ones."""
    try:
        import pymupdf
        return pymupdf
    except Exception:
        import fitz
        return fitz


def _has_pymupdf() -> bool:
    return _has("pymupdf") or _has("fitz")


def is_tesseract_available() -> bool:
    """True only when BOTH pytesseract and the Tesseract binary exist."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def is_pdf_text_available() -> bool:
    return _has("pdfplumber") or _has_pymupdf() or _has("pypdf")


def is_pdf_raster_available() -> bool:
    return _has_pymupdf() or _has("pdf2image")


def is_ocr_available() -> bool:
    """Kept for backwards compatibility - true if any image OCR works."""
    return is_tesseract_available() or _has("easyocr")


def reader_diagnostics() -> dict:
    """
    Plain-English report of what this computer can currently read.
    Shown in Settings -> Document Reading so the administrator can see at
    a glance why a particular file did or did not come out automatically.
    """
    tess = is_tesseract_available()
    return {
        "pdf_text_layer": is_pdf_text_available(),
        "pdf_rasterise": is_pdf_raster_available(),
        "tesseract": tess,
        "easyocr": _has("easyocr"),
        "pillow": _has("PIL"),
        "pymupdf": _has_pymupdf(),
        "pdfplumber": _has("pdfplumber"),
        "pypdf": _has("pypdf"),
        "pdf2image": _has("pdf2image"),
        "can_read_digital_pdf": is_pdf_text_available(),
        "can_read_scanned_pdf": is_pdf_raster_available() and (tess or _has("easyocr")),
        "can_read_images": tess or _has("easyocr"),
    }


def reader_problems() -> dict:
    """
    Exact reason each missing component is missing (for Settings ->
    Document Reading). Only entries that are actually broken are returned.
    """
    problems = {}
    for label, modules in (
        ("pdfplumber", ("pdfplumber",)),
        ("PyMuPDF", ("pymupdf", "fitz")),
        ("pypdf", ("pypdf",)),
        ("Pillow", ("PIL",)),
        ("pytesseract", ("pytesseract",)),
    ):
        error = _import_error(*modules)
        if error:
            problems[label] = error
    if "pytesseract" not in problems and not is_tesseract_available():
        problems["Tesseract program"] = "not found on this computer (see README, section 3)"
    return problems


def missing_component_hint() -> str:
    """One short sentence telling the user exactly what to install next."""
    d = reader_diagnostics()
    if not d["can_read_digital_pdf"]:
        return (
            "No PDF text reader is working, so even digital visa PDFs cannot be read "
            "cleanly. Run 'pip install pdfplumber PyMuPDF pypdf' in the same Python "
            "environment that runs this app, then restart it. Settings -> Document "
            "Reading shows the exact error."
        )
    if not d["can_read_images"]:
        return (
            "Tesseract OCR is not installed on this computer, so photos and "
            "scanned documents cannot be read automatically. Install it from "
            "https://github.com/UB-Mannheim/tesseract/wiki (Windows) or run "
            "'brew install tesseract' (macOS), then restart the app. "
            "Digital PDF visas still work without it."
        )
    if not d["can_read_scanned_pdf"]:
        return (
            "Scanned PDFs cannot be converted to images yet. Run "
            "'pip install PyMuPDF' and restart the app."
        )
    return ""


# ------------------------------------------------------------- public API

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}


def extract_passport_data(file_path: Path) -> OcrResult:
    """
    Best-effort extraction. Never raises for "could not read" - that is a
    normal, expected outcome and returns an OcrResult with a warning.
    Raises DocumentProcessingError only for a genuinely unreadable file.
    """
    result = OcrResult()
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".pdf":
            text, method = _read_pdf(file_path)
        elif suffix in IMAGE_SUFFIXES:
            text, method = _read_image(file_path)
        else:
            text, method = "", ""
    except DocumentProcessingError:
        raise
    except Exception as e:
        logger.warning("Document reading failed for %s: %s", file_path.name, e)
        raise DocumentProcessingError() from e

    result.raw_text = text or ""
    result.method = method

    if not text.strip():
        result.available = bool(method)
        hint = missing_component_hint()
        result.warning = (
            "No text could be read from this file. "
            + (hint or "The picture may be blurred, angled or too dark - try a "
                       "flatter, brighter photo, or type the details in below.")
        )
        return result

    _parse_document(text, result)

    # Second opinion: a PDF text layer can be damaged (overprinted glyphs,
    # odd font encodings). If name / passport / visa is still missing, read
    # the page as a picture too and fill only the gaps.
    if (suffix == ".pdf" and method == "PDF text layer"
            and not (result.name and result.passport_number and result.visa_number)
            and is_pdf_raster_available()
            and (is_tesseract_available() or _has("easyocr"))):
        _merge_ocr_second_opinion(file_path, result)

    if not result.found_anything:
        result.warning = (
            "The document was read but no passport, visa or gender details "
            "could be recognised in it. Please fill the fields in below - "
            "the file itself has still been attached to this pilgrim."
        )
    elif len(result.fields_found) < 3:
        result.warning = (
            f"Partly read ({', '.join(result.fields_found)}). "
            "Please check the remaining fields before saving."
        )
    return result


def _merge_ocr_second_opinion(file_path: Path, result: OcrResult) -> None:
    try:
        ocr_text, ocr_method = _pdf_rasterise_and_ocr(file_path)
    except Exception as e:                          # noqa: BLE001
        logger.debug("Second-opinion OCR failed: %s", e)
        return
    if not ocr_text.strip():
        return
    second = OcrResult()
    _parse_document(ocr_text, second)
    changed = False
    for attr, label in (("name", "name"), ("passport_number", "passport number"),
                        ("visa_number", "visa number")):
        if not getattr(result, attr) and getattr(second, attr):
            setattr(result, attr, getattr(second, attr))
            if label not in result.fields_found:
                result.fields_found.append(label)
            changed = True
    if result.gender is None and second.gender is not None:
        result.gender = second.gender
        result.gender_source = second.gender_source
        if "gender" not in result.fields_found:
            result.fields_found.append("gender")
        changed = True
    if changed:
        result.method = f"{result.method} + page OCR"
        result.raw_text += "\n\n----- page OCR -----\n" + ocr_text


# ----------------------------------------------------------- PDF backends

def _read_pdf(file_path: Path) -> Tuple[str, str]:
    """Text layer first (fast + exact), rasterise + OCR only if needed."""
    text = _pdf_text_layer(file_path)
    if _looks_useful(text):
        return text, "PDF text layer"

    ocr_text, method = _pdf_rasterise_and_ocr(file_path)
    if _looks_useful(ocr_text):
        # Keep both: the thin text layer sometimes holds the visa number
        # while the OCR pass holds the MRZ.
        return (text + "\n" + ocr_text).strip(), method
    return (text or ocr_text or "").strip(), method or ("PDF text layer" if text else "")


def _pdf_text_layer(file_path: Path) -> str:
    """
    Text layer of a digital PDF, cleaned as far as possible.

    Some official PDFs (the Saudi e-visa is one) draw every character two
    or three times on top of itself to fake a bold font. Read naively that
    turns 1234567890 into 111222333444555666777888999000. pdfplumber can
    drop the stacked duplicates (dedupe_chars); PyMuPDF already ignores
    them. Both texts are kept - they order the page differently, and the
    parser copes with either order.
    """
    parts: List[str] = []

    # pdfplumber - best layout fidelity, with duplicate glyphs removed
    try:
        import pdfplumber
        chunks = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages[:3]:
                try:
                    page = page.dedupe_chars(tolerance=1)
                except Exception as e:              # noqa: BLE001
                    logger.debug("dedupe_chars unavailable: %s", e)
                chunks.append(page.extract_text() or "")
        joined = "\n".join(chunks).strip()
        if joined:
            parts.append(joined)
    except Exception as e:
        logger.debug("pdfplumber text extraction failed: %s", e)

    # PyMuPDF
    try:
        mu = _pymupdf()
        with mu.open(str(file_path)) as doc:
            joined = "\n".join(doc[i].get_text() for i in range(min(3, doc.page_count)))
        if joined.strip():
            parts.append(joined.strip())
    except Exception as e:
        logger.debug("PyMuPDF text extraction failed: %s", e)

    if parts:
        return "\n".join(parts)

    # pypdf - last resort
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        joined = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
        if joined.strip():
            return joined.strip()
    except Exception as e:
        logger.debug("pypdf text extraction failed: %s", e)

    return ""


def _pdf_rasterise_and_ocr(file_path: Path) -> Tuple[str, str]:
    """Render the first pages to images and OCR them."""
    images = []

    # PyMuPDF renders without any external binary - preferred.
    try:
        mu = _pymupdf()
        from PIL import Image
        import io
        with mu.open(str(file_path)) as doc:
            for index in range(min(2, doc.page_count)):
                pix = doc[index].get_pixmap(dpi=300)
                images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        if images:
            return _ocr_images(images), "Scanned PDF (PyMuPDF + OCR)"
    except Exception as e:
        logger.debug("PyMuPDF rasterisation failed: %s", e)

    # pdf2image needs Poppler installed separately.
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(file_path), dpi=300, first_page=1, last_page=2)
        if images:
            return _ocr_images(images), "Scanned PDF (pdf2image + OCR)"
    except Exception as e:
        logger.debug("pdf2image rasterisation failed: %s", e)

    return "", ""


# --------------------------------------------------------- image backends

def _read_image(file_path: Path) -> Tuple[str, str]:
    try:
        from PIL import Image
        image = Image.open(file_path)
        try:
            image.load()
        except Exception as e:
            raise DocumentProcessingError() from e
    except DocumentProcessingError:
        raise
    except Exception as e:
        logger.warning("Could not open image %s: %s", file_path.name, e)
        raise DocumentProcessingError() from e

    return _ocr_images([image]), "Image OCR"


def _ocr_images(images) -> str:
    """OCR a list of PIL images with several strategies, keep the best."""
    if is_tesseract_available():
        return _tesseract_pass(images)
    if _has("easyocr"):
        return _easyocr_pass(images)
    return ""


def _tesseract_pass(images) -> str:
    import pytesseract
    outputs = []
    # PSM 6 = uniform block of text (good for visa forms)
    # PSM 4 = columns of variable size (good for passport data pages)
    # PSM 3 = fully automatic (good fallback)
    configs = [
        r"--oem 3 --psm 6",
        r"--oem 3 --psm 4",
        r"--oem 3 --psm 3",
    ]
    for image in images:
        for variant in _preprocess_variants(image):
            best = ""
            for config in configs:
                try:
                    text = pytesseract.image_to_string(variant, config=config)
                except Exception as e:
                    logger.debug("Tesseract pass failed (%s): %s", config, e)
                    continue
                if _score_text(text) > _score_text(best):
                    best = text
            if best.strip():
                outputs.append(best)
            if _looks_useful("\n".join(outputs)):
                break
    return "\n".join(outputs).strip()


def _easyocr_pass(images) -> str:
    try:
        import easyocr
        import numpy as np
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        lines = []
        for image in images:
            lines.extend(reader.readtext(np.array(image.convert("RGB")), detail=0))
        return "\n".join(lines)
    except Exception as e:
        logger.debug("EasyOCR pass failed: %s", e)
        return ""


def _preprocess_variants(image):
    """
    Yield the original plus cleaned-up versions. Phone photos of visas are
    usually low contrast and small; upscaling and auto-contrasting them
    lifts Tesseract's accuracy dramatically.
    """
    variants = []
    try:
        from PIL import Image, ImageOps, ImageFilter

        rgb = image.convert("RGB")
        grey = ImageOps.grayscale(rgb)

        # Upscale small images - Tesseract wants ~300 DPI equivalent.
        width, height = grey.size
        if max(width, height) < 1800:
            scale = 1800 / max(width, height)
            grey = grey.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

        contrasted = ImageOps.autocontrast(grey, cutoff=2)
        sharpened = contrasted.filter(ImageFilter.SHARPEN)
        binarised = sharpened.point(lambda px: 255 if px > 150 else 0, mode="1")

        variants = [contrasted, sharpened, binarised]
    except Exception as e:
        logger.debug("Image pre-processing failed: %s", e)

    variants.append(image)
    return variants


def _score_text(text: str) -> int:
    """Rough quality score - more real words and MRZ characters is better."""
    if not text:
        return 0
    letters = sum(1 for c in text if c.isalnum())
    mrz_bonus = 40 * len(_find_mrz_lines(text))
    keyword_bonus = 25 * sum(
        1 for kw in ("PASSPORT", "VISA", "SEX", "GENDER", "NATIONALITY", "SURNAME")
        if kw in text.upper()
    )
    return letters + mrz_bonus + keyword_bonus


def _looks_useful(text: str) -> bool:
    if not text or len(text.strip()) < 12:
        return False
    upper = text.upper()
    if _find_mrz_lines(text):
        return True
    return any(kw in upper for kw in (
        "PASSPORT", "VISA", "SEX", "GENDER", "NATIONALITY", "SURNAME",
        "GIVEN NAME", "DATE OF BIRTH", "PERMIT", "TASREEH",
    ))


# -------------------------------------------------------------- parsing

# Name words that (almost only) women carry in Pakistani passports. Used
# ONLY as a last-resort guess and always reported as a guess.
_FEMALE_NAME_MARKERS = {
    "BIBI", "BI", "BEGUM", "BEGAM", "KHATOON", "KHATUN", "KHATON", "BANO", "BANU",
    "NISA", "NISSA", "BEEBEE",
}

_VISA_LABEL_RE = re.compile(r"VISA\s*(?:NO|NUMBER|NUM|ID|#)", re.I)


def _clean_mrz_line(raw: str) -> str:
    """
    OCR often reads the filler '<' as K, S, C or a stray symbol. Repair that
    on lines that are clearly MRZ (lots of '<'), leave every other line alone.
    """
    compact = re.sub(r"\s+", "", raw).upper()
    if compact.count("<") < 6:
        return compact
    compact = re.sub(r"[^A-Z0-9<]", "<", compact)
    previous = None
    while previous != compact:
        previous = compact
        compact = re.sub(r"(?<=<)[KSCEGL](?=<)", "<", compact)
    return compact


def _find_mrz_lines(text: str) -> List[str]:
    lines = []
    for line in text.splitlines():
        compact = re.sub(r"\s+", "", line).upper()
        if compact.count("<") < 3:
            continue
        cleaned = _clean_mrz_line(line)
        if _MRZ_LINE_RE.match(cleaned):
            lines.append(cleaned)
    return lines


def _parse_document(text: str, result: OcrResult) -> None:
    """Fill the result from the raw text. Order matters: MRZ is the most
    reliable source, so it goes first and later passes only fill gaps."""
    _parse_mrz(text, result)
    _parse_labelled_fields(text, result)
    _parse_gender(text, result)
    _finalise(result)


def _fix_mrz_name(name: str) -> str:
    """Repair typical OCR slips in an MRZ name (0 for O, 1 for I, runs of a letter)."""
    name = name.translate({ord("0"): "O", ord("1"): "I", ord("5"): "S", ord("8"): "B"})
    return re.sub(r"([A-Z])\1{2,}", r"\1\1", name)


def _parse_mrz(text: str, result: OcrResult) -> None:
    mrz = _find_mrz_lines(text)
    if len(mrz) < 2:
        return
    line1, line2 = mrz[0], mrz[1]

    # --- Name: TD3 line 1 is  P<PAKSURNAME<<GIVEN<NAMES<<<<<
    name_part = line1[5:] if len(line1) > 5 else ""
    surname, _, given = name_part.partition("<<")
    surname = surname.replace("<", " ").strip()
    given = given.split("<<")[0].replace("<", " ").strip()
    full = " ".join(x for x in (given, surname) if x)
    full = _fix_mrz_name(full)
    full = " ".join(w for w in full.split() if w not in _STOPWORDS)
    if full:
        result.name = full.title()

    # --- Passport number: TD3 line 2 positions 0-8
    if len(line2) >= 9:
        candidate = line2[:9].replace("<", "").strip()
        if len(candidate) >= 5 and candidate not in _STOPWORDS:
            result.passport_number = candidate

    # --- Gender, ICAO letter: TD3 line 2 position 20
    if len(line2) > 20:
        marker = line2[20]
        if marker == "M":
            result.gender, result.gender_source = Gender.MALE, "MRZ"
        elif marker == "F":
            result.gender, result.gender_source = Gender.FEMALE, "MRZ"

    # TD2/TD1 layouts put the sex marker elsewhere - scan for the
    # date-of-birth + sex + expiry pattern as a backup.
    if result.gender is None:
        match = re.search(r"\d{6}[0-9<]([MF])\d{6}", line2)
        if match:
            result.gender = Gender.MALE if match.group(1) == "M" else Gender.FEMALE
            result.gender_source = "MRZ"

    # Saudi e-visa MRZ: the dates are 8 digits (DDMMYYYY) and the sex is a
    # number, not a letter:  NAT + DOB(8) + check + SEX(1|2) + EXPIRY(8) + check
    # e.g.  PAK 15011985 2 2 14122031 9   ->  2 = female (ISO 5218: 1 = male, 2 = female)
    if result.gender is None:
        match = re.search(r"[A-Z]{3}\d{8}\d([12])\d{8}\d", line2)
        if match:
            result.gender = Gender.MALE if match.group(1) == "1" else Gender.FEMALE
            result.gender_source = "MRZ code"


def _collapse_overprint(token: str) -> str:
    """
    '111222333444555666777888999000' (every character x3) -> '1234567890'
    and the x2 version. Only applied to tokens too long to be a real
    number, so a genuine number is never altered.
    """
    for k in (3, 2):
        if len(token) % k == 0 and len(token) // k >= 5:
            groups = [token[i:i + k] for i in range(0, len(token), k)]
            if all(len(set(g)) == 1 for g in groups):
                return "".join(g[0] for g in groups)
    return token


def _find_visa_number(text: str) -> str:
    """
    Layout-independent visa number search.

    A visa number is a run of 8-12 digits. Where it sits relative to the
    words 'Visa No.' varies: some documents print the value AFTER the label,
    the Saudi e-visa prints it BEFORE the label (and again under the
    barcode), and PDF readers / OCR order the page differently again. So
    instead of one pattern we collect every digit run and score it:

      + on the same line as 'Visa No.'                     (strong)
      + on the line right above / below a 'Visa No.' line  (barcode caption)
      + appears more than once on the page                 (field + barcode)
      - on / right under an 'Application No.' line         (a different number)
    """
    lines = [line.strip() for line in text.splitlines()]
    label_lines = {i for i, line in enumerate(lines) if _VISA_LABEL_RE.search(line)}
    app_lines = {i for i, line in enumerate(lines) if "APPLICATION" in line.upper()}

    scores: dict = {}
    counts: dict = {}
    first_seen: dict = {}
    order = 0
    for i, line in enumerate(lines):
        if "<" in line:                      # MRZ lines hold dates, not the visa no.
            continue
        for match in re.finditer(r"(?<![A-Za-z0-9/.\-])(\d{8,40})(?![A-Za-z0-9/\-])", line):
            token = match.group(1)
            if len(token) > 12:
                token = _collapse_overprint(token)
            if not 8 <= len(token) <= 12:
                continue
            score = 1
            if i in label_lines:
                score += 6
            elif (i - 1) in label_lines or (i + 1) in label_lines:
                score += 3
            if i in app_lines:
                score -= 8
            elif (i - 1) in app_lines:
                score -= 4
            scores[token] = scores.get(token, 0) + score
            counts[token] = counts.get(token, 0) + 1
            first_seen.setdefault(token, order)
            order += 1

    best_token, best_score = "", 0
    for token, score in scores.items():
        total = score + (2 if counts[token] >= 2 else 0)
        if total > best_score or (total == best_score and best_token
                                  and first_seen[token] < first_seen[best_token]):
            best_token, best_score = token, total
    return best_token if best_score >= 3 else ""


def _value_around_label(text: str, label_pattern: str, value_pattern: str) -> str:
    """
    Find `value` next to `label` on the same line, whichever side it is on
    ('Passport No: AB123' or 'AB123  Passport No.').
    """
    label_re = re.compile(label_pattern)
    value_re = re.compile(value_pattern)
    for line in text.upper().splitlines():
        label = label_re.search(line)
        if not label:
            continue
        after = value_re.search(line[label.end():])
        if after:
            return after.group(1)
        before = list(value_re.finditer(line[:label.start()]))
        if before:
            return before[-1].group(1)
    return ""


def _parse_labelled_fields(text: str, result: OcrResult) -> None:
    upper = text.upper()

    # ---- Passport number
    if not result.passport_number:
        for pattern in (
            r"PASSPORT\s*(?:NO|NUMBER|NUM|#)\s*[:.#\-]?\s*([A-Z]{0,2}\s?\d{6,9}[A-Z]?)",
            r"(?:DOCUMENT|DOC)\s*(?:NO|NUMBER)\s*[:.#\-]?\s*([A-Z0-9]{6,12})",
            r"\bPASSPORT\b[^\n]{0,20}?\b([A-Z]{2}\d{7})\b",
        ):
            match = re.search(pattern, upper)
            if match:
                candidate = match.group(1).replace(" ", "")
                if candidate not in _STOPWORDS:
                    result.passport_number = candidate
                    break
    if not result.passport_number:
        # value printed BEFORE its label (Saudi e-visa layout)
        candidate = _value_around_label(
            text, r"PASSPORT\s*(?:NO|NUMBER|NUM|#)",
            r"(?<![A-Z0-9])([A-Z]{1,2}\d{6,9})(?![A-Z0-9])",
        )
        if candidate and candidate not in _STOPWORDS:
            result.passport_number = candidate

    # ---- Visa number
    if not result.visa_number:
        result.visa_number = _find_visa_number(text)
    if not result.visa_number:
        for pattern in (
            r"VISA\s*(?:NO|NUMBER|NUM|ID|#)\s*[:.#\-]?\s*([A-Z0-9]{5,40})",
            r"(?:رقم\s*التأشيرة)\s*[:.#\-]?\s*([A-Z0-9]{5,40})",
            r"\bE-?VISA\s*(?:NO|NUMBER)?\s*[:.#\-]?\s*([A-Z0-9]{5,40})",
            r"(?:APPLICATION|PERMIT)\s*(?:NO|NUMBER)\s*[:.#\-]?\s*([A-Z0-9]{5,40})",
        ):
            match = re.search(pattern, upper)
            if match:
                candidate = match.group(1).strip()
                if len(candidate) > 12:
                    candidate = _collapse_overprint(candidate)
                if (candidate not in _STOPWORDS and any(c.isdigit() for c in candidate)
                        and len(candidate) <= 20):
                    result.visa_number = candidate
                    break

    # ---- Name
    if not result.name:
        # NOTE: the character class deliberately excludes newlines, so a
        # label on one line can never swallow the next line's label.
        for pattern in (
            r"(?:FULL[ \t]*NAME|NAME[ \t]*OF[ \t]*(?:HOLDER|APPLICANT)|APPLICANT[ \t]*NAME)[ \t]*[:.\-]?[ \t]*([A-Z][A-Z \t'.-]{3,60})",
            r"(?:GIVEN[ \t]*NAMES?)[ \t]*[:.\-]?[ \t]*([A-Z][A-Z \t'.-]{2,40})",
            r"\bNAME\b[ \t]*[:.\-]?[ \t]{1,30}([A-Z][A-Z \t'.-]{3,60})",
        ):
            match = re.search(pattern, upper)
            if match:
                candidate = " ".join(
                    w for w in match.group(1).split() if w not in _STOPWORDS
                ).strip()
                if len(candidate) >= 3:
                    result.name = candidate.title()
                    break
    if not result.name:
        # value printed BEFORE the word 'Name' (Saudi e-visa layout)
        for line in text.splitlines():
            match = re.match(r"^(.*?)\s+NAME\s*$", line.strip(), re.I)
            if not match or re.search(r"GIVEN|SURNAME|FATHER|MOTHER|SPOUSE|FILE|USER|AGENT|OPERATOR", line, re.I):
                continue
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z'.-]*", match.group(1))
                     if w.upper() not in _STOPWORDS and len(w) >= 2]
            if words:
                result.name = " ".join(words).title()
                break


def _parse_gender(text: str, result: OcrResult) -> None:
    """
    Gender detection, in order of trustworthiness:

      1. MRZ letter / MRZ number        (already done in _parse_mrz)
      2. an explicit label: Sex / Gender / Male / Female / Arabic wording
      3. a guess from the name (Bibi, Begum, Khatoon ...) - reported as a
         guess so the administrator knows to check it

    Many visas (including the Saudi e-visa) print NO sex field at all. When
    nothing is found the gender is left undecided rather than assumed.
    """
    if result.gender is not None:
        return

    upper = " " + re.sub(r"[ \t]+", " ", text.upper()) + " "

    male_patterns = [
        r"\b(?:SEX|GENDER|SEXE|SESSO|GÉNERO|GENERO)\s*(?:/\s*\w+)?\s*[:=\-.]?\s*\(?\s*M\b",
        r"\b(?:SEX|GENDER|SEXE)\s*(?:/\s*\w+)?\s*[:=\-.]?\s*MALE\b",
        r"\bMALE\b(?!\s*/)",
        r"\bM\s*/\s*ذكر",
        r"\bMR\.?\s+[A-Z]",          # honorific
    ]
    female_patterns = [
        r"\b(?:SEX|GENDER|SEXE|SESSO|GÉNERO|GENERO)\s*(?:/\s*\w+)?\s*[:=\-.]?\s*\(?\s*F\b",
        r"\b(?:SEX|GENDER|SEXE)\s*(?:/\s*\w+)?\s*[:=\-.]?\s*FEMALE\b",
        r"\bFEMALE\b",
        r"\bF\s*/\s*أنثى",
        r"\b(?:MRS|MS|MISS)\.?\s+[A-Z]",
    ]

    # Arabic. PDF readers often hand Arabic back visually reversed and in
    # 'presentation forms', so look at the normalised text both ways round.
    arabic = unicodedata.normalize("NFKC", text)
    arabic_both = arabic + "\n" + "\n".join(line[::-1] for line in arabic.splitlines())
    arabic_female = re.search(r"[أا]نث[ىي]|[ىي]ثن[أا]", arabic_both) is not None
    arabic_male = re.search(r"ذكر|ركذ", arabic_both) is not None

    # FEMALE is checked first on the word-level patterns because the
    # substring "MALE" also occurs inside "FEMALE".
    if arabic_female or any(re.search(p, upper) for p in female_patterns):
        result.gender, result.gender_source = Gender.FEMALE, "label"
        return
    if arabic_male or any(re.search(p, upper) for p in male_patterns):
        result.gender, result.gender_source = Gender.MALE, "label"
        return

    # Last resort on labels: a lone M or F directly under or beside a Sex/Gender label.
    match = re.search(r"\b(?:SEX|GENDER)\b[^A-Z0-9]{0,12}([MF])\b", upper)
    if match:
        result.gender = Gender.MALE if match.group(1) == "M" else Gender.FEMALE
        result.gender_source = "label"
        return

    # Family-relation markers: D/O, W/O (female), S/O (male)
    if re.search(r"\b(?:D/O|W/O|DAUGHTER OF|WIFE OF)\b", upper):
        result.gender, result.gender_source = Gender.FEMALE, "name (guess)"
        return
    if re.search(r"\b(?:S/O|SON OF)\b", upper):
        result.gender, result.gender_source = Gender.MALE, "name (guess)"
        return

    # Name-based guess (women only - there is no reliable male marker).
    words = {w for w in re.split(r"[^A-Z]+", (result.name or "").upper()) if w}
    if words & _FEMALE_NAME_MARKERS:
        result.gender, result.gender_source = Gender.FEMALE, "name (guess)"


def _finalise(result: OcrResult) -> None:
    if result.name:
        result.name = re.sub(r"\s+", " ", result.name).strip()
        result.fields_found.append("name")
    if result.passport_number:
        result.passport_number = result.passport_number.upper().strip()
        result.fields_found.append("passport number")
    if result.visa_number:
        result.visa_number = result.visa_number.upper().strip()
        result.fields_found.append("visa number")
    if result.gender is not None:
        result.fields_found.append("gender")
