# Nasz dzień — specyfikacja GUI v1.1 (analiza i ulepszenia)

Wersja 1.1 · 19 października 2026 · opracowano na podstawie paczki v1.0 ([design/gui-v1.0](../../design/gui-v1.0/)) i rzeczywistego API ([api.md](../api.md), [openapi.json](../openapi.json)).

**Jak czytać:** v1.1 = v1.0 + zmiany z tego dokumentu. Przy sprzeczności obowiązuje v1.1. Sekcje v1.0, których nie wymieniono, pozostają bez zmian. Tokeny v1.1: [design/tokens/tokens.json](../../design/tokens/tokens.json) (format W3C Design Tokens) i [motion.json](../../design/tokens/motion.json); kontrast: [kontrast.md](kontrast.md) (`task gui:contrast`).

## 0. Ocena v1.0 i najważniejsze zmiany

**Co jest bardzo dobre i zostaje:** dwa motywy na wspólnej strukturze, pięć zakładek, luksus przez rytm i przewidywalność zamiast efektów, ruch jako tłumaczenie zmiany (z czasami i krzywymi), tryb ograniczonego ruchu, „brak wyceny ≠ 0 zł”, AI tylko z potwierdzeniem, gość bez konta, lista odbioru z testami poprawności. To mocna podstawa.

**Dwanaście zmian v1.1 (szczegóły w kolejnych sekcjach):**

1. **Kontrast:** złoto jako zwykły tekst w jasnym motywie ma 3,14:1 (wymagane 4,5:1). Nowy token `textGold` `#7F663F` (5,07:1). Checkboxy i pola rysowane kolorem separatora (makiety) mają 1,33–1,74:1 (wymagane 3:1). Obrys kontrolki zawsze `controlBorder`.
2. **Brakujące tokeny:** fokus, wybrane, nieaktywne, przycisk usuwania, informacja, status neutralny, przyciemnienie tła, szkielet. Wszystkie 76 par sprawdzone skryptem.
3. **Zgodność z API:** „Zapisz wybór” oferty tworzy budżet i płatności oraz odrzuca inne oferty, więc wymaga dialogu z konsekwencjami (sekcja 3.2). Wesele z samym miesiącem nie ma odliczania dni (sekcja 2.4).
4. **Kluczowe przewagi produktu są niewidoczne na makietach:** automatyczne usadzenie z regułami, konflikty i przesunięcie harmonogramu, ostrzeżenia AI (cytat, niepewne pola, podejrzane polecenia w dokumencie). Dodane do ekranów 04, 07 i 09.
5. **RSVP rodziny:** jedno zaproszenie = kilka osób z osobnymi odpowiedziami na każde wydarzenie, status „Jeszcze nie wiem”, dieta z osobną zgodą, termin odpowiedzi i stan „zamknięte”.
6. **Polskie formatowanie zasadami, nie ręcznie:** liczba mnoga (`Intl.PluralRules`), bez automatycznego wołacza imion, grupowanie kwot, daty i godziny w Europe/Warsaw.
7. **Mapowanie błędów API na komunikaty** (409 konflikt wersji, 422 z polami, 429 z czasem, 413, brak sieci) oraz `Idempotency-Key` przeciw podwójnemu zapisowi.
8. **Brakujące ekrany MVP:** logowanie, rejestracja ze zgodami, tworzenie wesela, dokumenty i postęp analizy, usługodawcy, członkowie i role, prywatność konta (eksport, usunięcie), stany puste.
9. **Uczciwe granice MVP:** noclegi z pokojami i kursami oraz pakiet PDF wymagają nowych modułów backendu. Do tego czasu ekrany 08 i 09 mają wersję uproszczoną (sekcja 5).
10. **Prywatność frontendu:** fonty hostowane u nas (bez Google Fonts), brak skryptów stron trzecich, refresh token w ciasteczku `HttpOnly` dla wersji webowej.
11. **Stos:** PWA (React + TypeScript + Vite) z dostępnymi komponentami React Aria, jeden kod dla pary i gościa; aplikacje sklepowe później przez Capacitor. Wszystko na licencjach MIT/Apache/ISC/OFL (sekcja 10).
12. **Budżety wydajności i testy automatyczne:** rozmiar JS, LCP, axe, Playwright na 320/390/768/1280 px, oba motywy, tekst 200%.

