# Raport: otwarte punkty techniczne z audytu 23.10.2026

Pięć punktów z sekcji „Otwarte technicznie” raportu `raport-audyt-2026-10-23.md`, zrobionych
na prośbę właściciela 23.10.2026. Nie wymagały decyzji biznesowych. Ostatnia migracja: `b7e2f4a9c1d3`.

## 1. Rewizja programu przy przesunięciu (4.3)

**Problem:** podgląd „Przesuń ten i wszystkie późniejsze” liczył zmiany na stanie z chwili podglądu,
a zatwierdzenie liczyło je od nowa na stanie bieżącym. Gdy ktoś inny w międzyczasie zmienił program
(drugi telefon w dniu ślubu), zapisywało się coś innego niż to, co para widziała w podglądzie.

**Co jest teraz:**
- `POST /schedule/shift` zwraca `revision`, czyli skrót stanu programu (identyfikatory i wersje punktów).
  Zmienia się przy każdej edycji, dodaniu i usunięciu punktu.
- Zatwierdzenie z `revision` z podglądu przy zmienionym programie kończy się `409 conflict.version_mismatch`.
  Program zostaje bez zmian. GUI wczytuje aktualny program i prosi o ponowny podgląd
  (ten sam komunikat co przy innych konfliktach wersji).
- Kolejka przesunięć bez sieci (C2) przed wysłaniem pobiera rewizję, potem sprawdza godzinę punktu.
  Zmiana programu między sprawdzeniem a wysłaniem daje 409. Kolejka wtedy sprawdza ponownie
  (maks. 3 próby). „Wyślij mimo to” celowo wysyła bez rewizji.
- `revision` jest opcjonalne: starsze klienty działają jak dotąd.

- Przy okazji: sekcja „Przesuń…” w oknie punktu jest teraz poza formularzem. Formularz ma klucz z wersją,
  więc dotąd po odświeżeniu punktu montował się od nowa i komunikat o konflikcie znikał.

Testy: `test_shift_with_stale_preview_is_rejected`; E2E „Harmonogram dnia…” (zmiana punktu przez API
między podglądem a zatwierdzeniem → komunikat, program bez zmian).

## 2. Założenia waloryzacji zapisane na weselu (4.4)

**Problem:** stopy inflacji wybrane w Budżecie żyły tylko w pamięci karty. Ekran Dziś i inne
urządzenia liczyły zawsze 5% i 10%.

**Co jest teraz:**
- Tabela `budget_assumptions` (jeden wiersz na wesele; brak wiersza oznacza wartości domyślne 5% i 10%).
- `PUT /budget/indexation/assumptions` zapisuje założenia. Wymaga uprawnienia do edycji, zapis trafia do audytu.
- `GET /budget/indexation` bez parametrów liczy według zapisanych założeń. Parametry `expected_rate`
  i `worst_rate` nadal pozwalają podejrzeć inny wariant bez zapisu. Odpowiedź ma pole `assumptions`.
- GUI: wybór w karcie „Podwyżki cen w umowach” zapisuje się od razu („Zapisano założenia — tak liczą
  Budżet i Dziś”). Osoba z podglądem widzi założenia jako tekst. Ekran Dziś pokazuje stopę z zapisu.
  Wspólny hook `useIndexation` jest w `indexationRates.ts`, więc ekran Dziś nie dociąga karty z Budżetu.

Testy: `test_assumptions_saved_on_wedding` (zapis, podgląd bez zapisu, walidacja, 403 dla podglądu),
wpis w `test_idor.py`, vitest `rateOptions`; E2E „Budżet: podwyżka ceny…” (wybór 15% w Budżecie → link
na ekranie Dziś pokazuje 15%).

## 3. Osobny worker e-maili

**Problem:** jeden worker brał zadania po kolei. OCR lub analiza AI (do 10 min) wstrzymywały reset hasła,
weryfikację adresu i linki RSVP.

**Co jest teraz:**
- `WP_WORKER_LANE`: `all` (domyślnie; wszystkie zadania i utrzymanie) albo `fast`
  (tylko `send_email`, bez utrzymania). `claim_next(db, types)` zawęża kolejkę do typów toru.
- `deploy/compose.prod.yaml`: nowa usługa `worker-fast`, bez plików i bez dostępu do ClamAV.
  Dziedziczą ją `compose.test.yaml` (środowisko dla znajomych) i `compose.oracle.yaml`.
  `scripts/udostepnij-test.ps1` przy zmianie adresu odtwarza też `worker-fast`.
- W dev zostaje jeden worker.

Test: `test_fast_lane_takes_only_emails`.

## 4. Kontrole konfiguracji produkcyjnej (`_prod_guards`)

`WP_ENV=prod` nie wystartuje, gdy:
- `WP_PUBLIC_APP_URL` nie zaczyna się od `https://` (linki z tokenami w e-mailach i kodach QR,
  ciasteczko `Secure`);
- `WP_SMTP_HOST` nie jest jawnie ustawiony;
- zdalny serwer SMTP jest bez `WP_SMTP_STARTTLS=true`. Bez szyfrowania dozwolone są tylko `localhost`,
  `127.0.0.1`, `::1` i `mailpit`, czyli połączenia, które nie opuszczają maszyny ani sieci Dockera;
- `WP_AI_ENABLED` nie jest ustawione jawnie. Decyzja o AI ma być świadoma (hosting, DPA);
- AI jest włączone z dublerem testowym (`fake`, `fake_external`).

Sprawdzone, że istniejące środowiska przechodzą: `.env.test` (tunel https, Mailpit), lokalny staging
`.env.prod` (`https://localhost:9443`, SMTP `localhost`; plik nietknięty), Oracle (`instaluj.sh`:
https, Mailpit, `WP_AI_ENABLED=false`). Wzór `.env.prod.example` ma puste `WP_SMTP_HOST`, więc
start bez uzupełnienia go zatrzyma się z jasnym komunikatem.

Test: `test_production_guards_url_mail_ai` (5 przypadków; poprawna konfiguracja i Mailpit przechodzą).

## 5. CI na GitHub Actions

`.github/workflows/ci.yml` uruchamia się przy pushu do `main`, przy każdym PR i ręcznie. Ma trzy zadania:
- **backend**: PostgreSQL 17 (usługa), Tesseract (testy OCR jak w Dockerze), `ruff check`,
  `ruff format --check`, `mypy app`, bandit, blokada licencji AGPL/SSPL, `pytest`, zgodność
  `docs/openapi.json` z kodem, `pip-audit`;
- **frontend**: `npm ci`, zgodność `schema.d.ts` ze specyfikacją, `tsc`, eslint, vitest, licencje,
  build, budżet startu (≤ 170 KB), `npm audit` (zależności produkcyjne, poziom high);
- **sekrety**: gitleaks na całej historii.

Repozytorium jest publiczne, więc GitHub Actions jest bezpłatne. Workflow zawiera tylko testowe
hasło bazy CI i nie zawiera żadnych sekretów.

E2E (Playwright, 8 profili) zostaje lokalne, bo wymaga pełnego środowiska Docker z danymi demo.

**Do zrobienia przez właściciela:** żeby CI było *obowiązkową* bramką, trzeba w GitHubie dodać regułę
dla `main` (Settings → Branches → Require status checks: `backend`, `frontend`, `sekrety`).
To ustawienie konta i nie da się go zapisać w repozytorium.
