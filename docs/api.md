# Projekt API v1 (MVP)

Źródłem prawdy jest OpenAPI generowane przez FastAPI (`/api/v1/openapi.json`, Swagger UI: `/api/v1/docs`, eksport: `task openapi` → `docs/openapi.json`). Ten dokument ustala konwencje i listę endpointów.

## 0. Status implementacji (Etap 5, 2026-10-19)

| Obszar | Status |
|---|---|
| Auth: register, verify-email, login, refresh, logout, password/forgot, password/reset | ✅ zaimplementowane i przetestowane |
| **Klient webowy** (nagłówek `X-Client: web`): refresh token w ciasteczku `wp_refresh` (`HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`), w JSON `refresh_token: null`; `/auth/refresh` bez treści czyta ciasteczko; wylogowanie i nieudane odświeżenie czyszczą ciasteczko | ✅ GUI krok 1 |
| Konto: `GET/PATCH /me`, sesje, zgody, `DELETE /me` + `POST /me/cancel-deletion` | ✅ |
| Dodane względem projektu: `POST /me/verify-email/resend`, `POST /me/password` (zmiana hasła) | ✅ |
| **Zmiana względem projektu:** eksport konta to `GET /me/export` (synchronicznie, JSON), a nie `POST` z 202. Dane konta są małe, kolejka jest zbędna | ✅ |
| Wesela: `POST/GET /weddings`, `GET/PATCH/DELETE /weddings/{id}` (ETag + If-Match) | ✅ |
| Wydarzenia, członkowie, zaproszenia, `POST /invitations/accept` | ✅ |
| `POST /weddings/{id}/reschedule` (z `dry_run`), `GET /weddings/{id}/summary` | ✅ Etap 3 |
| **Zmiana względem projektu:** eksport wesela to `GET /weddings/{id}/export` (synchronicznie, JSON); wersja asynchroniczna z plikami w Etapie 4 | ✅ Etap 3 |
| Planer: zadania, `complete`/`reopen`, zależności (`PUT/DELETE …/dependencies/{id}`) | ✅ Etap 3 |
| Budżet: kategorie, `apply-split`, pozycje, płatności, `mark-paid`, `payments/schedule`, `overview`, `history` | ✅ Etap 3 |
| Goście: gospodarstwa, goście, obecność, `stats`, `import` (CSV w JSON, `dry_run`), `rsvp-link` | ✅ Etap 3 |
| Publiczne RSVP: `GET/PUT /rsvp/{token}` (bez konta) | ✅ Etap 3 |
| Ustawienia przypomnień: `GET/PUT /me/notifications` | ✅ Etap 3 |
| Nagłówek `Idempotency-Key` (wszystkie uwierzytelnione `POST` poza auth i linkami RSVP) | ✅ Etap 3 |
| Testy kontraktowe Schemathesis (wszystkie operacje) | ✅ Etap 3 |
| Usługodawcy: `GET /vendor-categories`, CRUD `/weddings/{id}/vendors` (z `possible_duplicates`) | ✅ Etap 4 |
| Dokumenty: upload `multipart/form-data` (202), wersje, `…/file`, `…/text`, `…/retry` | ✅ Etap 4 |
| Oferty: CRUD, `approve`, `reject`, `compare`, `select` | ✅ Etap 4 |
| AI: `POST …/documents/{d}/versions/{v}/analyze` (body: `vendor_id`, 202), `GET /weddings/{id}/ai-runs`, `GET …/ai-runs/{run}` | ✅ Etap 5 (lokalny model Ollama) |
| Harmonogram dnia: CRUD `/weddings/{id}/schedule`, `conflicts`, `shift` (`dry_run`), `from-template` (`dry_run`), zależności | ✅ po Etapie 5 |
| Plan stołów: `GET /weddings/{id}/seating`, stoły, reguły „razem/osobno”, ręczne sadzanie, `auto` (OR-Tools, `dry_run`), `assignments` (zapis podglądu), `clear` | ✅ po Etapie 5 |
| Planer v1.1: `tasks/catch-up` i `tasks/sync-template` (`dry_run`), podzadania z szablonu, `tip`, `vendor_category`, `vendor_id` w zadaniu | ✅ 2026-10-20 |
| Usługodawcy v1.1: `vendor-checklist` (pytania, lista kontrolna umowy), `crew_meals`, pozycja oferty `per_crew`, `compare.crew` | ✅ 2026-10-20 |
| Kalendarz: `GET /weddings/{id}/calendar`, `calendar-feed` (prywatny ICS), publiczne `GET /calendar/{token}.ics` | ✅ 2026-10-20 |
| Dzień ślubu: rola `coordinator`, `plan_b` i `for_guests` w programie, `vendors/{v}/day-link`, publiczne `GET /day/{token}` | ✅ 2026-10-20 |
| Goście: `language` zaproszenia (`pl`/`en`/puste = automatycznie) — język e-maila RSVP i strony gościa; RSVP zwraca `language` | ✅ 2026-10-21 |
| Plan stołów: `POST …/seating/auto-runs` (202, liczenie w workerze, te same parametry co `auto`) i `GET …/seating/auto-runs/{id}` (`queued`/`running`/`done` z propozycją/`failed` z kodem błędu); przebiegi usuwane po 7 dniach | ✅ 2026-10-21 |
| Goście: `GET …/guests/export.csv` (średnik, UTF-8 z BOM, uprawnienie eksportu; `include_notes=true` dołącza uwagi dietetyczne — wpis w audycie; ochrona przed formułami arkusza) | ✅ 2026-10-21 |
| Budżet: `GET …/budget/export.csv?part=items|payments` — pozycje kosztowe (plan, umowa, szacunek, zapłacono, do zapłaty) albo harmonogram płatności; kwoty z przecinkiem dziesiętnym, wpis w audycie, uprawnienie eksportu | ✅ 2026-10-21 |
| Podgląd strony gościa: `GET …/guest-info/preview` (fikcyjna rodzina, informacje także przed publikacją, `preview_info_published`) | ✅ 2026-10-21 |
| Dokumenty: `GET …/documents/search?q=` — tytuł, nazwa pliku i odczytany tekst bieżących wersji, bez wielkości liter i polskich znaków, z prostą odmianą słów (każde słowo musi wystąpić); wynik z fragmentem i numerem strony (maks. 50) | ✅ 2026-10-21 |
| Budżet: `child_unit_price` w pozycji „za osobę” (dorośli i nastolatki po cenie pełnej, dzieci 4–12 po dziecięcej, maluchy bez opłaty; tylko przy liczbie zaproszonych/potwierdzonych), `children_used` w odpowiedzi | ✅ 2026-10-21 |
| Układ sali: `GET/PUT …/seating/room` (wymiary, parkiet/scena/bar/wejście/bufet; `If-Match`), `pos_x`/`pos_y`/`rotation` stołów, `POST …/seating/seat-numbers` (`keep_existing`, `dry_run`), automat: `near_groups` + `near_target` (`head`/`dance_floor`) → `near_applied` | ✅ 2026-10-21 |
| Skan antywirusowy dokumentów: `scan_status` w wersji (`not_scanned`/`pending`/`clean`/`infected`); pobranie i ponowny odczyt przy `pending` → 409 `document.scan_pending`, przy `infected` → 409 `document.infected`; ponowne wgranie zablokowanego pliku → 422 `document.infected` | ✅ 2026-10-21 |
| Link dla sali/cateringu: `GET /day/{token}` zwraca `catering` (potwierdzeni wg wieku, bez odpowiedzi, diety, posiłki obsługi, stoły); `POST …/day-link` `{share_catering}` — imiona i uwagi tylko za zgodą (`day_link.catering_not_allowed` dla innych kategorii) | ✅ 2026-10-20 |
| Goście v1.1: `guest-info` (strona dla gości), `rsvp-emails` (`dry_run`), `gift_note`/`thanked` w gospodarstwie; RSVP zwraca `info` i `schedule` | ✅ 2026-10-20 |