## 1. Kolory i dostępność

### 1.1 Poprawki tokenów

| Problem w v1.0 | Pomiar | Zmiana v1.1 |
|---|---|---|
| Złoto `#A88754` jako tekst (jasny): liczby „12 oczekujące”, „8 osób bez miejsca”, etykiety | 3,14:1 na tle, 3,36:1 na karcie | `goldDecorative` tylko ornamenty i tekst ≥ 24 px; tekst: **`textGold` `#7F663F`** (5,07 / 5,42 / 4,51 na akcencie) |
| Checkbox i pola na makiecie w kolorze separatora | jasny 1,33:1, ciemny 1,54–1,74:1 | obrys kontrolki **zawsze** `controlBorder` (3,32–5,51:1) |
| Brak koloru fokusu | — | `focusRing` = kolor akcji (7,4–9,7:1), 2 px + odstęp 2 px, także na przycisku głównym |
| Statusy w ciemnym motywie wszystkie złote (Goście: 82 / 12 / 6) | utrata znaczenia | liczby w kolorach statusów: `successText`, `warningText`, `neutralText` + nazwa statusu |
| Brak stanów | — | `selectedSurface`/`selectedBorder`, `textDisabled`, `actionDanger`/`textOnDanger`, `infoText`/`infoBackground`, `neutralText`/`neutralBackground`, `scrim`, `skeleton` |

Wynik całej palety: [kontrast.md](kontrast.md): **0 par poniżej progu** w obu motywach. Kontrola działa w CI (`task gui:contrast` kończy się błędem przy regresji).

### 1.2 Zasady

- **Wybór nigdy samym kolorem**: wybrana oferta ma obrys `selectedBorder`, ikonę zaznaczenia i tekst „Wybrano” (jak na makiecie 03, utrzymać).
- **Etykiety nawigacji 12 px** zostają (z ikoną), ale przy powiększeniu tekstu etykieta może zajmować dwie linie. Pasek rośnie, nie ucina.
- **WIELKIE LITERY z rozstrzeleniem** (ciemny motyw: „PRZEWIDYWANY KOSZT”, „DNI DO ŚLUBU”) tylko jako `overline`: maksymalnie 3 słowa, nigdy zdania ani przyciski. Zapis w HTML małymi literami, wielkie przez CSS (czytniki ekranu czytają słowo, nie litery).
- **Obszar dotyku 48 × 48 px** także dla małych przycisków na makietach („Dodaj gości”, „Tak/Nie” w RSVP, „Zmień”). Wygląd może być mniejszy, obszar nie.
- **Inicjały w awatarach** („A”, „M”) mają nazwę dostępną: „Anna, współorganizatorka”.
- **Ikona stołu:** na makiecie 07 symbol przypomina słońce. Zastąpić okrągłym stołem z krzesłami (Lucide nie ma takiej ikony: własna w tej samej siatce 24 px i kresce 1,75).

## 2. Język i formatowanie (pl-PL)

### 2.1 Kwoty

