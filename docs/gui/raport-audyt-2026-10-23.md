# Raport: poprawki po zewnętrznym audycie z 23.10.2026

Audyt „Nasz dzień — audyt kodu i strategia produktu” (commit `a773c76`) wskazał błędy P0/P1.
Każde ustalenie najpierw sprawdziłem w kodzie; poniżej to, co się potwierdziło i co zrobiono.
Punkty wymagające decyzji właściciela są na końcu — nie zostały ruszone.

## Naprawione

| Punkt audytu | Co było | Co jest teraz | Test |
|---|---|---|---|
| **Strona gościa (P0)** | `_rsvp_expiry` brał wcześniejszą z dat: termin RSVP albo dzień wesela, więc link przestawał działać dzień po terminie RSVP (np. 2.07 przy ślubie 14.08). | Termin RSVP zamyka tylko edycję odpowiedzi (`_is_open`, bez zmian). Strona gościa działa do **7 dni po ostatnim dniu wesela**, liczonych od *aktualnej* daty wesela (przesunięcie daty nie skraca linków). Bez daty wesela — zapisane `expires_at` (rok). Dotyczy też linków wydanych wcześniej, o ile nie zostały odwołane. | `test_guest_page_works_after_rsvp_deadline_until_week_after_wedding` |
| **S1 — replay idempotencji (P0)** | Zapisana odpowiedź była zwracana po samym podpisie JWT, bez sprawdzenia sesji i roli. | Przed odtworzeniem: `authenticate()` (wylogowanie/odwołanie sesji → 401), a dla ścieżek `/weddings/{id}` — członkostwo (brak → 404) i ta sama rola co przy pierwszym żądaniu (inna → 403 `idempotency.context_changed`). Nowa kolumna `idempotency_keys.member_role` (migracja `a1d4c7e9b2f0`, tylko dodanie kolumny). | `test_idempotency_replay_requires_active_session`, `test_idempotency_replay_rechecks_membership_and_role` |
| **S2 — cache po wylogowaniu (P0)** | Jeden `QueryClient` żył ponad sesjami. | `api/sessionCache.ts`: przy wylogowaniu (także wygaśnięciu sesji) i przy zmianie konta (`sub` z tokena) anulujemy odczyty i czyścimy cache. Odświeżenie tokena tego samego konta niczego nie czyści. | `sessionCache.test.ts` |
| **S3 — tokeny w logach (P0 wdrożenia)** | Access log Caddy w JSON z pełnym URI; uvicorn z domyślnym access logiem (surowe ścieżki). | Caddy: filtr logu zamienia ciągi ≥ 40 znaków base64url po `/` lub `=` na `REDACTED` (tokeny mają 43 znaki, UUID 36 zostają), usuwa `Authorization`, `Cookie`, `Referer`, `Set-Cookie`. Uvicorn: `--no-access-log` (żądania loguje API z szablonem trasy). | Sprawdzone na kontenerze `caddy:2.10-alpine`: `/rsvp/REDACTED`, `/nowe-haslo?token=REDACTED`, `/w/<uuid>` bez zmian; `caddy validate` OK |
| **S5 — linki bez terminu (P1)** | Link pomocnika i link usługodawcy działały do odwołania. | Pomocnik: do 30 dni po weselu (zwroty, rozliczenia). Usługodawca (program dnia): do 7 dni po weselu. Bez daty wesela — jak dotąd, do odwołania. Wspólne `workspace.service.link_active`. | `test_links_without_login_expire_after_wedding` |
| **S6 — worker AI (P1)** | Rola i zgoda sprawdzane tylko przy zleceniu. | Worker przed przetwarzaniem ponownie sprawdza: aktywne konto zlecającego, `RUN_AI` w weselu, tego samego dostawcę (lokalny/zewnętrzny) co przy zleceniu i — dla zewnętrznego — aktywną zgodę. Inaczej status `blocked` z powodem. | `test_worker_rechecks_role_and_provider_before_processing` |
| **Walidator AI** | `amount="NaN"` → `InvalidOperation`; ilość spoza cytatu dostawała `medium`. | `is_finite()` przed porównaniem; ilość (≠ 1) musi stać w cytacie, inaczej `unverified`. | `test_non_finite_amounts_are_dropped_not_crashing`, `test_quantity_without_evidence_is_unverified` |
| **4.2 — kolejka (P1, P0 przy AI)** | Blokada 5 min, AI do 10 min, bez odnawiania. | Heartbeat w workerze odnawia blokadę co minutę, dopóki handler pracuje (`queue.extend_lock`); po zakończeniu handlera wątek się zatrzymuje. | `test_long_job_keeps_its_lock` |
| **4.4 — różne założenia** | Dziś liczyło stałe 5%/10%, Budżet — wartości z pól. | Wspólne domyślne stopy (`indexationRates.ts`); podpowiedź na Dziś mówi, przy jakiej inflacji liczy. Zapisywanie własnych założeń na weselu — nie zrobione (wymaga pola w bazie i UI; do backlogu). | vitest/tsc |
| **Szybkie usprawnienie 6** | Kreator ignorował błąd podziału budżetu i sponsorów (`.catch(() => null)`). | Wesele nadal powstaje, ale komunikat mówi, czego nie udało się zapisać i gdzie to zrobić. | tsc/eslint |

## Sprawdzone, bez zmian

- **mypy**: u mnie `Success: no issues found in 144 source files` — błąd wewnętrzny z audytu dotyczył środowiska audytora.
- **OpenAPI**: bez zmian po poprawkach (`scripts.export_openapi` nie zmienia `docs/openapi.json`).

## Wymaga decyzji właściciela (nie ruszane)

1. **Oferta → raty (4.1, P0)** — to istniejący punkt **A6**: czy „Wybieram tę ofertę” ma tworzyć dopłatę wyliczoną
   jak w „co jeśli” (suma − kwoty stałe), czy kwoty z warunków oferty. Audyt proponuje rozdzielić ratę z umowy,
   prognozę i „kwotę do rozplanowania” oraz pokazać podgląd przed zapisem.
2. **Wybrana oferta jako koszt stały** — czy pozycja z oferty ma się przeliczać przy zmianie liczby gości.
3. **S4 — link dla sali z imionami i dietami** — podstawa prawna i zakres (znane ograniczenie nr 41).
4. **Nazwa „Dzień” → „Dzień ślubu”** i inne zmiany nawigacji — audyt zaleca najpierw test z parami.
5. Strategia (cena 199 zł / 24 mies., pilotaż 8–12 par, katalog firm, AI) — decyzje biznesowe.

## Otwarte technicznie — zrobione 23.10 (raport `raport-audyt-otwarte-techniczne.md`)

- ✅ 4.3: rewizja programu w `ShiftIn` (podgląd przesunięcia jako blokada wersji).
- ✅ Zapisywanie założeń waloryzacji na weselu.
- ✅ Rozdzielenie wykonawców szybkich e-maili od OCR/AI (`worker-fast`).
- ✅ `_prod_guards`: kontrola HTTPS publicznego URL, SMTP i jawnego `ai_enabled`.
- ✅ CI (`.github/workflows/ci.yml`); obowiązkowa bramka wymaga reguły gałęzi w ustawieniach GitHuba (właściciel).
