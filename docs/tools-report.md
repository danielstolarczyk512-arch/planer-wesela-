# Raport narzędzi — Etap 0

Data audytu: 2026-10-19 · System: Windows 11 Pro · Katalog: `D:\aplikacjaweselna` (pusty, bez repozytorium git)

## 1. Stan środowiska przed audytem

| Narzędzie | Stan |
|---|---|
| Python | 3.10.6 (za stary — projekt wymaga 3.12) |
| Git | 2.54.0 |
| Docker / Compose | Docker 29.6.1, Compose v5.3.0 — **demon nie działał** (Docker Desktop wyłączony) |
| winget | dostępny (użyty jako oficjalne źródło pakietów) |
| Node, uv, Ruff, pre-commit, Gitleaks, Task, psql, Trivy, Tesseract, Ollama, gh | brak |
| Uprawnienia do `D:\aplikacjaweselna` | konto użytkownika ma tylko odczyt (zapis wyłącznie dla Administratorów) |

## 2. Zainstalowane narzędzia (zweryfikowane)

| Narzędzie | Wersja | Cel | Licencja | Koszt | Instalacja | Usunięcie |
|---|---|---|---|---|---|---|
| uv | 0.13.1 | menedżer Pythona i zależności (zastępuje pip/venv/Poetry, lockfile) | MIT / Apache-2.0 | 0 zł | `winget install astral-sh.uv` | `winget uninstall astral-sh.uv` |
| Python (przez uv) | 3.12.15 | runtime backendu | PSF | 0 zł | `uv python install 3.12` | `uv python uninstall 3.12` |
| Ruff | 0.17.1 | linter + formatter (zastępuje flake8/black/isort) | MIT | 0 zł | `uv tool install ruff` | `uv tool uninstall ruff` |
| pre-commit | 4.6.2 | uruchamia Ruff/Gitleaks przed każdym commitem | MIT | 0 zł | `uv tool install pre-commit` | `uv tool uninstall pre-commit` |
| Gitleaks | 8.30.1 | skanowanie sekretów w repo | MIT | 0 zł | `winget install Gitleaks.Gitleaks` | `winget uninstall Gitleaks.Gitleaks` |
| Task (go-task) | 3.54.0 | skrypty projektu (`task test`, `task lint`) — na Windows prostsze niż Make | MIT | 0 zł | `winget install Task.Task` | `winget uninstall Task.Task` |
| Node.js LTS | 24.20.0 (npm 11.19.0) | serwery MCP (Playwright), Mermaid CLI, później GUI (Expo/React Native) | MIT | 0 zł | `winget install OpenJS.NodeJS.LTS` | `winget uninstall OpenJS.NodeJS.LTS` |

Żadne z nich nie wymaga konta, klucza API ani nie wysyła kodu projektu na zewnątrz.

Uwaga: `uv python install` zgłosił błąd tworzenia aliasu katalogu „3.12” (link na Windows), ale interpreter działa (`uv run --python 3.12 python --version` → 3.12.15). Bez wpływu na projekt.

## 2a. Zależności projektu (Etap 2, przypięte w `uv.lock`)

