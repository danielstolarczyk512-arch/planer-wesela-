# Motyw Romantyczny — etapy 0–2 (25.10.2026)

Wdrożenie pakietu „Nasz_Dzien_Premium_UI_2026” (koncepcja premium od właściciela): etap 0 (audyt),
etap 1 (fundamenty wyglądu) i etap 2 (ekran Dziś). Kolejne etapy (budżet, goście, plan, stoły,
usługodawcy, strona gościa) — po akceptacji właściciela, zgodnie z ustaloną pracą etapami.

## Decyzje właściciela

- Nowy wygląd jako **nowy motyw domyślny „Romantyczny”** (jasny i ciemny wariant); dotychczasowe
  motywy zostają do wyboru (Systemowy, Ciepły beż, Ciemna elegancja, Biel i złoto).
- Zdjęcia: **kadry z pakietu** (na polecenie właściciela) — szczegóły i zastrzeżenie licencyjne
  w `frontend/public/media/ZRODLA.md`.
- Praca etapami z akceptacją: zrzuty 1280 / 390 / 320 px po każdym etapie.

## Etap 0 — audyt (stan zastany)

- System wyglądu: tokeny `design/tokens/tokens.json` → `scripts/tokens_to_css.py` → `--wp-*`;
  motywy light / dark / gold; panel wyglądu (`AppearanceTools`) i ustawienia; kontrola kontrastu
  `scripts/check_contrast.py`.
- Nawigacja: telefon — dolny pasek 6 zakładek; od 768 px — wąski pasek boczny; od 1100 px — szerszy.
- Ekran Dziś: nagłówek z nazwą wesela, bordowa karta odliczania, najbliższe kroki, 2 kafelki
  (koszt, goście), najbliższa płatność.
- **Znaleziony błąd (naprawiony):** tokeny podawały kroje „DM Sans”, „Lora”, „Inter”, „Bodoni Moda”,
  a pakiety `@fontsource-variable` rejestrują je jako „… Variable”. W efekcie **wszystkie motywy
  wyświetlały czcionki systemowe** (Georgia, Segoe UI) zamiast zaprojektowanych. Teraz w tokenach
  jest najpierw nazwa „… Variable”, potem dotychczasowa.
- 5 największych problemów UX (do kolejnych etapów): (1) ekran Dziś bez syntezy postępu (brak
  „ile zrobione / ile zostało” w zadaniach, budżecie, usługodawcach); (2) jednolite, „księgowe”
  karty bez hierarchii; (3) brak fotografii i emocji w aplikacji (poza stroną gościa); (4) wąska
  treść na dużych ekranach (60rem); (5) długie listy w Budżecie i Gościach bez wyróżnienia
  najważniejszych liczb — etap 3.

## Etap 1 — fundamenty

- Tokeny: palety `romantic` i `romanticDark` (kość słoniowa `#FBF8F4`, ciemny atrament `#342721`,
  miedź `#8A5248` dla akcji, złoto tekstu `#7E5D3B`), kroje Bodoni Moda (nagłówki) + DM Sans (treść),
  zaokrąglenia 20/14 px, miękki cień. **Kontrast: 0 par poniżej progu WCAG AA** (`docs/gui/kontrast.md`).
- Generator CSS: Romantyczny jest domyślny i podąża za trybem ciemnym systemu; „Systemowy” zachowuje
  dotychczasowe zachowanie (klasyczny jasny/ciemny wg systemu).
- Preferencje: bez zapisanego wyboru — Romantyczny; wcześniejsze wybory (jasny, ciemny, złoty)
  zostają; jedna lista stylów `THEME_OPTIONS` dla ustawień, panelu wyglądu i galerii komponentów.
- `styles/romantic.css` (tylko w tym motywie): tło z ciepłą poświatą, szeryfowe nagłówki, przejrzysty
  nagłówek aplikacji, karty z cienką linią, przycisk główny w miedzi, drugorzędny pudrowy, dolny pasek
  z rozmyciem, pasek boczny 15rem z pudrową aktywną pozycją i zdjęciem pary (od 1100 px, znika na
  niskich ekranach), uniesienie kart-linków (wyłączone przy ograniczeniu ruchu).
- Bez nowych zależności; budżet startu 151,8 KB gzip (limit 170 KB).

## Etap 2 — ekran Dziś

- Powitanie wg pory dnia (czas polski), nazwa wesela, podtytuł.
- Odliczanie: jasna karta z pudrowym tłem i zdjęciem stołu wtapiającym się w tło (telefon: zdjęcie
  pod tekstem); liczba w miedzi. Zachowane: region „Odliczanie do ślubu”, przełącznik dni/tygodnie/
  miesiące, stan zadań.
- 4 kafelki z pierścieniami postępu — **tylko prawdziwe dane z API**: Zadania (wykonane z wszystkich),
  Budżet (przewidywany koszt wobec budżetu, „Ponad budżet”, podwyżki cen), Goście (potwierdzeni
  z zaproszonych, prognoza frekwencji), Usługodawcy (zarezerwowani spośród nieodrzuconych).
  Pierścień jest dekoracją (`aria-hidden`), liczby są w tekście. Telefon: 2 kolumny, bez poziomego
  przewijania od 320 px.
- Na komputerze treść ekranu Dziś do 72rem; „Wymaga uwagi” i „Najbliższe kroki” obok siebie.
- Kafelka „Inspiracje” z makiety **nie dodano** — aplikacja nie ma modułu inspiracji (etap C5);
  przycisk prowadziłby donikąd.

## Powitanie i strona tytułowa

- 8 nagrań w kolumnach (5 nowych z Pexels: tort, taniec, panna młoda, pocałunek, bukiet), bez powtórzeń.
- Pierwszy ekran: zdjęcie pary w łuku nad nagłówkiem (łagodne wejście, wyłączone przy ograniczeniu
  ruchu), napis „Planer wesela”.

## Weryfikacja

- `npx tsc -b --noEmit`, `npx eslint src e2e` — bez błędów; `npx vitest run` — 149 testów zaliczonych;
  `node scripts/check-budget.mjs` — 151,8 KB gzip.
- Podgląd na danych E2E (port 5174): 1280 px jasny i ciemny, 390 px, 320 px — bez poziomego przewijania.
- E2E (8 profili, axe): 448 zaliczonych, 78 pominiętych z założenia, 10 nieudanych → po poprawkach
  zielone: test zmiany motywu (nowe nazwy stylów, 8 profili) i eksport gości do CSV (przycisk jest
  w menu „Więcej działań” od zmian z 23.10 — test nie był zaktualizowany; 2 profile).

## Do decyzji / ryzyka

- Prawa do kadrów z pakietu (obrazy AI) — właściciel potwierdza w regulaminie narzędzia przed startem
  komercyjnym (`ZRODLA.md`).
- Poprawka nazw krojów zmienia wygląd także motywów klasycznych (teraz wyświetlają zaprojektowane kroje).