- API zwraca `{"amount": "37200.00", "currency": "PLN"}`. **Nigdy nie zamieniać na liczbę zmiennoprzecinkową.** Sumy liczy serwer; frontend formatuje napis.
- Format: `Intl.NumberFormat("pl-PL", {style: "currency", currency: "PLN", useGrouping: "always"})`. **`useGrouping: "always"`**, bo domyślnie pl-PL nie grupuje liczb czterocyfrowych („5000 zł” obok „37 200 zł” psuje kolumny; makiety słusznie pokazują „5 000 zł”).
- Grosze tylko, gdy są różne od zera, chyba że kolumna zawiera kwoty z groszami (wtedy wszystkie z groszami).
- Kwota i „zł” nie mogą się rozdzielić (Intl wstawia twardą spację; nie zastępować jej zwykłą).
- Pole kwoty: `inputmode="decimal"`, akceptuje przecinek i kropkę, spacje ignoruje, po zakończeniu edycji formatuje.
- **Brak kwoty** = „Brak wyceny” (`neutralText`), w sumach dopisek „+ pozycje bez wyceny (2)”. Nigdy „0 zł”.

### 2.2 Liczba mnoga i odmiana

- Wszystkie liczebniki przez `Intl.PluralRules("pl-PL")`: 1 dzień / 2 dni / 5 dni; 1 osoba / 2 osoby / 5 osób / 22 osoby; 1 zadanie / 2 zadania / 5 zadań. Teksty w pliku komunikatów z formami `one/few/many/other` (format ICU MessageFormat). **Odmienia się całe zdanie, nie tylko rzeczownik:** „Zostało 1 zadanie / Zostały 3 zadania / Zostało 5 zadań” (błąd „Zostało 3 zadania” wyszedł przy pierwszej wersji podglądu, więc komunikaty z liczbą mają formy całego zdania).
- **Nie generujemy wołacza imion** („Witajcie, Anno i Michale”): automat myli się przy wielu imionach (Kuba, Ola, imiona obce). Zamiast tego: „Dzień dobry!” albo „Anna i Michał” w mianowniku. Opcjonalnie para wpisuje sama, jak chce być witana.
- Dynamiczne teksty motywacyjne („Wszystko zaczyna się układać”) **tylko wtedy, gdy są prawdziwe**. Przy zadaniach po terminie: „3 zadania po terminie” z linkiem.
- Neutralny ton porównań: zamiast „Różnica wynosi **tylko** 200 zł” piszemy „Różnica: 200 zł”. Aplikacja nie ocenia, która oferta jest lepsza.

### 2.3 Daty i czas

- Strefa zawsze Europe/Warsaw (API zwraca godziny z przesunięciem +01:00/+02:00). Format: „1 lipca 2028”, „sobota, 1 lipca”, „15:00”. Bez „01.07.2028” w treści (dopuszczalne w tabelach).
- Kurs lub wydarzenie po północy pokazuje własną datę („2 lipca, 01:30”) i w osi czasu oznaczenie „po północy”.

### 2.4 Odliczanie

| Dane wesela | Ekran Dziś |
|---|---|
| dokładna data (`wedding_date`) | „30 dni do ślubu” (liczba mnoga!), w dniu ślubu: „Dziś Wasz dzień”, po ślubie: podsumowanie zamiast liczby ujemnej |
| tylko miesiąc (`planned_month`) | „Wrzesień 2027 · ok. 11 miesięcy” + akcja „Ustal datę” (zmiana daty przesuwa terminy zadań z podglądem: `POST /weddings/{id}/reschedule`) |
| brak daty | „Ustalcie datę lub miesiąc” jako pierwszy krok |

Dni liczone jako różnica dat kalendarzowych w Europe/Warsaw (nie dzielenie milisekund przez 24 h).

## 3. Zgodność z API

### 3.1 Ekrany i endpointy

