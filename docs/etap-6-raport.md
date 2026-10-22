# Raport: Etap 6, stabilizacja i dokumentacja wdrożeniowa

Data: 2026-10-19. Format raportu wg sekcji 17 założeń projektu.

## Wykonane działania

| Obszar | Co działa |
|---|---|
| **Hasła** | Ocena siły offline przez **zxcvbn** (MIT): słowniki, wzorce klawiatury, daty, powtórzenia, słowa z adresu e-mail i polskie słowa kontekstowe („wesele”, „ślub”, „kocham”). Wymagany wynik ≥ 2 (odporność na zgadywanie przy limicie prób). Hasło nie opuszcza serwera. |
| **Odświeżanie sesji na słabym zasięgu** | Ponowienie tego samego refresh tokena w ciągu 30 s, gdy następca nie był jeszcze użyty, nie wylogowuje już urządzenia: klient dostaje nowy token w tej samej rodzinie sesji (zdarzenie `refresh_token_retry`). Użycie starego tokena później albo po użyciu następcy nadal zamyka całą rodzinę jako możliwa kradzież. |
| **Retencja** | Dziennik audytu nadal tylko do dopisywania. Wyzwalacz w bazie przepuszcza `DELETE` wyłącznie w transakcji procedury retencji i wyłącznie dla wpisów starszych niż 24 miesiące; `UPDATE` jest zawsze zablokowany. Zdarzenia bezpieczeństwa są przechowywane 12 miesięcy. Worker uruchamia retencję raz na dobę. |
| **Sprzątanie plików** | Raz na dobę worker usuwa pliki bez rekordu wersji dokumentu, np. gdy zapis pliku przeszedł, a transakcja w bazie nie. Pliki młodsze niż doba zostają, bo mogą należeć do trwającego uploadu. |
| **Rotacja klucza szyfrowania** | Klucze mają wersje (bajt w szyfrogramie). Stare klucze w `WP_DATA_ENCRYPTION_PREVIOUS_KEYS` służą tylko do odczytu, a `scripts/rotate_encryption_key.py` (`generate` / `rotate --dry-run` / `rotate`) przeszyfrowuje dane. Przeszyfrowanie nie zmienia wersji rekordu, więc klienci nie dostają konfliktów, a równoległa edycja wygrywa. |
| **Magazyn S3** | `S3Storage` (boto3, Apache-2.0) obok magazynu lokalnego, wybierany przez `WP_STORAGE_BACKEND=s3`. Te same testy przechodzą dla obu implementacji (S3 emulowany przez moto, bez sieci). Usuwanie prefiksu nie zahacza o podobne nazwy (`weddings/a` ≠ `weddings/a1`). |
| **Globalny limit żądań** | 600 żądań/min na użytkownika (z ważnego tokena) albo na prefiks IP; 429 z `Retry-After`; `/health` bez limitu. Ostrzejsze limity (logowanie, RSVP, AI, stoły) działają osobno. |
| **Wydajność** | Testy obciążeniowe Locust (MIT). Wąskie gardło: jeden proces API i domyślna pula 5 połączeń. Obie wartości są teraz konfigurowalne (`WEB_CONCURRENCY`, `WP_DB_POOL_SIZE`, `WP_DB_MAX_OVERFLOW`). |
| **Konfiguracja produkcyjna** | `deploy/compose.prod.yaml`: Caddy (Apache-2.0) z automatycznym TLS, HSTS i nagłówkami bezpieczeństwa; API bez opublikowanych portów; baza w sieci bez internetu; kontenery tylko do odczytu, bez uprawnień jądra, bez eskalacji, z rotacją logów. Adres zaufanego proxy jest konfigurowalny (wcześniej wpisany na sztywno `127.0.0.1`). |
| **Kopie** | `backup_db drill`: świeża kopia → nowa, pusta baza → wersja schematu, liczby rekordów w 12 kluczowych tabelach i obecność każdego pliku dokumentu w archiwum. |
| **Dokumentacja** | [wdrozenie.md](wdrozenie.md) (runbook: start, aktualizacje, kopie, rotacja, monitorowanie, incydenty i 72 h na zgłoszenie do UODO, staging na Synology, lista kontrolna przed startem), [hosting.md](hosting.md) (warianty do decyzji). |

## Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Kryterium: p95 list < 300 ms przy 100 równoczesnych użytkownikach | **spełnione**: p95 list 62–120 ms, 7304 żądania, **0 błędów** (4 procesy API) |
| Kryterium: backup odtworzony od zera | **spełnione**: `backup_db drill` (schemat `a9052588a747`, 12 tabel zgodnych, 3/3 pliki dokumentów) |
| Kryterium: raport licencji bez AGPL | **spełnione** (`task licenses`) |
| Staging w konfiguracji produkcyjnej (`scripts/staging_check.py`) | **10/10**: HTTPS przez Caddy, HSTS i nagłówki, wyłączona dokumentacja, HTTP→HTTPS, rejestracja i logowanie, upload przy systemie plików tylko do odczytu, ekstrakcja w workerze, usunięcie konta |
| Testy na hoście (`task ci`) | **603 passed**, 5 skipped (OCR i model LLM), pokrycie **93%** |
| Testy w Dockerze | **606 passed**, 2 skipped |
| Trivy (obraz z OR-Tools, boto3, zxcvbn) | 0 HIGH/CRITICAL |
| Ruff, mypy `--strict`, Bandit, pip-audit, Gitleaks | czysto |

Nowe testy: ocena haseł (wzorce klawiatury, słownik + rok, słowa kontekstowe), okno tolerancji refresh tokena (w oknie i po nim), retencja (zwykły `DELETE` i `UPDATE` zablokowane, świeżych wpisów nie da się usunąć nawet z flagą, flaga działa tylko w transakcji procedury), sprzątanie plików (stary osierocony usunięty, świeży i z rekordem zostają), rotacja klucza (odczyt starym kluczem, podgląd, rotacja, usunięcie starego klucza, błędny format), magazyn lokalny i S3 (te same scenariusze, niebezpieczne klucze), globalny limit (per użytkownik, per IP przy nieważnym tokenie, `/health` bez limitu).

## Decyzje

| Decyzja | Uzasadnienie | Alternatywa |
|---|---|---|
| zxcvbn zamiast listy 100 tys. haseł | wykrywa wzorce, a nie tylko dokładne trafienia; MIT; zero plików do pobierania i aktualizowania | lista z wycieków: trzeba sprawdzić jej licencję (często niejasna) |
| Retencja audytu przez flagę transakcji + wiek wpisu w wyzwalaczu | aplikacja nadal nie może zmieniać historii; nawet błąd w kodzie nie usunie świeżych wpisów | osobna rola bazy z uprawnieniem `DELETE` (więcej konfiguracji, do rozważenia przy zarządzanej bazie) |
| Globalny limit w pamięci procesu | zero dodatkowej infrastruktury; wystarcza na jeden serwer | Redis (przy skalowaniu poziomym) |
| Caddy jako reverse proxy | automatyczny TLS, prosta konfiguracja, Apache-2.0 | nginx + certbot (więcej elementów) |
| AI wyłączone na start (rekomendacja w hosting.md) | GPU na serwerze to wysoki koszt stały; zewnętrzny dostawca wymaga umowy powierzenia i opinii prawnej | decyzja właściciela |

Koszt: 0 zł. Nowe zależności: zxcvbn (MIT), boto3/botocore/s3transfer (Apache-2.0), jmespath (MIT); tylko do testów: moto (Apache-2.0), locust (MIT).

## Problemy i ograniczenia

- Aktualna lista: [znane-ograniczenia.md](znane-ograniczenia.md). Etap 6 zamknął punkty 1–5, 10, 18 i 20; doszedł punkt 34.
- Cen hostingu nie udało się pobrać: narzędzia wyszukiwania w sieci nie działały w tej sesji, a cenniki ładują kwoty dynamicznie. [hosting.md](hosting.md) zawiera wymagania, warianty i linki do sprawdzenia.
- Konfiguracja produkcyjna jest sprawdzona lokalnie (staging na `localhost`), nie na docelowym serwerze.
- Kopia na Synology (udział SMB) czeka na podłączenie NAS.

## Następny krok: decyzja o hostingu

Do decyzji ([hosting.md](hosting.md), sekcja 6): dostawca VPS (Hetzner DE/FI czy OVHcloud PL), AI na start (rekomendacja: wyłączone), domena i SMTP. Potem pierwsze wdrożenie według [wdrozenie.md](wdrozenie.md), a dalej v1.1: MFA (TOTP) przed otwarciem rejestracji i katalog publiczny (v2).
