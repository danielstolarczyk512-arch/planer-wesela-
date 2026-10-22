# 04. Plan rozwoju: jak być wyraźnie lepszym planerem i na czym zarabiać

Stan: 2026-10-20. Dokument powstał w 4 rundach: krytyczna ocena („Wesele z klasą” i nasza
aplikacja) → wyszukiwanie w internecie → wnioski → korekta listy. Uzupełnia
[03-porownanie-wesele-z-klasa.md](03-porownanie-wesele-z-klasa.md) (lista braków A1–C3).

**Stan wdrożenia (2026-10-20):** zrobione v1.1 — opis w
[raporcie usprawnień v1.1](../gui/raport-usprawnienia-v1-1.md); pozostałe punkty w
[planie dokończenia v1.1](../plan-dokonczenie-v1-1.md) i [jego raporcie](../gui/raport-dokonczenie-v1-1.md).
Status w tabelach „Rozpiska”: ✅ zrobione · ⏳ częściowo · ⏸ odłożone · ✖ odrzucone.

Oznaczenia: **[Ź]** fakt ze źródła (lista na końcu), **[O]** obserwacja z przejścia po aplikacji,
**[H]** hipoteza do sprawdzenia z parami. Ceny konkurencji z dnia odczytu — mogą się zmienić.

---

## Runda 1 — krytyka obu aplikacji i problemy par

### Wesele z klasą — słabe strony [O]
- Planer to dodatek do katalogu firm: skróty „Znajdź fotografa”, blog, reklama strony ślubnej.
- Lista gości płaska (osoba po osobie, ikony bez opisu), brak gospodarstw i odpowiedzi „za całą rodzinę”.
- Budżet to tabela cena–zaliczka–pozostało: brak terminów rat, przypomnień, zadatku vs zaliczki,
  kosztu zależnego od liczby gości.
- Plan stołów na WWW to lista; edytor wizualny tylko w aplikacji mobilnej.
- Brak harmonogramu dnia z godzinami, brak jakiejkolwiek pracy z ofertami i umowami.
- Grywalizacja (diamenty, odznaki) i Q&A służą treściom portalu, nie organizacji.

### Nasza aplikacja — słabe strony [O] (przejście po „Wesele demo”)
- **K1. Nasza przewaga jest schowana.** „Usługodawcy i oferty”, „Dokumenty”, „Harmonogram dnia”
  i „Plan stołów” są w zakładce „Więcej”. Nowa para widzi zwykły planer.
- **K2. Lawina zaległości na starcie.** Para zakładająca wesele 10 miesięcy przed datą dostaje
  od razu „8 zadań po terminie” — demotywuje i zniekształca ekran „Dziś”.
- **K3. Cienki szablon zadań:** 31 zadań wobec 82 u lidera; brak wskazówek, list dokumentów,
  zadań na dzień ślubu i po ślubie.
- **K4. Budżet bez planu:** wszystkie kategorie „bez planu” — podział budżetu nie jest częścią
  startu, więc wskaźnik „wykorzystano 79%” nie mówi, gdzie jest problem.
- **K5. Brak wydruków** (poza harmonogramem): sala dostaje plan stołów „z telefonu”.
- **K6. Wyróżnik zależy od AI**, a AI ma być na start wyłączone (hosting). Bez AI ręczne
  wprowadzenie oferty musi być szybkie, inaczej przewaga znika.
- **K7. Brak strony dla gości** — RSVP to formularz bez informacji (dojazd, nocleg, plan).

### Czego szukają pary [Ź]
Najczęstsze błędy wg praktyków (DJ, agencje): za późna rezerwacja sali i muzyki, budżet bez
rezerwy 10–15%, niedoszacowana liczba gości, **brak harmonogramu dnia**, brak umów na piśmie,
**brak planu B** (pogoda, opóźnienia), **brak komunikacji z usługodawcami** (każdy musi znać
harmonogram), **brak osoby koordynującej w dniu ślubu**, pominięte grupy gości (dzieci, seniorzy,
niepijący, goście spoza miasta), zapomniane koszty (noclegi, transport, poprawiny).
Rankingi 2026 oceniają planery po: logice terminów, **ratach i przypomnieniach o dopłatach**,
RSVP z dietami i osobami towarzyszącymi, przydatności w dniu ślubu, pracy we dwoje.

