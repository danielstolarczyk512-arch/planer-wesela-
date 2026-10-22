# Raport: zdjęcia z iPhone'a (HEIC) — plan dalszej pracy, A2

Data: 2026-10-21. Znane ograniczenie nr 17 — zawężone; pełne rozwiązanie czeka na test na iPhonie
i ewentualną decyzję licencyjną.

## Licencje (dlaczego bez biblioteki)
- Dekodowanie HEIC w Pythonie wymaga `libheif` (LGPL-3.0) i dekodera HEVC `libde265` (LGPL-3.0).
  Popularne koła `pillow-heif` (sama biblioteka BSD-3) dołączają także **koder x265 (GPL-2.0)** —
  to wykluczone przez ADR-0006 (GPL tylko jako osobny proces).
- Wersja tylko do odczytu `pi-heif` (bez kodera) zawiera wyłącznie biblioteki LGPL — formalnie
  dopuszczalne przy dynamicznym linkowaniu, ale ADR wymaga wtedy wpisu w raporcie licencji;
  przed użyciem trzeba sprawdzić zawartość koła (`*.dist-info/licenses`) na wersji docelowej.
  **Nie dodawałem tej zależności** — niepotrzebna, jeśli wariant bez biblioteki zadziała (niżej).

## Wariant wdrożony (bez nowych zależności)
- **Wybór pliku na iPhonie:** pole wyboru pliku deklaruje typy MIME (`image/jpeg`, `image/png`,
  `application/pdf`, DOCX) obok rozszerzeń. Safari na iOS przy takim `accept` zamienia zdjęcie
  z galerii z HEIC na JPEG przed wysłaniem (zachowanie „najbardziej zgodny format”).
- **Serwer rozpoznaje HEIC/HEIF** po sygnaturze (`ftyp` + marka `heic`/`mif1`/…) i zamiast
  ogólnego „nieobsługiwany format” zwraca `422 document.heic_unsupported` z instrukcją
  (wgrać z telefonu przyciskiem — iPhone zapisze JPG — albo wysłać jako JPG/PDF). To dotyczy np.
  plików HEIC przesłanych z komputera (AirDrop, iCloud).
- **GUI:** plik z rozszerzeniem `.heic`/`.heif` jest zatrzymany przed wysłaniem z tym samym
  komunikatem.

## Do sprawdzenia przez właściciela
- **Test na prawdziwym iPhonie** (zdjęcie z aparatu → „Wgraj dokument”): czy plik dociera jako
  JPG. Lokalnie nie mam iPhone'a; na Androidzie problem nie występuje (JPEG domyślnie).
- Jeśli konwersja nie zadziała (np. inne aplikacje plików), decyzja: `pi-heif` (LGPL, tylko odczyt)
  po sprawdzeniu licencji koła albo konwersja w osobnym kontenerze.