| Ekran | Dane z API | Uwagi |
|---|---|---|
| 01 Dziś | `GET /weddings/{id}/summary`, `GET …/payments/schedule`, `GET …/tasks?…` | najbliższa płatność z harmonogramu płatności; 3 zadania z `due_next_14_days` |
| 02 Budżet | `GET …/budget/overview`, `…/budget/items`, `…/payments` | „W umowach / Wpłacono / Do zapłaty” = pola przeglądu; historia zmian: `GET …/budget/history` |
| 03 Oferty | `POST …/offers/compare`, `POST …/offers/{id}/select` | pozycje nieznane, ostrzeżenia minimum gości, flagi braków |
| 04 Umowa / odczyt AI | `POST …/documents/{d}/versions/{v}/analyze`, `GET …/ai-runs/{r}`, `GET …/offers/{o}`, `POST …/offers/{o}/approve` | cytat ze stroną, `confidence`, `unverified_fields`, `deposit_kind`, `suspicious_instructions` |
| 05 Plan | `GET/POST/PATCH …/tasks`, `…/complete`, `…/reopen` | `source`/`template_code` = pochodzenie terminu; PATCH z `If-Match` |
| 06 Goście | `GET …/households`, `GET …/guests/stats`, `PUT …/guests/{g}/attendance/{e}` | statusy: attending, declined, maybe, pending |
| 07 Stoły | `GET …/seating`, `POST …/seating/auto`, `PUT …/seating/assignments`, `…/rules` | problemy planu z serwera; automat z podglądem |
| 08 Noclegi i transport | `needs_accommodation`, `needs_transport`, `GET …/guests/stats` | **brak modułu rezerwacji/pokoi/kursów** (sekcja 5) |
| 09 Dzień wesela | `GET …/schedule`, `…/conflicts`, `POST …/shift`, `…/from-template`, `GET …/vendors` | **brak pakietu PDF z wersjami** (sekcja 5) |
| 10 RSVP | `GET/PUT /rsvp/{token}` | osobny widok bez logowania |

### 3.2 Sprzeczności makiet z logiką aplikacji (do poprawy w GUI)

1. **„Zapisz wybór” oferty (03)** nie jest szkicem: `select` tworzy pozycję budżetu i płatności (zadatek, raty z datami), oznacza usługodawcę jako zarezerwowanego w aplikacji i odrzuca inne oferty tej kategorii. Poprawka: zaznaczenie karty to wybór lokalny, a przycisk „Wybierz Dwór pod Lipami…” otwiera **dialog z konsekwencjami**: „Dodamy do budżetu 37 200 zł i płatność zadatku 5 000 zł do 1 grudnia. Ofertę Ogród nad Jeziorem oznaczymy jako odrzuconą. Nie wysyłamy niczego do sali.” Potwierdzenie i cofnięcie przez ponowne otwarcie oferty.
2. **„Pozostałe opłaty: 0 zł” (03)** tylko wtedy, gdy oferta naprawdę je wyklucza. Gdy nieznane: „Brak informacji” + lista „Nieznane pozycje” z API.
3. **Minimum gości (03):** API zwraca ostrzeżenie `offer.min_guests_not_met`. Pokazać przy karcie: „Przy 90 osobach płacisz za 100 (minimum)”.
4. **Zadatek a zaliczka (04):** różne skutki prawne. Pole „Zadatek” pokazuje rozpoznany rodzaj (`deposit_kind`) z cytatem; jeśli nierozpoznany, status „Do sprawdzenia: zadatek czy zaliczka?”.
5. **Liczba „82 / 100” (01):** 100 = zaproszeni (lista), nie planowana liczba z ustawień. Etykieta: „82 z 100 zaproszonych”.

## 4. Poprawki ekranów

