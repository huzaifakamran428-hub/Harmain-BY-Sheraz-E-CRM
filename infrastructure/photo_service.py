"""
Pilgrim photo extraction (companion to ocr_service.py).

Two very different sources, so two very different strategies:

  1. DIGITAL PDF VISAS (Saudi e-visa, Nusuk permits) embed the pilgrim's
     photo as its own separate picture object on the page, next to the
     printed text - see the ID-style photo in the top-left of the sample
     visa. PyMuPDF can list and pull out every embedded picture object
     directly, at full quality, with no guessing about where a face is.
     This needs nothing beyond the pymupdf dependency the app already
     uses for OCR.

  2. A PLAIN PHOTO of a passport/visa (a phone picture, a scan saved as
     JPG/PNG) is just one flat picture - there is no separate photo
     object to pull out. Finding the person's face in it needs a face
     detector. OpenCV's built-in Haar cascade (bundled with the
     `opencv-python` package - no internet download needed at runtime)
     is used when that package is installed; when it is not, extraction
     is skipped and the administrator can attach the picture by hand
     with "Set Photo" - exactly the same graceful fall-through pattern
     already used for OCR when Tesseract is missing.

Never raises for "could not find a photo" - that is a normal, expected
outcome. The document itself is always kept either way.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from core.logging_setup import get_logger
from infrastructure.ocr_service import IMAGE_SUFFIXES, _has, _pymupdf

logger = get_logger(__name__)

# A passport/visa photo is a head-and-shoulders portrait - noticeably
# taller than it is wide, but not a strip (that is a signature or a
# barcode). Logos, seals and QR codes are usually square or wider than
# tall, so a plain "portrait-shaped" cutoff is not enough on its own -
# real Saudi e-visas also embed a near-square watermark seal and QR
# codes that a loose ratio check would otherwise prefer by sheer size.
_MIN_PHOTO_SIDE_PX = 70
_PHOTO_RATIO_RANGE = (0.55, 0.98)      # width / height, hard filter
_IDEAL_PHOTO_RATIO = 0.78              # standard 35x45mm visa/passport photo
# A full-page scan (or a large background seal) embedded as one big
# picture is not a "photo" in this sense - skip pictures clearly larger
# than a passport photo ever is.
_MAX_PHOTO_SIDE_PX = 1400


@dataclass
class PhotoResult:
    """What the extractor managed to find, if anything."""
    image_bytes: Optional[bytes] = None    # PNG bytes, ready to store
    method: str = ""                       # how it was found, for the status line
    warning: str = ""                      # user-facing note when nothing was found


def extract_person_photo(file_path: Path) -> PhotoResult:
    """
    Best-effort: pull a photo of the pilgrim out of the stored document.
    Always returns a PhotoResult, even when nothing could be found -
    that is never a reason to block saving the pilgrim.
    """
    result = PhotoResult()
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".pdf":
            raw, method = _pdf_embedded_photo(file_path)
        elif suffix in IMAGE_SUFFIXES:
            raw, method = _image_face_crop(file_path)
        else:
            raw, method = None, ""
    except Exception as e:                                  # noqa: BLE001
        logger.warning("Photo extraction failed for %s: %s", file_path.name, e)
        raw, method = None, ""

    if not raw:
        if suffix in IMAGE_SUFFIXES and not _has("cv2"):
            result.warning = (
                'No face could be detected automatically in this photo (the optional '
                '"opencv-python" package is not installed on this computer). Use '
                '"Set Photo" to attach the pilgrim\'s picture yourself.'
            )
        else:
            result.warning = (
                'No photo could be picked up automatically from this document. Use '
                '"Set Photo" to attach the pilgrim\'s picture yourself.'
            )
        return result

    png_bytes = _normalize_to_png(raw)
    if not png_bytes:
        result.warning = "A photo was found but could not be processed. Please set it with \"Set Photo\"."
        return result

    result.image_bytes = png_bytes
    result.method = method
    return result


def photo_backend_available_for_images() -> bool:
    """True when this computer can auto-detect a face inside a plain photo upload."""
    return _has("cv2")


# ------------------------------------------------------------ PDF source

def _pdf_embedded_photo(file_path: Path) -> Tuple[Optional[bytes], str]:
    """
    Scan the first two pages for embedded picture objects and pick the
    one that looks most like a passport-style portrait: a reasonably
    sized, portrait-oriented picture whose shape is closest to the
    standard 35x45mm visa/passport photo - not simply the largest
    portrait-ish picture on the page, because a Saudi e-visa also embeds
    a near-square background seal and QR codes that are often far
    bigger than the actual photo and would otherwise win on size alone.
    """
    try:
        mu = _pymupdf()
    except Exception as e:                                  # noqa: BLE001
        logger.debug("PyMuPDF unavailable for photo extraction: %s", e)
        return None, ""

    # (closeness-to-ideal-ratio, -area, data, width, height) - sorted so the
    # best-shaped candidate wins, and the larger one wins any near-tie.
    candidates: List[Tuple[float, int, bytes, int, int]] = []
    try:
        with mu.open(str(file_path)) as doc:
            for page_index in range(min(2, doc.page_count)):
                page = doc[page_index]
                for img in page.get_images(full=True):
                    xref = img[0]
                    try:
                        info = doc.extract_image(xref)
                    except Exception as e:                   # noqa: BLE001
                        logger.debug("Could not extract embedded image xref %s: %s", xref, e)
                        continue
                    data = info.get("image")
                    width, height = info.get("width", 0), info.get("height", 0)
                    if not data:
                        continue
                    if not (_MIN_PHOTO_SIDE_PX <= width <= _MAX_PHOTO_SIDE_PX
                             and _MIN_PHOTO_SIDE_PX <= height <= _MAX_PHOTO_SIDE_PX):
                        continue
                    ratio = (width / height) if height else 0
                    if not (_PHOTO_RATIO_RANGE[0] <= ratio <= _PHOTO_RATIO_RANGE[1]):
                        continue
                    score = abs(ratio - _IDEAL_PHOTO_RATIO)
                    candidates.append((score, -(width * height), data, width, height))
    except Exception as e:                                  # noqa: BLE001
        logger.debug("PDF photo scan failed for %s: %s", file_path.name, e)
        return None, ""

    if not candidates:
        return None, ""

    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2], "PDF embedded photo"


# ---------------------------------------------------------- image source

def _image_face_crop(file_path: Path) -> Tuple[Optional[bytes], str]:
    """Detect the largest face in a flat photo and crop a portrait around it."""
    if not _has("cv2"):
        return None, ""
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps

        pil_image = Image.open(file_path)
        pil_image = ImageOps.exif_transpose(pil_image)          # phone photos rotate on read
        rgb = pil_image.convert("RGB")
        array = np.array(rgb)
        grey = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        faces = cascade.detectMultiScale(grey, scaleFactor=1.1, minNeighbors=5,
                                          minSize=(_MIN_PHOTO_SIDE_PX, _MIN_PHOTO_SIDE_PX))
        if len(faces) == 0:
            return None, ""

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])     # largest face on the page
        # Pad out from the bare face box to something closer to a passport
        # photo (room above the head, shoulders below), then clamp to the image.
        pad_x, pad_top, pad_bottom = int(w * 0.6), int(h * 0.7), int(h * 1.1)
        left = max(0, x - pad_x)
        top = max(0, y - pad_top)
        right = min(rgb.width, x + w + pad_x)
        bottom = min(rgb.height, y + h + pad_bottom)

        cropped = rgb.crop((left, top, right, bottom))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        return buffer.getvalue(), "Face detected in photo"
    except Exception as e:                                      # noqa: BLE001
        logger.debug("Face detection failed for %s: %s", file_path.name, e)
        return None, ""


# --------------------------------------------------------------- shared

def _normalize_to_png(data: bytes) -> Optional[bytes]:
    """Re-encode whatever format the source used into plain PNG, so the
    UI can always load it (some embedded PDF images use formats Qt
    cannot open directly)."""
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(data)).convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:                                      # noqa: BLE001
        logger.debug("Photo normalisation failed: %s", e)
        return None
