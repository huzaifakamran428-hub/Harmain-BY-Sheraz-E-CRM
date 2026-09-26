"""
Regression tests for pilgrim photo extraction (infrastructure/photo_service.py):

  * a digital visa PDF embeds several pictures on the page - a portrait
    photo, plus square-ish decorations (a QR code, a watermark seal).
    The extractor must pick the portrait photo, not simply the largest
    or the first picture on the page.
  * a document with no portrait-shaped picture at all (only square/wide
    decorations) must come back with nothing, not a wrong guess.

Run with:  python tests/unit/test_photo_extraction.py
"""
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infrastructure.photo_service import extract_person_photo, _has


def _make_pdf_with_images(pdf_path: Path, images: list) -> None:
    """images: list of (PIL.Image, x, y, display_width, display_height)."""
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(pdf_path), pagesize=(600, 800))
    for image, x, y, w, h in images:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(buf), x, y, width=w, height=h)
    c.save()


def _solid_image(width: int, height: int, color):
    from PIL import Image
    return Image.new("RGB", (width, height), color)


def test_picks_portrait_photo_over_square_decorations():
    if not _has("fitz") and not _has("pymupdf"):
        print("SKIP  test_picks_portrait_photo_over_square_decorations (pymupdf not installed)")
        return
    # A portrait "photo" (35x45mm-ish ratio) plus a big square "seal" and a
    # small square "QR code" - the seal is bigger in raw pixel area, so a
    # naive largest-portrait-ish-image heuristic would wrongly prefer it.
    photo = _solid_image(298, 387, (180, 90, 90))
    seal = _solid_image(760, 785, (40, 40, 40))
    qr = _solid_image(120, 120, (0, 0, 0))
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "visa.pdf"
        _make_pdf_with_images(pdf_path, [
            (seal, 250, 400, 200, 207),
            (photo, 40, 600, 90, 117),
            (qr, 40, 40, 60, 60),
        ])
        result = extract_person_photo(pdf_path)
        assert result.image_bytes, f"expected a photo to be found; warning={result.warning}"
        assert result.method == "PDF embedded photo", result.method

        from PIL import Image
        extracted = Image.open(io.BytesIO(result.image_bytes))
        ratio = extracted.width / extracted.height
        assert 0.6 <= ratio <= 0.95, f"expected the portrait photo's ratio, got {ratio:.3f} ({extracted.size})"


def test_no_portrait_shaped_image_returns_nothing():
    if not _has("fitz") and not _has("pymupdf"):
        print("SKIP  test_no_portrait_shaped_image_returns_nothing (pymupdf not installed)")
        return
    seal = _solid_image(760, 785, (40, 40, 40))
    banner = _solid_image(400, 90, (10, 10, 10))
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "no_photo.pdf"
        _make_pdf_with_images(pdf_path, [
            (seal, 200, 400, 200, 207),
            (banner, 100, 50, 300, 67),
        ])
        result = extract_person_photo(pdf_path)
        assert result.image_bytes is None, "should not have picked a square/wide decoration as the photo"
        assert result.warning


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}  {e}")
    print(f"\n{'ALL PASSED' if not failures else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
