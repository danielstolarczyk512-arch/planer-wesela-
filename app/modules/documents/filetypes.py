"""Rozpoznawanie typu pliku po zawartości (sygnaturze), nie po rozszerzeniu ani nagłówku klienta."""

import io
import re
import unicodedata
import zipfile

from app.core.errors import Unprocessable

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
JPEG = "image/jpeg"
PNG = "image/png"
EXTENSIONS = {PDF: ".pdf", DOCX: ".docx", JPEG: ".jpg", PNG: ".png"}

# Ochrona przed „zip bombą” w DOCX.
MAX_ZIP_ENTRIES = 1000
MAX_ZIP_UNCOMPRESSED = 100 * 1024 * 1024
MAX_ZIP_RATIO = 200


def _reject(detail: str) -> Unprocessable:
    return Unprocessable(detail, code="document.unsupported_type")


def detect(data: bytes) -> str:
    if not data:
        raise _reject("Plik jest pusty.")
    if b"%PDF-" in data[:1024]:
        return PDF
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if data.startswith(b"PK\x03\x04"):
        _check_docx(data)
        return DOCX
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        raise _reject("Stary format .doc nie jest obsługiwany. Zapisz plik jako PDF lub DOCX.")
    if is_heic(data):
        # Bez dekodera HEIC w aplikacji (libheif: LGPL, koder x265: GPL) — zob. raport A2.
        raise Unprocessable(
            "Zdjęcie jest w formacie HEIC (domyślnym w iPhonie). Wgraj je z telefonu przyciskiem "
            "„Wybierz plik” — iPhone sam zapisze je jako JPG — albo wyślij jako JPG lub PDF.",
            code="document.heic_unsupported",
        )
    raise _reject("Obsługiwane formaty: PDF, DOCX, JPG, PNG.")


HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1", b"avif"}


def is_heic(data: bytes) -> bool:
    """HEIC/HEIF (i AVIF): kontener ISO BMFF z polem `ftyp` i marką HEIF na początku pliku."""
    return len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS


def _check_docx(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            entries = zf.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise _reject("Plik DOCX ma zbyt wiele elementów.")
            total = 0
            for e in entries:
                total += e.file_size
                if e.compress_size and e.file_size / e.compress_size > MAX_ZIP_RATIO:
                    raise _reject("Podejrzany plik DOCX (nietypowa kompresja).")
            if total > MAX_ZIP_UNCOMPRESSED:
                raise _reject("Plik DOCX po rozpakowaniu jest zbyt duży.")
            names = {e.filename for e in entries}
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise _reject("Archiwum ZIP nie jest dokumentem Word (DOCX).")
    except zipfile.BadZipFile as exc:
        raise _reject("Uszkodzony plik DOCX.") from exc


def sanitize_filename(name: str | None, mime: str) -> str:
    """Nazwa tylko do wyświetlania i pobierania; nigdy nie jest ścieżką na dysku."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = unicodedata.normalize("NFC", base)
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C")
    base = re.sub(r"\s+", " ", base).strip(" .")[:120]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    return (stem or "dokument") + EXTENSIONS[mime]
