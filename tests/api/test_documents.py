from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.jobs import worker
from app.modules.documents.models import DocumentVersion
from tests.api.test_workspace import invite_and_accept
from tests.fixtures.offer_corpus import corpus, tesseract_available

API = "/api/v1"


def pdf_sample():
    return next(s for s in corpus() if s.mime == "application/pdf" and not s.needs_ocr)


def upload(client, headers, wedding, sample, **form):
    return client.post(
        f"{API}/weddings/{wedding['id']}/documents",
        headers=headers,
        files={"file": (f"{sample.name}.bin", sample.data, "application/x-any")},
        data={"kind": "offer", **form},
    )


def drain_jobs():
    while worker.run_once():
        pass


def storage_files() -> int:
    return sum(1 for p in Path(get_settings().storage_dir).rglob("*") if p.is_file())


def test_upload_extract_download(client, alice, wedding):
    sample = pdf_sample()
    r = upload(client, alice, wedding, sample, title="Oferta sali")
    assert r.status_code == 202, r.text
    doc = r.json()
    assert doc["title"] == "Oferta sali"
    v = doc["versions"][0]
    assert v["mime_type"] == "application/pdf"  # z zawartości, nie z nagłówka klienta
    assert v["original_filename"].endswith(".pdf")
    assert v["text_status"] == "pending"

    drain_jobs()
    base = f"{API}/weddings/{wedding['id']}/documents/{doc['id']}/versions/{v['id']}"
    text = client.get(f"{base}/text", headers=alice).json()
    assert text["text_status"] == "done"
    assert text["page_count"] == 2
    assert sample.expected[0] in text["pages"][0]["text"]

    f = client.get(f"{base}/file", headers=alice)
    assert f.status_code == 200
    assert f.content == sample.data
    assert f.headers["content-disposition"].startswith("attachment;")
    assert f.headers["content-security-policy"] == "sandbox"


def test_docx_and_new_version_and_dedupe(client, alice, wedding, db):
    docx = next(s for s in corpus() if s.name.startswith("docx-"))
    doc = upload(client, alice, wedding, docx).json()
    drain_jobs()
    files_before = storage_files()

    url = f"{API}/weddings/{wedding['id']}/documents/{doc['id']}/versions"
    r = client.post(url, headers=alice, files={"file": ("v2.docx", docx.data)})
    assert r.status_code == 202
    versions = r.json()["versions"]
    assert [v["version_no"] for v in versions] == [1, 2]
    # Ten sam plik: bez nowego pliku na dysku i bez ponownego przetwarzania.
    assert versions[1]["text_status"] == "done"
    assert storage_files() == files_before
    assert db.scalar(select(func.count(func.distinct(DocumentVersion.storage_key)))) == 1


def test_rejects_unsupported_and_too_large(client, alice, wedding, monkeypatch):
    url = f"{API}/weddings/{wedding['id']}/documents"
    r = client.post(
        url, headers=alice, files={"file": ("x.pdf", b"MZ fake exe", "application/pdf")}
    )
    assert r.status_code == 422
    assert r.json()["code"] == "document.unsupported_type"
    # Zdjęcie HEIC z iPhone'a (nagłówek ISO BMFF z marką „heic”): jasny komunikat, co zrobić.
    heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64
    r = client.post(url, headers=alice, files={"file": ("IMG_0001.HEIC", heic, "image/heic")})
    assert r.status_code == 422
    assert r.json()["code"] == "document.heic_unsupported"
    assert "JPG" in r.json()["detail"]
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    big = b"%PDF-1.4\n" + b"0" * (3 * 1024 * 1024)
    r = client.post(url, headers=alice, files={"file": ("big.pdf", big)})
    assert r.status_code == 413
    assert r.json()["code"] == "document.too_large"


