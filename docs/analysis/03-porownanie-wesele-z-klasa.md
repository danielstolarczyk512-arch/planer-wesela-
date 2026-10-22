# 03. Porównanie z planerem „Wesele z klasą” i plan uzupełnień

Przegląd planera www.weselezklasa.pl/planer/ na koncie właściciela, 2026-10-20 (ręczne
przejście po ekranach jak użytkownik, bez pobierania treści). Opisujemy **funkcje**, nie
kopiujemy tekstów, list zadań ani wyglądu — wszystkie treści (podpowiedzi, listy pytań)
piszemy sami.

## 1. Co ma planer konkurencji

| Moduł | Funkcje |
|---|---|
| Start | odliczanie z wyborem wyglądu („Zmień widget”), wskaźniki: postęp zadań, wybrane firmy, potwierdzeni i rozmieszczeni goście, wykorzystanie budżetu; grywalizacja (diamenty, odznaki), blog |
| Lista zadań | gotowe etapy I–V, „Dzień ślubu”, „Po ślubie”, **listy dokumentów do ślubu konkordatowego i cywilnego**; przy zadaniu **„Sprawdź wskazówki”** i skrót do katalogu firm; edycja: notatka, etap, **przypisana firma**, data **i godzina**; własne etapy, zmiana kolejności; **kalendarz zadań**; **eksport do PDF**; „Twój niezbędnik” — **listy pytań do sali, salonu sukien, fotografa, kamerzysty, DJ-a, zespołu, wynajmu aut** |
| Lista gości | grupy; przy gościu: zaproszenie, potwierdzenie, przyjęcie, zniżka, nocleg, transport, dieta, notatka oraz **znacznik „usługodawca”** (np. fotograf jako osoba na sali) |
| Plan stołów | stoły prostokątne/okrągłe, liczba miejsc „od–do”, ostrzeżenie o przepełnieniu, **PDF z listą stołów**, podsumowanie; edytor wizualny tylko w aplikacji mobilnej |
| Budżet | grupy z gotowymi pozycjami (cena, zaliczka, pozostało, notatka), filtry „zapłacone” i „wliczone do budżetu”, **PDF budżetu**, podsumowanie |
| Strona ślubna (płatna, od 19 zł/mies.) | 15 szablonów, własny adres, hasło, mapa, plan dnia, RSVP z menu i dietami, historia pary, **galeria zdjęć od gości przez kod QR na stole**, **księga życzeń**, film, do 6 języków |
| Społeczność / portal | Ślubne Q&A, inspiracje (zapisane zdjęcia), wiadomości z firmami, katalog firm, aplikacja mobilna, zaproszenie partnera do planera |

## 2. Gdzie jesteśmy mocniejsi (nie zmieniać kierunku)

Oferty i umowy z **realnym kosztem przy tej samej liczbie gości**, porównanie ofert, AI czytające
oferty (lokalnie, z cytatami), harmonogram płatności i zaległości, zależności zadań, terminy
liczone od daty ślubu i typu ceremonii, harmonogram dnia z wykrywaniem konfliktów, reguły
sadzania i automatyczny przydział, RSVP osobno dla każdego wydarzenia, role członków, MFA,
eksport i usunięcie danych (RODO), PWA z trybem offline. Konkurencja nie ma niczego z tej listy.

## 3. Braki u nas — ocena

Skala: wartość dla pary / nakład / ryzyko (prawne, utrzymanie).

| # | Funkcja | Wartość | Nakład | Ryzyko | Rekomendacja |
|---|---|---|---|---|---|
| A1 | **Wskazówki przy zadaniach** (krótkie „jak to zrobić, o co zapytać, na co uważać”) | wysoka | mały | niskie (własne treści) | v1.1 |
| A2 | **Widok kalendarza** (zadania, raty, wydarzenia w jednym miesiącu) + **subskrypcja ICS** do Google/Apple | wysoka | średni | niskie | v1.1 |
| A3 | **Listy dokumentów do ślubu** wg typu ceremonii jako podzadania (mamy `parent_task_id`) | wysoka | mały | średnie — zasady parafii/USC się różnią: zawsze „sprawdźcie u źródła” | v1.1 |
| A4 | **Pytania do usługodawcy** wg kategorii, z miejscem na odpowiedź, widoczne w porównaniu ofert | wysoka (łączy się z naszą przewagą) | średni | niskie | v1.1 |
| A5 | **Wydruk / PDF**: lista gości, plan stołów dla sali (z dietami), winietki, budżet, lista zadań | wysoka | mały–średni | niskie | v1.1 |
| A6 | **Zadanie powiązane z usługodawcą** (i odwrotnie: zadania na karcie firmy) | średnia | mały | niskie | v1.1 |
| A7 | **Obsługa na sali** (fotograf, zespół — posiłki i miejsca), liczona w koszcie wesela | średnia | mały | niskie | v1.1 |
| A8 | **Grupowanie zadań w okresy** („12+ mies.”, „6–12”, …, „Dzień ślubu”, „Po ślubie”) | średnia (czytelność) | mały | niskie | v1.1 |
| A9 | Godzina przy terminie zadania | niska | mały | niskie | razem z A2 |
| B1 | **Strona informacyjna dla gości** pod istniejącym linkiem RSVP: dojazd (link do mapy), plan dnia, nocleg, transport, dress code, prezenty, kontakt | wysoka | średni | średnie — dane gości, dostęp tylko z tokenem | v1.2 |
| B2 | Kolor/motyw przewodni i tablica inspiracji (własne zdjęcia i linki) | niska–średnia | średni | niskie | v1.2 |
| B3 | Wygląd odliczania (kilka wariantów w naszym stylu) | niska | mały | niskie | opcjonalnie |
| C1 | **Galeria zdjęć od gości (QR) i księga życzeń** | średnia–wysoka | duży | **wysokie**: wizerunek osób, moderacja, skan plików (ClamAV), koszt przechowywania | v2, **decyzja właściciela** |
| C2 | Wersje językowe strony dla gości | niska (PL rynek) | średni | niskie | v2 |
| C3 | Q&A społeczności, blog, grywalizacja, wiadomości z firmami | niska dla naszego profilu | duży | moderacja, regulamin | nie robimy (katalog firm i tak w v2) |