**Wniosek rundy 1:** pary nie potrzebują „dłuższej listy”, tylko systemu, w którym jedna zmiana
(liczba gości, odpowiedź gościa, przesunięcie godziny) od razu aktualizuje koszt, stoły, catering
i harmonogram — oraz pomocy w **dniu ślubu**, gdzie dziś są zdani na kartki i telefony.

---

## Runda 2 — organizacja i dzień ślubu

**Rynek [Ź]:** w 2026 powstał osobny segment aplikacji „day-of / run of show” (AisleTimeline,
EventSync, Ever Timeline, ringbearer, Elos, Coordon). Wspólne cechy:
- jeden scenariusz dnia, z którego **każdy usługodawca widzi swój widok** (godzina przyjazdu
  fotografa, próba dźwięku zespołu), udostępniany linkiem tylko do odczytu i odwoływalny;
- **tryb na żywo**: baner „teraz dzieje się…”, przesunięcie wszystkich kolejnych punktów jednym
  ruchem, gdy ceremonia się opóźni;
- działanie offline na sali, wydruk jednej strony dla koordynatora, listy ujęć dla fotografa.
Coordon pozycjonuje się wprost hasłem „planowanie + dzień ślubu w jednym” bez katalogu firm.

**Weryfikacja u nas:** mamy harmonogram z wykrywaniem konfliktów i role członków — brakuje
linków dla usługodawców (znane ograniczenie nr 27), trybu na żywo i wydruku.

**Korekta listy:** dochodzi filar **„Dzień ślubu”** (D1–D5 niżej). To naturalne przedłużenie
naszej przewagi: znamy usługodawców, umowy, godziny i gości — konkurencja z katalogiem nie zna.

---

## Runda 3 — usługi płatne: co już się sprzedaje w Polsce [Ź]

| Usługa | Ceny na rynku PL | Nasycenie |
|---|---|---|
| Galeria zdjęć od gości przez QR | 29,99 zł – 999 zł jednorazowo (SnapThis, Wspólna Galeria od 69 zł, Album QR 149 zł, goscie.app 999 zł) | **bardzo duże** (10+ firm) |
| E-zaproszenia z RSVP | od 29 zł (e-zaproszenie.pl), wiele podobnych | duże |
| Strona ślubna | Wesele z klasą 19–34 zł/mies. | średnie |
| Planer w abonamencie | Wedding Board 59 zł/mies. (sadzanie z regułami, PDF dla sali, winietki, lista dla cateringu); Wedly 79–149 zł/mies. (AI, beta) | rośnie |
| Zagranica | The Private Wedding App 19,99 $/mies. lub **189 $ jednorazowo**; Zola: plan stołów 14,99 $, SMS do gości do 79,99 $ | — |
| Koordynacja dnia ślubu (człowiek) | **4 000–8 000 zł**, średnio ok. 5 100 zł; konsultacja 200–500 zł | — |
| Sprawdzenie umowy przez prawnika | **499–899 zł** (Poprawnik), inni „kilkaset zł” | — |

**Wnioski:**
1. **Automatyczne sadzanie przestało być wyróżnikiem** (Wedding Board ma reguły i PDF). Robimy je
   dobrze, ale nie sprzedajemy jako główną przewagę.
2. **Galeria QR i e-zaproszenia** — rynek zatłoczony, niskie ceny, wysokie ryzyko (wizerunek gości,
   przechowywanie, moderacja). Nie budujemy sami na start; ewentualnie integracja/partner.
3. Ludzie **płacą tysiące za koordynację i setki za sprawdzenie umowy** — to dokładnie nasz obszar.
   Pakiet, który daje 30–50% tej wartości za ułamek ceny, ma sens.
4. Wesele to projekt na 12–18 miesięcy: abonament 59–79 zł/mies. daje razem 700–1 400 zł i
   zniechęca. **Jednorazowa opłata „na całe wesele”** (jak 189 $ u Private Wedding App, nasze
   założenie 299 zł) jest uczciwsza i łatwiejsza do sprzedania [H].

