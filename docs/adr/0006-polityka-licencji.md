# ADR-0006: Polityka licencji zależności

- Status: zaakceptowany, Data: 2026-10-19

## Decyzja
Dozwolone bez zgody: MIT, BSD, Apache-2.0, ISC, PSF, Zlib, MPL-2.0 (bez modyfikacji plików biblioteki), LGPL (tylko dynamiczne linkowanie, czyli zwykły import w Pythonie).
Zakazane w kodzie i obrazach produkcyjnych: **AGPL, SSPL, BUSL, Commons Clause, licencje „non-commercial”**.
GPL: tylko jako **osobny proces/kontener** komunikujący się przez sieć/CLI (np. ClamAV), po zapisaniu w raporcie licencji.
Modele AI: tylko licencje dopuszczające użycie komercyjne. Licencja modelu zapisana w `prompt_versions`/konfiguracji.

## Konkretne skutki
Odrzucone: PyMuPDF (AGPL), OCRmyPDF (wymaga Ghostscript AGPL), MinIO (AGPL). Zamienniki: pypdf, pypdfium2, Tesseract, S3 u dostawcy.

## Egzekwowanie
`pip-licenses` (MIT) w CI z listą zakazanych licencji, raport `docs/licenses.md` generowany automatycznie.
