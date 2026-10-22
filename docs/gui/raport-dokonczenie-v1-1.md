# Raport: dokończenie v1.1

Plan: [docs/plan-dokonczenie-v1-1.md](../plan-dokonczenie-v1-1.md). Kolejność: 6 → 5 → 1 → 4 → 3 → 2.

## 6. Niestabilny E2E „Budżet…” (390 px) — naprawione

- **Przyczyna (błąd GUI, nie testu):** kafelki „Wpłacono / Do zapłaty” w siatce `stat-grid`
  (2 kolumny po min. 9 rem na 390 px). Kwota jest nierozdzielna (twarde spacje, np. „123 456,78 zł”)
  i przy dużych sumach rozpychała kolumnę o ~21 px. W pełnym E2E testy równoległe dopisują wydatki
  do „Wesela demo”, więc sumy rosły i błąd pojawiał się tylko czasem. Pojedynczo test przechodził
  20/20; pod obciążeniem (4 workery, 390 px) — 3 błędy na 108.
- **Naprawa:** kafelek w siatce ma `min-width: 0` i `container-type: inline-size`, a kwota
  `font-size: clamp(1.125rem, 13cqi, var(--wp-text-amount-min))` — zmniejsza się tylko, gdy nie
  mieści się w kafelku (dotyczy też Dziś, porównania ofert, kalkulatora napojów).
- **Test:** `expectNoHorizontalScroll` w `wedding.spec.ts` przy błędzie wypisuje elementy
  wystające poza ekran.
- **Weryfikacja:** `wedding.spec.ts` na 320/390 × 3 powtórzenia, 4 workery — 162/162;
  testy „Budżet” w 390-dark × 20 (4 workery) — 60/60.

## 5. Statusy w analizie 04 — zrobione

Tabele „Rozpiska” w [04-plan-rozwoju-i-uslugi-platne.md](../analysis/04-plan-rozwoju-i-uslugi-platne.md)
mają kolumnę **Status** (✅ / ⏳ / ⏸ / ✖) z odnośnikami; na początku dokumentu akapit „Stan wdrożenia”.
Aktualizowane po każdym kolejnym punkcie.

## 1. M5 „Co jeśli”: dwa scenariusze obok siebie + raty — zrobione

**Backend** (`app/modules/offers`):
- `POST /weddings/{id}/offers/scenarios` — `{offer_ids, scenarios: [2–3 × ScenarioIn]}`; dla każdej
  oferty i scenariusza: koszt, **różnica względem scenariusza 1**, **dopłata** i jej różnica,
  harmonogram płatności (`payments`), nieznane pozycje i uwagi. Uprawnienie: odczyt (jak `compare`).
- Czysta funkcja `payment_plan(terms, total, anchor)` (bez zapisu) i wspólna `payment_rows`
  (terminy z `due_date` / `days_before_wedding`) — z niej korzysta też `select_offer`.
- **Dopłata = suma − kwoty stałe** (zadatek, zaliczka, raty). Rata „final” z oferty wyznacza tylko
  termin dopłaty; jej kwota zależy od scenariusza (oznaczona `computed: true`, w GUI „wyliczona”).
  Gdy kwoty stałe przekraczają koszt — uwaga `payment.fixed_exceed_total`.
- Testy: `test_scenarios_difference_and_final_payment` (100 vs 120 dorosłych: różnica 20 × 330 zł,
  dopłata rośnie o całą różnicę, kolejność i terminy rat, oferta bez warunków = cała kwota jako
  dopłata, 1 scenariusz → 422); trasa dopisana do `test_idor.py`.

**Frontend** (`CompareView.tsx`, nowy `ScenarioCompare.tsx`):
- W „Co jeśli…” (Premium) pole „Porównaj dwa scenariusze”: zestawy pól A „Plan” i B „Co jeśli”
  (puste = liczba z listy gości), jeden przycisk „Porównaj”.
- Wynik: od 768 px tabela oferta × scenariusz (koszt A, koszt B, różnica, dopłata B z różnicą);
  na telefonie karty z wierszami A/B. W „Raty i dopłata” lista rat dla A i B (termin, rodzaj,
  kwota); różnice opisane tekstem („+5 000 zł w dopłacie”, „bez zmian”), nie kolorem.
- Vitest `scenarios.test.ts` (`diffText`); E2E „Oferty…” rozszerzony o dwa scenariusze na 390-light
  i 1280-light (axe, brak poziomego przewijania).

**Uwaga (bez zmiany zachowania):** „Wybieram tę ofertę” nadal tworzy płatności dokładnie jak
w ofercie — rata „final” ma kwotę z oferty, nie wyliczoną. Suma płatności może więc różnić się od
kosztu z budżetu (widoczne jako „Do zapłaty”). Ujednolicenie z `payment_plan` zmieniłoby istniejące
płatności użytkowników — do decyzji.

## 4. Link dla sali z liczbami — zrobione

