# Nasz dzień — planer wesela

Polska aplikacja dla par młodych: oferty i umowy usługodawców z realnym kosztem, budżet i płatności (plan wydatków,
sponsorzy), goście z RSVP i stroną dla gości (menu, stół, lista prezentów, życzenia), plan stołów, harmonogram dnia ślubu
z linkami dla usługodawców, plan zadań z pomocnikami bez konta. Zakres i decyzje: [docs/README.md](docs/README.md).

- **Backend:** Python 3.12, FastAPI, PostgreSQL (`app/`).
- **Frontend:** React 19 + TypeScript, PWA (`frontend/`).
- **AI:** lokalny model przez Ollama, opcjonalnie; wynik zawsze do zatwierdzenia przez człowieka.

Stan prac i raporty: [CLAUDE.md](CLAUDE.md), [docs/gui/](docs/gui/). Wdrożenie: [docs/wdrozenie.md](docs/wdrozenie.md).

**Licencja:** oprogramowanie własnościowe — wszelkie prawa zastrzeżone ([LICENSE](LICENSE)). Kod jest widoczny publicznie,
ale nie wolno go kopiować ani używać bez pisemnej zgody autora.

## Wymagania

| Narzędzie | Wersja | Instalacja (Windows) |
|---|---|---|
| Docker Desktop | 29+ (Compose v2) | https://www.docker.com/products/docker-desktop |
| uv | 0.13+ | `winget install astral-sh.uv` |
| Task | 3.x | `winget install Task.Task` |
| Gitleaks | 8.x | `winget install Gitleaks.Gitleaks` |
| Ollama (AI, opcjonalnie) | 0.40+ | `winget install Ollama.Ollama --scope user`, potem `ollama pull qwen2.5:7b-instruct` |

Bez Ollamy aplikacja działa w pełni poza analizą AI (wtedy błąd jest czytelny, a oferty wpisuje się ręcznie).

Python 3.12 instaluje `uv` automatycznie (`.python-version`).

## Pierwsze uruchomienie

```bash
task setup
```

```bash
task up
```

`task setup` tworzy lub uzupełnia `.env` (losowe `WP_JWT_SECRET` i `WP_DATA_ENCRYPTION_KEY`), instaluje zależności i hook pre-commit.

> **Klucz `WP_DATA_ENCRYPTION_KEY`** szyfruje uwagi dietetyczne gości. Zapisz go w menedżerze haseł. Bez niego tych danych nie da się odczytać, także z kopii zapasowej, bo klucz celowo nie trafia do kopii bazy. `task up` buduje obraz i uruchamia: PostgreSQL, migracje, API, worker i Mailpit.

| Adres | Co to jest |
|---|---|
| http://localhost:8010/api/v1/docs | Swagger UI (dokumentacja i testowanie API) |
| http://localhost:8010/health/ready | gotowość (baza + migracje) |
| http://localhost:8025 | Mailpit: podgląd wysłanych e-maili (nic nie wychodzi do internetu) |
| localhost:5433 | PostgreSQL (tylko 127.0.0.1) |

Porty 8010 i 5433 zamiast domyślnych 8000/5432, bo te są zajęte przez inny projekt na tym laptopie. Zmienisz je w `.env` (`API_PORT`, `POSTGRES_PORT`).

Dane demo (fikcyjne): `task seed` tworzy konto `demo@example.com` (hasło w `scripts/seed.py`).

**Aplikacja webowa (GUI):** `task web:install`, potem `task web:dev` → http://localhost:5173. Szczegóły: [frontend/README.md](frontend/README.md).

## Codzienna praca

