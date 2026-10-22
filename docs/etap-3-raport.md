# Raport: Etap 3, planer, budżet, goście

Data: 2026-10-19. Format raportu wg sekcji 17 założeń projektu.

## Wykonane działania

| Obszar | Co działa |
|---|---|
| **Planer** | 33 zadania szablonowe (wersja `2026.1`), filtrowane po typie ceremonii (cywilny, konkordatowy, wyznaniowy, humanistyczny). Terminy względne liczone od daty ślubu lub planowanego miesiąca. Zależności z wykrywaniem cykli. Filtry: status, kategoria, termin, osoba, „po terminie”. Osoba odpowiedzialna musi być członkiem wesela. |
| **Zmiana daty ślubu** | `POST /weddings/{id}/reschedule` z podglądem (`dry_run`). Przesuwa tylko otwarte zadania z terminem względnym, bez ręcznie ustawionych i zakończonych. Płatności nie są ruszane. `PATCH` zmieniający datę przy istniejących terminach zwraca 409 `wedding.reschedule_required`. Pierwsze ustalenie daty uzupełnia terminy automatycznie. |
| **Budżet** | 12 domyślnych kategorii (w tym rezerwa). Orientacyjny podział budżetu z podglądem. Pozycje stałe i „za osobę” liczone od wybranej liczby gości (planowana, zaproszeni, potwierdzeni). Szacunek: rzeczywisty → potwierdzony → planowany. Płatności z typem **zadatek / zaliczka** / rata / dopłata / inna, z informacją, że to nie porada prawna. Podsumowanie: szacowany koszt, zapłacone, do zapłaty, przekroczenie budżetu, koszt na osobę, zaległe płatności i płatności w ciągu 30 dni. Historia zmian z audytu. |
| **Goście** | Gospodarstwa (jedno zaproszenie na rodzinę), goście (wiek, osoba towarzysząca, dieta, nocleg, transport). Obecność per wydarzenie (ślub, przyjęcie, poprawiny). Statystyki z rozbiciem na dorosłych i dzieci. Filtry. |
| **RSVP bez konta** | Link z tokenem per gospodarstwo (w bazie tylko hash, rotacja, wygaśnięcie po terminie). Gość widzi wyłącznie swoje gospodarstwo (bez nazwisk). Uwagi dietetyczne tylko ze zgodą na dane o zdrowiu. Po terminie RSVP zwraca 409. Limit żądań per IP. |
| **Import CSV** | Separator `;` lub `,`, BOM z Excela, polskie nazwy wartości („panna młoda”, „wegetariańska”, „tak”). Tryb `dry_run`. Przy błędach nic nie jest zapisywane, a raport zawiera numery wierszy. Limit 2000 wierszy. |
| **Dane wrażliwe** | Uwagi dietetyczne (mogą zawierać alergie, art. 9 RODO) szyfrowane AES-256-GCM, a szyfrogram jest związany z id gościa. Klucz `WP_DATA_ENCRYPTION_KEY` jest oddzielny od bazy. Do audytu trafiają tylko nazwy zmienionych pól, nie imiona ani notatki. |
| **Retencja** | Worker anonimizuje dane gości 90 dni po ostatnim dniu wesela (imiona → „Gość N”, kontakty i notatki usunięte, linki RSVP unieważnione). Każde wesele jest anonimizowane tylko raz. |
| **Przypomnienia** | Jedno zbiorcze podsumowanie e-mail (zadania, płatności, terminy RSVP w ciągu 7 dni i zaległe), dziennie lub tygodniowo, z możliwością wyłączenia. Wysyłka nie przed 8:00 czasu polskiego. Przy wielu workerach nie powstają duplikaty (`digest_log`). |
| **Pulpit i eksport** | `GET /weddings/{id}/summary` zwraca wszystko w jednym zapytaniu (pod aplikację mobilną). `GET /weddings/{id}/export` daje pełny eksport JSON (RODO art. 15/20), dostępny dla właściciela i współorganizatora, z wpisem w audycie. |
| **Idempotency-Key** | Middleware dla `POST`. Powtórka zwraca zapisaną odpowiedź (`Idempotency-Replayed: true`). Inna treść z tym samym kluczem daje 422. Klucz jest per użytkownik i ważny 24 h. Odpowiedzi z sekretami (linki RSVP, logowanie) nie są zapisywane. |
| **Kopie zapasowe** | `task backup`: `pg_dump`, potem **próbne odtworzenie do tymczasowej bazy**, opcjonalna kopia na Synology (`BACKUP_TARGET`) i rotacja. Sprawdzone: zrzut 65 KiB, odtworzono 25 tabel. |
| **Test dymny** | `task smoke`: 11 kontroli end-to-end na działającym Dockerze, w tym e-mail przez workera do Mailpit. |

### Poprawki błędów znalezionych w trakcie

