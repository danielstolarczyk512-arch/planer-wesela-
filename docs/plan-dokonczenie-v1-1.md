# Plan dokończenia v1.1 (6 punktów) — instrukcja dla kolejnej sesji

Stan wyjściowy: commit `ca7cc6e` („Usprawnienia v1.1…”), drzewo czyste, ostatnia migracja `5c1e7a90b2d4`.
Opis wdrożonych funkcji: [docs/gui/raport-usprawnienia-v1-1.md](gui/raport-usprawnienia-v1-1.md).
Zasady jak zawsze (CLAUDE.md): Premium = tylko znaczek `components/Premium.tsx`, bez płatności;
prawdziwego wesela właściciela nie ruszać — testy ręczne na „Wesele demo”; licencje tylko
permisywne; każda zmiana: backend + testy → `task web:types` → GUI → E2E → raport → commit.

Kolejność: **6 → 5 → 1 → 4 → 3 → 2** (od najprostszego; 2 jest najbardziej ryzykowny).

---

## 6. Niestabilny E2E „Budżet: podsumowanie, płatności, walidacja nowego wydatku” (390-dark)

Plik: `frontend/e2e/wedding.spec.ts` (test od linii ~88).

1. Odtworzyć: `npx playwright test -g "Budżet: podsumowanie" --project=390-dark --repeat-each=20`
   (przed startem `delete from rate_limit_hits` w bazie). Zebrać ślady: `--trace=retain-on-failure`.
2. Prawdopodobne przyczyny (sprawdzić w śladzie, nie zgadywać):
   - na stronie Budżetu doszły elementy z v1.1 (podzakładki, podpowiedź podziału budżetu,
     kalkulator napojów) → `expectAccessible` może łapać stan w trakcie animacji wejścia
     (`enter-tab`) albo zwijania Disclosure;
   - `Escape` przy arkuszu „Dodaj wydatek” — arkusz z `isDirty` może pokazywać pytanie
     o porzucenie zmian, gdy pola dostały wartości z walidacji;
   - przewijanie na 390 px: przycisk „Dodaj wydatek” pod kalkulatorem/podpowiedzią.
3. Naprawa właściwa dla przyczyny, np. czekanie na koniec animacji (`await expect(dialog).toBeVisible()`
   + `page.waitForFunction(() => !document.getAnimations().length)`), jednoznaczny lokator,
   albo poprawka w komponencie (jeśli to błąd GUI, a nie testu).
4. Gotowe, gdy: 20 powtórzeń w 390-dark i pełne E2E bez błędów. Usunąć wzmiankę z „Stanu” w CLAUDE.md.

## 5. Status w `docs/analysis/04-plan-rozwoju-i-uslugi-platne.md`

1. W tabelach „Rozpiska” dodać kolumnę **Status** (✅ zrobione / ⏳ częściowo / ⏸ odłożone / ✖ odrzucone)
   z odnośnikiem do raportu. Stan na dziś:
   - ✅ N1–N6, N8, M1–M3, M6, M7, D1, D2, D4, D5, G1 (podstawa), G2, G3 (e-mail), G4 (wydruk), G5, L1;
   - ⏳ N7 (zadanie↔usługodawca ✅, okresy i godzina ✖), M5 (punkt 1 tego planu), D3 (punkt 2),
     G1 Premium (punkt 3), G4 link dla sali (punkt 4), G3 SMS ⏸ (płatna usługa);
   - ⏸ M4 (AI raty — AI na start wyłączone), L2–L5 (poza zakresem / decyzje).
2. Na początku dokumentu akapit „Stan wdrożenia (data)” z odnośnikiem do `docs/gui/raport-usprawnienia-v1-1.md`.
3. Po każdym punkcie z tego planu aktualizować status. Tylko dokumentacja — bez testów.

## 1. M5 „Co jeśli”: dwa scenariusze obok siebie + wpływ na raty

Dziś: `CompareView.tsx` ma „Co jeśli…” (dorośli/dzieci/poprawiny) → jedno `POST /offers/compare`.

**Backend** (`app/modules/offers`):
1. Nowy endpoint `POST /weddings/{id}/offers/scenarios`:
   wejście `{offer_ids: [...], scenarios: [ScenarioIn, ScenarioIn]}` (2–3 scenariusze; `ScenarioIn` =
   pola scenariusza z `CompareIn`: `guest_basis`, `adults`, `children`, `after_party_*`, `crew`,
   `include_optional`, plus `label`). Wynik: dla każdego scenariusza lista wycen (jak `OfferQuote`)
   + **różnica względem scenariusza 1** dla każdej oferty.