Godziny (`date-time`) wydarzeń i harmonogramu API zwraca zawsze w czasie polskim (`+01:00`/`+02:00`), niezależnie od strefy podanej na wejściu. Na wejściu wymagany jest offset (godzina bez strefy → 422).

Błędy walidacji specyficzne dla Etapu 3: `wedding.reschedule_required` (409, zmiana daty przez PATCH przy istniejących terminach), `task.dependency_cycle` (422), `budget.category_not_empty` (409), `rsvp.closed` (409), `rsvp.invalid_target` (422), `import.malformed` (422), `idempotency.key_reused` (422), `idempotency.in_progress` (409), `validation.invalid_value` (422, np. znak NUL).

Błędy Etapu 4: `document.unsupported_type` (422), `document.too_large` (413), `document.quota` (409), `document.text_not_ready` (422), `vendor.invalid_nip` (422), `offer.not_approved` (409), `offer.unverified_fields` (409), `offer.already_selected` (409), `offer.citation_not_found` (422), `offer.citation_without_document` (422).

Błędy Etapu 5: `ai.disabled` (503, wyłącznik), `ai.consent_required` (409, dostawca zewnętrzny bez zgody), `rate_limited` (429, dzienny limit analiz na wesele), `document.text_not_ready` (422), `ai.run_not_found` (404). Wynik analizy to zawsze szkic oferty `needs_review` z polem `unverified_fields`.

