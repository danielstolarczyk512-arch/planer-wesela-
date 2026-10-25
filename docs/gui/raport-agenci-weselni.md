# Raport: katalog firm, badacz i asystent doboru („agenci weselni”)

Data: 2026-10-25. Pakiet wejściowy: `Nasz-dzien-pakiet-dla-Claude.zip`. Decyzje: [ADR-0008](../adr/0008-katalog-i-agenci-weselni.md).
Zrobione etapy **0–3**. Etap 4 (prawdziwa poczta, odbiór odpowiedzi) czeka na decyzje właściciela.

## Co naprawdę działa

**Badacz (etap 1)** — „aktualizuje podane strony”, a **nie** „samodzielnie odkrywa nowe firmy”.
- Administrator (`global_role=admin`) dodaje adresy stron firm (`/admin/katalog`, API `/admin/discovery/*`).
- Proces `discovery-scheduler` planuje zadania, `discovery-worker` (tor `discovery`, zwykły worker ich nie przejmuje)
  pobiera HTML, wyciąga fakty (JSON-LD, `tel:`/`mailto:`, linie z cenami), zapisuje dowody z datą, scala firmy tylko po
  telefonie/e-mailu, flaguje sprzeczne ceny, publikuje tylko udokumentowane firmy.
- Pobieranie: ochrona SSRF (DNS sprawdzany przy każdym połączeniu, także po przekierowaniu), robots.txt, limity czasu/rozmiaru/
  przekierowań, odstęp 5 s na domenę, dzienny limit 100, `Retry-After`, wyłącznik awaryjny domeny, 401/403/CAPTCHA = stop,
  404/410 = wycofanie z historią, pauza z panelu.
- **Wyszukiwanie nowych adresów: NIE skonfigurowano** (brak legalnego, bezpłatnego źródła — ocena w ADR-0008). GUI mówi to wprost.

**Asystent (etap 2)** — Budżet → „Dobór firm”: Rozmowa, Katalog, Kandydaci, Zapytania.
- Dobór w kodzie (`concierge/matching.py`): kategoria, region, budżet tylko przy porównywalnej jednostce, zakres/styl z dowodem,
  uzasadnienie + braki zamiast punktów; nieznany termin = „niepotwierdzona”.
- Czat: lokalny model, narzędzia o zamkniętych schematach (`extra=forbid`), `wedding_id` z serwera, odpowiedź w tle (przeżywa
  odświeżenie), ponowna kontrola uprawnień w workerze, czyszczenie adresów spoza wyników, tryb bez AI (filtry + wyniki wg preferencji).
- Prośba o research zleca badaczowi tylko `request_id` (kategoria i region); wynik uczciwie mówi „odświeżono N źródeł”.

**Zapytania (etap 3)** — szkic bez budżetu → ekran zatwierdzenia (co zobaczy firma) → wysyłka **tylko do lokalnego Mailpit**.
- Rewizje niezmienne, zgoda dotyczy hasha (adresat+temat+treść); zmiana = nowa rewizja; unikalna dostawa na rewizję (podwójne
  kliknięcie), SMTP: tymczasowy błąd → ponowienie, odrzucenie → błąd, awaria po DATA → „niepewny”, bez automatycznego dublowania.
- Odpowiedź wklejona ręcznie → wątek + dokument DOCX → istniejąca analiza AI → szkic oferty (`needs_review`); katalog nietknięty.
- Eksport wesela (`/export`) obejmuje preferencje, rozmowy, kandydatów, zapytania; usunięcie wesela kasuje dane prywatne, katalog zostaje.

## Jak uruchomić
- Dev (opcjonalnie): `docker compose --profile discovery up -d` (badacz na bazie dev; dodaj źródła w `/admin/katalog`).
- Pokaz na fikcyjnych stronach: `docker compose --profile e2e up -d` (fixtures `docker/demo-sites`, badacz na `wedding_e2e`).
  Konto demo musi mieć rolę admin w tej bazie: `update users set global_role='admin' where email='demo@example.com'`.
- Konfiguracja bez sekretów: `.env.example` (sekcja „Katalog firm i badacz”). Domyślnie: bez kosztów, bez zewnętrznej wysyłki.

## Wyniki sprawdzeń
- Testy nowe: `test_discovery` (30), `test_concierge` (28), `test_inquiries` (21), jednostkowe SSRF/fetcher (35) i korpus ekstrakcji (16),
  IDOR dla wszystkich nowych tras, kontrakt schemathesis; frontend: vitest `assistant.test.tsx` (3), `tsc`, `eslint`.
- Pokaz na żywo (Docker, baza `wedding_e2e`): dodanie źródeł w GUI → pobranie 2 fikcyjnych stron (6 faktów + 4/2 pakiety) →
  katalog → dobór z dowodami → kandydaci → 2 zapytania zatwierdzone jednym ekranem → 2 wiadomości w Mailpit (Reply-To pary) →
  odpowiedź wklejona → status „Odpowiedź otrzymana”. Czat z prawdziwym `qwen2.5:7b-instruct`: 5 kroków narzędzi i karty wyników
  (pierwsza próba ujawniła zmyśloną kategorię „fotografia” — poprawiono prompt i dodano tryb zapasowy).
- Dane demo są fikcyjne (`.demo.example`, oznaczone „DEMO”); wyniki prawdziwego pobrania czyjejkolwiek strony **nie były** wykonywane.

## Ograniczenia (zob. też `znane-ograniczenia.md` 62–70)
- Ekstrakcja regułowa: tylko HTML z czytelnymi cenami; PDF/OCR i strony z JavaScriptem nie są obsługiwane.
- Analiza AI odpowiedzi firmy zależy od lokalnego modelu (wolna na 4 GB GPU; model `qwen3.5:4b` przekracza limit czasu).
- Blokada adresów wewnętrznych jest aplikacyjna; zaporę wyjścia na hoście trzeba dodać na produkcji. Rola bazy badacza nie jest zawężona.
- Brak odbioru poczty, bounce, odmów kontaktu, przypomnień; styl tylko z tagów potwierdzonych przez człowieka (admin API).
- Panel admina to prosty ekran (bez scalania w GUI — jest w API); brak linku w menu (adres `/admin/katalog`).
- Do sprawdzenia: wdrożenie migracji na bazie dev odbyło się przy `docker compose up` (dodane tylko nowe tabele i 2 kolumny).

## Decyzje do etapu 4 (właściciela)
1. Czy i jakie źródło nowych adresów (np. OSM po opinii prawnej, zgłoszenia firm, płatne API za zgodą).
2. Nadawca i domena pocztowa, SPF/DKIM/DMARC, odbiór odpowiedzi (webhook/IMAP), zasady kontaktu i listy „nie kontaktować”, koszty.
3. Podstawa prawna i DPA, jeśli AI miałoby działać poza lokalnym modelem; polityka retencji rozmów.
4. Lista stron do pierwszego prawdziwego pobrania (z podstawą dostępu).