---

## Runda 4 — wykonalność, prawo, płatności

- **Bramki płatności [Ź]:** BLIK w Przelewy24 ok. 1,2% + 0,30 zł; Tpay/Autopay podobnie; Stripe
  droższy na BLIK. Przy 299 zł prowizja ≈ 3,9 zł. Bramka = umowa z firmą → **decyzja właściciela**
  (wymaga działalności gospodarczej, regulaminu, faktur).
- **SMS [Ź]:** bramki PL ok. 0,08–0,17 zł/SMS (często abonament ok. 49 zł/mies. dla niższej
  stawki). Pakiet SMS do gości jest opłacalny, ale to **płatna usługa zewnętrzna** → zgoda
  właściciela + umowa powierzenia (numery telefonów gości).
- **Umowy:** analiza ryzyk przez nas = porada prawna (ryzyko). Bezpieczny model: my porządkujemy
  dane i listę pytań („czego brakuje w umowie” jako lista kontrolna, bez oceny prawnej), a
  **ocenę robi współpracujący prawnik** (płatna usługa partnera, prowizja) → opinia prawna i
  umowa z kancelarią wymagane.
- **Programy dla sal [Ź]** (WeddiFlow, Anolla, Univents, ProMenu) — rynek zajęty. Salę traktujemy
  jako **odbiorcę darmowego linku** od pary (plan stołów, diety, liczby), co jest kanałem
  polecającym nas parom, nie źródłem przychodu.
- **Konsument:** sprzedaż treści cyfrowych wymaga zgody na wykonanie przed upływem 14 dni i
  potwierdzenia utraty prawa odstąpienia; regulamin i polityka są robocze → **prawnik**.

**Korekta końcowa:** pozycjonowanie „**Wasz osobisty koordynator: pieniądze, umowy i dzień ślubu
pod kontrolą**”. Darmowy rdzeń musi być nie gorszy niż u lidera (inaczej nikt nie przejdzie),
a płacimy za to, co zastępuje koordynatora i stres finansowy.

---

## Rozpiska: co wprowadzić do programu

Nakład: S (do 3 dni), M (1–2 tyg.), L (3+ tyg.). Plan: **F** = darmowe, **P** = Premium.

### Etap 0 — dokończyć (przed wszystkim)
| ID | Zadanie | Nakład | Status |
|---|---|---|---|
| E0.1 | MFA: naprawa E2E, commit (w toku) | S | ✅ commit `e21c6db` |

### Etap 1 — „pierwsze 10 minut” i parytet z liderem (darmowe, v1.1)
| ID | Funkcja | Dlaczego | Moduły | Kryterium gotowości | Nakład | Plan | Status |
|---|---|---|---|---|---|---|---|
| N1 | **Nowa nawigacja**: Dziś · Plan · Pieniądze (budżet + usługodawcy + oferty + płatności) · Goście (+ stoły) · Dzień (harmonogram + na żywo) | K1 | frontend `shell`, `wedding` | wszystkie wyróżniki ≤ 1 dotknięcie; E2E 8 profili | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| N2 | **Tryb nadrabiania** przy późnym starcie: zaległe zadania z szablonu rozłożone na najbliższe tygodnie wg priorytetu, „3 najważniejsze teraz” na Dziś | K2 | `planner` (przeliczenie terminów), `TodayView` | nowe wesele < 12 mies. przed datą nie ma zadań „po terminie” | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| N3 | **Szablon zadań 31 → ok. 80** z okresami, dniem ślubu, „po ślubie” (zmiana nazwiska, rozliczenia) — własne treści | K3 | `planner/templates.py` | wersja `2027.1`, testy zależności | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| N4 | **Wskazówki przy zadaniach** (A1) | K3 | `planner` | każde zadanie szablonu ma wskazówkę | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| N5 | **Listy dokumentów** wg typu ceremonii + „uzupełnij z szablonu” po zmianie ceremonii (A3, ogr. nr 11) | lider ma | `planner` | podzadania + podgląd zmian | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| N6 | **Start z podziałem budżetu**: kwota + liczba gości → plan kategorii (mamy endpoint) w kreatorze | K4 | `budget`, onboarding | żadna kategoria „bez planu” po starcie | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| N7 | **Okresy w planie** (A8), zadanie ↔ usługodawca (A6), godzina terminu (A9) | lider ma | `planner`, `vendors` | — | S | F | ⏳ zadanie↔usługodawca ✅; okresy i godzina ✖ ([raport](../gui/raport-usprawnienia-v1-1.md)) |
| N8 | **Wydruki/PDF przez druk przeglądarki** (A5): goście, plan stołów dla sali z dietami, winietki, budżet, zadania | K5 | frontend `print.css` | wydruk A4 czytelny, bez nawigacji | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |

### Etap 2 — wyróżnik „Pieniądze i umowy” (v1.2)
| ID | Funkcja | Dlaczego | Moduły | Kryterium gotowości | Nakład | Plan | Status |
|---|---|---|---|---|---|---|---|
| M1 | **Szybkie wprowadzanie oferty bez AI**: szablony typowych ofert (sala „za talerzyk” z dziećmi, napojami, poprawinami; fotograf pakiet; DJ godziny) | K6 — przewaga działa bez AI | `offers`, `OfferEditor` | oferta sali w < 3 min | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| M2 | **Pytania do usługodawców** z odpowiedziami w porównaniu ofert (A4) | lider ma listy; my łączymy z ceną | `vendors`, `CompareView` | odpowiedzi widoczne obok ceny | M | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| M3 | **Lista kontrolna umowy** (czy jest: termin, cena za osobę, minimum gości, zadatek/zaliczka, rezygnacja, godziny, nadgodziny, korkowe, posiłek obsługi) — bez oceny prawnej, z odesłaniem do prawnika | błąd nr 7 „brak umów”; ludzie płacą 499–899 zł za analizę | `documents`, `offers` | lista przy każdej umowie; tekst zatwierdzony przez prawnika | M | **P** | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) (tekst do zatwierdzenia przez prawnika) |
| M4 | **AI: odczyt harmonogramu rat z umowy** (ogr. nr 23) jako szkic do zatwierdzenia | oszczędza wpisywanie | `ai` | ewaluacja na korpusie | M | **P** | ⏸ AI na start wyłączone |
| M5 | **Scenariusze „co jeśli”**: +20 gości, poprawiny tak/nie, inna sala → różnica kosztu i rat | nikt tego nie ma | `offers/pricing`, `budget` | porównanie 2 scenariuszy | M | **P** | ✅ [raport](../gui/raport-dokonczenie-v1-1.md) (dwa scenariusze, raty) |
| M6 | **Obsługa na sali** (posiłki/miejsca zespołu, fotografa) w koszcie i stołach (A7) | ukryty koszt | `vendors`, `pricing`, `seating` | — | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| M7 | **Kalendarz + subskrypcja ICS** (zadania, raty, wydarzenia) (A2) | ranking: przypomnienia o dopłatach | `overview` | prywatny link odwoływalny | M | F (ICS: **P**) | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |

### Etap 3 — wyróżnik „Dzień ślubu” (v1.2–v1.3)
| ID | Funkcja | Dlaczego | Moduły | Kryterium gotowości | Nakład | Plan | Status |
|---|---|---|---|---|---|---|---|
| D1 | **Linki dla usługodawców**: każdy widzi swoje punkty harmonogramu, kontakt do koordynatora, adres; tylko odczyt, odwoływalne (ogr. nr 27) | segment „run of show” | `schedule` (tokeny jak RSVP) | link bez logowania, bez danych gości | M | **P** | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| D2 | **Rola „Koordynator dnia”** (świadek/rodzina): widzi harmonogram, kontakty, listę rzeczy do zabrania, plan B; bez budżetu | błąd nr 15 „brak koordynatora” | `workspace/permissions` | nowa rola + E2E | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| D3 | **Tryb na żywo**: „teraz / za chwilę”, przesunięcie kolejnych punktów o X min, widoczne w linkach D1; działa offline (PWA) | segment „day-of” | `schedule`, SW | przesunięcie widoczne < 5 s u usługodawcy | L | **P** | ✅ tryb na żywo ([raport v1.1](../gui/raport-usprawnienia-v1-1.md)); bez sieci — kopia programu ([raport](../gui/raport-dokonczenie-v1-1.md)) |
| D4 | **Plan B** przy punktach harmonogramu (deszcz, opóźnienie) + **lista „koszyk ratunkowy”** | błąd nr 10 | `schedule`, `planner` | — | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| D5 | **Wydruk scenariusza dnia** na 1 stronę dla koordynatora i sali | segment „day-of” | frontend print | — | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |

### Etap 4 — goście bez dzwonienia (v1.3)
| ID | Funkcja | Dlaczego | Moduły | Kryterium gotowości | Nakład | Plan | Status |
|---|---|---|---|---|---|---|---|
| G1 | **Strona informacyjna pod linkiem RSVP** (B1): dojazd (link do mapy), plan dnia (tylko wydarzenia dla gości), nocleg, transport, dress code, prezenty | lider sprzedaje za 19–34 zł/mies. | `guests`, `schedule` | podgląd „jak zobaczy gość” | M | F (podstawowa) / **P** (motywy, własny tekst powitania, QR na zaproszenie) | ✅ podstawa ([raport v1.1](../gui/raport-usprawnienia-v1-1.md)); QR i wygląd ([raport](../gui/raport-dokonczenie-v1-1.md)) |
| G2 | **Osoba towarzysząca w RSVP** (ogr. nr 12) — **decyzja właściciela** o limicie | ranking: plus-one | `guests` | — | S | F | ✅ bez limitu miejsc (decyzja 2026-10-20) |
| G3 | **Przypomnienia RSVP e-mailem** (gość z e-mailem), a **SMS jako pakiet** | „telefony po rodzinie” | `notifications` (+ bramka SMS) | wysyłka z limitem i zgodą | M | e-mail F / SMS **P** (pakiet) | ⏳ e-mail ✅; SMS ⏸ (płatna usługa) |
| G4 | **Liczby dla cateringu i sali**: diety, dzieci, obsługa na stół; eksport po każdej zmianie | „jedna odpowiedź aktualizuje wszystko” | `seating`, `guests` | wydruk i link dla sali | S | F | ✅ wydruk i link dla sali ([raport](../gui/raport-dokonczenie-v1-1.md)) |
| G5 | **Prezenty i podziękowania** (kto, co, podziękowanie wysłane) — po weselu | polski zwyczaj kopert; brak u konkurencji [H] | `guests` | — | S | F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |

### Etap 5 — opcjonalnie / później
| ID | Funkcja | Uwagi | Status |
|---|---|---|---|
| L1 | Kalkulator alkoholu i napojów (liczba gości, godziny, niepijący) → pozycja budżetu | popularny temat poradników [H]; S, F | ✅ [raport](../gui/raport-usprawnienia-v1-1.md) |
| L2 | Motyw/kolor przewodni, tablica inspiracji (własne zdjęcia) (B2) | M, F | ⏸ poza zakresem |
| L3 | Konto dla wedding plannerki: wiele wesel, jej logo w linkach, szablony | Aisle Planner 25–40 $/mies.; **B2B 99–199 zł/mies.** [H]; L | ⏸ decyzja biznesowa |
| L4 | Galeria zdjęć od gości / księga życzeń (C1) | **nie budować na start** — rynek zatłoczony, RODO; ewentualnie partner | ✖ nie budować na start |
| L5 | Sprawdzenie umowy przez prawnika-partnera (z M3) | prowizja od usługi 499–899 zł; **opinia prawna + umowa z kancelarią** | ⏸ wymaga opinii prawnej i umowy z kancelarią |

---

## Model płatny — propozycja do decyzji właściciela