Błędy harmonogramu: `schedule.dependency_cycle` (422), `schedule.invalid_responsible` (422, osoba odpowiedzialna spoza członków wesela), `event.not_found`/`vendor.not_found` (404, odwołanie do cudzego wydarzenia lub usługodawcy), `schedule.date_required` (422, szablon bez daty ślubu), `schedule.not_empty` (409, szablon tylko do pustego programu).

Błędy planu stołów: `seating.no_tables`, `seating.capacity_insufficient`, `seating.locked_over_capacity`, `seating.infeasible`, `seating.timeout` (422, automat), `seating.invalid_seat` (422), `seating.seat_taken` (409), `seating.rule_exists` (409), `seating.same_guest` (422), `seating.duplicate_guest` (422), `seating.too_many_tables`/`seating.too_many_rules` (409), `rate_limited` (429, 30 automatycznych usadzeń na godzinę na wesele).

Usunięcie wesela (`DELETE /weddings/{id}`) jest natychmiastowe i trwałe (decyzja Etapu 2: prostsza zgodność z RODO). Wpis zostaje w dzienniku audytu.

## 1. Konwencje

| Temat | Reguła |
|---|---|
| Wersjonowanie | prefiks `/api/v1`; zmiany niekompatybilne tylko w `/api/v2`; pola dodajemy, nie zmieniamy znaczenia; deprecjacja przez nagłówek `Deprecation` + `Sunset` |
| Uwierzytelnianie | `Authorization: Bearer <access JWT>`; RSVP gościa: `/api/v1/rsvp/{token}` (token w ścieżce, nie w query, nie logowany) |
| Autoryzacja | sprawdzana w serwisie: członkostwo w weselu + rola → akcja. Zasób spoza dostępu → **404** |
| Format błędów | RFC 9457 `application/problem+json`: `type`, `title`, `status`, `detail`, `code` (stabilny, np. `wedding.not_found`, `offer.not_approved`), `errors[]` dla walidacji |
| Paginacja | kursorowa: `?limit=50&cursor=…` → `{ "items": [...], "next_cursor": "…" | null }`; `limit` ≤ 200 |
| Filtrowanie/sortowanie | jawna lista pól per endpoint, np. `?status=todo&due_before=2027-05-01&sort=due_date,-priority`; nieznane pole → 422 |
| Synchronizacja mobilna | `?updated_since=<timestamptz>` na listach |
| Współbieżność | `PATCH` wymaga `If-Match: "<version>"` (lub pola `version`); niezgodność → **409** `conflict.version_mismatch` |
| Idempotencja | `Idempotency-Key` (UUID) na `POST` tworzących zasoby i akcjach; powtórka zwraca zapisaną odpowiedź (24 h) |
| Kwoty | `{"amount": "1234.50", "currency": "PLN"}`, `amount` jako string |
| Daty | ISO 8601; `date` dla dat kalendarzowych, `date-time` z offsetem dla momentów |
| Limity żądań | globalnie per użytkownik + ostrzejsze dla `/auth/*`, uploadu i AI; odpowiedź **429** + `Retry-After` |
| Akcje | operacje niebędące CRUD jako `POST /…/{id}/<akcja>` (np. `approve`, `select`) |
| Długie operacje | **202 Accepted** + zasób ze statusem (np. wersja dokumentu `text_status`), klient odpytuje albo synchronizuje |

