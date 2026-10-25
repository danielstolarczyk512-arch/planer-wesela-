# Wdrożenie i utrzymanie (runbook)

Dokument dla osoby, która stawia i utrzymuje produkcję albo staging. Wybór dostawcy: [hosting.md](hosting.md).

## 1. Architektura produkcyjna

```
internet ──443──▶ Caddy (TLS, nagłówki, limit treści)
                    │  sieć edge
                    ▼
                  api (uvicorn, WEB_CONCURRENCY procesów) ──┐
                  worker (kolejka, utrzymanie, OCR, AI) ────┤ sieć backend (bez internetu)
                  worker-fast (tylko e-maile) ──────────────┤
                                                             ▼
                                                   PostgreSQL 17 (wolumen)
worker ──sieć scan──▶ clamav (clamd, skan plików przed pobraniem/odczytem; sygnatury z internetu)
pliki: magazyn S3-compatible w UE (albo wolumen „filestore”)
AI: wyłączone na start albo Ollama na serwerze z GPU / dostawca z umową powierzenia
```

- Pliki: [deploy/compose.prod.yaml](../deploy/compose.prod.yaml), [deploy/Caddyfile](../deploy/Caddyfile), [deploy/.env.prod.example](../deploy/.env.prod.example).
- Na zewnątrz otwarte są tylko porty 80 i 443 (Caddy). Baza nie ma portu i nie ma dostępu do internetu.
- Kontenery aplikacji działają z systemem plików tylko do odczytu (`read_only`, `/tmp` w pamięci), bez uprawnień jądra (`cap_drop: ALL`) i bez eskalacji (`no-new-privileges`), jako użytkownik bez uprawnień administratora.
- `WP_ENV=prod` blokuje start z przykładowym sekretem JWT i z włączoną dokumentacją API, a `scripts/seed.py` nie zadziała.
  Od 2026-10-23 także bez: `WP_PUBLIC_APP_URL` z `https://`, jawnie ustawionego `WP_SMTP_HOST`
  (zdalny serwer SMTP wymaga `WP_SMTP_STARTTLS=true`; bez szyfrowania tylko `localhost` i `mailpit`
  w sieci Dockera), jawnie ustawionego `WP_AI_ENABLED` i z dublerem testowym jako `WP_AI_PROVIDER`.
- **Dwa workery:** `worker` (wszystkie zadania i utrzymanie) oraz `worker-fast` (`WP_WORKER_LANE=fast`,
  tylko e-maile). Długi OCR lub AI (do 10 min) nie wstrzymuje resetu hasła, weryfikacji adresu
  ani linków RSVP. W dev wystarcza jeden worker (`WP_WORKER_LANE=all`, domyślnie).
- **Skanowanie plików (ClamAV):** każdy wgrany plik czeka w stanie „sprawdzanie” (bez pobierania
  i odczytu tekstu), aż worker sprawdzi go w `clamd`. Zainfekowany: wersja oznaczona „zablokowany”,
  plik usunięty z magazynu, wpis w audycie. Skaner niedostępny: zadanie ponawiane (do ok. 2 dób),
  plik pozostaje zablokowany — nic nie przechodzi bez sprawdzenia. `WP_ENV=prod` wymaga
  `WP_CLAMAV_HOST` (w `compose.prod.yaml`: `clamav`). Pliki sprzed wdrożenia skanera worker
  sprawdza partiami po 100 przy każdym cyklu utrzymania.

## 2. Wymagania serwera

