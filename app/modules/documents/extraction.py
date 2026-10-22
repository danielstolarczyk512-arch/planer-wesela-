"""Ekstrakcja tekstu z PDF, DOCX i zdjęć. Lokalnie, bez wysyłania plików na zewnątrz.

- PDF z warstwą tekstową: pypdf (BSD).
- PDF-skan i zdjęcia: render stron pypdfium2 (Apache/BSD) + OCR Tesseract (Apache-2.0, `pol`).
- DOCX: python-docx (MIT), akapity i tabele.
Celowo bez PyMuPDF (AGPL) i OCRmyPDF/Ghostscript (AGPL), zob. ADR-0006.
"""

import io
import re
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.modules.documents import filetypes

Image.MAX_IMAGE_PIXELS = 40_000_000  # ochrona przed „bombami dekompresji”
MAX_PDF_PAGES = 100
MAX_TEXT_CHARS = 1_000_000
MIN_CHARS_PER_PAGE = 30  # mniej oznacza najpewniej skan → OCR
OCR_DPI = 200


class ExtractionError(Exception):
    """Błąd zależny od pliku (nie od serwera): ponawianie nic nie da."""


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    page_offsets: list[list[int]]
    page_count: int
    ocr_used: bool


def _clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _join(pages: list[str], ocr_used: bool) -> ExtractionResult:
    parts, offsets, position = [], [], 0
    for page in pages:
        cleaned = _clean(page)
        offsets.append([position, position + len(cleaned)])
        parts.append(cleaned)
        position += len(cleaned) + 2  # separator "\n\n"
    text = "\n\n".join(parts)[:MAX_TEXT_CHARS]
    return ExtractionResult(
        text=text, page_offsets=offsets, page_count=len(pages), ocr_used=ocr_used
    )


def _ocr(image: Image.Image) -> str:
    settings = get_settings()
    if not settings.ocr_enabled:
        raise ExtractionError("OCR jest wyłączony. Wpisz dane ręcznie.")
    import pytesseract  # import lokalny: moduł jest potrzebny tylko w workerze

    try:
        result: str = pytesseract.image_to_string(
            image.convert("L"), lang=settings.ocr_languages, timeout=90
        )
        return result
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractionError("OCR (Tesseract) nie jest dostępny na tym serwerze.") from exc
    except RuntimeError as exc:  # przekroczony czas
        raise ExtractionError("OCR trwał zbyt długo.") from exc


def _pdf(data: bytes) -> ExtractionResult:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("PDF jest zabezpieczony hasłem. Wgraj wersję bez hasła.")
        pages = [p.extract_text() or "" for p in reader.pages[:MAX_PDF_PAGES]]
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise ExtractionError("Nie udało się odczytać pliku PDF (uszkodzony?).") from exc
    if not pages:
        raise ExtractionError("PDF nie zawiera stron.")
    if sum(len(p.strip()) for p in pages) >= MIN_CHARS_PER_PAGE * len(pages):
        return _join(pages, ocr_used=False)
    return _join(_ocr_pdf(data), ocr_used=True)


def _ocr_pdf(data: bytes) -> list[str]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise ExtractionError("Nie udało się wyrenderować PDF do OCR.") from exc
    try:
        limit = min(len(pdf), get_settings().ocr_max_pages)
        return [_ocr(pdf[i].render(scale=OCR_DPI / 72).to_pil()) for i in range(limit)]
    finally:
        pdf.close()


def _docx(data: bytes) -> ExtractionResult:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:  # python-docx zgłasza różne wyjątki dla uszkodzonych plików
        raise ExtractionError("Nie udało się odczytać pliku DOCX.") from exc
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    return _join(["\n".join(lines)], ocr_used=False)


def _image(data: bytes) -> ExtractionResult:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            return _join([_ocr(img)], ocr_used=True)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ExtractionError("Nie udało się odczytać obrazu.") from exc


def extract(data: bytes, mime: str) -> ExtractionResult:
    if mime == filetypes.PDF:
        return _pdf(data)
    if mime == filetypes.DOCX:
        return _docx(data)
    if mime in (filetypes.JPEG, filetypes.PNG):
        return _image(data)
    raise ExtractionError(f"Nieobsługiwany typ: {mime}")
