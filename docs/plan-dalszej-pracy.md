# Plan dalszej pracy (po dokończeniu v1.1)

Stan: 2026-10-20, commit `4b122d0`, ostatnia migracja `3b7e9f2c5d18`; backend 710 testów, vitest 84,
E2E zielone. Zrobione: v1.1 i jej dokończenie (raporty w `docs/gui/`).
Zasady jak zawsze (CLAUDE.md): tylko licencje permisywne (GPL tylko jako osobny proces, ADR-0006),
bez płatnych usług bez zgody, prawdziwego wesela właściciela nie ruszać, każda zmiana:
backend + testy → `task web:types` → GUI → E2E (8 profili) → raport → commit.

Oznaczenia: 🟢 można robić od razu · 🟡 najpierw krótka decyzja właściciela · 🔴 decyzja biznesowa/prawna,
nie robić samodzielnie.

---

## Etap A — dokończenie techniczne (bez decyzji biznesowych), ok. 1–2 tygodnie

**Stan 2026-10-21:** A1 ✅, A2 ✅ (wariant bez zależności; test na iPhonie — właściciel), A3 ✅, A4 ✅,
A7 ✅ (bez testu obciążenia — czeka na A5); A5 i A6 — decyzje właściciela. Raporty w `docs/gui/`.

### A1. 🟢 Skanowanie plików (ClamAV jako osobny kontener) — znane ograniczenie nr 16
- Kontener `clamav` (oficjalny obraz, GPL — osobny proces, komunikacja przez sieć `clamd`, zgodnie z ADR-0006)
  w `compose.yaml` i w compose produkcyjnym; klient w Pythonie przez gniazdo TCP (`INSTREAM`) —
  własny kod albo biblioteka na licencji permisywnej (sprawdzić `scripts/check-licenses`).
- Worker: po uploadzie dokument w stanie `scanning` → `clean` / `infected` (kwarantanna, bez pobierania
  i bez ekstrakcji); gdy ClamAV niedostępny — stan `scan_pending` i ponowienie, nie przepuszczamy.
- GUI: status „sprawdzanie pliku…”, komunikat przy zainfekowanym pliku.
- Testy: plik EICAR (test w Dockerze, jak OCR), brak skanera → ponowienie; aktualizacja `docs/wdrozenie.md`.

### A2. 🟡 Zdjęcia z iPhone'a (HEIC) — znane ograniczenie nr 17
- **Najpierw licencje:** `pillow-heif` (BSD) dołącza libheif (LGPL) i dekodery; sprawdzić, czy wheel nie
  zawiera komponentów GPL (np. koder x265). Jeśli tak — nie używać.
- Wariant bez nowych zależności (preferowany do sprawdzenia): `accept` w polu wyboru pliku bez HEIC
  → iOS sam konwertuje zdjęcie do JPEG przy wysyłce. Sprawdzić na prawdziwym iPhonie.
- Decyzja właściciela tylko, jeśli potrzebna biblioteka LGPL (dynamiczne linkowanie jest dopuszczalne,
  ale wymaga wpisu w `docs/licenses.md`).

### A3. 🟢 Układ sali i numery miejsc — znane ograniczenie nr 29
- Model: pozycja stołu na planie sali (`x`, `y`, obrót), opcjonalnie parkiet/scena jako elementy;
  `seat_number` już istnieje w przypisaniach.
- Automat: numery miejsc przy stole (pary obok siebie, dzieci przy rodzicach) — rozszerzenie
  `seating/engine.py`; reguła „blisko parkietu/stołu pary” wg odległości z planu sali.
- GUI: plan sali SVG z przeciąganiem stołów (dostępna alternatywa: lista z polami pozycji i przyciskami
  „w lewo/prawo”), widok stołu z miejscami; wydruk planu sali dla sali i winietki z numerem miejsca.
- Testy: silnik (jednostkowe), API, E2E na 390 i 1280 (axe, bez poziomego przewijania).

### A4. 🟢 E-maile HTML — znane ograniczenie nr 6
- `app/core/email.py`: wiadomości `multipart/alternative` (tekst + HTML), proste szablony bez zewnętrznych
  obrazów i czcionek, kolory z tokenów, link „Zmień powiadomienia”.
- Szablony: weryfikacja e-mail, reset hasła, zaproszenie do wesela, podsumowanie dnia, link RSVP do gości, MFA.
- Testy: obie części w wiadomości, poprawne linki, brak danych wrażliwych; podgląd w Mailpit.

