# Raport: usprawnienia v1.1 (plan, pieniądze, dzień ślubu, goście)

Data: 2026-10-20. Źródło listy: [docs/analysis/04-plan-rozwoju-i-uslugi-platne.md](../analysis/04-plan-rozwoju-i-uslugi-platne.md).
Płatności nie są wdrożone — funkcje planu Premium mają tylko znaczek „Premium” i działają dla wszystkich.

## Ponowna ocena listy przed wdrożeniem

| ID | Decyzja | Powód |
|---|---|---|
| A8 okresy w planie | odrzucone | grupowanie po miesiącach już pokazuje oś czasu; okresy dublowałyby nagłówki |
| A9 godzina zadania | odrzucone | godziny należą do harmonogramu dnia, nie do listy zadań |
| G2 osoba towarzysząca w RSVP | wdrożone | decyzja właściciela 2026-10-20: bez limitu miejsc |
| G3 SMS | odrzucone na teraz | płatna usługa zewnętrzna; wdrożony tylko e-mail |
| M4 AI: raty z umowy | odłożone | AI ma być na start wyłączone (hosting); do zrobienia razem z ewaluacją na prawdziwych umowach |
| L2 inspiracje, L3 konto B2B, L4 galeria QR, L5 prawnik-partner | poza zakresem | niska wartość teraz albo decyzje biznesowe/prawne |

## Co wdrożono

### Plan przygotowań
- Szablon `2027.1`: 77 zadań (było 31) + listy dokumentów do ślubu konkordatowego i cywilnego jako **podzadania**; przy każdym zadaniu krótka **wskazówka** (własne treści, z adnotacją „potwierdźcie u źródła” przy formalnościach).
- **Tryb nadrabiania**: nowe wesele założone późno nie ma lawiny „po terminie” — zaległe zadania dostają terminy w najbliższych tygodniach (ćwierć czasu do ślubu, 14–60 dni), z zachowaniem kolejności zależności. Dla istniejących wesel: „Pokaż nowe terminy” (podgląd → zapis).
- **Uzupełnij z szablonu** (także po zmianie typu ceremonii): podgląd nowych zadań i niepasujących (te ostatnie oznaczamy „pominięte”, nic nie usuwamy).
- Zadanie ↔ **usługodawca** (wybór w zadaniu, lista zadań na karcie firmy, skrót „Dodaj usługodawcę do tego zadania”).
- **Kalendarz** (podzakładka Planu): zadania, płatności, wydarzenia dzień po dniu; **kalendarz w telefonie** (ICS, Premium) — prywatny adres, bez kwot, do wyłączenia.

### Nawigacja
- 6 zakładek: Dziś · Plan · Budżet · Goście · Dzień · Więcej; podzakładki: Plan (Zadania/Kalendarz), Budżet (Wydatki/Usługodawcy), Goście (Lista/Plan stołów). Usługodawcy, oferty i harmonogram nie są już schowane w „Więcej”.

### Pieniądze i usługodawcy
- **Szablony ofert** wg kategorii (sala, catering, fotograf, filmowiec, muzyka, dekoracje, transport) — wpisuje się tylko kwoty; puste podpowiedzi są pomijane przy zapisie.
- **Pytania przed rezerwacją** wg kategorii, z odpowiedziami widocznymi w **porównaniu ofert** obok ceny.
- **Lista kontrolna umowy** (Premium): „jest / brakuje / nie sprawdzone” — bez oceny prawnej, z odesłaniem do prawnika.
- **Posiłki dla obsługi**: pole przy muzykach/fotografie, nowa pozycja oferty „za posiłek dla obsługi” (`per_crew`) doliczana w porównaniu.
- **„Co jeśli…”** (Premium) w porównaniu: własna liczba dorosłych, dzieci i gości poprawin.
- **Podział budżetu na start**: propozycja podziału, gdy kategorie nie mają planu.
- **Kalkulator alkoholu i napojów** z założeniami do zmiany i dodaniem do budżetu.

### Dzień ślubu
- Rola **koordynator dnia** (np. świadek): widzi tylko program, wydarzenia i kontakty do usługodawców; może przesuwać program; nie widzi budżetu, gości (diet) ani ofert; nie dostaje podsumowań e-mail.
- **Plan B** przy punktach programu; widoczny w programie, trybie na żywo i u usługodawcy.
- **Tryb na żywo** (Premium): „teraz / za chwilę”, przesunięcie programu jednym ruchem, odświeżanie co 30 s.
- **Link dla usługodawcy** (Premium): program dnia bez logowania, szczegóły tylko przy jego punktach, odświeżanie co minutę, link do wyłączenia.

### Goście
- **Strona dla gości** pod linkiem RSVP: powitanie, dojazd (link „Pokaż na mapie”), nocleg, transport, dress code, prezenty, kontakt; publikacja ręczna; punkty programu z „Pokaż gościom”.
- **Linki RSVP e-mailem** do rodzin bez odpowiedzi (podgląd; rodziny z aktywnym linkiem domyślnie pomijane, bo nowy link unieważnia stary). Dodano e-mail i telefon w edycji zaproszenia.
- **Prezenty i podziękowania** (po weselu).
- **Osoba towarzysząca w RSVP**: gość sam dopisuje osoby (imię, opcjonalnie nazwisko, wiek) i od razu potwierdza ich obecność; może usunąć tylko osoby dopisane przez siebie, do terminu odpowiedzi. Bez limitu miejsc (decyzja właściciela) — jedynie bezpiecznik 20 dopisanych osób na zaproszenie przeciw nadużyciu publicznego linku. Para widzi dopisek „dopisana przez gości”.

### Wydruki (bez bibliotek PDF — „Zapisz jako PDF” w przeglądarce)
- Plan stołów dla sali (diety, dzieci, posiłki obsługi), winietki, lista gości, budżet z płatnościami, lista zadań; harmonogram jak dotąd.

## Bezpieczeństwo i RODO
- Nowe publiczne adresy (ICS, program dla usługodawcy) to tokeny przechowywane jako hash, z limitem zapytań na IP, `Cache-Control`, `noindex`; wygasają z członkostwem / usunięciem usługodawcy.
- ICS i link usługodawcy nie zawierają kwot ani danych gości. Wydruk dla sali zawiera diety — ostrzeżenie przed drukiem.
- Rola koordynatora oddzielona nowym uprawnieniem `day:read` / `day:run`; test IDOR obejmuje wszystkie nowe trasy.
- E-maile do gości wysyła aplikacja w imieniu pary — do potwierdzenia w opinii prawnej (rola RODO, znane ograniczenia nr 37).

## Weryfikacja
- Backend: `ruff`, `mypy` czyste; `pytest` — 700 zielonych, 5 pominiętych (OCR i Ollama tylko w Dockerze).
- Frontend: `tsc`, `eslint` czyste; `vitest` 74 zielone (nowy `improvements.test.ts`).
- E2E (8 profili, axe): 226 zielonych, 22 pominięte (testy przypisane do wybranych profili), bez niestabilnych. Test RSVP obejmuje dopisanie osoby towarzyszącej.
- Migracje do `5c1e7a90b2d4` zastosowane w bazie dev (kolumna `guests.added_via_rsvp`, domyślnie `false` — istniejące dane bez zmian).
