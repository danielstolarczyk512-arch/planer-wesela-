# Raport: Etap 2, fundament backendu

Data: 2026-10-19. Format raportu wg sekcji 17 założeń projektu.

## Wykonane działania

- Projekt Python 3.12 zarządzany przez `uv` (lockfile `uv.lock`), struktura modularnego monolitu (`app/core`, `app/jobs`, `app/modules/{identity,workspace,audit}`).
- Konfiguracja wyłącznie ze zmiennych środowiskowych (`WP_*`), `.env.example`, generator `.env` z losowym sekretem (`task setup`), blokady konfiguracji produkcyjnej (przykładowy sekret, włączona dokumentacja).
- Docker: wieloetapowy `Dockerfile` (bez `uv` i cache w obrazie, użytkownik nie-root, healthcheck), `compose.yaml` (db, migrate, api, worker, mailpit; porty tylko na 127.0.0.1).
- PostgreSQL 17 + Alembic: migracja początkowa (13 tabel), wyzwalacz blokujący `UPDATE/DELETE` dziennika audytu, osobna baza testowa.
- Logi JSON (structlog) z `request_id`; logowany szablon trasy zamiast ścieżki (tokeny z URL nie trafiają do logów); nagłówki bezpieczeństwa.
- Błędy RFC 9457 (`application/problem+json`) ze stabilnymi kodami; walidacja nie odsyła wartości pól (hasła).
- Uwierzytelnianie (ADR-0004): Argon2id, access JWT 15 min, rotowane refresh tokeny z wykrywaniem ponownego użycia, natychmiastowe wylogowanie (sesja sprawdzana przy każdym żądaniu), weryfikacja e-mail, reset i zmiana hasła, limity prób w PostgreSQL, ochrona przed enumeracją kont.
- Konto i RODO: zgody (historia, wycofanie), eksport danych (JSON), usunięcie konta z 30-dniową karencją i automatyczną anonimizacją przez worker.
- Workspace: wesela (ETag/If-Match, optymistyczne blokowanie), wydarzenia (ślub, przyjęcie, poprawiny), role `owner/coorganizer/viewer`, zaproszenia e-mail z tokenem (tylko na zweryfikowany adres zaproszonego), ochrona ostatniego właściciela.
- Kolejka zadań w PostgreSQL (ADR-0003) + worker: wysyłka e-maili, ponawianie z backoffem, status `dead`, czyszczenie payloadu z tokenami, okresowe utrzymanie (blokada advisory).
- Narzędzia jakości: Ruff, mypy `--strict`, pytest + coverage (próg 85%), Hypothesis, Bandit, pip-audit, pip-licenses (blokada AGPL/SSPL), Gitleaks (`.gitleaks.toml`), Trivy (z kontenera), pre-commit (hooki lokalne), Taskfile.

### Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Testy (`pytest`) | **104 passed**, 0 failed |
| Pokrycie | **92%** (próg 85%) |
| Ruff lint + format | czysto |
| mypy `--strict` (app) | 0 błędów |
| Bandit | 0 problemów (3 fałszywe alarmy B105 opisane `# nosec` z uzasadnieniem) |
| pip-audit | brak znanych podatności |
| Licencje | brak AGPL/SSPL; LGPL-3.0 (psycopg) dozwolone wg ADR-0006 jako zwykły import |
| Gitleaks | 0 trafień w plikach repozytorium (wykluczone `.venv` i lokalny `.env`) |
| Trivy (obraz) | 0 podatności HIGH/CRITICAL (Debian 12.15 + pakiety Pythona) |
| Uruchomienie end-to-end w Dockerze | `health/ready = ok`; rejestracja → e-mail przez worker do Mailpit → weryfikacja → logowanie → utworzenie wesela |
| Zgodność modeli z migracjami | test `compare_metadata` = brak różnic |
| Migracje w obie strony | `downgrade base` → `upgrade head` przy każdym uruchomieniu testów |

## Decyzje

| Decyzja | Uzasadnienie | Alternatywa |
|---|---|---|
| Synchroniczne SQLAlchemy + psycopg 3 | prostsze testy i transakcje; FastAPI uruchamia endpointy w puli wątków | async SQLAlchemy (dodamy, jeśli profilowanie pokaże potrzebę) |
| Sesja = rodzina refresh tokenów (urządzenie) | wylogowanie urządzenia i wykrywanie kradzieży tokena | pojedyncze tokeny bez rodzin |
| Sprawdzanie sesji w bazie przy każdym żądaniu | natychmiastowe wylogowanie; koszt jednego zapytania po PK | czysty JWT (bez możliwości unieważnienia przez 15 min) |
| Limity żądań w PostgreSQL | działają przy wielu instancjach bez Redis (ADR-0002) | Redis przy dużym ruchu |
| Brak członkostwa → 404 | nie ujawniamy istnienia wesela | 403 |
| `DELETE /weddings/{id}` trwałe i natychmiastowe | prostsza zgodność z RODO; audyt zostaje | miękkie usunięcie z retencją |
| Porty 5433/8010 | 5432 i 8000 zajmuje inny projekt na laptopie (`inna aplikacja`), którego nie ruszałem | zmiana w `.env` |

Wpływ na koszty: 0 zł (wyłącznie OSS, lokalnie). Bezpieczeństwo: patrz tabela wyników. Rozwój: moduły kolejnych etapów dodaje się według wzorca `models/schemas/service/router` + wpis w `app/models.py` + test IDOR (test pilnuje pokrycia każdej trasy `/weddings/{id}/…`).

## Problemy i ograniczenia

1. **Uprawnienia do `D:\aplikacjaweselna`**: Twoje konto nie ma prawa zapisu (grupa Administratorzy działa przez UAC tylko jako „deny only”). Cała praca powstała w katalogu roboczym (scratchpad) i zostanie przeniesiona do projektu po nadaniu uprawnień.
2. Brak repozytorium git (bez zapisu w katalogu projektu nie da się zrobić `git init`). Gitleaks w pre-commit zacznie działać po `git init` + `task setup`.
3. Znane ograniczenia techniczne: [znane-ograniczenia.md](znane-ograniczenia.md).

## Następny krok: Etap 3 (planer, budżet, goście)

Warunki rozpoczęcia: projekt przeniesiony do `D:\aplikacjaweselna`, `git init` i pierwszy commit, akceptacja tego raportu.

Zakres: zadania z szablonu i `reschedule` z `dry_run`, budżet (kategorie, pozycje, płatności zadatek/zaliczka), przegląd budżetu, gospodarstwa i goście, RSVP przez link, import CSV, przypomnienia e-mail, `Idempotency-Key`, eksport wesela, Schemathesis.

Kryteria akceptacji: jak w `plan-koszty-ryzyka.md` (Etap 3) + wszystkie kontrole z tabeli wyników na zielono.
