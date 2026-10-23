# CLAUDE.md — przekazanie pracy dla kolejnej sesji

Ten plik Claude Code wczytuje automatycznie. Opisuje projekt, zasady właściciela, stan prac
i następne kroki. **Aktualizuj sekcję „Stan” i „Następne kroki” przy każdym większym commicie.**

## Projekt

**„Nasz dzień” (Wedding Planner AI)** — komercyjna polska aplikacja do planowania wesela:
oferty i umowy usługodawców, realny koszt, budżet i płatności, goście z RSVP, plan stołów,
harmonogram dnia. Repo `D:\aplikacjaweselna`, **publiczne** na GitHubie
`danielstolarczyk512-arch/planer-wesela-` (od 2026-10-23). Pracujemy na lokalnej gałęzi `publikacja` (śledzi `origin/main`);
lokalny `main` i tag `historia-lokalna-2026-10-23` to stara historia z danymi prywatnymi — **nie wysyłać**. W plikach
repo nie wpisywać danych osobowych właściciela ani gości. Właściciel pisze po polsku —
odpowiadaj, komentuj kod i pisz dokumentację **po polsku**.

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 17; modularny monolit
  `app/modules/*` (identity, workspace, planner, budget, guests, vendors, offers, documents, ai,
  schedule, seating, notifications, audit, overview). Błędy RFC 9457 ze stałymi kodami,
  `If-Match`/`version` (409/428), `Idempotency-Key`, identyfikatory UUIDv7, czas polski przez `clock.local()`.
- **Frontend:** `frontend/` — React 19, TypeScript 5.9, Vite, React Aria Components, React Router
  (lazy routes, View Transitions), TanStack Query, openapi-fetch + typy z OpenAPI. Bez zod
  i react-hook-form. Tokeny projektu: `design/tokens/*.json` → zmienne `--wp-*` (`task gui:tokens`; typografia `--wp-type-*`, kolory tekstu `--wp-text-*`). PWA (`public/sw.js`).
- **AI:** lokalny model przez Ollama (`qwen2.5:7b-instruct`), wynik zawsze jako szkic z cytatami do
  zatwierdzenia przez człowieka. Zewnętrzny dostawca — nie wdrożony (wymaga zgody i DPA).

## Zasady właściciela (wiążące)

- Aplikacja **komercyjna i w pełni legalna**: tylko darmowe narzędzia z licencją pozwalającą na
  użytek komercyjny — **bez AGPL/SSPL/GPL** (ADR-0006; ClamAV tylko jako osobny proces). RODO.
- **Nie zapisuj sekretów w repozytorium** (pre-commit z gitleaks; hasła testowe generuj w testach).
- **Nie usuwaj istniejących danych ani plików bez potwierdzenia.** W bazie dev jest prawdziwe
  wesele właściciela — **nie ruszać**. „Wesele demo”
  (demo@example.com / hasło w `scripts/seed.py`) zawiera fikcyjne dane; testy E2E zakładają
  własne, tymczasowe wesela przez API i usuwają je w `finally`.
- **Nie używaj płatnych usług bez wyraźnej zgody.** Bez scrapingu konkurencji, bez obchodzenia
  zabezpieczeń.
- **Nie twórz pozornej implementacji** — funkcja działa naprawdę albo jest jasno opisana jako brak.
- **Nie wysyłaj danych osobowych/umów/dokumentów do zewnętrznego modelu** bez podstawy prawnej.
- Pracuj samodzielnie (testy, Docker, commity); pytaj tylko o decyzje biznesowe i prawne.
- Commit: wiadomości po polsku, na końcu `Co-Authored-By: Claude …`.

## Środowisko (Windows) — pułapki

- **Porty:** API dev `127.0.0.1:8010` (Docker), Postgres `5433`, Mailpit `8025`, Vite `5173`
  (proxy `/api` → 8010), podgląd buildu `4173`; środowisko E2E: API `8011`, Vite `5174`, podgląd `4174`. **Port 8000 i 5432 to inna aplikacja
  właściciela — nie ruszać.**