| Ekran | Zmiany v1.1 |
|---|---|
| **01 Dziś** | odliczanie wg sekcji 2.4; prawdziwy komunikat stanu; karta „Najbliższa płatność” z typem (zadatek/rata) i dniami do terminu; płatność po terminie: `warning` i na górze. Jeśli jest analiza AI czekająca na przegląd: karta „Odczyt umowy fotografa czeka na sprawdzenie”. |
| **02 Budżet** | jedna akcja dodawania (makieta ma „+” w nagłówku **i** przycisk na dole). Zostaje przycisk na dole albo przypięty pasek akcji; „+” w nagłówku usunąć. Pasek limitu z opisem tekstowym („Wykorzystano 96% limitu”). Przy przekroczeniu: `error` + kwota przekroczenia. Wiersz wydatku: status słowny („Umowa podpisana”, „Szacunek”, „Brak wyceny”). |
| **03 Oferty** | sekcja 3.2; na telefonie 2 karty obok siebie tylko przy szerokości ≥ 360 px i tekście 100%, inaczej karty jedna pod drugą + przypięte podsumowanie różnicy. „Zobacz szczegółowe warunki” = tabela z nagłówkiem przypiętym do lewej (pierwsza kolumna nazwy parametru). |
| **04 Sprawdzenie umowy** | każde pole: wartość + **cytat ze strony** (dotknięcie przewija fragment dokumentu i podświetla cytat); pole niepewne: obrys `warning` + „Potwierdź lub popraw”. Ostrzeżenie `suspicious_instructions`: „Dokument zawiera fragment wyglądający na polecenie dla automatu — sprawdź dane ręcznie”. „Zatwierdź dane” nieaktywny, dopóki są niepotwierdzone pola wymagane; po dotknięciu przewija do pierwszego. Postęp analizy: „Czytamy dokument… (zwykle 1–3 min)”, możliwość wyjścia z ekranu (powiadomienie po zakończeniu). |
| **05 Plan** | segmenty „Teraz / Później / Zrobione” + filtr osoby; zadanie z pochodzeniem terminu („z szablonu: 2 mies. przed ślubem”); zadanie po terminie z oznaczeniem słownym. Cofnięcie ukończenia przez 6 s (v1.0) i przez filtr „Zrobione”. |
| **06 Goście** | statusy liczbowe w kolorach statusów (ciemny motyw!); filtr „Jeszcze nie wiem” (maybe); karta rodziny rozwija osoby z odpowiedzią **na każde wydarzenie**; akcje: „Wyślij link RSVP” (kopiuj/udostępnij, link pokazywany raz), „Odpowiedz za gościa”. Import CSV z podglądem błędów. Usunięcie: dialog „Usunąć tylko Zosię czy całe zaproszenie Kowalskich?”. |
| **07 Stoły** | **„Rozsadź automatycznie”** (przycisk drugorzędny nad listą): panel z opcjami (rodziny razem, stół dziecięcy, tylko potwierdzeni) → podgląd zmian (kto gdzie, przypięci bez zmian) → „Zastosuj” / „Odrzuć”. Sekcja **„Problemy planu”** z serwera (przepełniony stół, złamana reguła „osobno”, rozdzielona rodzina) z przejściem do stołu. **Reguły** („Ciocia Halina i Grażyna — osobno”) jako osobna lista w „…”; reguły prywatne, nie trafiają do eksportów. Przypięcie ręczne = ikona pinezki + „Przypięte”. Typy stołów: zwykły, pary młodej, dziecięcy. |
| **08 Noclegi i transport** | MVP: lista osób z potrzebą noclegu/transportu (z RSVP) + liczby; „Rezerwacja potwierdzona” i kursy dopiero z modułem logistyki (sekcja 5). |
| **09 Dzień wesela** | punkty programu z osobą odpowiedzialną i usługodawcą; **konflikty** przy punkcie („DJ w dwóch miejscach 16:15–16:30”) i zbiorczo; akcja **„Opóźnienie? Przesuń program”** (o ile minut, od którego punktu → podgląd → zastosuj); „Utwórz z szablonu” przy pustym planie; zakładka Kontakty = usługodawcy z telefonem (dotknięcie dzwoni). Pakiet PDF: sekcja 5. |
| **10 RSVP** | lista osób z zaproszenia, dla każdej: wesele / poprawiny (Tak / Nie / Jeszcze nie wiem); dieta (lista) + uwaga dietetyczna dopiero po zaznaczeniu zgody („Uwaga może dotyczyć zdrowia; widzi ją tylko para”); nocleg i transport; termin odpowiedzi; po terminie stan „Zapisy zamknięte — skontaktuj się z parą”; po zapisie podsumowanie i „Zmień odpowiedź”. Brak zakładek pary, brak danych innych gości. |