| Plan | Cena (propozycja) | Zawartość |
|---|---|---|
| **Darmowy** | 0 zł | wszystko z Etapu 1, budżet z ratami, goście i RSVP e-mail, plan stołów z automatem, harmonogram, podstawowa strona dla gości, wydruki |
| **Premium „na całe wesele”** | **299 zł jednorazowo** (do 3 mies. po dacie ślubu; potem dostęp tylko do odczytu i eksport) | M3–M5, ICS, D1 + D3 (linki dla usługodawców i tryb na żywo), AI (gdy włączone), motywy strony dla gości |
| **Pakiet SMS** | np. 100 SMS za 29 zł | przypomnienia RSVP i informacje w dniu ślubu (koszt ok. 9–17 zł) |
| **Plannerka (B2B)** | 99–199 zł/mies. | L3 |
| **Usługi partnerów** | prowizja | prawnik (L5), ewentualnie galeria QR (L4) |

Uzasadnienie: koordynator kosztuje ok. 5 000 zł, analiza umowy 499–899 zł; Premium za 299 zł
zastępuje część tej pracy. Abonament miesięczny przegrywa przy projekcie na 12–18 miesięcy [H].

## Decyzje właściciela (nie wdrażamy bez nich)
1. Model cenowy i ceny (tabela wyżej); działalność, bramka płatności (Przelewy24/Tpay — BLIK).
2. Dostawca SMS (płatny) i umowa powierzenia danych gości.
3. Treść listy kontrolnej umowy (M3) i ewentualna współpraca z kancelarią (L5) — prawnik.
4. Osoba towarzysząca w RSVP (G2) — limit miejsc.
5. Czy galeria zdjęć gości w ogóle (L4) — własna czy partner.
6. Regulamin, polityka, prawo odstąpienia dla treści cyfrowych — prawnik.

## Kolejność
E0 → Etap 1 (N1, N2, N6 najpierw — pierwsze wrażenie) → Etap 2 (M1, M2, M6, M7) →
Etap 3 (D2, D4, D5, potem D1, D3) → Etap 4 → Premium (M3–M5, D1/D3, ICS) po decyzjach 1–3.
Każdy krok: backend + testy → `task web:types` → GUI → E2E (8 profili, axe) → raport `docs/gui/`.

## Weryfikacja z parami (przed wydaniem Premium) [H]
- 5–8 wywiadów: czy zapłacą 299 zł jednorazowo; które z M3/M5/D1/D3 są „warte pieniędzy”.
- Test z prawdziwymi ofertami: czas wprowadzenia oferty bez AI (cel < 3 min).
- Test dnia ślubu z jednym usługodawcą (DJ lub fotograf) — czy link D1 jest dla niego użyteczny.

## Źródła (odczyt 2026-10-20)
- Planer Wesele z klasą (konto właściciela): weselezklasa.pl/planer/, /planer/harmonogram, /lista-gosci, /plan-stolow, /budzet, /strona-slubna/
- Rankingi 2026: rosevow.com/planning/best-wedding-planning-apps; theprivateweddingapp.com/blog/best-wedding-planning-apps-2026; coordon.com/en/blog/best-wedding-planning-apps
- Błędy par: wesela-muzyka-zabawa.com/post/organizacja-wesela-top-20-bledow; vipevents.pl/organizacja-wesela-10-rzeczy-pary-zapominaja-blog/
- Dzień ślubu: aisletimeline.com, geteventsync.app, evertimeline.app, ringbearer.ai/product/day-of-timeline, tryelos.com/tools/day-of-timeline (opisy z wyników wyszukiwania)
- Galerie QR (ceny z opisów wyników): snapthis.pl, wspolnagaleria.pl, albumqr.io/pl, goscie.app, weddie.app/pl
- E-zaproszenia: e-zaproszenie.pl (od 29 zł)
- Planery PL: weddingboard.pl/pl/aplikacja (59 zł/mies.), wedly.com.pl (79–149 zł/mies., beta)
- Koordynacja: cenauslug.pl (śr. 5 096 zł), pswp.pl (4–8 tys. zł), paperstudio.pl (konsultacja 200–500 zł)
- Analiza umów: poprawnik.com/uslugi/analiza-umow (499–899 zł)
- Płatności i SMS: feeflowcalculator.com/przelewy24 (BLIK 1,2% + 0,30 zł), sendly.link/pl/blog/ile-kosztuje-sms-w-polsce-2026/, sms-api.pl (poniżej 9 gr/SMS)
- Programy dla sal: weddiflow.pl, anolla.com/pl, univents.app/pl, promenu.pl