| Pakiet | Wersja | Cel | Licencja |
|---|---|---|---|
| fastapi | 0.146.0 | API | MIT |
| uvicorn[standard] | 0.54.0 | serwer ASGI | BSD-3 |
| pydantic-settings | 2.16 | konfiguracja z env | MIT |
| sqlalchemy | 2.1.5 | ORM | MIT |
| psycopg[binary] | 3.3.6 | sterownik PostgreSQL | LGPL-3.0 (dozwolone wg ADR-0006: zwykły import, bez modyfikacji) |
| alembic | 1.20.0 | migracje | MIT |
| argon2-cffi | 25.1.0 | haszowanie haseł (Argon2id) | MIT |
| pyjwt | 2.15.1 | access tokeny | MIT |
| structlog | 26.1.0 | logi JSON | MIT / Apache-2.0 |
| email-validator | 2.3.0 | walidacja e-mail | Unlicense |
| tzdata | 2026.5 | strefy czasowe (Windows nie ma systemowej bazy) | Apache-2.0 |
| cryptography (Etap 3) | 50.0.2 | szyfrowanie kolumn AES-256-GCM (uwagi dietetyczne) | Apache-2.0 / BSD |
| python-multipart (Etap 4) | 0.0.32 | upload plików (multipart/form-data) | Apache-2.0 |
| pypdf (Etap 4) | 6.21.1 | tekst z PDF | BSD-3 |
| pypdfium2 (Etap 4) | 5.14.0 | render stron PDF do OCR (PDFium) | Apache-2.0 / BSD-3 (+ licencje komponentów PDFium: BSD, FreeType FTL, zlib) |
| python-docx (Etap 4) | 1.2.0 | tekst z DOCX | MIT |
| pytesseract (Etap 4) | 0.3.13 | wywołanie Tesseract OCR | Apache-2.0 |
| Pillow (Etap 4) | 13.0.0 | obrazy do OCR | MIT-CMU |
| dev: reportlab (Etap 4) | 5.0.1 | generowanie PDF korpusu testowego | BSD |
| system (obraz Docker): tesseract-ocr, tesseract-ocr-pol | Debian 12 | silnik OCR + język polski | Apache-2.0 |
| system (obraz Docker): fonts-dejavu-core | Debian 12 | czcionka do korpusu testowego | licencja Bitstream Vera/DejaVu (wolna) |
| PostgreSQL `pg_trgm` (Etap 4) | contrib PG 17 | podobieństwo nazw (duplikaty usługodawców) | PostgreSQL License |

| httpx (Etap 5: zależność główna) | 0.28.1 | klient HTTP do Ollama | BSD-3 |
| **Ollama** (Etap 5, host) | 0.40.5 | lokalny serwer modeli (GPU laptopa) | MIT; instalacja `winget install Ollama.Ollama --scope user` (bez administratora), usunięcie `winget uninstall Ollama.Ollama` |
| model `qwen2.5:7b-instruct` | Q4, 4,7 GB | odczyt ofert (domyślny) | Apache-2.0 |
| model `SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M` | 6,7 GB | polski model, porównanie | Apache-2.0 |

| **ClamAV** (v1.1, kontener `clamav/clamav:1.4`) | 1.4 | skan antywirusowy wgranych plików | **GPL-2.0 — wyłącznie osobny kontener** (ADR-0006): aplikacja rozmawia z `clamd` przez TCP (protokół INSTREAM, własny klient `app/core/antivirus.py`, biblioteka standardowa), nie linkuje ani nie dystrybuuje kodu ClamAV w swoim obrazie. Sygnatury (freshclam) — bezpłatne, pobierane z serwerów ClamAV |

Modele z licencjami restrykcyjnymi (np. Llama Community License, Gemma Terms) świadomie pominięte: dodatkowe ograniczenia użycia komercyjnego.

Odrzucone w Etapie 4: PyMuPDF (AGPL), OCRmyPDF (wymaga Ghostscript na AGPL), MinIO (AGPL), Tesseract na laptopie (instalator wymaga administratora; OCR działa w kontenerze).
| dev: pytest, pytest-cov, hypothesis, httpx | — | testy | MIT / MPL-2.0 (hypothesis) / BSD |
| dev: schemathesis (Etap 3) | 4.32.0 | testy kontraktowe OpenAPI (znalazły 4 klasy błędów 500) | MIT |
| dev: ruff, mypy, bandit, pip-audit, pip-licenses, pre-commit | — | jakość i bezpieczeństwo | MIT / Apache-2.0 |

Obrazy Dockera: `postgres:17-bookworm` (PostgreSQL License), `axllent/mailpit:v1.27` (MIT, tylko dev), `python:3.12-slim-bookworm` (PSF + Debian), `aquasec/trivy:0.69.1` (Apache-2.0, tylko skan). Pełny raport licencji: [licenses.md](licenses.md).

Locust (testy obciążeniowe): odłożony do Etapu 6.

## 3. Narzędzia celowo NIE instalowane globalnie

| Narzędzie | Decyzja | Uzasadnienie |
|---|---|---|
| pytest, pytest-cov, Hypothesis, mypy/Pyright, Bandit, pip-audit, Schemathesis, Alembic | zależności dev projektu (`uv add --dev`) w Etapie 2 | wersje przypięte w `uv.lock`, odtwarzalne na każdej maszynie |
| PostgreSQL / psql | w Dockerze (`postgres:17`) | brak instalacji w systemie, łatwy reset |
| Trivy | przez obraz `aquasec/trivy` | bez kolejnego binarium; uruchamiany ad hoc |
| Tesseract / OCRmyPDF / LibreOffice | Etap 4, w kontenerze | niepotrzebne do fundamentu backendu |
| Ollama | Etap 5 | najpierw ustalimy, które funkcje w ogóle potrzebują LLM |
| Redis, Meilisearch, pgvector | odrzucone na MVP | PostgreSQL FTS + kolejka w tabeli wystarczą na start |
| GitHub CLI (gh) | odłożone | brak repozytorium zdalnego |
| Make | odrzucone | na Windows wymaga dodatkowych warstw; Task robi to samo |