## 2. Role i uprawnienia (skrót)

| Akcja | owner | coorganizer | viewer | coordinator | sponsor | gość (RSVP) |
|---|---|---|---|---|---|---|
| odczyt danych wesela | ✅ | ✅ | ✅ | tylko program dnia, wydarzenia, usługodawcy, kursy (bez nazwisk) | tylko własny wkład (`/my-contribution`) | tylko własne gospodarstwo |
| edycja zadań, budżetu, gości, ofert, dokumentów | ✅ | ✅ | ❌ | ❌ | zgłoszenie przelewu (do potwierdzenia) | tylko RSVP (w tym wybór kursu) |
| przesuwanie programu w dniu ślubu (`schedule/shift`) | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| zapraszanie członków, zmiana ról | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| usunięcie/eksport wesela | ✅ | eksport ✅ | ❌ | ❌ | ❌ | ❌ |
| uruchomienie analizy AI | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

Akcje w kodzie (`workspace/permissions.py`): `BASIC` (podstawowe dane wesela i opuszczenie — każdy członek),
`FUNDER_SELF` (sponsor). Pełna lista endpointów: OpenAPI (`docs/openapi.json`).

## 3. Endpointy

### Auth i konto (`identity`)

| Metoda | Ścieżka | Opis | Uprawnienia |
|---|---|---|---|
| POST | `/auth/register` | rejestracja (e-mail, hasło, akceptacja regulaminu w wersji X) | publiczny, limit |
| POST | `/auth/verify-email` | potwierdzenie tokenem | publiczny |
| POST | `/auth/login` | logowanie → access + refresh | publiczny, limit |
| POST | `/auth/refresh` | rotacja refresh tokena | refresh token |
| POST | `/auth/logout` | unieważnienie bieżącej sesji | zalogowany |
| POST | `/auth/password/forgot` | wysyłka linku (zawsze 202, bez ujawniania, czy konto istnieje) | publiczny, limit |
| POST | `/auth/password/reset` | ustawienie hasła tokenem, unieważnia wszystkie sesje | publiczny |
| GET/PATCH | `/me` | profil | zalogowany |
| GET | `/me/sessions` · DELETE `/me/sessions/{id}` | zarządzanie sesjami | zalogowany |
| GET/POST | `/me/consents` · DELETE `/me/consents/{type}` | zgody (historia) | zalogowany |
| POST | `/me/export` | eksport danych (202 → `data_requests`) | zalogowany |
| DELETE | `/me` | usunięcie konta (wymaga hasła; 30 dni karencji) | zalogowany |

### Wesela (`workspace`)

| Metoda | Ścieżka | Opis | Uprawnienia |
|---|---|---|---|
| GET/POST | `/weddings` | moje wesela / utworzenie (twórca = owner; generuje zadania z szablonu i domyślne kategorie budżetu) | zalogowany |
| GET/PATCH/DELETE | `/weddings/{wid}` | szczegóły / edycja / usunięcie | członek / edytor / owner |
| POST | `/weddings/{wid}/reschedule` | zmiana daty: `{"wedding_date": "...", "dry_run": true}` → lista zmian terminów; `dry_run=false` zatwierdza | edytor |
| GET | `/weddings/{wid}/summary` | podsumowanie: budżet vs koszty, płatności w 30 dni, RSVP, zadania po terminie | członek |
| CRUD | `/weddings/{wid}/events` | wydarzenia (ceremonia, przyjęcie, poprawiny) | edytor |
| GET | `/weddings/{wid}/members` · PATCH/DELETE `/members/{uid}` | członkowie i role | owner |
| POST | `/weddings/{wid}/invitations` · POST `/invitations/{token}/accept` | zaproszenie partnera/współpracownika | owner / zaproszony |

### Planer