- Docker Desktop bywa wyłączony po restarcie: uruchom `Docker Desktop.exe`, potem
  `docker compose up -d` (migracje robi kontener `migrate`). Po zmianie zależności Pythona:
  `docker compose build api worker migrate && docker compose up -d`.
- Baza w kontenerze: `docker exec wedding-planner-db-1 psql -U wedding -d wedding`.
  **E2E działa w osobnym środowisku** (od 2026-10-21): `docker compose --profile e2e up -d` →
  baza `wedding_e2e` (dane demo wgrywa `migrate-e2e`), API `127.0.0.1:8011`, Vite testów na 5174/4174.
  Baza dev (prawdziwe wesele właściciela na koncie demo!) nie jest używana przez testy.
  Przed pełnym E2E: `docker exec wedding-planner-db-1 psql -U wedding -d wedding_e2e -c "delete from rate_limit_hits"`.
  Po zmianach backendu przebuduj też obraz testowy: `docker compose --profile e2e build migrate-e2e`.
- **Commit:** hook gitleaks wymaga `gitleaks.exe` z WinGet w PATH — w PowerShellu:
  `$g = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter gitleaks.exe | Select -First 1; $env:PATH = "$($g.DirectoryName);$env:PATH"; git commit …`
- Coś normalizuje pliki po zapisie: **znikają ukośniki w wyrażeniach regularnych w szablonach
  `` ` ` `` i escape `\uFEFF`** — zamiast tego `String.fromCharCode(0xfeff)` i wyszukiwanie
  bez regexów. Narzędzie Write zamienia `\u00a0` na znak — używaj `\s` w testach.
- Bash w tym środowisku to Git Bash; heredoki działają, ale do edycji plików wygodniej Python.

## Weryfikacja

- Backend: `uv run ruff check app tests scripts`, `uv run mypy app`, `uv run pytest -q`
  (ostatnio **1133 passed**, 6 skipped — OCR i Ollama tylko w Dockerze/na żądanie).
- Typy API po zmianach backendu: `task web:types` (docs/openapi.json → frontend/src/api/schema.d.ts).
- Frontend (w `frontend/`): `npx tsc -b --noEmit`, `npx eslint src e2e`, `npx vitest run`
  (ostatnio 139 testów), `npx playwright test` (8 profili: 320/390/768/1280 × jasny/ciemny; axe),
  `E2E_PROD=1 npx playwright test` (build produkcyjny z CSP), `node scripts/check-budget.mjs`
  (start ≤ 170 KB gzip, ostatnio ~142 KB), `node scripts/check-licenses.mjs`.

## Stan (2026-10-21)

Backend: etapy 0–6 zrobione. GUI: kroki 1–6 i „lista A” zrobione — raporty w `docs/gui/`
(`raport-krok-*.md`, `raport-ustawienia-edycja.md`, `raport-mfa.md`). Ekrany: logowanie/rejestracja/reset,
Dziś, Plan (zależności), Budżet (płatności, kategorie, podział), Goście (import CSV, RSVP link),
`/rsvp/:token`, ustawienia wesela, harmonogram, plan stołów, usługodawcy/oferty/porównanie,
dokumenty + AI, ustawienia konta, MFA, PWA i tryb offline.

**Usprawnienia v1.1 — zrobione** (raport `docs/gui/raport-usprawnienia-v1-1.md`): szablon planu `2027.1`
(77 zadań, wskazówki, dokumenty jako podzadania), nadrabianie zaległości, uzupełnianie z szablonu,
zadanie ↔ usługodawca, kalendarz + ICS; 6 zakładek z podzakładkami; pytania do usługodawców, lista
kontrolna umowy, posiłki dla obsługi, szablony ofert, „co jeśli”; wydruki; dzień ślubu (rola
`coordinator`, plan B, tryb na żywo, link `/dzien/:token`); goście: strona dla gości, linki RSVP
e-mailem, prezenty i podziękowania, **osoba towarzysząca dopisywana przez gościa w RSVP (bez limitu;
bezpiecznik 20 na zaproszenie)**. Premium to tylko znaczek (`components/Premium.tsx`), bez płatności.