## 4. Pluginy i serwery MCP dla Claude Code

Już włączony: **engineering** (ADR, system-design, testing-strategy, code-review, documentation, deploy-checklist) — wystarcza na Etapy 1–2.
Wbudowane: `security-review`, `code-review`, `simplify`, `init` (CLAUDE.md), wbudowana przeglądarka (Swagger UI, research rynku).

| Plugin | Wydawca | Do czego | Kiedy | Ryzyko | Rekomendacja |
|---|---|---|---|---|---|
| code-simplifier | Anthropic | agent upraszczający kod | od Etapu 2 | niskie, lokalny | **włączyć teraz** |
| frontend-design | Anthropic | jakość i estetyka UI („żeby była ładna”) | etap GUI | niskie, lokalny skill | **włączyć przed GUI** |
| Design | Anthropic | UX copy, dostępność, design system, handoff | etap GUI / badania UX | niskie; dołączone MCP (Figma, Slack…) nie muszą być łączone | **włączyć przed GUI** |
| playwright | Microsoft | testy E2E, zrzuty ekranu aplikacji | etap GUI | niskie, lokalny | włączyć przed GUI |
| context7 | Upstash | aktualna dokumentacja FastAPI/SQLAlchemy/Pydantic | od Etapu 2 | zapytania (nie kod) idą do zewnętrznej usługi; wymaga konta | opcjonalnie |
| commit-commands | Anthropic | commity / PR | gdy będzie repo zdalne | niskie | opcjonalnie |
| securitymaxxing | społeczność | audyt OWASP / API / LLM Top 10 | Etap 6 | niezweryfikowany wydawca, zasięg „privileged” | nie teraz — wystarczy `security-review` |
| 42crunch API security | partner | audyt OpenAPI | — | wymaga konta 42Crunch | odrzucone |
| Diagrams (Kroki) | społeczność | render diagramów | — | wysyła diagramy do kroki.io | odrzucone — Mermaid lokalnie |

## 5. Docker na laptopie vs Synology DS225+

**Decyzja: development na Dockerze na laptopie; Synology jako backup i (później) staging — nie produkcja.**

| Rola | Laptop (Docker Desktop) | Synology DS225+ (Container Manager) |
|---|---|---|
| Codzienny development, testy, migracje | ✅ najszybsza pętla, reset bazy w sekundy, działa offline | ❌ opóźnienia sieci, trudniejszy debug |
| Kopie zapasowe bazy (`pg_dump` → NAS) | — | ✅ dobre zastosowanie od razu |
| Demo/staging w sieci domowej | — | ✅ później (Etap 3+), np. testy z partnerem |
| Produkcja dla klientów | ❌ | ❌ łącze domowe, brak SLA, ryzyko RODO (dane gości, umowy), wystawianie NAS-a do internetu |

Produkcję komercyjną planuję na serwerze w UE (VPS / managed PostgreSQL u europejskiego dostawcy) — koszty w Iteracji 2.

DS225+ to model x86 z Container Manager, więc obraz `postgres` zadziała. RAM fabrycznie jest skromny — przy stagingu (API + PostgreSQL) warto go rozszerzyć. Nigdy nie wystawiaj portu 5432 do internetu; dostęp zdalny tylko przez VPN (Tailscale/WireGuard).

## 6. Wymagane działania użytkownika

1. **Nadaj swojemu kontu prawo zapisu do `D:\aplikacjaweselna`** — teraz tylko Administratorzy mogą tam zapisywać, więc nie mogę utworzyć ani jednego pliku projektu.
2. **Uruchom Docker Desktop** i włącz „Start Docker Desktop when you sign in”.
3. Zrestartuj Claude Code, żeby nowy PATH (uv, ruff, gitleaks, task, node) był widoczny.
4. Włącz zaakceptowane pluginy z sekcji 4.