**Backend:**
- Rozszerzony istniejący link usługodawcy: dla kategorii `venue`/`catering` `GET /day/{token}`
  zwraca sekcję `catering` — potwierdzeni na przyjęcie wg wieku (dorośli, nastolatki, dzieci,
  maluchy), „jeszcze bez odpowiedzi”, diety inne niż standardowa, posiłki dla obsługi (suma
  `crew_meals` usługodawców) oraz stoły z liczbami i dietami (posadzeni, którzy nie odmówili).
  Liczone przy każdym otwarciu — zmiana na liście gości widoczna od razu.
- **Zgoda pary:** `VendorDayLink.share_catering` (migracja `8d2f4c6a1e37`, domyślnie `false`),
  ustawiane przy tworzeniu linku (`POST …/day-link {share_catering: true}`). Tylko za zgodą przy
  stołach pojawiają się imiona, diety i uwagi dietetyczne (odszyfrowane). Bez zgody — same liczby.
  Dla innych kategorii zgoda odrzucana (`day_link.catering_not_allowed`, 422), a sekcji brak.
  Zmiana zgody = nowy link (stary przestaje działać). Zgoda zapisywana w audycie.
- Test `test_venue_link_catering_numbers_and_consent`: liczby bez zgody (brak imion i notatek
  w odpowiedzi), odmowa nie liczy się przy stole, zmiana odpowiedzi widoczna od razu, dane za zgodą,
  brak sekcji i 422 dla zespołu.

**Frontend:**
- `DayLinkSection.tsx`: dla sali/cateringu opis, co zobaczy sala, pole „Udostępnić sali listę diet
  i plan stołów?” z ostrzeżeniem o danych o zdrowiu; status mówi, czy link pokazuje imiona.
- `DayPage.tsx`: sekcja „Dla kuchni i obsługi sali” (podsumowanie + stoły, imiona i uwagi tylko za
  zgodą), przycisk „Drukuj” (style druku w `rsvp.css`).
- E2E „Link dla sali…”: tymczasowe wesele przez API, zgoda w GUI, strona sali w osobnej przeglądarce
  (liczby, dieta, stół, uwaga), axe, brak poziomego przewijania — 8 profili.

**RODO:** nowe znane ograniczenie nr 41 (dane o zdrowiu dla firmy zewnętrznej za zgodą pary;
podstawa prawna do opinii prawnika, jak nr 37).

## 3. G1 Premium: kod QR na zaproszenie + wygląd strony dla gości — zrobione

**Kod QR** (`segno`, BSD — jak w MFA):
- `POST …/households/{h}/rsvp-link` zwraca dodatkowo `qr_svg` (kod z adresem `public_app_url/rsvp/{token}`).
  W arkuszu zaproszenia pod nowym linkiem: obraz kodu, „Pobierz kod QR (SVG)” i „Drukuj kartę z kodem”.
- Druk hurtowy `/druk/qr` (odnośnik „Karty z kodem QR” na liście gości): `POST /weddings/{id}/rsvp-qr`
  `{household_ids, include_with_link, dry_run}`. Podgląd bez tworzenia linków; rodziny z aktywnym
  linkiem pomijane, chyba że para zaznaczy „także rodziny, które mają już link”. Karty A6, 4 na A4:
  nazwa wesela, rodzina, kod, „Zeskanujcie, aby potwierdzić obecność do …”, adres drobnym drukiem.
- Testy: kod QR = dokładnie adres z tokenem (porównanie z `segno`), token z karty działa, stary link
  nietknięty bez `include_with_link` i unieważniony z nim, obce `household_ids` → 404, IDOR.
- Uwaga: kod zawiera adres z `WP_PUBLIC_APP_URL` (adres produkcyjny), a pole „Link” w arkuszu —
  bieżący adres przeglądarki; na produkcji to ten sam adres.

**Wygląd strony dla gości:**
- `GuestInfo.theme` (`classic`/`garden`/`modern`, migracja `3b7e9f2c5d18`, domyślnie `classic`)
  i `accent` (6 nazw: róż, szałwia, granat, złoto, śliwka, morski). RSVP zwraca `theme`.
- Paleta w `features/rsvp/themes.ts`: każdy kolor ma wersję jasną i ciemną; test w
  `styles/tokens.test.ts` sprawdza kontrast ≥ 4,5 : 1 na tle i powierzchni obu motywów.
- `RsvpPage` ustawia `data-guest-theme` i zmienne akcentu; style w `rsvp.css` wyłącznie przez
  zmienne `--wp-*` (bez zewnętrznych czcionek i obrazów — CSP): Ogród (szeryfowe nagłówki, pas
  akcentu u góry), Nowoczesny (ostre rogi, pas z boku, wersaliki w nadtytule).
- `GuestInfoSheet`: wybór motywu i koloru (Premium) z podglądem nagłówka.
  **Uzupełnienie (2026-10-21):** „Zobacz jak gość” — `GET /guest-info/preview` zwraca widok strony
  gościa z prawdziwymi wydarzeniami, programem, informacjami (także przed publikacją — z adnotacją)
  i wyglądem, ale z fikcyjną rodziną (bez tokenu i bez danych gości); strona `/w/:id/podglad-goscia`
  używa tego samego formularza RSVP w trybie podglądu (nic się nie wysyła). Test API i E2E.
