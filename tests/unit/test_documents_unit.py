import io
import zipfile

import pytest

from app.core.errors import Unprocessable
from app.core.storage import LocalStorage
from app.modules.documents import filetypes
from app.modules.documents.extraction import ExtractionError, extract
from tests.fixtures.offer_corpus import corpus, normalize, tesseract_available

# --- rozpoznawanie typów -----------------------------------------------------------------


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_detects_corpus_types():
    for sample in corpus():
        assert filetypes.detect(sample.data) == sample.mime, sample.name


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"MZ\x90\x00 to jest program exe",
        b"\xd0\xcf\x11\xe0 stary .doc",
        b"<html><script>alert(1)</script></html>",
    ],
)
def test_rejects_unsupported(data):
    with pytest.raises(Unprocessable):
        filetypes.detect(data)


def test_rejects_zip_that_is_not_docx():
    with pytest.raises(Unprocessable, match="nie jest dokumentem Word"):
        filetypes.detect(_zip({"a.txt": b"x"}))


def test_rejects_zip_bomb():
    bomb = _zip({"[Content_Types].xml": b"x", "word/document.xml": b"0" * 30_000_000})
    with pytest.raises(Unprocessable, match="kompresja"):
        filetypes.detect(bomb)


def test_sanitize_filename():
    assert filetypes.sanitize_filename("../../etc/passwd", filetypes.PDF) == "passwd.pdf"
    assert filetypes.sanitize_filename("Umowa\x00 sala.exe", filetypes.PDF) == "Umowa sala.pdf"
    assert filetypes.sanitize_filename(None, filetypes.DOCX) == "dokument.docx"
    assert len(filetypes.sanitize_filename("a" * 500 + ".pdf", filetypes.PDF)) <= 124


# --- magazyn plików --------------------------------------------------------------------


def test_local_storage_roundtrip_and_traversal(tmp_path):
    s = LocalStorage(tmp_path)
    s.put("weddings/w1/a", b"abc")
    assert s.get("weddings/w1/a") == b"abc"
    s.put("weddings/w1/b", b"def")
    assert s.delete_prefix("weddings/w1") == 2
    assert not (tmp_path / "weddings" / "w1").exists()
    for bad in ("../x", "weddings/../../x", "/etc/passwd", "C:/x", "weddings/w1/.."):
        with pytest.raises(ValueError, match=r"(?i)klucz"):
            s.put(bad, b"x")


# --- ekstrakcja na korpusie 20 ofert ------------------------------------------------------


def test_corpus_size():
    samples = corpus()
    assert len(samples) == 20
    assert sum(s.needs_ocr for s in samples) == 4


@pytest.mark.parametrize("sample", [s for s in corpus() if not s.needs_ocr], ids=lambda s: s.name)
def test_text_extraction_corpus(sample):
    result = extract(sample.data, sample.mime)
    text = normalize(result.text)
    for phrase in sample.expected:
        assert normalize(phrase) in text, f"{sample.name}: brak „{phrase}”"
    assert result.ocr_used is False
    if sample.mime == filetypes.PDF:
        assert result.page_count == 2
        first = result.text[result.page_offsets[0][0] : result.page_offsets[0][1]]
        assert "Menu weselne" in first
        assert "Zadatek" not in first  # zadatek jest na stronie 2


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract niedostępny: test w Dockerze")
@pytest.mark.parametrize("sample", [s for s in corpus() if s.needs_ocr], ids=lambda s: s.name)
def test_ocr_corpus(sample):
    result = extract(sample.data, sample.mime)
    assert result.ocr_used is True
    text = normalize(result.text, strip_diacritics=True)
    for phrase in sample.expected:
        assert normalize(phrase, strip_diacritics=True) in text, f"{sample.name}: {phrase}"


@pytest.mark.skipif(tesseract_available(), reason="Test zachowania bez Tesseracta")
def test_scan_without_tesseract_fails_clearly():
    scan = next(s for s in corpus() if s.needs_ocr)
    with pytest.raises(ExtractionError, match="OCR"):
        extract(scan.data, scan.mime)


def test_encrypted_pdf_fails_clearly():
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(corpus()[0].data)).pages:
        writer.add_page(page)
    writer.encrypt("tajne-haslo")
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ExtractionError, match="hasłem"):
        extract(buf.getvalue(), filetypes.PDF)


def test_corrupted_files_fail_clearly():
    with pytest.raises(ExtractionError):
        extract(b"%PDF-1.4 to nie jest prawdziwy pdf", filetypes.PDF)
    with pytest.raises(ExtractionError):
        extract(b"\x89PNG\r\n\x1a\nuszkodzony", filetypes.PNG)


def test_search_stemming_polish_endings():
    from app.modules.documents.service import search_terms, stem

    assert stem("sali") == "sal"
    assert stem("umowie") == "umow"
    assert stem("zaliczki") == "zaliczk"
    assert stem("dekoracjami") == "dekoracj"
    assert stem("obiad") == "obiad"
    assert stem("zlotej") == "zlot"
    assert stem("weselnych") == "weseln"
    assert stem("sal") == "sal"  # krótkie słowa bez zmian
    # Polskie znaki i wielkość liter: „Salą” = „sala” → „sal”; jednoliterowe słowa pomijane.
    assert search_terms("Salą w  Zaliczkę a") == ["sal", "zaliczk"]