## 5. Brakujące ekrany i granice MVP

| Priorytet | Ekran | API |
|---|---|---|
| MVP | Logowanie, rejestracja (regulamin + polityka prywatności jako osobne zgody), weryfikacja e-mail, reset hasła | `/auth/*` |
| MVP | Kreator wesela: data albo miesiąc, typ ceremonii, liczba gości, budżet (każdy krok można pominąć) | `POST /weddings` |
| MVP | Dokumenty: lista, upload (aparat / plik), postęp ekstrakcji i OCR, błędy (zły typ, za duży, zaszyfrowany PDF, limit) | `/documents` |
| MVP | Usługodawcy: lista, dodanie z ostrzeżeniem o możliwym duplikacie | `/vendors` |
| MVP | Członkowie i role (zaproszenie partnera, rola tylko do odczytu dla rodziców), widok bez uprawnień do zapisu | `/members`, `/invitations` |
| MVP | Konto i prywatność: sesje na urządzeniach, zgody, eksport danych, usunięcie konta (30 dni na anulowanie), przypomnienia e-mail | `/me/*` |
| MVP | Stany puste każdego modułu (jedno zdanie + jedna akcja) | — |
| v1.1 | Noclegi (hotel, pokoje, płatnik, noce) i transport (kursy, miejsca, godziny) | **nowy moduł backendu** |
| v1.1 | Pakiet dla sali / usługodawcy: PDF z wersją, datą i statusem „Nieaktualny” po zmianie danych | **nowy moduł backendu** (eksport z migawką i sumą kontrolną danych) |
| v1.1 | Aktywność („Michał zmienił termin płatności”) | **nowy endpoint** na bazie istniejącego `audit_log` |
| v1.1 | MFA (TOTP) | ADR-0004 |
| v1.1 | Widok tabletu/desktopu (lista–szczegóły) dopracowany na makietach | — |

Do czasu modułów v1.1 ekrany 08 i 09 pokazują wersję MVP. **Nie robimy atrap** z przyciskami, które nic nie zapisują.

## 6. Stany, błędy i zaufanie (uzupełnienie sekcji 7 v1.0)

| Sytuacja (API) | Interfejs |
|---|---|
| 409 `conflict.version_mismatch` (ktoś zmienił rekord; wysyłamy `If-Match`) | panel „Ta pozycja została zmieniona przez Michała” z porównaniem: „Zachowaj moje / Weź jego / Połącz ręcznie”; formularz nie znika |
| 422 z `errors[]` | tekst przy polu, fokus na pierwszym błędzie, podsumowanie u góry formularza przy więcej niż 2 błędach |
| 422 kody domenowe (`offer.unverified_fields`, `seating.capacity_insufficient`, …) | komunikat z API (`detail`) + działanie naprawcze („Dodaj stół”) |
| 429 `rate_limited` + `Retry-After` | „Za dużo prób. Spróbuj za 30 s” z odliczaniem; przycisk nieaktywny do czasu |
| 413 `document.too_large` | przed wysłaniem sprawdzamy rozmiar po stronie klienta (20 MB) |
| brak sieci | baner „Brak połączenia — pokazujemy dane z 14:32”; zapisy nie udają sukcesu; formularz zostaje |
| 401 po wygaśnięciu sesji | ciche odświeżenie tokena; przy porażce logowanie z powrotem do tego samego ekranu i zachowanym szkicem |
| 403 (rola tylko do odczytu) | akcje zapisu ukryte albo nieaktywne z opisem „Masz dostęp tylko do podglądu” |
| 404 (nie istnieje albo brak dostępu) | „Nie znaleziono” bez sugerowania, że rekord istnieje |

**Podwójny zapis:** każde wysłanie formularza tworzącego rekord dostaje nagłówek **`Idempotency-Key`** (UUID na próbę zapisu, ten sam przy ponowieniu). API zwraca wtedy zapisaną odpowiedź zamiast tworzyć duplikat. Spełnia to punkt listy odbioru „Podwójne dotknięcie zapisu nie tworzy dwóch rekordów”.