- E2E „Karty z kodem QR i wygląd strony dla gości” (390 jasny/ciemny): druk hurtowy, wybór wyglądu
  w arkuszu, strona gościa w każdym z 3 motywów — axe i brak poziomego przewijania; test RSVP
  sprawdza obraz kodu i pobranie SVG.

## 2. D3 Tryb na żywo bez sieci — zrobione

Zasada z `public/sw.js` bez zmian: `/api/*` nigdy w pamięci podręcznej service workera. Zamiast tego
**jawny, wąski zapis programu** w `localStorage` (`src/lib/dayCopy.ts`):
- tylko tytuł, godziny, miejsce, plan B, przygotowania i nazwa usługodawcy — **bez gości, diet i
  kwot** (pola filtrowane przy zapisie, nawet gdy wywołujący przekaże więcej); z datą zapisu;
- wygasa dzień po ślubie (bez daty ślubu — tydzień od zapisu), znika przy `logout()`;
- każdy odczyt/zapis w `try/catch` (tryb prywatny, pełna pamięć — wtedy bez kopii).

**Para / koordynator** (`ScheduleView` → `LivePanel`): przycisk „Zapisz program na tym telefonie
(na wypadek braku zasięgu)”; potem informacja o kopii i „Usuń kopię z tego urządzenia”. Gdy kopia
istnieje, odświeża się sama po każdej zmianie programu (np. przesunięciu). Bez sieci: komunikat
„Bez połączenia — program z godz. HH:MM… Przesuwanie programu wymaga internetu” i ukryte
przesuwanie. **Start aplikacji bez sieci** (sesji nie da się przywrócić bez API) pokazuje na ekranie
„Brak połączenia” zapisane programy (`OfflineDay`: „teraz / za chwilę” i pełna lista). Kolejki
przesunięć offline nie ma (zgodnie z planem — nie w pierwszej wersji).

**Usługodawca** (`/dzien/:token`): kopia zapisywana po każdym otwarciu, pokazywana przy błędzie sieci
z godziną zapisu; przy 404 (link wyłączony) kopia jest usuwana.

Wspólne style programu (`day-list`, `live__*`) przeniesione do `components/OfflineDay.css`.
Polityka prywatności (robocza, `LegalPages.tsx`) opisuje kopię; znane ograniczenie nr 43.

**Testy:** vitest `lib/dayCopy.test.ts` (whitelist pól, wygasanie, lista kopii, czyszczenie bez
ruszania innych kluczy); E2E „Dzień ślubu bez sieci…” (zapis, `setOffline(true)` → komunikat
i brak przesuwania, wylogowanie usuwa kopię — 8 profili); E2E PWA w buildzie produkcyjnym z CSP:
przeładowanie bez sieci — program na ekranie „Brak połączenia” i na stronie usługodawcy, `/api/*`
nadal poza pamięcią podręczną; istniejący test „API poza pamięcią” przechodzi.

## Weryfikacja (całość)

- Backend: `ruff`, `mypy` czyste; `pytest` — 710 zaliczonych, 5 pominiętych (OCR i Ollama tylko
  w Dockerze); kontrakt (schemathesis) obejmuje nowe trasy.
- Frontend: `tsc`, `eslint` czyste; `vitest` 84; start aplikacji 140,8 KB gzip (limit 170 KB);
  licencje bez zmian (bez GPL/AGPL).
- E2E (8 profili, axe): 244 zaliczone, 36 pominiętych (PWA i testy przypisane do wybranych
  profili), bez niestabilnych. Build produkcyjny z CSP (`E2E_PROD=1`): 217 zaliczonych, 62 pominięte, 1 błąd chwilowy
  (strona logowania nie wczytała się w 30 s na starcie testu „Goście: edycja…” — osobno 6/6).
- **Dodatkowa poprawka znaleziona w E2E produkcyjnym:** „Plan: zależność zadań” padał czasem na
  320/390 px (2/12) — po dodaniu zależności znikał wybór zadania z fokusem, fokus trafiał na `<body>`
  poza dialog i `Escape` nie zamykał arkusza (błąd dostępności, nie testu). `EditTaskSheet`: po
  dodaniu/usunięciu zależności fokus przechodzi na nagłówek sekcji. Po poprawce 12/12.
- Docker: przebudowane `api`, `worker`, `migrate`; migracje do `3b7e9f2c5d18` w bazie dev
  (tylko nowe kolumny z wartościami domyślnymi).
- Przegląd ręczny (390 px, jasny i ciemny): strona sali z liczbami i stołami, strona gościa w motywie
  „Ogród” z akcentem. Poprawka po przeglądzie: lista stołów na stronie publicznej miała kropki
  (styl `row-list` jest tylko w części dla zalogowanych) — własna klasa `day-tables`. Dane do
  przeglądu na tymczasowym weselu, usuniętym po sprawdzeniu; wesele właściciela nietknięte.