| Metoda | Ścieżka | Opis |
|---|---|---|
| CRUD | `/weddings/{wid}/tasks` | zadania (filtry: status, kategoria, termin, przypisany) |
| POST | `/weddings/{wid}/tasks/{tid}/complete` · `/reopen` | zmiana statusu z historią |
| PUT/DELETE | `/weddings/{wid}/tasks/{tid}/dependencies/{dep_id}` | zależności (cykl → 422 `task.dependency_cycle`) |

### Budżet

| Metoda | Ścieżka | Opis |
|---|---|---|
| CRUD | `/weddings/{wid}/budget/categories` | kategorie, w tym rezerwa |
| CRUD | `/weddings/{wid}/budget/items` | pozycje (fixed / per_guest z podstawą liczby gości) |
| CRUD | `/weddings/{wid}/budget/items/{iid}/payments` | płatności z typem zadatek/zaliczka/rata/dopłata |
| POST | `/weddings/{wid}/payments/{pid}/mark-paid` | oznaczenie zapłaty |
| GET | `/weddings/{wid}/budget/overview` | sumy: planowane/potwierdzone/rzeczywiste, zapłacone/pozostałe, koszt na osobę, przekroczenia |
| GET | `/weddings/{wid}/payments/schedule` | harmonogram płatności (najbliższe, po terminie) |
| GET | `/weddings/{wid}/budget/history` | historia zmian (z `audit_log`) |

### Harmonogram dnia ślubu

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET/POST | `/weddings/{wid}/schedule` | program dnia (filtry `event_id`, `vendor_id` — np. plan dla zespołu); każdy punkt ma `ends_at`, `depends_on`, `conflicts` |
| GET/PATCH/DELETE | `/weddings/{wid}/schedule/{sid}` | punkt programu (PATCH z If-Match) |
| PUT/DELETE | `/weddings/{wid}/schedule/{sid}/dependencies/{dep}` | „zaczyna się po zakończeniu” (cykl → 422) |
| GET | `/weddings/{wid}/schedule/conflicts` | ta sama osoba lub usługodawca w dwóch miejscach (z buforami), zła kolejność, punkt poza ramami wydarzenia, usługodawca niezarezerwowany |
| POST | `/weddings/{wid}/schedule/shift` | „ceremonia się opóźniła”: przesuwa punkt i wszystkie późniejsze o N minut; `dry_run` pokazuje zmiany i konflikty po przesunięciu |
| POST | `/weddings/{wid}/schedule/from-template` | typowy program polskiego wesela (błogosławieństwo, ceremonia, chleb i sól, obiad, pierwszy taniec, tort, oczepiny); `dry_run` domyślnie |