**Najnowszy zamiar wygrywa:** każde żądanie widoku ma `AbortController`; zmiana zakładki anuluje stare żądania (biblioteka zapytań robi to sama), więc spóźniona odpowiedź nie nadpisze aktualnego ekranu.

## 7. Ruch: doprecyzowanie wdrożenia (uzupełnienie sekcji 6 v1.0)

- Przejścia między widokami: **View Transitions API** (natywne w nowoczesnych przeglądarkach) z wariantem zastępczym „bez animacji”. Animacje kontrolek: CSS (`transform`, `opacity`) z czasami i krzywymi z `motion.json` jako zmienne CSS.
- Bez biblioteki animacji na start. Jeśli dolny panel z gestem tego wymaga, dopuszczalna lekka biblioteka (np. Motion, MIT), ale tylko dla panelu.
- Ograniczenie ruchu: `@media (prefers-reduced-motion: reduce)` **lub** ustawienie aplikacji → klasa na `<html>` zerująca przesunięcia i skalę; przenikania ≤ 100 ms.
- Ruch nie opóźnia danych: kwota po zapisie pojawia się w tej samej klatce co potwierdzenie serwera.
- Zmiana motywu: podmiana zmiennych CSS na `<html>` (`data-theme`), bez przeładowania i bez ponownego montowania komponentów, więc fokus, wpisany tekst i klawiatura zostają.

## 8. Bezpieczeństwo i prywatność frontendu

- **Fonty hostowane z naszej domeny** (paczki Fontsource, licencja OFL; tylko podzbiory latin + latin-ext). Dynamiczne Google Fonts przekazuje adres IP do Google; niemiecki sąd uznał to za naruszenie RODO (LG München I, 20.01.2022, 3 O 17493/20).
- Bez skryptów stron trzecich (analityka, czaty, piksele). Jeśli analityka: samodzielnie hostowana, bez ciasteczek i po zgodzie. Uwaga na licencje: Plausible jest na AGPL (odrzucone, ADR-0006).
- **Tokeny w wersji webowej:** access token tylko w pamięci; refresh token w ciasteczku `HttpOnly; Secure; SameSite=Strict`, a nie w localStorage (ryzyko XSS). Wymaga małej zmiany backendu: tryb ciasteczka dla `/auth/login` i `/auth/refresh` (aplikacja sklepowa dalej używa treści odpowiedzi + bezpiecznego magazynu systemu).
- Content-Security-Policy bez `unsafe-inline` dla skryptów; nagłówki ustawia Caddy (deploy/Caddyfile).
- Token RSVP tylko w ścieżce (`/rsvp/{token}`), nigdy w zapytaniu analitycznym ani w logach; strona RSVP z `Referrer-Policy: no-referrer`. Bez danych osobowych w adresach URL.
- Szkice formularzy lokalnie (IndexedDB) bez uwag dietetycznych, które są danymi wrażliwymi i nie zostają w przeglądarce.

## 9. Wydajność (mierzalne budżety)

| Miara | Cel | Jak sprawdzamy |
|---|---|---|
| JS na start (gzip) | ≤ 170 KB panel pary, ≤ 60 KB strona RSVP | raport bundlera w CI |
| LCP (średni Android, 4G) | ≤ 2,5 s | Lighthouse CI |
| CLS | ≤ 0,05 (fonty z metrykami zastępczymi `size-adjust`) | Lighthouse CI |
| INP | ≤ 200 ms | Lighthouse / pomiar w terenie bez danych osobowych |
| Lista gości 300 osób | przewijanie bez zacięć; wirtualizacja od 100 wierszy | profil na telefonie |

Strona RSVP jest osobnym, lekkim wejściem (bez kodu panelu pary), bo otwierają ją goście na różnych telefonach z linku w komunikatorze.