### A5. ✅ Porządki w bazie dev i testach (noc 20/21.10)
- Wesela „Obciążenie N” usunięte (kopia przed usunięciem w `backups/`), test obciążenia sprząta po sobie,
  E2E ma osobną bazę `wedding_e2e`. Zostało 50 kont `loadtest-*` bez wesel — patrz „Następne kroki”.

### A6. 🔴→🟢 Dopłata przy „Wybieram tę ofertę”
- Decyzja właściciela (CLAUDE.md, krok 0): czy dopłatę liczyć jak w „co jeśli” (suma − kwoty stałe).
  Po decyzji: zmiana w `offers/service.select_offer` (użyć `payment_plan`), test, opis w raporcie.

### A7. 🟢 Przegląd przed wdrożeniem
- `/security-review` całości zmian v1.1, audyt zależności (`uv`, `npm audit`, `check-licenses`),
  pełne E2E produkcyjne, test obciążenia (z A5), próba odtworzenia kopii (`backup_db drill`),
  pomiar budżetu startu (≤ 170 KB), przegląd dostępności na prawdziwych telefonach (TalkBack/VoiceOver).

---

## Etap B — przygotowanie startu komercyjnego (decyzje właściciela) 🔴

| Decyzja | Co przygotować technicznie, gdy zapadnie |
|---|---|
| Hosting (`docs/hosting.md`), czy AI na start | wdrożenie wg `docs/wdrozenie.md`, HTTPS (pełna PWA, ciasteczka `Secure`), monitoring, kopie na Synology |
| Prawnik: regulamin, polityka, rola RODO (nr 37, 41), DPA, DPIA, rejestr czynności | wersje dokumentów w `LegalPages.tsx` (dziś `2026-10-draft`), zgody w rejestracji, ewentualne zmiany w e-mailach do gości i linku dla sali |
| Płatności Premium: ceny (propozycja 299 zł jednorazowo), bramka (Przelewy24/Tpay, BLIK), dane firmy, faktury | moduł `billing`: plan wesela, płatność jednorazowa, webhook, blokada funkcji Premium zamiast samego znaczka, prawo odstąpienia (treści cyfrowe) |
| SMS do gości (płatna usługa) | pakiety SMS, dostawca, umowa powierzenia |
| Testy z parami (5–8 wywiadów, prawdziwe oferty i telefony) | poprawki UX z wywiadów, ewaluacja AI na prawdziwych ofertach (znane ograniczenie nr 22) |

---

## Etap C — v1.2 (rozwój produktu, po starcie lub równolegle z etapem B)
1. 🟡 AI: odczyt harmonogramu rat z umowy (odłożone M4) — gdy AI będzie włączone; ewaluacja na prawdziwych umowach.
2. ✅ Kolejka przesunięć programu bez sieci (znane ograniczenie nr 43) — zapis lokalny i wysłanie po powrocie sieci, z rozwiązywaniem konfliktów (raport `docs/gui/raport-kolejka-offline.md`).
3. ✅ Kreator pierwszego uruchomienia (data, ceremonia, budżet, liczba gości → podział budżetu i plan w 2 minuty) — raport `docs/gui/raport-kreator.md`.
4. 🟢 Powiadomienia push (PWA) zamiast samych e-maili: płatności i terminy; wymaga HTTPS (etap B).
5. 🟡 Tablica inspiracji (B2) — niski priorytet (zdjęcia: magazyn, skanowanie, prawa do obrazów).
   ✅ Kolor przewodni (B2): akcent ze strony dla gości także na winietkach i kartach QR (w druku wersja jasna).
   ✅ Wygląd odliczania (B3): dni / tygodnie / pełne miesiące kalendarzowe, wybór zapamiętany na urządzeniu.
   ✅ Strona gościa po angielsku (C2 z analizy 03) — raport `docs/gui/raport-strona-gosci-en.md`.
6. 🔴 Konto dla wedding plannerek (L3, B2B), galeria zdjęć od gości (L4), prawnik-partner (L5).

## Etap D — v2
Katalog firm (tylko dane od firm), oferty B2B, analiza ryzyk umów (po opinii prawnej), płatności Premium
w pełni (jeśli nie w etapie B).

---

