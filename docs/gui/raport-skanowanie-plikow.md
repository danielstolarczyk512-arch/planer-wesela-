# Raport: skanowanie wgrywanych plików (ClamAV) — plan dalszej pracy, A1

Data: 2026-10-21. Usuwa znane ograniczenie nr 16.

## Licencja i architektura
- ClamAV jest na licencji GPL-2.0, więc zgodnie z ADR-0006 działa **wyłącznie jako osobny kontener**
  (`clamav/clamav:1.4`). Aplikacja łączy się z `clamd` przez TCP i wysyła plik protokołem `INSTREAM`.
- Klient to własny kod (`app/core/antivirus.py`, ok. 40 linii, biblioteka standardowa) — **bez nowych
  zależności** Pythona. Wpis w `docs/tools-report.md`.
- Produkcja (`deploy/compose.prod.yaml`): kontener `clamav` bez publikowanych portów, w osobnej sieci
  `scan` (tylko worker ↔ ClamAV; z internetem dla aktualizacji sygnatur). `WP_ENV=prod` wymaga
  `WP_CLAMAV_HOST` — aplikacja nie wystartuje bez skanera.
- Dev (`compose.yaml`): profil `scan`, domyślnie wyłączony (ClamAV potrzebuje ok. 1,5 GB RAM i przy
  pierwszym starcie pobiera ok. 300 MB sygnatur). Włączenie: `docker compose --profile scan up -d`
  i `WP_CLAMAV_HOST_DOCKER=clamav`.

## Przepływ
- Wersja dokumentu ma `scan_status`: `not_scanned` (skaner wyłączony / plik sprzed wdrożenia),
  `pending`, `clean`, `infected` (migracja `6e1a2b9c4f70`).
- Upload przy włączonym skanerze → `pending` i zadanie `scan_file`; ekstrakcja tekstu (i OCR, i AI)
  dopiero po czystym wyniku. Pobranie i „spróbuj ponownie” przy `pending` → 409 `document.scan_pending`.
- Ten sam plik (ten sam skrót) w weselu: wynik przejęty bez ponownego skanu; plik wcześniej
  zablokowany → odrzucony od razu (422 `document.infected`).
- **Zainfekowany:** wszystkie wersje z tym plikiem → `infected` z nazwą sygnatury, tekst „Plik
  zablokowany…”, plik **usunięty z magazynu** (kwarantanna), wpis w audycie (`infected`).
- **Skaner niedostępny / błąd skanera:** zadanie wraca do kolejki z rosnącą przerwą (do 1 h),
  maks. 50 prób (ok. 2 doby); plik w tym czasie zablokowany — nic nie przechodzi bez sprawdzenia.
- Pliki sprzed wdrożenia skanera: worker przy każdym cyklu utrzymania (15 min) kolejkuje do 100
  plików `not_scanned`.

## GUI (`Documents.tsx`)
- Na liście: „Sprawdzanie pliku…” / „Zablokowany” zamiast stanu odczytu tekstu; lista odświeża się,
  dopóki trwa skan.
- W szczegółach: komunikat o sprawdzaniu albo o zablokowanym pliku (co zrobić), przycisk „Pobierz
  plik” tylko dla plików czystych lub niesprawdzanych.

## Testy
- `tests/unit/test_antivirus.py` — klient na prawdziwym gnieździe TCP z serwerem udającym `clamd`:
  przesyłanie w porcjach, wynik czysty, sygnatura, błąd skanera, brak połączenia.
- `tests/api/test_document_scan.py` — przez prawdziwą kolejkę i worker (skaner jako dubler): skan
  przed ekstrakcją, blokada pobrania, przejęcie wyniku dla tego samego pliku, kwarantanna i audyt,
  ponowienie przy niedostępnym skanerze, pliki sprzed wdrożenia, wymóg skanera w produkcji.
- **Prawdziwy ClamAV:** `test_real_clamd_detects_eicar` (plik testowy EICAR) — uruchamiany przy
  `WP_TEST_CLAMAV_HOST`; przeszedł na lokalnym kontenerze. Ciąg EICAR składany w czasie działania
  (dosłowny w źródle bywa blokowany przez antywirus stacji).
- E2E „Dokumenty…” (8 profili) przeszedł z API i workerem połączonymi z prawdziwym `clamd`.
  Po sprawdzeniu środowisko dev wróciło do ustawień domyślnych (skaner wyłączony, kontener zatrzymany).
- Uwaga z testu w dev: włączenie skanera kolejkuje stare pliki; przy wykryciu zagrożenia plik jest
  usuwany. Prawdziwe wesele właściciela nie miało dokumentów; 3 pliki demo — czyste.
- Ponowny test 2026-10-21 wieczorem (`WP_TEST_CLAMAV_HOST=127.0.0.1`, `clamav/clamav:1.4`): testy skanowania
  10/10, EICAR wykryty; kontener zatrzymany po teście.