2. Wpływ na raty: dla oferty z warunkami `deposit`/`payment_schedule` (`OfferTerm`) policzyć
   harmonogram płatności dla scenariusza — użyć tej samej logiki co `select_offer`
   (`service.select_offer` buduje płatności z warunków; wydzielić czystą funkcję
   `payment_plan(offer, terms, quote, wedding_date) -> list[{kind, amount, due_date}]`, bez zapisu).
   Rata „dopłata” = suma − zadatek − raty stałe (tak jak dziś przy wyborze oferty).
3. Testy w `tests/api/test_offers.py`: dwa scenariusze (100 vs 120 dorosłych), różnica = 20 × cena;
   oferta z zadatkiem i ratą końcową — dopłata rośnie o różnicę; IDOR: dopisać trasę do
   `tests/api/test_idor.py`.

**Frontend** (`CompareView.tsx`):
1. Przełącznik „Porównaj dwa scenariusze” (Premium): dwa zestawy pól (A: „Plan”, B: „Co jeśli”),
   jeden przycisk „Porównaj”.
2. Wynik: na ≥ 768 px tabela oferta × scenariusz (koszt, różnica B−A, dopłata przed ślubem);
   na 320–390 px karty oferty z dwoma wierszami A/B (bez poziomego przewijania).
3. W szczegółach oferty: lista rat dla A i B (termin, rodzaj, kwota), różnice wyróżnione tekstem
   („+3 000 zł w dopłacie”), nie samym kolorem.
4. Vitest dla funkcji formatującej różnice; E2E: rozszerzyć test „Oferty…” o dwa scenariusze
   (na jednym profilu desktop i jednym 390).

## 4. Link dla sali z liczbami (na wzór linku dla usługodawcy)

Wzór: `VendorDayLink` + `public_day` w `app/modules/schedule/service.py` i strona `features/rsvp/DayPage.tsx`.

**Backend**:
1. Najprościej: rozszerzyć istniejący link usługodawcy — gdy usługodawca ma kategorię `venue`
   lub `catering`, `GET /day/{token}` zwraca dodatkowo sekcję `catering`:
   `{adults, children, infants, diets: [{label, count}], crew_meals, tables: [{name, guests: [{name, age_group, diet, diet_note}]}]}`.
   Liczby: potwierdzeni na przyjęcie (`attending` na wydarzeniu `reception`) + bez odpowiedzi
   osobno („jeszcze niepotwierdzonych: N”), stoły z `seating`.
2. **Dane o zdrowiu (diety, uwagi) trafiają do firmy zewnętrznej** → włączenie wymaga świadomej
   zgody pary: pole `VendorDayLink.share_catering: bool` (domyślnie `false`) ustawiane przy
   tworzeniu linku z pytaniem „Udostępnić sali listę diet i plan stołów?”. Bez zgody — tylko liczby
   bez nazwisk. Opisać w `docs/znane-ograniczenia.md` i w raporcie (RODO).
3. Migracja: kolumna `share_catering` (server_default false). Testy: z i bez zgody (brak nazwisk
   i notatek), tylko dla kategorii sala/catering, zmiana liczby gości widoczna od razu.

**Frontend**:
1. `DayLinkSection.tsx`: dla sali/cateringu pole wyboru zgody + wyjaśnienie, co sala zobaczy.
2. `DayPage.tsx`: sekcja „Dla kuchni i obsługi sali” (podsumowanie + stoły), czytelna na tablecie,
   z przyciskiem „Drukuj” (użyć stylów z `features/wedding/print.css` lub własnych w `rsvp.css`).
3. E2E: utworzenie linku dla sali przez API, otwarcie strony, liczby zgadzają się z listą gości.

## 3. G1 Premium: kod QR na zaproszenie + wygląd strony dla gości

**Kod QR** (biblioteka już jest: `segno`, licencja BSD — używana w `identity/mfa.py`):
1. Nie da się zrobić jednego QR dla wszystkich (RSVP jest per rodzina, token tylko jako hash).
   Rozwiązanie: QR generowany **w chwili tworzenia linku RSVP** (token znany tylko wtedy):
   `POST /households/{h}/rsvp-link` zwraca dodatkowo `qr_svg`. W GUI (arkusz zaproszenia, sekcja
   linku) przyciski „Pobierz kod QR (SVG)” i „Drukuj kartę z kodem” — karta A6 z imieniem rodziny,
   kodem i krótkim tekstem („Zeskanujcie, aby potwierdzić obecność do …”).