### Plan stołów

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/weddings/{wid}/seating` | stoły z gośćmi i wolnymi miejscami, goście bez miejsca (bez odmów i niemowląt), problemy: przepełniony stół, złamana reguła, rozdzielona rodzina, dorosły przy stole dziecięcym, osoba po odmowie przy stole |
| CRUD | `/weddings/{wid}/seating/tables` | stoły: `regular`, `head` (para młoda, automat pomija), `kids` (dziecięcy); kształt, pojemność 1–40; PATCH z If-Match |
| GET/POST/DELETE | `/weddings/{wid}/seating/rules` | „razem” / „osobno” dla pary osób (twarde ograniczenia automatu) |
| PUT/DELETE | `/weddings/{wid}/seating/guests/{gid}` | ręczne posadzenie (opcjonalnie numer miejsca); przypięte — automat go nie przesunie |
| POST | `/weddings/{wid}/seating/auto` | automatyczne usadzenie: rodziny razem, dzieci przy stole dziecięcym, grupy (`group_label` gospodarstwa) i strony panny/pana młodego blisko siebie, reguły i przypięcia nienaruszone; `dry_run` domyślnie, wynik deterministyczny |
| PUT | `/weddings/{wid}/seating/assignments` | zapis wielu przypisań (np. dokładnie zaakceptowany podgląd); `replace_unlocked` |
| POST | `/weddings/{wid}/seating/clear` | wyczyszczenie planu (domyślnie bez przypiętych) |

### Usługodawcy, oferty, porównanie

| Metoda | Ścieżka | Opis |
|---|---|---|
| CRUD | `/weddings/{wid}/vendors` | moi usługodawcy (ostrzeżenie o możliwym duplikacie w odpowiedzi) |
| CRUD | `/weddings/{wid}/offers` | oferty z `pricing_components` i `terms` |
| POST | `/weddings/{wid}/offers/{oid}/approve` | zatwierdzenie (wymagane dla ofert z AI; pola `unverified` muszą być zaakceptowane lub poprawione) |
| POST | `/weddings/{wid}/offers/compare` | porównanie kosztu całkowitego (niżej) |
| POST | `/weddings/{wid}/offers/scenarios` | „co jeśli”: 2–3 scenariusze — koszt, różnica do pierwszego, dopłata i harmonogram rat (bez zapisu) |
| POST | `/weddings/{wid}/offers/{oid}/select` | wybór: tworzy pozycję budżetu i płatności; inne oferty tej kategorii → `rejected` (opcjonalnie) |

Przykład porównania:

```http
POST /api/v1/weddings/0192.../offers/compare
{ "offer_ids": ["...a", "...b"], "guest_basis": "planned", "adults": 100, "children": 8, "include_optional": false }
```

```json
{
  "guest_basis": {"adults": 100, "children": 8},
  "results": [
    {
      "offer_id": "...a",
      "vendor_name": "Dworek A",
      "total": {"amount": "41240.00", "currency": "PLN"},
      "per_adult_effective": {"amount": "412.40", "currency": "PLN"},
      "breakdown": [
        {"label": "Menu weselne", "kind": "per_guest", "amount": "330.00", "quantity": 100, "subtotal": "33000.00", "citation": {"page": 1, "quote": "330 zł/os."}},
        {"label": "Dzieci 4–10 lat (50%)", "kind": "per_child", "subtotal": "1320.00"},
        {"label": "Poprawiny", "kind": "per_guest", "subtotal": "6920.00"}
      ],
      "unknown": ["Napoje/alkohol", "Opłata za obsługę"],
      "warnings": ["offer.min_guests_not_met: minimum 120 osób, rozliczenie wg 120"]
    }
  ],
  "disclaimer": "Wyliczenie na podstawie zatwierdzonych danych ofert. Nie stanowi porady prawnej ani finansowej."
}
```

### Dokumenty i AI

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/weddings/{wid}/documents` | upload (`multipart/form-data`: plik, `kind`, `vendor_id?`) → **202**, ekstrakcja tekstu w tle |
| GET | `/weddings/{wid}/documents` · `/documents/{did}` | lista / szczegóły z wersjami i statusem |
| POST | `/weddings/{wid}/documents/{did}/versions` | nowa wersja |
| GET | `/weddings/{wid}/documents/{did}/versions/{vid}/file` | pobranie pliku (strumień, `Content-Disposition: attachment`) |
| GET | `/weddings/{wid}/documents/{did}/versions/{vid}/text` | wyekstrahowany tekst ze stronami |
| POST | `/weddings/{wid}/documents/{did}/versions/{vid}/analyze` | uruchomienie `OfferExtractor` → **202** + `ai_run_id`; 402/429 przy przekroczeniu limitu planu; 409 gdy brak zgody na zewnętrzne przetwarzanie a provider jest zewnętrzny |
| GET | `/weddings/{wid}/ai-runs/{rid}` | status, model, wersja promptu, wynik, błędy walidacji |

### Goście i RSVP

