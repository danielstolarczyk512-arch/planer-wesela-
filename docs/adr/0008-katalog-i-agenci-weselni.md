# ADR-0008: Katalog firm, agent badawczy i asystent doboru usługodawców

- Status: zaakceptowany (etap 0 pakietu „agenci weselni”), Data: 2026-10-25

## Kontekst
Para szuka usługodawców ręcznie (prywatny `Vendor`, zapytania do skopiowania). Pakiet z 25.10.2026
opisuje dwie role produktu: **badacz katalogu** (cyklicznie aktualizuje wspólny katalog z dozwolonych
źródeł) i **asystent pary** (czat w aplikacji: dobór firm, prywatne zapytania). To role produktu,
nie dwa modele ani framework wieloagentowy.

## Decyzja
1. **Dwa światy danych.** Wspólny, publiczny katalog (`catalog_*`: firmy, pakiety, fakty z dowodami)
   jest osobny od prywatnych danych wesela (`vendors`, oferty, rozmowy, zapytania). Katalog nigdy
   nie dostaje budżetów, wiadomości ani indywidualnych wycen. Powiązanie prywatnego `Vendor` z firmą
   z katalogu jest jawne (nullable `catalog_vendor_id`), a aktualizacja katalogu nie nadpisuje
   notatek i ustaleń pary.
2. **Moduły** jednego backendu (bez mikroserwisów): `catalog` (firmy, fakty, publikacja, API),
   `discovery` (źródła, pobieranie, ekstrakcja, harmonogram), później `concierge` (czat, preferencje)
   i `inquiries` (prywatna korespondencja). Badacz widzi tylko katalog i zminimalizowane zlecenie
   (kategoria, region), nigdy prywatne oferty i rozmowy.
3. **Kolejka:** istniejąca kolejka PostgreSQL (ADR-0003). Nowy tor workera `discovery` obsługuje
   wyłącznie zadania researchu; tor `all` ich **nie** przejmuje (`claim_next(exclude=…)`), więc
   ograniczenia sieciowe nowego procesu nie da się ominąć. Osobny proces `discovery-scheduler`
   planuje zadania pod blokadą doradczą PostgreSQL (dwie repliki nie dublują zadań).
4. **Źródła:** tylko adresy podane przez administratora (`global_role = admin`) — „aktualizujemy
   podane strony”. Pobieranie HTML przez własnego klienta z ochroną przed SSRF (sprawdzenie DNS
   przy **każdym** połączeniu, w tym po przekierowaniu), limitami czasu/rozmiaru/przekierowań,
   `robots.txt`, `Retry-After`, 401/403/CAPTCHA = zatrzymanie źródła (bez obchodzenia), 404/410 =
   wycofanie z zachowaniem historii.
5. **Ekstrakcja deterministyczna** (JSON-LD, `tel:`/`mailto:`, linie z cenami) — bez LLM. Każdy fakt ma
   cytat z dowodu i datę. Brak ceny = „zapytaj o wycenę”, brak sezonu jawny. LLM nie czyta pobranych
   stron, więc instrukcje ukryte w HTML nie mają czym być wykonane (odporność z konstrukcji);
   użycie LLM do trudniejszych stron to osobna decyzja z ewaluacją (jak w ADR-0005).
6. **Wyszukiwanie nowych adresów:** adapter z jawnym stanem „nie skonfigurowano”. Nie ma wybranego
   legalnego, bezpłatnego dostawcy (poniżej), więc GUI mówi „aktualizujemy podane źródła, nie
   przeszukujemy całego internetu”. Bez scrapingu katalogów konkurencji i wyszukiwarek, bez obchodzenia
   zabezpieczeń.
7. **Czat (etap 2):** narzędzia o zamkniętych schematach, `wedding_id` z kontekstu serwera, model bez
   SQL/powłoki/sekretów i bez możliwości wysyłki. Wysyłka zapytań (etap 3) to osobny endpoint
   uruchamiany zatwierdzającą akcją UI; w MVP poczta trafia wyłącznie do Mailpit.

## Źródła nowych adresów — ocena (do weryfikacji przed użyciem)
| Źródło | Ocena |
|---|---|
| Google Places API | płatne, ograniczenia przechowywania/atrybucji — wymaga zgody właściciela na koszt |
| Meta (Facebook/Instagram) | automatyczne zbieranie bez zezwolenia zabronione — pomijamy |
| Wyszukiwarki ogólne | API płatne lub scraping wyników (zabroniony) — brak |
| SearXNG | AGPL i meta-scraping wyszukiwarek — wykluczone (ADR-0006) |
| OpenStreetMap (Overpass) | dane firm (np. `craft=photographer`) na licencji ODbL; wymaga oceny obowiązków share-alike i atrybucji — kandydat na późniejszy adapter po opinii prawnej |
| Własne zgłoszenia firm | formularz „dodaj swoją firmę” (v2) — najczystsze prawnie |

Ocena z wiedzy projektowej, nieweryfikowana online w tej sesji — przed wdrożeniem adaptera sprawdzić aktualne warunki.

## Konsekwencje
+ zero nowych usług i zależności (httpx i stdlib), katalog niezależny od wesel (usunięcie wesela
  nie rusza katalogu), dowody przy każdym fakcie.
− praca całodobowa wymaga stale włączonego hosta (Docker); ekstrakcja regułowa pokryje tylko strony
  z czytelnymi cenami; poziom sieciowy blokady adresów wewnętrznych to zabezpieczenie aplikacyjne
  (Docker nie filtruje wyjścia per adres) — na produkcji dodać regułę zapory hosta.

## Odrzucone
Redis/Celery i framework agentowy (brak wykazanej potrzeby), jeden wspólny `Vendor` dla katalogu
i wesela (mieszanie danych prywatnych i publicznych), LLM czytający surowe strony, scraping katalogów
konkurencji.