def test_quota(client, alice, wedding, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_documents_per_wedding", 1)
    samples = [s for s in corpus() if not s.needs_ocr]
    assert upload(client, alice, wedding, samples[0]).status_code == 202
    r = upload(client, alice, wedding, samples[1])
    assert r.status_code == 409
    assert r.json()["code"] == "document.quota"


def test_scan_without_ocr_marked_failed_and_retry(client, alice, wedding):
    scan = next(s for s in corpus() if s.needs_ocr)
    doc = upload(client, alice, wedding, scan).json()
    drain_jobs()
    v = client.get(f"{API}/weddings/{wedding['id']}/documents/{doc['id']}", headers=alice).json()[
        "versions"
    ][0]
    if tesseract_available():
        assert v["text_status"] == "done"
        assert v["ocr_used"] is True
    else:
        assert v["text_status"] == "failed"
        assert "OCR" in v["text_error"]
        retry = client.post(
            f"{API}/weddings/{wedding['id']}/documents/{doc['id']}/versions/{v['id']}/retry",
            headers=alice,
        )
        assert retry.status_code == 202
        assert retry.json()["text_status"] == "pending"


def test_delete_document_and_wedding_remove_files(client, alice, wedding):
    samples = [s for s in corpus() if not s.needs_ocr]
    d1 = upload(client, alice, wedding, samples[0]).json()
    upload(client, alice, wedding, samples[1])
    assert storage_files() >= 2
    before = storage_files()
    assert (
        client.delete(
            f"{API}/weddings/{wedding['id']}/documents/{d1['id']}", headers=alice
        ).status_code
        == 204
    )
    assert storage_files() == before - 1

    assert client.delete(f"{API}/weddings/{wedding['id']}", headers=alice).status_code == 204
    drain_jobs()
    prefix = Path(get_settings().storage_dir) / "weddings" / wedding["id"]
    assert not prefix.exists()


def test_viewer_can_read_not_upload(client, alice, user_factory, wedding):
    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    doc = upload(client, alice, wedding, pdf_sample()).json()
    url = f"{API}/weddings/{wedding['id']}/documents"
    assert client.get(f"{url}/{doc['id']}", headers=viewer).status_code == 200
    assert upload(client, viewer, wedding, pdf_sample()).status_code == 403
    assert client.delete(f"{url}/{doc['id']}", headers=viewer).status_code == 403


def test_search_documents_text_title_and_diacritics(client, alice, wedding):
    sample = pdf_sample()
    doc = upload(client, alice, wedding, sample, title="Oferta Dworek Złota Jesień").json()
    drain_jobs()
    url = f"{API}/weddings/{wedding['id']}/documents/search"
    word = next(w for w in sample.expected[0].split() if len(w) >= 4)

    # Treść: bez rozróżniania wielkości liter, z fragmentem i numerem strony.
    r = client.get(url, headers=alice, params={"q": word.upper()})
    assert r.status_code == 200, r.text
    hits = r.json()
    assert [h["document_id"] for h in hits] == [doc["id"]]
    assert hits[0]["page"] == 1
    assert word.lower() in hits[0]["snippet"].lower()

    # Tytuł bez polskich znaków.
    r = client.get(url, headers=alice, params={"q": "zlota jesien"}).json()
    assert r[0]["in_title"] is True
    # Odmiana i kolejność słów: „złotej jesieni”, „jesień złota” — oba słowa muszą wystąpić.
    for q in ("złotej jesieni", "jesień złota"):
        r = client.get(url, headers=alice, params={"q": q}).json()
        assert [h["document_id"] for h in r] == [doc["id"]], q
    assert client.get(url, headers=alice, params={"q": "złota xyzzy"}).json() == []

    # Brak trafień; znaki LIKE traktowane dosłownie; za krótkie zapytanie odrzucone.
    assert client.get(url, headers=alice, params={"q": "xyzzy-brak"}).json() == []
    assert client.get(url, headers=alice, params={"q": "%%"}).json() == []
    assert client.get(url, headers=alice, params={"q": "a"}).status_code == 422