| Metoda | Ścieżka | Opis |
|---|---|---|
| CRUD | `/weddings/{wid}/households` | gospodarstwa |
| CRUD | `/weddings/{wid}/households/{hid}/guests` | goście (dieta, nocleg, transport, osoba towarzysząca) |
| PUT | `/weddings/{wid}/guests/{gid}/attendance/{eid}` | RSVP wpisane przez parę |
| GET | `/weddings/{wid}/guests/stats` | liczby: zaproszeni/potwierdzeni/odmowy per wydarzenie, dorośli/dzieci, diety, noclegi |
| POST | `/weddings/{wid}/households/{hid}/rsvp-link` | wygenerowanie/rotacja linku RSVP (zwracany raz) |
| POST | `/weddings/{wid}/guests/import` | import CSV (walidacja, raport błędów, `dry_run`) |
| GET | `/rsvp/{token}` | gość: dane gospodarstwa i wydarzeń (minimum danych) |
| PUT | `/rsvp/{token}` | gość: odpowiedź dla każdej osoby i wydarzenia, dieta, nocleg; limit żądań |
| POST | `/weddings/{wid}/rsvp-qr` | karty z kodem QR: nowe linki dla wybranych rodzin (`dry_run` = podgląd; rodziny z linkiem pominięte bez `include_with_link`); `rsvp-link` zwraca też `qr_svg` |
| POST | `/rsvp/{token}/companions` | gość: dopisanie osoby towarzyszącej (bez limitu miejsc; bezpiecznik 20, `rsvp.companions_limit`) |
| DELETE | `/rsvp/{token}/companions/{guest_id}` | gość: usunięcie osoby dopisanej przez siebie (inne → `rsvp.invalid_target`) |

### Rozbudowa 2026-10-22 (raporty w `docs/gui/`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/weddings/{wid}/attendance-forecast` | prognoza frekwencji, minimum sali, termin ostatecznej liczby, alerty, propozycje z rezerwy |
| CRUD, POST `…/invite` | `/weddings/{wid}/reserve` | lista rezerwowa; „Zaproś” tworzy gospodarstwo |
| GET, POST `…/plan`, `…/delivered` | `/weddings/{wid}/invitation-delivery` | wręczanie zaproszeń osobiście: objazdy po miejscowościach |
| GET/PUT | `/weddings/{wid}/vendors/{vid}/brief` | informacje dla usługodawcy (If-Match) |
| GET | `/weddings/{wid}/vendor-briefs` | kto zna aktualny program (wersje, potwierdzenia) |
| POST | `/day/{token}/ack` | usługodawca potwierdza wersję programu (409 przy starej) |
| CRUD | `/weddings/{wid}/funders` (+ `contributions`, `…/confirm`) | portfel sponsorów; `funder_id` w płatnościach |
| GET, POST `…/reports` | `/weddings/{wid}/my-contribution` | widok sponsora; zgłoszenie przelewu |
| GET, PUT `…/{code}` | `/weddings/{wid}/ceremony-documents` | dokumenty do ślubu: okna ważności (źródła gov.pl) |
| GET | `/weddings/{wid}/budget/indexation` | strażnik waloryzacji: dziś / prognoza / najgorszy przypadek |
| GET | `/weddings/{wid}/logistics` | transport i noclegi; CRUD `transport-runs`, `lodging-rooms`, `PUT …/guests` |
| GET | `/weddings/{wid}/day-transport` | kursy dla ekranu Dzień (także koordynator; bez nazwisk) |
| GET | `/weddings/{wid}/lodging/rooming.csv` | lista pokoi dla hotelu |
| GET | `/weddings/{wid}/after-wedding` | po weselu; CRUD `deliverables`, `PUT after-checks/{code}` |
| GET | `/weddings/{wid}/attention` | „Wymaga uwagi” na ekranie Dziś |

RSVP (`/rsvp/{token}`): pole `transport_runs` (kursy udostępnione gościom, wolne miejsca) i `transport_run_ids`
w odpowiedzi gościa (409 `rsvp.transport_full`). Link usługodawcy (`/day/{token}`): `brief`, `version`, `transport`.