**Dokończenie v1.1 — zrobione** (plan `docs/plan-dokonczenie-v1-1.md`, raport
`docs/gui/raport-dokonczenie-v1-1.md`): naprawiony niestabilny E2E budżetu (długie kwoty w kafelkach);
statusy w `docs/analysis/04`; „co jeśli” — dwa scenariusze z ratami (`POST /offers/scenarios`,
`payment_plan`); link dla sali z liczbami dla kuchni (imiona i diety tylko za zgodą `share_catering`);
kod QR przy linku RSVP i karty `/druk/qr` (`POST /rsvp-qr`); motywy strony dla gości (3 motywy,
6 akcentów sprawdzonych pod kontrast); program dnia bez sieci (`lib/dayCopy.ts`, kopia w
`localStorage` bez gości i kwot; SW nadal nie buforuje `/api/*`).
**Plan dalszej pracy — etap A (2026-10-21):** A1 skanowanie plików (ClamAV jako osobny kontener,
`app/core/antivirus.py`, `scan_status` w wersjach dokumentów; dev: profil `scan`, prod: wymagane
`WP_CLAMAV_HOST`; raport `docs/gui/raport-skanowanie-plikow.md`); A4 e-maile HTML
(`app/core/mail_templates.py`, `multipart/alternative`; raport `docs/gui/raport-emaile-html.md`);
A3 układ sali i numery miejsc (`RoomLayout.tsx`, `seating_rooms`, `POST …/seat-numbers`, „blisko” w automacie;
raport `docs/gui/raport-uklad-sali.md`).
A2 HEIC: bez nowych zależności (`accept` z typami MIME, rozpoznanie HEIC na serwerze, komunikat) —
**do sprawdzenia przez właściciela na iPhonie** (raport `docs/gui/raport-heic.md`).
A7 przegląd przed wdrożeniem (raport `docs/gui/raport-przeglad-przed-wdrozeniem.md`): audyt zależności
(certifi zaktualizowane), licencje, bandit, próba odtworzenia kopii — OK. Niestabilny E2E do obserwacji:
w buildzie produkcyjnym czasem nie wczytuje się `/logowanie` przy pierwszym kroku (po powtórzeniu OK).
Dev: `WP_PUBLIC_APP_URL=http://localhost:5173` (wcześniej błędnie 8000).
**Noc 20/21.10 (praca samodzielna za zgodą właściciela):** A5 — usunięto 300 wesel „Obciążenie N”
(po kopii `backups/wedding-20261020-223443.dump`), locustfile sprząta po sobie, test obciążenia OK;
**osobne środowisko E2E** (profil `e2e`, baza `wedding_e2e`); C3 kreator nowego wesela; C2 kolejka
przesunięć programu bez sieci; cena dziecięca w budżecie (ogr. 13); wyszukiwanie w dokumentach (ogr. 21);
nastolatki przy stole dziecięcym (31); deterministyczny odczyt zadatku (32); polskie słowa w ocenie
hasła (1); „Zobacz jak gość” (podgląd strony RSVP); lista gości do Excela (CSV); strona gościa i e-mail RSVP po angielsku (język zaproszenia);
automat stołów w workerze (30). Raporty w `docs/gui/`, podsumowanie: `docs/gui/raport-noc-2026-10-21.md`.
Wieczór 21.10: punkty 1–5 z „Następnych kroków” w `docs/plan-dalszej-pracy.md` zrobione (nawigacja podglądu gościa,
stabilny E2E ruchu, `HydrateFallback`, EICAR z prawdziwym clamd, usunięte 50 kont `loadtest-*` po kopii).
Ostatnia weryfikacja: backend 1133, vitest 139, E2E dev 445 + 13 poprawionych zielonych, E2E produkcyjne 419 + 29 powtórzonych zielonych (22.10, po analizie 08). Test E2E z przekroczonym czasem zostawia tymczasowe wesele w `wedding_e2e` — sprzątać po nazwie.
Limit RSVP na IP w konfiguracji: `WP_RSVP_RATE_LIMIT` (domyślnie 60/10 min; E2E 2000).
**Noc 21/22.10:** 10 propozycji nowych funkcji (`docs/analysis/05-propozycje-nowych-funkcji.md`); zrobiona
propozycja 3 — **prognoza frekwencji i lista rezerwowa** (Goście → Frekwencja, `guests/forecast.py`,
`guests/reserve.py`, tabela `reserve_entries`; raport `docs/gui/raport-prognoza-frekwencji.md`).
Propozycja 9 — **informacje dla usługodawców i potwierdzanie wersji programu** (`schedule/briefs.py`,
tabela `vendor_briefs`, `POST /day/{token}/ack`, „Kto zna aktualny program” w harmonogramie; raport
`docs/gui/raport-pakiety-uslugodawcow.md`).
Propozycja 6 — **portfel sponsorów i rola `sponsor`** (Budżet → „Kto płaci”, `budget/funders.py`, tabele
`funders`, `funder_contributions`, `funder_id` w płatnościach/członkach/zaproszeniach; nowe akcje `BASIC`
i `FUNDER_SELF`; sponsor widzi tylko „Nasz wkład”; raport `docs/gui/raport-portfel-sponsorow.md`).
Propozycja 7 — **licznik ważności dokumentów do ślubu** (Plan → „Dokumenty do ślubu”, `planner/documents.py`
z zasadami i źródłami gov.pl, tabela `ceremony_documents`, sekcja w podsumowaniu e-mail; poprawka: digest
pomija rolę sponsor; raport `docs/gui/raport-dokumenty-do-slubu.md`; zasady do przeglądu przez prawnika).
Propozycja 1 — **strażnik waloryzacji cen** (pola klauzuli przy wydatku, karta „Podwyżki cen w umowach”
w budżecie: dziś / prognoza / najgorszy przypadek, `budget/indexation.py`, terminy aneksów w podsumowaniu;
raport `docs/gui/raport-waloryzacja.md`).
Propozycja 4 — **wręczanie zaproszeń osobiście** (Goście → „Zaproszenia”: objazdy po miejscowościach, plan,
„Wręczone”, tempo na weekend; `guests/delivery.py`; raport `docs/gui/raport-wreczanie-zaproszen.md`).
Propozycja 8 — **transport i noclegi gości** (moduł `logistics`: kursy z miejscami, kurs powrotny przed tortem,
pokoje, lista pokoi CSV, kursy na linku przewoźnika bez nazwisk; Goście → „Transport i noclegi”; raport
`docs/gui/raport-transport-noclegi.md`). Rejestr `app/models.py` uzupełniony o wszystkie tabele.
Propozycja 10 — **po weselu** (moduł `aftercare`: rozliczenie, zdjęcia/film z terminem i przypomnieniem do
skopiowania, zmiana nazwiska ze źródłami gov.pl, podziękowania, archiwum; Więcej → „Po weselu”; raport
`docs/gui/raport-po-weselu.md`). Z listy `docs/analysis/05` zostały 2 (AI — gdy AI włączone) i 5 (koperty — RODO).
Usprawnienia z analizy: **„Wymaga uwagi” na ekranie Dziś** (`overview/attention.py`) i **przypomnienia w kalendarzu
i ICS** (dokumenty, aneksy, oddanie zdjęć, objazdy — bez nazwisk; raport `docs/gui/raport-wymaga-uwagi-kalendarz.md`).
**Gość wybiera kurs autokaru w RSVP** (`show_to_guests`, tylko wolne miejsca, 409 przy pełnym kursie; raport
`docs/gui/raport-rsvp-kursy.md`). Kolejne usprawnienia: `docs/analysis/06-analiza-po-rozbudowie.md` — U1–U6 zrobione (frekwencja w e-mailu, kursy
na ekranie Dzień dla koordynatora, wydruk objazdu, sponsor zgłasza przelew, kurs i pokój przy gościu; raporty
`docs/gui/raport-usprawnienia-u1-u3.md`, `raport-usprawnienia-u4-u6.md`), U5 już było; U7–U10 (kto płaci przy
płatności, listy pasażerów do druku, podpowiedzi „po weselu”, filtry gości; `raport-usprawnienia-u7-u9.md`).
Podgląd GUI na danych E2E: `preview_start frontend-e2e` (port 5174, API 8011) — nie na bazie dev.
**„Co zabrać” na dzień ślubu** (Harmonogram dnia; koordynator odhacza; koperty bez kwot; raport
`docs/gui/raport-co-zabrac.md`). Eksport gości do Excela z wręczeniem, kursem i pokojem; e-mail dla sponsora;
rozkład przejazdów na stronie gościa; „Dziś Wasz dzień!” — lista w `docs/analysis/06` (druga runda).
**Analiza 07 (22.10, prośba właściciela: 10 kolejnych funkcji z inspiracji rynkiem) — zrobione:** pomocnik wyboru daty
(Ustawienia → „Porównajcie daty”, `workspace/dates.py`), tryb czytelny na stronie gościa, muzyka (Dzień → Muzyka, propozycje
gości w RSVP, lista na linku DJ-a), zdjęcia grupowe (Dzień → Zdjęcia grupowe, link fotografa), plan przygotowań (Dzień →
Przygotowania, link fryzjerki/makijażystki), menu z alergenami (Goście → Menu, moduł `menu`), „Gdzie siedzimy”, komunikat
dla gości i księga życzeń (Goście → „Komunikat, stół i życzenia”, `guests/page.py`), pomocnicy bez konta (Plan → Pomocnicy,
`/pomocnik/:token`, `planner/helpers.py`). Raport: `docs/gui/raport-dziesiec-funkcji-07.md`. Tekst pomocniczy poprawiony na
14 px (tokeny typografii `--wp-type-*`).
**Analiza 08 (22.10, spójność i 7 funkcji) — zrobione:** tekst pomocniczy 14 px (typografia `--wp-type-*`), Goście →
„Strona gościa” (wszystko o stronie gościa w jednym miejscu), Dzień → „Fryzura i makijaż”, „Cofnij” przy usuwaniu w krótkich
listach; wyszukiwarka (lupa w nagłówku, `/szukaj`, `overview/search.py`), plan wydatków i koszt gościa (`budget/insights.py`),
lista prezentów z rezerwacją gości (`guests/gifts.py`), wiadomości do usługodawców (`lib/vendorMessages.ts`), komentarze przy
zadaniach (`planner/comments.py`), podsumowanie dla rodziców (`/druk/podsumowanie`). Raport: `docs/gui/raport-spojnosc-i-funkcje-08.md`.
**Audyt zewnętrzny 23.10 — poprawki P0/P1 zrobione** (raport `docs/gui/raport-audyt-2026-10-23.md`): strona gościa
działa do 7 dni po weselu niezależnie od terminu RSVP; replay `Idempotency-Key` sprawdza sesję i rolę; cache React Query
czyszczony przy wylogowaniu/zmianie konta; redakcja tokenów w logach Caddy i bez access logu uvicorna; linki pomocnika
(30 dni) i usługodawcy (7 dni) wygasają po weselu; worker AI ponawia kontrolę uprawnień; heartbeat blokady zadań;
walidator AI (NaN, ilość bez dowodu). Z audytu czekają na decyzję: A6 (oferta → raty), koszt oferty przy zmianie gości, S4.
Ostatnia migracja: `a1d4c7e9b2f0`.
**Test dla znajomych (23.10):** projekt Dockera `naszdzien-test` (konfiguracja prod na laptopie, Caddy
`127.0.0.1:8090`, Mailpit `127.0.0.1:8026`, własna baza; `deploy/compose.test.yaml`, sekrety w `deploy/.env.test`),
udostępnianie szybkim tunelem Cloudflare: `scripts/udostepnij-test.ps1`, instrukcja `docs/test-dla-znajomych.md`.
`deploy/.env.prod` (lokalny staging z 19.10) zostaje nietknięty.