## 4. Jak to wdrożyć spójnie (wzorce projektu)

Wszystko w istniejących modułach, z `version`/`If-Match`, błędami RFC 9457, testami API,
regenerowanymi typami (`task web:types`), komponentami React Aria i tokenami `--wp-*`.
Żadnych nowych zależności z licencją copyleft; PDF przez arkusz stylów druku (przeglądarka
„Zapisz jako PDF”) — bez bibliotek serwerowych.

**A1 Wskazówki.** `TaskTemplate.tip` (krótki tekst, nasz) + pole `Task.guide_code`; treści
wersjonowane w kodzie jak szablony (`TEMPLATE_VERSION`). GUI: w `EditTaskSheet` rozwijana sekcja
„Wskazówki”, przy zadaniach powiązanych z kategorią usługodawcy przycisk „Dodaj usługodawcę”
(nasz moduł, nie katalog). Bez migracji danych istniejących zadań — wskazówka dobierana po
`template_code`.

**A2 Kalendarz + ICS.** Endpoint `GET /weddings/{id}/calendar?from&to` w `overview` składający
zadania, raty (`Payment.due_date`) i wydarzenia. Widok miesiąca w `PlanView` (przełącznik
Lista/Kalendarz, `Segmented`); na 320 px lista dni zamiast siatki. ICS: prywatny adres z tokenem
(jak RSVP: hash w bazie, unieważnianie w ustawieniach), bez danych gości w treści wpisów.
Format ICS generujemy sami (prosty tekst, RFC 5545) — bez bibliotek.

**A3 Dokumenty.** W szablonach zadanie-rodzic „Dokumenty do ślubu (…)” z podzadaniami zależnymi
od `ceremony_type`. Dotyczy to też istniejącego punktu backlogu „uzupełnij zadania z szablonu po
zmianie typu ceremonii” — robić razem. Każda lista z adnotacją „wymagania potwierdźcie w parafii/USC”.

**A4 Pytania do usługodawcy.** Nowa tabela `vendor_questions` (vendor_id, code/treść, answer,
sort_order) w module `vendors`; zestawy startowe wg kategorii usługodawcy w `vendors/templates.py`.
GUI: zakładka „Pytania” w `VendorView`; w `CompareView` wiersze z odpowiedziami obok cen.
AI (opcjonalnie później): podpowiedź odpowiedzi z odczytanej oferty, zawsze jako szkic z cytatem.

**A5 Wydruki.** Wspólny `print.css` (ukrycie nawigacji, czarno-biały, podział stron) i przycisk
„Drukuj / PDF” w Goście, Plan stołów, Budżet, Plan. Plan stołów dla sali: stół → goście + diety
+ dzieci; winietki: siatka kart do wycięcia. Wydruk z dietami zawiera dane wrażliwe — krótka
informacja przed drukiem.

**A6 Zadanie ↔ usługodawca.** `Task.vendor_id` (FK, `SET NULL`), wybór w `EditTaskSheet`, lista
zadań na `VendorView`.

**A7 Obsługa na sali.** `Vendor.crew_count` (+ czy posiłek, czy miejsce przy stole); `pricing.py`
dolicza posiłki obsługi, gdy oferta sali ma cenę za posiłek dla obsługi; plan stołów pokazuje
osobną pozycję „Obsługa”. Nie mieszamy obsługi z gośćmi (RSVP, statystyki).

**A8 Okresy.** Wyłącznie GUI: grupowanie po `due_date` względem daty ślubu w `tasks.tsx`,
nagłówki sekcji z licznikiem „3/9”. Bez zmian w modelu.

**B1 Strona dla gości.** Rozszerzenie `/rsvp/:token`: sekcje informacyjne z nowego modelu
`GuestInfoPage` (wedding_id, bloki: dojazd, nocleg, transport, dress code, prezenty, kontakt;
flaga „opublikowane”). Plan dnia z `schedule` tylko dla wydarzeń oznaczonych jako widoczne dla
gości. Mapa wyłącznie jako link (bez osadzania zewnętrznych map — CSP i RODO). Edycja w
ustawieniach wesela z podglądem „jak zobaczy gość”.

## 5. Proponowana kolejność

1. Najpierw dokończyć i zacommitować MFA (w toku).
2. Pakiet „Plan” v1.1: A8 → A1 → A3 (+ uzupełnianie zadań po zmianie ceremonii) → A6 → A2.
3. Pakiet „Usługodawcy”: A4 → A7.
4. Pakiet „Wydruki”: A5.
5. B1 (po pakietach 2–4), B2/B3 opcjonalnie.
6. C1 tylko po decyzji właściciela (koszty przechowywania, regulamin, wizerunek gości, moderacja).

Każdy pakiet: backend + testy → typy → GUI → E2E w 8 profilach z axe → raport w `docs/gui/`.