## Weryfikacja pracy nocnej 20/21.10 (2026-10-21, rano)
Sprawdzone niezależnie: drzewo czyste (33 commity od `4b122d0`), migracje jedna gałąź `c8e1a4d2f913`;
backend 776 ✔ / 6 pominiętych; vitest 100 ✔; licencje ✔; E2E (środowisko `wedding_e2e`) 265 ✔,
1 niestabilny (niżej). Wesele właściciela nietknięte (ostatnia zmiana 19.10); wesela
„Obciążenie N” usunięte, kopia `backups/wedding-20261020-223443.dump` jest. W programie: kreator (4 kroki),
eksport gości do CSV (uwagi dietetyczne tylko na życzenie, audyt), „Zobacz jak gość”, nowa nawigacja.
A5 ✅ (poza resztką niżej). A7 ✅ łącznie z testem obciążenia.

## Następne kroki (stan 2026-10-21)

### Od razu, bez decyzji (małe) 🟢
1. ✅ **Nawigacja:** na `/w/:id/podglad-goscia` podświetla się „Dziś” — dodać `podglad-goscia` do `also`
   zakładki Goście w `WeddingShell.tsx` (+ przypadek w `improvements.test.ts`).
2. ✅ (`expect.poll`, 40/40 na 8 profilach × 5) **Niestabilny E2E** „ograniczenie ruchu z systemu wyłącza przesunięcia i skalę” (`e2e/app.spec.ts:125`,
   768-dark, 1 na pełny przebieg; osobno 10/10): zmienne CSS czytane, zanim arkusz się załadował
   (puste wartości). Czekać na `expect.poll` aż zmienna będzie niepusta, potem porównać.
3. ✅ (`HydrateFallback` = szkielet; ostrzeżenie zniknęło; pierwszy render `/logowanie` w buildzie produkcyjnym: mediana ok. 80 ms, maks. ok. 220 ms na 20 wczytaniach — przyczyna dawnej niestabilności nie leży w czasie renderu, obserwować na stagingu) **Niestabilne pierwsze wczytanie `/logowanie` w E2E produkcyjnym** (z raportu nocy): sprawdzić
   ostrzeżenie „No `HydrateFallback` element” — dodać `HydrateFallback`/szkielet dla leniwych tras
   i zmierzyć czas pierwszego renderu w buildzie produkcyjnym.
4. ✅ (2026-10-21 wieczorem: `test_real_clamd_detects_eicar` zaliczony z `clamav/clamav:1.4`, kontener potem zatrzymany) **ClamAV z prawdziwym clamd:** test EICAR jest pomijany bez `WP_TEST_CLAMAV_HOST` — raz uruchomić
   `docker compose --profile scan up -d` (ok. 1,5 GB RAM) i test, wynik w raporcie.
5. ✅ (za potwierdzeniem właściciela, po kopii `backups/wedding-20261021-213315-przed-loadtest.dump`: 50 kont zgłoszonych do usunięcia przez API i zanonimizowanych — `scripts/cleanup_loadtest.py --accounts`; inne konta oczekujące na usunięcie nietknięte) **Resztka po teście obciążenia:** 50 kont `loadtest-*` bez wesel w bazie dev — usunąć po potwierdzeniu
   właściciela (kopia jest).

### Decyzje właściciela (blokują dalszy rozwój) 🔴
- **A6** dopłata przy „Wybieram tę ofertę” (rekomendacja: jak w „co jeśli”).
- **A2** test na iPhonie: czy zdjęcie z galerii trafia jako JPG.
- **Hosting** (najważniejsze): odblokowuje HTTPS → pełną PWA, powiadomienia push (C4), testy na telefonach,
  pierwsze wdrożenie staging wg `docs/wdrozenie.md`, kopie na Synology.
- **Prawnik:** regulamin, polityka (dziś `2026-10-draft`), RODO dla danych gości i e-maili (nr 37, 41), DPA, DPIA.
- **Premium:** ceny i bramka → moduł `billing` (blokada funkcji zamiast znaczka).
- **AI na start** → C1 odczyt rat z umowy.

### Po decyzji o hostingu (kolejność)
1. Staging z HTTPS i prawdziwą domeną → E2E produkcyjne na stagingu (sprawdzi też punkt 3).
2. Testy z 5–8 parami na prawdziwych telefonach i ofertach → poprawki UX.
3. C4 powiadomienia push (płatności, terminy, zmiany w programie dnia).
4. Monitoring, kopie na Synology (próba odtworzenia), rotacja klucza w praktyce.

Po każdym punkcie: raport w `docs/gui/`, aktualizacja `CLAUDE.md` („Stan”, „Następne kroki”)
i `docs/znane-ograniczenia.md`, osobny commit.