## Następne kroki (kolejność uzgodniona z właścicielem)

**Pełny plan: `docs/plan-dalszej-pracy.md`** — etap A zrobiony (A1–A5, A7); z etapu C zrobione C2, C3
i strona gościa po angielsku. Czeka na właściciela: A6, A2 (test na iPhonie), etap B.
**Podsumowanie rozbudowy 21/22.10 i lista decyzji: `docs/gui/raport-sesja-2026-10-22.md`.** Analiza 07 (10 funkcji): `docs/gui/raport-dziesiec-funkcji-07.md`. Analiza 08 (spójność, 7 funkcji): `docs/gui/raport-spojnosc-i-funkcje-08.md`. Runda 3 (U16 zaproszenia do drukarni, U17 prognoza poprawin, U18 koszt z podwyżkami na Dziś): `docs/gui/raport-runda-3.md`.

0. **Do decyzji właściciela (A6):** czy „Wybieram tę ofertę” ma tworzyć dopłatę
   wyliczoną jak w „co jeśli” (suma − kwoty stałe) zamiast kwoty „final” z oferty — zmieniłoby to
   nowe płatności (raport `docs/gui/raport-dokonczenie-v1-1.md`, punkt 1).
1. Bez decyzji właściciela można robić: kolejne propozycje z `docs/analysis/05` (z analizy 05 zostały 2 i 5 — czekają
   na decyzje; dalej: usprawnienia U1–U6 z `docs/analysis/06-analiza-po-rozbudowie.md`), etap C5 (tablica inspiracji; kolor przewodni i odliczanie zrobione), drobne ograniczenia
   z `docs/znane-ograniczenia.md`. AI: odczyt harmonogramu rat (odłożone — AI na start wyłączone,
   do zrobienia z ewaluacją na prawdziwych umowach). Push (C4) dopiero z HTTPS po wyborze hostingu.
2. **Decyzje właściciela przed startem komercyjnym** (nie rób ich sam): hosting (`docs/hosting.md`)
   i czy AI na start włączone; prawnik — regulamin i polityka (robocze w `LegalPages.tsx`, wersja
   `2026-10-draft`), rola RODO wobec danych gości i e-maili do gości (znane ograniczenia nr 37 —
   **na razie pomijamy**), diety dla sali za zgodą pary (nr 41), DPA, DPIA, rejestr czynności; dane firmy; ceny i bramka płatności Premium
   (**na razie pomijamy**); testy na prawdziwych ofertach i telefonach; kopia na Synology.
3. v2: katalog firm (tylko dane od firm), oferty B2B, analiza ryzyk umów (po opinii prawnej),
   płatności Premium.

## Uruchomienie na telefonie (podgląd w sieci lokalnej)

`cd frontend && npm run dev -- --host`, zezwolić w zaporze Windows (sieci prywatne), na telefonie
`http://<IP komputera>:5173`. Bez HTTPS ciasteczko sesji (Secure) nie działa — po przeładowaniu
trzeba się zalogować; pełna PWA dopiero pod HTTPS (po wyborze hostingu).