## 10. Stos i darmowe narzędzia (licencje komercyjne)

| Cel | Narzędzie | Licencja |
|---|---|---|
| Aplikacja (PWA, jeden kod dla pary i gościa) | React 19 + TypeScript + Vite | MIT |
| Dostępne kontrolki (dialog, dolny panel, listy, pola) | React Aria Components | Apache-2.0 |
| Routing | React Router | MIT |
| Dane z API, anulowanie, ponawianie | TanStack Query | MIT |
| Typowany klient generowany z naszego OpenAPI | openapi-typescript + openapi-fetch | MIT |
| Formularze i walidacja | React Hook Form + Zod | MIT |
| Ikony (kreska 1,75) | Lucide | ISC |
| Fonty self-hosted | Fontsource (Lora, DM Sans, Bodoni Moda, Inter: OFL) | MIT / OFL |
| Metryki zastępcze fontów (brak skoku układu) | fontaine | MIT |
| Tokeny → zmienne CSS i TS | Style Dictionary | Apache-2.0 |
| PWA (instalacja, offline odczytu) | vite-plugin-pwa (Workbox) | MIT |
| Testy jednostkowe i komponentów | Vitest + Testing Library | MIT |
| Testy E2E, 4 szerokości, oba motywy | Playwright | Apache-2.0 |
| Automatyczny audyt dostępności | axe-core (@axe-core/playwright) | MPL-2.0 (tylko narzędzie testowe, bez modyfikacji) |
| Katalog komponentów w obu motywach | Storybook | MIT |
| Budżety wydajności | Lighthouse CI | Apache-2.0 |
| Aplikacje w sklepach (później) | Capacitor | MIT |
| Projektowanie (zamiast płatnej Figmy, opcjonalnie) | Penpot | MPL-2.0 |

Node.js 24 jest już na laptopie; narzędzia instalują się przez npm per projekt, bez uprawnień administratora.

**Dlaczego PWA, a nie od razu aplikacja natywna:** strona RSVP i tak musi działać w przeglądarce bez instalacji; jeden kod dla pary i gości; szybsze testy z parami; API jest gotowe. Natywny wygląd i powiadomienia push dostaniemy przez Capacitor bez przepisywania. Decyzja do potwierdzenia (sekcja 12).

## 11. Kolejność wdrażania (zmieniona)

1. Szkielet: projekt frontend (Vite), tokeny → CSS (Style Dictionary), fonty, motywy Jasny/Ciemny/Systemowy, typowany klient API, logowanie z bezpiecznym przechowywaniem sesji. **Test:** kontrast, axe, 320/390/768/1280 px.
2. Komponenty bazowe: przycisk, pole (kwota, data), checkbox, chip, karta, status, komunikat, dolny panel, dialog, stan pusty, szkielet. Storybook w obu motywach.
3. Shell i cztery widoki: Dziś, Plan, Budżet, Goście. Najpierw poprawne bez animacji.
4. Oferty i odczyt AI (04), stoły z automatem (07), harmonogram z konfliktami (09), RSVP (10).
5. Ruch według `motion.json` + tryb ograniczonego ruchu; potem opcjonalne shared elements.
6. Pozostałe ekrany MVP (sekcja 5), PWA, testy na prawdziwych telefonach (Android średniej klasy, iPhone).

## 12. Decyzje właściciela

1. **Stos:** PWA (rekomendacja) czy od razu aplikacja natywna?
2. **Nazwa „Nasz dzień”:** przed startem komercyjnym sprawdzić znaki towarowe (UPRP, EUIPO TMview) i domenę. To popularne wyrażenie, więc może być trudne do zastrzeżenia.
3. **Moduły v1.1 backendu:** logistyka (noclegi i transport) i pakiety PDF. Zrobić przed GUI tych ekranów czy po MVP?
4. **Motyw zaproszenia dla gości:** czy para wybiera motyw strony RSVP (v1.0 to przewiduje), czy na start jeden motyw jasny?