| Błąd | Skutek | Naprawa | Test |
|---|---|---|---|
| Blokada utrzymania workera (`pg_try_advisory_xact_lock`) zwalniała się po pierwszym `commit` (Etap 2) | dwa workery mogły równolegle robić retencję | blokada sesyjna na osobnym połączeniu | testy workera |
| `planned_month = "0000-01"` | 500 | data od bieżącego miesiąca do +10 lat | `test_regressions.py` |
| Data ślubu `9999-12-31` | 500 (przepełnienie daty przy liczeniu terminów) | limit +10 lat | jw. |
| `PATCH` z `null` w polu wymaganym | 500 (NOT NULL w bazie) | `PatchModel.NOT_NULL` we wszystkich schematach aktualizacji → 422 | jw. |
| Znak NUL w tekście | 500 | `DataError` → 422 `validation.invalid_value` | jw. |
| CSV z `\r`, niezamkniętym cudzysłowem lub nadmiarowymi kolumnami | 500 | poprawne parsowanie + 422 `import.malformed` | jw. |

Cztery ostatnie znalazły automatyczne testy kontraktowe (Schemathesis). Żaden nie dotarł do użytkowników, bo nie ma jeszcze wdrożenia.

### Wyniki weryfikacji

| Kontrola | Wynik |
|---|---|
| Testy (`pytest`) | **328 passed**, 0 failed (w tym 86 przypadków kontraktowych Schemathesis) |
| Pokrycie | **92,4%** (próg 85%) |
| Test IDOR | każda z 58 tras `/weddings/{id}/…` zwraca 404 dla osoby spoza wesela i 401 bez logowania. Test sam wykrywa nowe trasy bez pokrycia. |
| Ruff + mypy `--strict` | czysto |
| Bandit / pip-audit / Gitleaks | 0 problemów / brak podatności / brak wycieków |
| Licencje | brak AGPL/SSPL/GPL; LGPL-3.0 (psycopg) dozwolone wg ADR-0006 |
| Trivy (obraz) | 0 HIGH/CRITICAL (Debian 12.15 i pakiety Pythona) |
| Migracje | `downgrade base` → `upgrade head` przy każdym uruchomieniu testów; modele zgodne z migracjami |
| Docker end-to-end | `task smoke`: 11/11 OK |
| Kopia zapasowa | zrzut + próbne odtworzenie OK |

## Decyzje

| Decyzja | Uzasadnienie |
|---|---|
| Szablon zadań w kodzie (`templates.py`), a nie w tabeli `task_templates` | wersjonowany w git, testowalny, bez panelu administracyjnego. Zadanie pamięta `template_code` i `template_version`. |
| Status „po terminie” liczony w locie (zadania, płatności) zamiast zapisywania przez workera | zawsze aktualny, bez zadania okresowego i bez rozjazdu danych |
| `PATCH` daty → 409, gdy terminy już są | spełnia wymaganie „zmiana daty nie przesuwa bezrefleksyjnie terminów” |
| Eksport wesela synchroniczny `GET` (bez plików) | dane wesela mają rząd setek KB. Wersja asynchroniczna wróci w Etapie 4 razem z dokumentami. |
| RSVP przez `PUT /rsvp/{token}` bez konta gościa | zgodnie z iteracją 3: rodzina odpowiada zbiorczo, bez rejestracji |
| Nowa zależność `cryptography` (Apache-2.0/BSD) | szyfrowanie kolumn AES-GCM, standard branżowy |
| Nowa zależność dev `schemathesis` (MIT) | testy kontraktowe: znalazły 4 klasy błędów 500 |

Koszt: 0 zł. Wpływ na bezpieczeństwo: dane o zdrowiu szyfrowane i automatycznie usuwane, a RSVP ma minimum danych i limit żądań.

## Problemy i ograniczenia

- Aktualna lista: [znane-ograniczenia.md](znane-ograniczenia.md).
- **Klucz szyfrowania**: jego utrata oznacza utratę uwag dietetycznych. Trzeba go przechowywać osobno (menedżer haseł) i nie wolno go zmieniać bez migracji (rotacja kluczy: format ma bajt wersji, procedura w Etapie 6).
- **Do decyzji prawnej** (bez zmian od Etapu 1): rola RODO platformy względem danych gości oraz treść zgody na dane o zdrowiu w formularzu RSVP.

## Następny krok: Etap 4 (dokumenty i oferty)

Zakres: przechowywanie plików (lokalnie i S3), upload z walidacją sygnatury, wersjonowanie, ekstrakcja tekstu (pypdf, python-docx, Tesseract w kontenerze), „moi usługodawcy” z wykrywaniem duplikatów (pg_trgm), oferty z komponentami cenowymi, **porównanie kosztu całkowitego**, wybór oferty → pozycja budżetu + harmonogram płatności.

Kryteria akceptacji: zestaw ≥ 20 syntetycznych ofert (PDF tekstowy, skan, DOCX) z oczekiwanym tekstem; porównanie zgodne z ręcznymi wyliczeniami; złośliwe pliki odrzucone; wszystkie kontrole z tabeli wyników zielone.
