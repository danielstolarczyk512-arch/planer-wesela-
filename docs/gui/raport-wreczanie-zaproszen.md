# Raport: wręczanie zaproszeń osobiście (objazdy)

Data: 2026-10-22. Propozycja 4 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Migracja `c9e1a3b5d7f8` (kolumny `delivery_method`, `delivery_by`, `delivery_place`, `delivery_planned_on`,
`delivered_on` w `households`).

## Problem

W Polsce zaproszenia rodzinie wręcza się zwykle osobiście. To dziesiątki wizyt w kilku miejscowościach,
rozłożone na weekendy i podzielone między stronę Panny Młodej i Pana Młodego. Aplikacje zakładają wysyłkę
pocztą albo e-mailem.

## Co zrobiono

- **W zaproszeniu (lista gości):** „Jak wręczamy zaproszenie” (osobiście, pocztą, e-mailem lub linkiem, inaczej).
  Przy „osobiście” dochodzi miejscowość (**tylko miejscowość, bez adresu**) i kto wręcza.
- **Goście → „Zaproszenia”** (`/w/:id/zaproszenia`, `InvitationsView.tsx`):
  - postęp „Wręczone osobiście: 1 z 3” i termin (zadanie z planu „Wręczcie lub wyślijcie zaproszenia”, a bez
    niego najwcześniejszy termin RSVP);
  - tempo: „Zostało 10 wizyt i 4 weekendy — ok. 3 na weekend”;
  - **objazdy**: grupy po miejscowościach (bez względu na wielkość liter i spacje), od największej liczby
    niewręczonych, „Bez miejscowości” na końcu;
  - zaznaczanie zaproszeń i „Zaplanuj objazd” (dzień i kto wręcza dla wielu naraz), „Wręczone” przy każdym
    zaproszeniu albo dla zaznaczonych;
  - „Pokaż na mapie”: zwykły link do OpenStreetMap z nazwą miejscowości. Aplikacja nic nie wysyła, link
    otwiera osoba, która kliknie.
- „Wręczone” ustawia istniejący status zaproszenia na „Doręczone”, więc reszta aplikacji (statystyki, filtry)
  widzi to od razu.

## API

- `GET /weddings/{id}/invitation-delivery`: grupy, postęp, liczby wg sposobu, termin, weekendy.
- `POST /weddings/{id}/invitation-delivery/plan` `{household_ids, planned_on?, delivery_by?}`.
- `POST /weddings/{id}/invitation-delivery/delivered` `{household_ids, delivered_on?}` (domyślnie dziś).
- Nowe pola w tworzeniu, edycji i odczycie gospodarstwa.

## Prywatność

Miejscowość i „kto wręcza” są czyszczone przy anonimizacji gości 90 dni po weselu. Sposób wręczenia
zostaje, bo to dane bez osoby. Audyt zapisuje zaplanowanie i wręczenie (bez treści).

## Weryfikacja

- Backend: `tests/api/test_invitation_delivery.py` (weekendy, grupowanie, termin z planu, plan, wręczone,
  obce gospodarstwo 404, walidacja sposobu, anonimizacja), trasy w `test_idor.py`.
- Frontend: `invitations.test.ts` (tempo, link do mapy, zakładka). E2E „Zaproszenia: objazdy…” zielony na 8 profilach.
  Przy 320 px axe zgłaszał podzakładki schowane pod przyklejonym nagłówkiem po przewinięciu, więc test przewija
  na górę przed kontrolą (ten sam wzorzec jest w innym teście). Bez przewinięcia na 320 px wszystko jest OK,
  także 4 podzakładki Gości.
- Całość: backend **876 passed**, vitest **115**, E2E dev **314 passed**, start 141,6 KB gzip.
- Baza dev: kopia przed migracją `backups/wedding-20261022-014947-przed-zaproszenia.dump`.