Pomiar (Locust, [sekcja 9](#9-wyniki-testów-obciążeniowych)): 100 równoczesnych par, 4 procesy API na laptopie, 0 błędów, p95 list poniżej 130 ms. Na start:

| Zasób | Minimum | Uwagi |
|---|---|---|
| CPU | 4 vCPU | OCR (Tesseract) i automat stołów (OR-Tools) potrafią zająć rdzeń na kilka sekund |
| RAM | 8 GB | PostgreSQL + 2 procesy API + worker + ClamAV (ok. 1,5–2 GB); AI lokalnie wymaga osobnego serwera z GPU |
| Dysk | 80 GB SSD/NVMe | baza + obrazy; pliki dokumentów najlepiej w S3 |
| System | Linux (Debian/Ubuntu LTS) z Dockerem i Compose v2 | |
| Lokalizacja | UE (najlepiej PL/DE) | RODO; umowa powierzenia z dostawcą |

## 3. Pierwsze uruchomienie

```bash
git clone <repozytorium> /opt/wedding-planner
```

```bash
cd /opt/wedding-planner/deploy && cp .env.prod.example .env.prod && chmod 600 .env.prod
```

1. Uzupełnij `.env.prod`: domena, hasło bazy, `WP_JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), `WP_DATA_ENCRYPTION_KEY` (`python -m scripts.rotate_encryption_key generate`), SMTP, S3, wersje regulaminu i polityki prywatności.
2. Rekord DNS `A`/`AAAA` domeny → adres serwera (Caddy sam pobierze certyfikat Let's Encrypt).
3. Zapora: tylko 22 (SSH, najlepiej z kluczem i bez logowania hasłem), 80, 443.

```bash
npm --prefix ../frontend ci --ignore-scripts && npm --prefix ../frontend run build
```

```bash
docker compose -f compose.prod.yaml --env-file .env.prod up -d --build
```

```bash
curl -fsS https://twojadomena.pl/health/ready
```

Aplikacja webowa (`frontend/dist`) i API działają pod jedną domeną (Caddy: `/api/*` → API, reszta → aplikacja), bo ciasteczko sesji ma `SameSite=Strict`. Przy każdej aktualizacji frontendu najpierw buduj `dist`, potem restart Caddy nie jest potrzebny (pliki są montowane).

Kolejność startu wymusza compose: baza → migracje (`migrate`) → api, worker i worker-fast → Caddy.

**Kubełek S3:** prywatny (blokada publicznego dostępu), szyfrowanie po stronie serwera, wersjonowanie obiektów albo kopia do drugiego kubełka, klucz dostępu z uprawnieniami tylko do tego kubełka.

## 4. Aktualizacja wersji

```bash
git pull && docker compose -f compose.prod.yaml --env-file .env.prod up -d --build
```

Migracje uruchamia usługa `migrate` przed api. Przed aktualizacją zrób kopię (sekcja 5). Migracje mają `downgrade`, ale bezpieczniejszy powrót to odtworzenie kopii sprzed aktualizacji.

Raz w tygodniu: `uv lock --upgrade` w repozytorium, `task ci`, `task image:scan` (Trivy) i wdrożenie poprawek bezpieczeństwa.

## 5. Kopie zapasowe

| Co | Jak | Gdzie |
|---|---|---|
| Baza | `task backup`: `pg_dump` + próbne odtworzenie do bazy tymczasowej + rotacja (14 kopii) | lokalnie + Synology (`BACKUP_TARGET`) albo drugi kubełek S3 w innym regionie UE |
| Pliki dokumentów | archiwum `tar.gz` z wolumenu (przy S3: wersjonowanie lub replikacja kubełka) | jw. |
| Klucz szyfrowania i sekrety | **ręcznie, osobno**: menedżer haseł właściciela + kopia offline | nigdy razem z kopią bazy |

- Harmonogram: kopia co noc (cron na serwerze albo zadanie na Synology), a do tego przed każdą aktualizacją.
- **Raz w miesiącu próba odtworzenia od zera:** `uv run python -m scripts.backup_db drill`. Robi świeżą kopię, odtwarza ją do nowej, pustej bazy, sprawdza wersję schematu i liczbę rekordów w kluczowych tabelach i potwierdza, że każdy plik dokumentu jest w archiwum. Wynik zapisz w dzienniku utrzymania.
- Odtworzenie po awarii: nowy serwer (sekcja 3) → `pg_restore` do pustej bazy → rozpakowanie plików do wolumenu `filestore` (albo przywrócenie kubełka) → ten sam `WP_DATA_ENCRYPTION_KEY` → start.

## 6. Rotacja klucza szyfrowania

Kiedy: podejrzenie wycieku klucza, odejście osoby z dostępem, a poza tym co 12 miesięcy.

1. `python -m scripts.rotate_encryption_key generate` → nowy klucz (zapisz w menedżerze haseł).
2. W `.env.prod`: `WP_DATA_ENCRYPTION_KEY=<nowy>`, `WP_DATA_ENCRYPTION_KEY_VERSION=<poprzednia + 1>`, `WP_DATA_ENCRYPTION_PREVIOUS_KEYS=<poprzednia>:<stary klucz>`.
3. Restart api i workera. Nowe dane szyfrują się nowym kluczem, stare dalej się odczytują.
4. `docker compose ... run --rm api python -m scripts.rotate_encryption_key rotate --dry-run`, potem bez `--dry-run`. Licznik `old_key` musi spaść do 0.
5. Usuń `WP_DATA_ENCRYPTION_PREVIOUS_KEYS`, zrestartuj, zniszcz stary klucz. Kopie bazy sprzed rotacji wymagają starego klucza: zachowaj go tak długo, jak te kopie.

Rotacja `WP_JWT_SECRET` wylogowuje wszystkich: zmień sekret i zrestartuj api.

## 7. Monitorowanie

| Sygnał | Źródło | Reakcja |
|---|---|---|
| Dostępność | `GET /health/ready` co minutę z zewnątrz (np. Uptime Kuma, MIT, na Synology) | alert e-mail/SMS po 2 nieudanych próbach |
| Błędy 5xx, czas odpowiedzi | logi JSON (`request_id`, `status`, `duration_ms`) w `docker compose logs`; Caddy loguje JSON | przegląd dzienny; przy wzroście: analiza po `request_id` |
| Kolejka zadań | tabela `jobs` (`status = 'dead'`) | przyczyna w `last_error` (typ błędu, bez danych osobowych) |
| Zdarzenia bezpieczeństwa | tabela `security_events` (`refresh_token_reuse`, seria `login_failed`) | sprawdzenie konta, ewentualnie unieważnienie sesji |
| Dysk, RAM | dostawca VPS / `df -h` | alarm przy 80% |
| Kopie | wynik `task backup` i comiesięcznej próby | brak kopii = incydent |

Utrzymanie w workerze: co 15 minut kolejka, limity, wygasłe dane i anonimizacja gości po weselu; raz na dobę retencja audytu (24 mies.) i zdarzeń bezpieczeństwa (12 mies.) oraz sprzątanie plików bez rekordu w bazie (starszych niż doba).

## 8. Incydenty i RODO

1. **Ograniczenie:** zablokuj ruch (Caddy/zapora), zachowaj logi i kopię stanu.
2. **Sekrety:** zmień `WP_JWT_SECRET` (wylogowanie wszystkich), hasło bazy, klucze S3/SMTP; przy wycieku klucza szyfrowania wykonaj rotację (sekcja 6).
3. **Ocena:** jakie dane, ilu osób, czy dane wrażliwe (uwagi dietetyczne mogą dotyczyć zdrowia).
4. **Zgłoszenie do UODO w ciągu 72 godzin** od wykrycia naruszenia, jeśli istnieje ryzyko dla osób (art. 33 RODO). Przy wysokim ryzyku zawiadom także osoby, których dane dotyczą (art. 34).
5. **Dziennik naruszeń:** wpis także wtedy, gdy zgłoszenie nie jest wymagane.

## 9. Wyniki testów obciążeniowych

Locust ([loadtest/locustfile.py](../loadtest/locustfile.py), `task load`). Każda wirtualna para loguje się, zakłada wesele z zadaniami z szablonu, dodaje 16 gości i 3 stoły, a potem przegląda pulpit, listy i plan stołów oraz czasem coś zapisuje (ok. 1–4 s przerwy między kliknięciami). Środowisko: laptop (Ryzen 7 5800H), Docker Desktop, PostgreSQL w kontenerze.

| Przebieg | Pary | Procesy API / pula | Żądania | Błędy | Mediana | p95 wszystkich | p95 list (pulpit, zadania, goście, budżet, stoły) | Maks. |
|---|---|---|---|---|---|---|---|---|
| 1 (stan wyjściowy) | 50 | 1 / 5+10 | 3415 | 0 | 36 ms | 1100 ms | 56–550 ms | 3,0 s |
| 2 | 50 | 2 / 10+10 | 3646 | 0 | 23 ms | 340 ms | 70–170 ms | 0,56 s |
| 3 | 100 | 2 / 10+10 | 6821 | 0 | 40 ms | 740 ms | 340–530 ms | 1,9 s |
| **4 (zalecana konfiguracja)** | **100** | **4 / 10+10** | **7304** | **0** | **21 ms** | **160 ms** | **62–120 ms** | **0,44 s** |
| 5 (po v1.1 i etapie A, 2026-10-21) | 100 | 2 / 10+10 | 6826 | 0 | 32 ms | 1100 ms | 48–660 ms (mediany 10–17 ms) | 3,4 s |

Wnioski:

- Kryterium Etapu 6 (p95 list < 300 ms przy 100 równoczesnych użytkownikach) jest spełnione przy **4 procesach API**. Zalecenie: `WEB_CONCURRENCY` równe liczbie vCPU serwera.
- Wąskim gardłem był pojedynczy proces API i domyślna pula 5 połączeń z bazą. Obie wartości są teraz konfigurowalne (`WEB_CONCURRENCY`, `WP_DB_POOL_SIZE`, `WP_DB_MAX_OVERFLOW`). Łączna liczba połączeń musi się zmieścić w `max_connections` PostgreSQL.
- Scenariusz jest celowo ostrzejszy niż rzeczywistość: wszystkie pary w ciągu kilkunastu sekund zakładają wesela i dodają po 16 gości.
- Automat stołów (`/seating/auto`) przy małych weselach odpowiada w ok. 30 ms (mediana); limit 30/h na wesele chroni CPU przed nadużyciem.
- Przebieg 5 (2 procesy API, jak w dev): odczyty bez regresji (mediany 10–17 ms), p95 zawyża faza startu, gdy 100 par jednocześnie zakłada wesela z 77 zadaniami szablonu `2027.1` i gości (zapisy ok. 0,6 s mediany). W produkcji obowiązuje zalecenie 4 procesów. Skrypt sprząta po sobie (`on_stop`); pozostałości po przerwanym teście usuwa `scripts.cleanup_loadtest`.

## 10. Staging na Synology DS225+

Synology służy do kopii i stagingu, nie do produkcji (łącze domowe, brak SLA, fizyczne bezpieczeństwo). Staging:

1. Container Manager → projekt z `deploy/compose.prod.yaml` i `.env.prod` z osobnymi sekretami (nigdy produkcyjnymi) i `WP_AI_ENABLED=false`.
2. Dostęp tylko z sieci lokalnej albo przez VPN (Tailscale/WireGuard). Nie otwieraj portów na routerze.
3. Dane: wyłącznie fikcyjne (`scripts/seed.py` działa tylko poza `WP_ENV=prod`, więc staging seedujesz z `WP_ENV=dev`).
4. DS225+ ma procesor x86-64, więc obrazy budują się bez zmian. Zalecane co najmniej 4 GB RAM.

## 11. Lista kontrolna przed startem komercyjnym

- [ ] Regulamin i polityka prywatności (wersje w `WP_TERMS_VERSION` / `WP_PRIVACY_VERSION`) przygotowane przez prawnika
- [ ] Umowy powierzenia: hosting, S3, SMTP (i dostawca AI, jeśli zewnętrzny)
- [ ] Rejestr czynności przetwarzania; DPIA (dane gości, w tym potencjalnie o zdrowiu)
- [ ] Opinia prawna: odczyt ofert przez AI to ekstrakcja faktów, nie porada prawna
- [ ] Ewaluacja AI na prawdziwych ofertach (za zgodą par) albo AI wyłączone
- [ ] Kopie: nocna kopia działa, próba odtworzenia od zera wykonana na serwerze docelowym
- [ ] Monitorowanie dostępności z alertem
- [ ] Sekrety tylko w `.env.prod` (uprawnienia 600) i menedżerze haseł
- [ ] MFA (TOTP) dla kont: v1.1, przed otwarciem rejestracji publicznej