### Prywatność, administracja, zdrowie

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/weddings/{wid}/export` | eksport wesela (ZIP: JSON + pliki) → 202 |
| GET | `/data-requests/{id}` | status eksportu/usunięcia |
| POST | `/reports` | zgłoszenie błędu danych / wyniku AI |
| GET | `/admin/jobs`, `/admin/ai-runs`, `/admin/security-events` | podgląd operacyjny (rola `admin`) |
| POST | `/admin/ai/kill-switch` | wyłączenie AI globalnie lub per typ |
| GET | `/health/live`, `/health/ready` | bez uwierzytelnienia, bez szczegółów wewnętrznych |

### Webhooki

Brak w MVP (nie ma zewnętrznych konsumentów). Wrócą przy B2B (v1.2) z podpisem HMAC.

## 4. Testy wymagane dla każdego endpointu

1. Sukces (schemat odpowiedzi zgodny z OpenAPI).
2. Brak uwierzytelnienia → 401.
3. **Członek innego wesela → 404** (test IDOR, parametryzowany dla wszystkich ścieżek `/weddings/{wid}/…`).
4. `viewer` przy zapisie → 403.
5. Walidacja (błędne dane) → 422 z `errors[]`.
6. Konflikt wersji → 409 (dla `PATCH`).
7. Idempotencja (dla `POST` tworzących).
8. Kontraktowo: Schemathesis na całym OpenAPI (fuzzing schematów).

### Dodane 2026-10-22 (analiza 07)

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/date-check?date=…&city=…&ceremony_type=…` | porównanie dat (święta, Adwent/Wielki Post, sezon, zachód słońca); bez wesela, wymaga logowania |
| GET/POST | `/weddings/{wid}/music` | utwory na momenty; `PATCH/DELETE …/{id}` (If-Match), `PUT …/song-requests` |
| POST | `/rsvp/{token}/songs` | gość proponuje utwór (do 3; para zatwierdza) |
| GET/POST | `/weddings/{wid}/photo-groups` | zdjęcia grupowe; `POST …/typical`, `PATCH …/{id}` (If-Match), `POST …/{id}/move`, `PUT …/{id}/done` (koordynator) |
| GET/PUT | `/weddings/{wid}/prep` | plan przygotowań (If-Match, `"0"` dla nowego); `POST …/people`, `PATCH/DELETE …/people/{id}`, `POST …/people/{id}/move` |
| GET/POST | `/weddings/{wid}/menu` | menu z alergenami i ostrzeżeniami o dietach; `PATCH/DELETE …/{id}`, `PUT …/show` |
| GET/PUT | `/weddings/{wid}/guest-page` | stół na stronie gościa, księga życzeń; `PUT …/announcement`, `POST …/announcement/email` (podgląd/wysyłka, raz) |
| GET | `/weddings/{wid}/wishes` | księga życzeń; `PUT …/{id}/hidden`, `DELETE …/{id}` |
| POST | `/rsvp/{token}/wishes` | gość zostawia życzenia (do 5) |
| GET/POST | `/weddings/{wid}/helpers` | pomocnicy bez konta (link raz); `POST …/{id}/link`, `DELETE …/{id}`; `PUT /weddings/{wid}/tasks/{tid}/helper` |
| GET | `/helper/{token}` | zadania pomocnika (bez logowania); `PUT /helper/{token}/tasks/{tid}/done` |

Link usługodawcy (`GET /day/{token}`) ma nowe pola: `music` (DJ, zespół, muzyk), `photo_groups` (fotograf, filmowiec),
`prep` (fryzjer, makijaż). Widok RSVP: `songs`, `menu`, `tables`, `wishes`, `announcement`.

### Dodane 2026-10-22 (analiza 08)

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/weddings/{wid}/search?q=` | wyszukiwarka: zadania, goście, usługodawcy, wydatki (od 2 znaków) |
| GET | `/weddings/{wid}/budget/cashflow` | plan wydatków po miesiącach, ile odkładać |
| GET | `/weddings/{wid}/budget/guest-cost` | koszt gościa: średni i każda kolejna osoba |
| GET/POST | `/weddings/{wid}/gifts` | lista prezentów; `PATCH/DELETE …/{id}` (If-Match przy edycji) |
| PUT | `/rsvp/{token}/gifts/{id}` | gość rezerwuje / zwalnia prezent (`{"reserved": bool}`, 409 `gift.taken`) |
| GET/POST | `/weddings/{wid}/tasks/{tid}/comments` | komentarze przy zadaniu; `DELETE …/{cid}` (autor albo właściciel) |

`GET /weddings/{wid}/guest-page` zwraca też stan części strony gościa (`info_published`, `show_menu`, `song_requests`,
`gifts_enabled`, `runs_shown`); `PUT` przyjmuje `gifts_enabled`. Widok RSVP: pole `gifts`.