| Polecenie | Działanie |
|---|---|
| `task up` / `task down` | start / stop (dane zostają) |
| `task logs` | logi api i workera (JSON) |
| `task db:up` | tylko baza i Mailpit (do testów) |
| `task test` | testy z pokryciem (próg 85%); testy OCR są pomijane, bo na laptopie nie ma Tesseracta |
| `task test:docker` | **pełne testy w kontenerze** z tymi samymi bibliotekami co produkcja (w tym OCR) |
| `task lint` | Ruff + mypy (strict) |
| `task fmt` | automatyczne formatowanie |
| `task security` | Bandit, pip-audit, Gitleaks |
| `task licenses` | raport licencji + blokada AGPL/SSPL |
| `task image:scan` | Trivy na obrazie Dockera |
| `task migration -- "opis"` | nowa migracja Alembic (autogenerate) |
| `task migrate` | migracje z hosta |
| `task reset-db` | **usuwa lokalne dane** i stawia bazę od nowa |
| `task openapi` | eksport specyfikacji do `docs/openapi.json` |
| `task smoke` | test end-to-end na działającym środowisku (po `task up` i `task seed`) |
| `task backup` | kopia bazy (+ próbne odtworzenie) i plików dokumentów, opcjonalnie na Synology (`BACKUP_TARGET` w `.env`) |
| `task ci` | lint + testy (w tym kontraktowe Schemathesis) + bezpieczeństwo + licencje |
| `task test:llm` | regresja jakości AI na prawdziwym modelu (wymaga uruchomionej Ollamy; ok. 15 min) |
| `task ai:eval -- model1 model2` | porównanie modeli na korpusie ofert → `docs/ai-ewaluacja.md` |
| `task load` | test obciążeniowy Locust (50 par, 2 min; więcej: `task load USERS=100`) |
| `uv run python -m scripts.backup_db drill` | próba odtworzenia od zera (kopia → pusta baza + pliki → porównanie) |
| `task rotate-key -- rotate --dry-run` | rotacja klucza szyfrowania (procedura w `docs/wdrozenie.md`) |

## Struktura

```
app/
  core/       konfiguracja, baza, błędy (RFC 9457), logi, bezpieczeństwo, limity, e-mail
  jobs/       kolejka zadań w PostgreSQL + worker (ADR-0003)
  modules/
    identity/       rejestracja, logowanie, sesje, hasła, zgody, eksport, usunięcie konta
    workspace/      wesela, wydarzenia, członkowie, zaproszenia, uprawnienia
    planner/        szablon zadań, zadania, zależności, zmiana daty z podglądem
    budget/         kategorie, pozycje, płatności (zadatek/zaliczka), podsumowanie
    guests/         gospodarstwa, goście, RSVP przez link, import CSV, retencja
    notifications/  zbiorcze przypomnienia e-mail
    vendors/        moi usługodawcy, normalizacja, wykrywanie duplikatów
    documents/      upload, wersje, ekstrakcja tekstu (pypdf, python-docx, Tesseract OCR)
    offers/         oferty, warunki, cytaty, silnik wyceny (pricing.py), porównanie, wybór
    ai/             dostawcy LLM (Ollama), prompty, OfferExtractor + walidacja, redakcja PII
    schedule/       harmonogram dnia ślubu: zależności, konflikty, przesunięcia, szablon
    seating/        plan stołów: reguły, kontrola, automat (OR-Tools CP-SAT)
    overview/       pulpit i eksport wesela
    audit/          dziennik zmian (append-only) i zdarzenia bezpieczeństwa
migrations/   Alembic
deploy/       produkcja/staging: compose.prod.yaml, Caddyfile, .env.prod.example
loadtest/     test obciążeniowy (Locust)
scripts/      setup_env, seed, smoke_e2e, backup_db, export_openapi, eval_llm, rotate_encryption_key
tests/        unit/ + api/ (w tym IDOR dla każdej trasy wesela) + contract/ (Schemathesis)
              fixtures/offer_corpus.py: 20 syntetycznych ofert (PDF, DOCX, skany)
docs/         analiza, architektura, ADR, model danych, API, raporty
```

## Aktualizacja zależności

```bash
uv lock --upgrade
```

Potem `task ci`. Raz w tygodniu `uv run pip-audit` (w ramach `task security`).

## Usunięcie środowiska

`docker compose down -v` usuwa kontenery i dane. Narzędzia: `winget uninstall astral-sh.uv Task.Task Gitleaks.Gitleaks`.

## Frontend (GUI)

API dev działa w Dockerze (`task up`, port 8010). Interfejs:

```bash
npm --prefix frontend install
```

```bash
npm --prefix frontend run dev
```

Potem w przeglądarce: http://localhost:5173 (konto demo z `scripts/seed.py` po `task seed`).