2. Druk hurtowy: na stronie `/druk/qr` (nowy rodzaj w `PrintView.tsx`) — **nowe** linki dla
   wybranych rodzin bez aktywnego linku (ten sam bezpiecznik co w `rsvp-emails`: rodziny z linkiem
   pomijane, chyba że para zaznaczy „wygeneruj nowe”). Endpoint `POST /weddings/{id}/rsvp-qr`
   `{household_ids, include_with_link, dry_run}` → `[{household, url, qr_svg}]`; karty 4 na A4.
3. Testy: SVG zawiera adres z tokenem, token działa; stary link unieważniony tylko przy
   `include_with_link`; IDOR.

**Wygląd strony dla gości** (bez zewnętrznych czcionek i obrazów — CSP):
1. `GuestInfo.theme` (`classic` / `garden` / `modern`) + opcjonalny kolor akcentu z palety 6 kolorów
   sprawdzonych pod kontrast (WCAG AA; test w `styles/tokens.test.ts`). Migracja z server_default.
2. RSVP zwraca `theme`; `RsvpPage.tsx` ustawia `data-theme-guest` na kontenerze, style w `rsvp.css`
   tylko przez zmienne `--wp-*` (jasny i ciemny motyw).
3. W `GuestInfoSheet.tsx` wybór wyglądu z podglądem (Premium) i link „Zobacz jak gość”.
4. E2E: axe dla każdego wyglądu w 390 jasny/ciemny.

## 2. D3 Tryb na żywo bez sieci (najbardziej ryzykowny — zgoda z zasadą „nie buforujemy API”)

Zasada z `public/sw.js`: dane z `/api/*` nigdy w pamięci przeglądarki (dane osobowe). Nie zmieniać
service workera. Zamiast tego **jawny, wąski zapis programu dnia** z zgodą użytkownika:

1. W trybie na żywo przycisk „Zapisz program na tym telefonie (na wypadek braku zasięgu)”.
   Zapis w IndexedDB (lub `localStorage`) tylko: tytuły, godziny, miejsca, plan B, przygotowania,
   nazwy usługodawców — **bez gości, diet i kwot**; z datą zapisu i id wesela.
2. Przy braku sieci (`navigator.onLine === false` albo błąd zapytania `schedule`): `LivePanel` czyta
   z kopii, pokazuje „Bez połączenia — program z godz. HH:MM” i ukrywa przesuwanie (zapis wymaga
   sieci). Opcjonalnie kolejka przesunięć do wysłania po powrocie sieci — **nie** w pierwszej wersji.
3. Kopia wygasa automatycznie dzień po ślubie i znika przy wylogowaniu (`logout()` w `api/auth.ts`
   czyści klucz) — dopisać do polityki prywatności (robocza w `LegalPages.tsx`) i do
   `docs/znane-ograniczenia.md`.
4. To samo dla strony usługodawcy `/dzien/:token` (publiczna): kopia programu w `localStorage`
   po pierwszym otwarciu, pokazywana przy braku sieci z datą.
5. Testy: vitest dla zapisu/odczytu/wygasania; E2E z `context.setOffline(true)` po zapisie —
   program widoczny, przesuwanie ukryte; po wylogowaniu kopii brak. Sprawdzić też test PWA
   („API poza pamięcią”) — musi nadal przechodzić.

---

## Weryfikacja na koniec (całość)
- Backend: `uv run ruff check app tests scripts`, `uv run mypy app`, `uv run pytest -q`.
- Frontend: `npx tsc -b --noEmit`, `npx eslint src e2e`, `npx vitest run`, `node scripts/check-budget.mjs`
  (nowe strony ładowane leniwie, start ≤ 170 KB gzip), pełne `npx playwright test` i `E2E_PROD=1`.
- Docker: `docker compose build api worker migrate && docker compose up -d`, ręcznie na „Wesele demo”
  (320 px i 1280 px), testowe linki wyłączyć po sprawdzeniu.
- Dokumentacja: raport `docs/gui/raport-dokonczenie-v1-1.md`, statusy w `docs/analysis/04`,
  „Stan” i „Następne kroki” w CLAUDE.md, znane ograniczenia (QR, kopia offline, dane dla sali).
- Commit po polsku z `Co-Authored-By`, hook gitleaks (instrukcja w CLAUDE.md).
