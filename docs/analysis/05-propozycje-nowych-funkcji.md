# 05. Dziesięć propozycji funkcji, których nie ma na rynku

Data: 2026-10-21. Status: propozycje do decyzji właściciela (nic nie jest jeszcze zrobione).

## Metoda

- Punkt wyjścia: nasze funkcje (CLAUDE.md, `docs/plan-dalszej-pracy.md`) i analiza `01-rynek-i-konkurencja.md`.
- Przegląd 2026-10-21 (WebSearch nie działał, więc wyszukiwarka DuckDuckGo w przeglądarce): Wesele z klasą,
  Wedding.pl, Bridebook, The Knot/Zola, Zankyou, Joy oraz nowe polskie aplikacje: **WeddingGo**, **Sposal**,
  **souveil**, **Asystent Weselny**, **Wedding Board**, Gatsby's party, kalkulatory (Notatnik Weselny).
- **Rynek ma już** (więc tego nie proponujemy): galerię zdjęć od gości z kodem QR, quiz i bingo, prośby
  o piosenki z głosowaniem, ogłoszenia na żywo dla gości, „AI copilot” i AI do planu stołów (WeddingGo),
  sejf na umowy, kreatory zaproszeń, osobne kalkulatory kopert i alkoholu na stronach z poradami.
- „Nie ma na rynku” oznacza: **nie znaleźliśmy tego w opisach tych aplikacji**. Przed dużą inwestycją
  trzeba to sprawdzić na kontach testowych i w wywiadach z parami (etap B).
- Każda propozycja opiera się na tym, co już mamy (realny koszt ofert, umowy, płatności, RSVP, harmonogram),
  bo dzięki temu konkurencji trudno ją skopiować.

Oznaczenia: nakład **S** (dni) / **M** (1–2 tygodnie) / **L** (więcej); ⚖️ = potrzebna weryfikacja prawna.

---

## 1. Strażnik waloryzacji cen — M ⚖️ ✅ zrobione 2026-10-22 (raport `docs/gui/raport-waloryzacja.md`)

**Problem:** salę i zespół rezerwuje się 1,5–2 lata wcześniej. Umowy często mają klauzulę waloryzacji
(„cena talerzyka może wzrosnąć o wskaźnik inflacji GUS”) albo cenę „wg cennika z roku wesela”. Para
dowiaduje się o podwyżce na kilka miesięcy przed ślubem.
**Funkcja:** przy umowie zaznaczamy (ręcznie albo z AI, jako szkic do zatwierdzenia) rodzaj klauzuli:
cena stała, inflacja GUS, cennik z roku wesela albo limit procentowy. Aplikacja pokazuje budżet
w trzech wariantach (dziś / prognoza / najgorszy przypadek) i przypomina o terminie aneksu.
Wskaźnik GUS wpisujemy z publicznego komunikatu, bez płatnych API.
**Dlaczego nowe:** inne budżety pokazują kwotę „na dziś”. Żadna aplikacja nie liczy ryzyka zmiany ceny.
**Na bazie:** `offers` (realny koszt, „co jeśli”), `budget`, `documents`.

## 2. Umowa zgodna z ofertą — M (AI)

**Problem:** w ofercie było „do 4:00, tort w cenie, minimum 80 osób”, a w umowie „do 3:00, minimum 90”.
Para podpisuje, bo nie porównuje 12 stron słowo po słowie.
**Funkcja:** po wgraniu umowy lokalny model porównuje ją z wybraną ofertą i listą kontrolną.
Pokazuje rozbieżności z cytatami z obu dokumentów: godziny, minimum gości, co jest w cenie, zadatek
czy zaliczka, kary za rezygnację. Wynik to szkic do zatwierdzenia. **Nie jest to porada prawna.**
**Dlaczego nowe:** konkurencja przechowuje umowy, ale ich nie czyta. To nasza nisza „rozumienia
ofert i umów” (analiza 01, pkt 2.7.5).
**Na bazie:** `ai` (szkic z cytatami), `vendors/checklists.py`, `offers`.

## 3. Prognoza frekwencji i lista rezerwowa — M ✅ zrobione 2026-10-21 (raport `docs/gui/raport-prognoza-frekwencji.md`)

**Problem:** zwykle część zaproszonych w końcu nie przychodzi, a sala liczy minimum gości i termin
podania ostatecznej liczby. Każdy pusty talerzyk to 250–600 zł. Pary po cichu trzymają w głowie
„drugą listę” osób, które zaprosiłyby, gdyby zwolniło się miejsce.
**Funkcja:** (a) prognoza: potwierdzeni + oczekujący × prawdopodobieństwo, czyli zakres
„przyjdzie 104–112 osób”, z kosztem wobec minimum z umowy; (b) lista rezerwowa z kolejnością.
Po odmowie aplikacja proponuje następną osobę i pilnuje terminu, po którym zaproszenie wyglądałoby
niezręcznie; (c) alert „za 9 dni sala chce ostatecznej liczby, brakuje odpowiedzi od 14 osób”.
**Dlaczego nowe:** RSVP mają wszyscy. Nikt nie łączy go z warunkami umowy z salą i drugą falą zaproszeń.
**Na bazie:** `guests` (RSVP), `offers` (minimum gości, termin), `notifications`.

## 4. Rozwożenie zaproszeń osobiście — S/M ✅ zrobione 2026-10-22 (raport `docs/gui/raport-wreczanie-zaproszen.md`)

**Problem:** w Polsce zaproszenia rodzinie wręcza się osobiście („babcia się obrazi, jak dostanie
SMS-a”). To dziesiątki wizyt w kilku miastach, rozłożone na tygodnie, z podziałem na stronę panny
młodej i pana młodego.
**Funkcja:** lista wizyt z gospodarstw domowych (kto wręcza, kiedy, adres, notatka), grupowanie
po miejscowości w „objazdy” na weekendy, odhaczanie „wręczone”, link do mapy (zwykły link `geo:`,
bez płatnego API) i przypomnienie „zostało 6 domów, do terminu RSVP 5 tygodni”.
**Dlaczego nowe:** aplikacje zakładają zaproszenia elektroniczne albo wysyłkę pocztą. Polskiej
tradycji wręczania nikt nie obsługuje.
**Na bazie:** `guests` (gospodarstwa), `planner` (zadania z terminami), kalendarz ICS.

## 5. Bilans wesela: koperty i koszt netto — S ⚖️

**Problem:** „Czy wesele się zwróci?” to jedno z najczęstszych pytań polskich par. Dziś odpowiadają
na nie osobne kalkulatory na blogach, oderwane od listy gości. Po weselu ktoś zapisuje na kartce,
od kogo była koperta, bo potrzebne są podziękowania.
**Funkcja:** prywatny rejestr kopert widoczny **tylko dla pary**: nie dla koordynatora, rodziców
ani w eksportach, a każdy odczyt trafia do audytu. Do tego prognoza wpływów (zakres, nie jedna liczba),
koszt netto po weselu i połączenie z naszymi podziękowaniami. Wycena jest opcjonalna i można ją wyłączyć.
**Dlaczego nowe:** kalkulatory kopert istnieją tylko osobno. Połączenia z prawdziwą listą gości,
budżetem i podziękowaniami nie znaleźliśmy.
⚖️ Dane o darowiznach od osób trzecich: minimalny zakres, sprawdzić z prawnikiem w ramach RODO (nr 37).
**Na bazie:** `guests` (prezent, podziękowania), `budget`.

## 6. Portfel sponsorów (rodzice i dziadkowie) — M ✅ zrobione 2026-10-22 (raport `docs/gui/raport-portfel-sponsorow.md`)

**Problem:** w Polsce wesele często współfinansują rodzice obu stron: „moi płacą za salę, twoi za
zespół”. Kto za co obiecał zapłacić, ile już przelał i jak to wyrównać, to częste źródło napięć.
**Funkcja:** każda płatność ma źródło finansowania (para / rodzice PM / rodzice PP / inni). Rodzice
dostają rolę „sponsor” z widokiem **tylko swoich pozycji i terminów**, bez gości, umów i reszty budżetu.
Do tego zestawienie „obiecane / wpłacone / do wyrównania”.
**Dlaczego nowe:** konkurencja ma współdzielenie konta we dwoje albo z plannerką. Częściowego
dostępu dla rodzin-sponsorów nie znaleźliśmy.
**Na bazie:** `budget` (płatności, podział), `workspace` (role, mamy już `coordinator`).

## 7. Licznik ważności dokumentów do ślubu — S ⚖️ ✅ zrobione 2026-10-22 (raport `docs/gui/raport-dokumenty-do-slubu.md`)

**Problem:** dokumenty do USC i parafii mają **okna ważności**. Załatwione za wcześnie tracą ważność,
załatwione za późno nie zdążą. Pary uczą się tego z forów.
**Funkcja:** z typu ślubu (cywilny / konkordatowy / wyznaniowy) i daty aplikacja wylicza dla każdego
dokumentu okno „najwcześniej / najpóźniej”. Przykłady: zaświadczenie z USC dla parafii, świadectwo
chrztu, nauki przedmałżeńskie, protokół przedślubny. Pokazuje to jako oś czasu z alertami, a przy
wgraniu skanu zapisuje datę wydania i ostrzega „straci ważność 12 dni przed ślubem”.
**Dlaczego nowe:** inne aplikacje mają zadanie „załatw dokumenty”. Nikt nie liczy okien ważności
od daty wydania.
⚖️ Terminy (np. 6 miesięcy dla zaświadczenia z USC, wymogi parafii) zweryfikować w przepisach i z prawnikiem,
a w aplikacji pokazywać źródło i zastrzeżenie „sprawdź w swojej parafii/USC”.
**Na bazie:** `planner` (szablon 2027.1 ma dokumenty jako podzadania), `documents`.

## 8. Transport i noclegi gości: kursy i lista pokoi — M ✅ zrobione 2026-10-22 (raport `docs/gui/raport-transport-noclegi.md`)

**Problem:** autokar z kościoła na salę i kursy powrotne (o 1:00 dla starszych, o 4:00 dla reszty)
oraz pokoje w hotelu dla gości z daleka. Dziś przewoźnik i hotel dostają listy z Excela, które
nieaktualne są już po pierwszej zmianie RSVP.
**Funkcja:** kursy z pojemnością i przystankami, gość wybiera kurs w RSVP (wiemy, kto jedzie),
alert „kurs 1:00 przepełniony o 6 osób”. Godziny kursów sprawdzane z harmonogramem dnia (np. kurs
przed tortem). Lista pokoi dla hotelu („rooming list”): kto z kim, ile nocy, kto płaci. Dla przewoźnika
i hotelu link tylko z liczbami i nazwiskami, bez diet i kwot (jak link dla sali).
**Dlaczego nowe:** konkurencja zbiera w RSVP tylko „potrzebuję transportu / noclegu” (WeddingGo, Wesele z klasą).
Planowania kursów z pojemnością i list dla hotelu nie znaleźliśmy.
**Na bazie:** `guests` (RSVP), `schedule` (konflikty), link dla sali.

## 9. Pakiety dla usługodawców z potwierdzeniem wersji — M ✅ zrobione 2026-10-22 (raport `docs/gui/raport-pakiety-uslugodawcow.md`)

**Problem:** po zmianie godziny w programie para pisze do pięciu firm i nie wie, czy zespół i fotograf
to przeczytali. W dniu ślubu wychodzi „mieliśmy starą wersję”.
**Funkcja:** każdy usługodawca dostaje swój link z tym, co go dotyczy. Fotograf: lista ujęć i „kto jest
kim” w rodzinie. DJ/zespół: utwory obowiązkowe i zakazane, pierwszy taniec, godziny. Kierowca: trasa
i godziny. Każda zmiana tworzy nową wersję. Usługodawca klika „Potwierdzam wersję 4”, a para widzi
na liście, kto ma aktualną wersję, i może wysłać przypomnienie.
**Dlaczego nowe:** inni udostępniają plan dnia gościom. Potwierdzania wersji przez usługodawców nie znaleźliśmy.
**Na bazie:** `schedule` (link `/dzien/:token`, tryb na żywo), link dla sali, `vendors`, `audit`.

## 10. Po weselu: rozliczenia, odbiór zdjęć i zmiana nazwiska — S/M ⚖️ ✅ zrobione 2026-10-22 (raport `docs/gui/raport-po-weselu.md`)

**Problem:** po weselu aplikacje „kończą się”, a zostaje sporo do zrobienia: dopłaty i zwrot kaucji
za salę, termin oddania zdjęć i filmu z umowy (fotografowie się spóźniają), zmiana nazwiska
w dowodzie, banku, u pracodawcy, ZUS i urzędzie skarbowym, opinie dla firm.
**Funkcja:** po dacie ślubu włącza się tryb „Po weselu”. Rozliczenie końcowe (kaucje, nadpłaty),
terminy z umów (alert „fotograf miał oddać zdjęcia 3 dni temu” z gotowym, uprzejmym szablonem
wiadomości), lista instytucji przy zmianie nazwiska z terminami i odhaczaniem, archiwum wesela do pobrania.
**Dlaczego nowe:** konkurencja po weselu oferuje tylko galerię zdjęć. U nas to dziś jedno zadanie
„Zaktualizujcie dokumenty po ślubie” w szablonie.
⚖️ Terminy urzędowe (np. wymiana dowodu po zmianie nazwiska) zweryfikować w przepisach.
**Na bazie:** `offers`/`documents` (terminy z umów), `budget`, `planner`, eksport danych.

---

## Pomysł dodatkowy (mały, S)

**Złota godzina i plener:** z adresu i daty liczymy lokalnie (wzór astronomiczny, bez API) zachód słońca,
złotą i niebieską godzinę. Harmonogram ostrzega, np. „sesja plenerowa 21:40 wypada po zachodzie słońca”.

## Rekomendowana kolejność

| Kolejność | Funkcja | Dlaczego |
|---|---|---|
| 1 | 3. Prognoza frekwencji i lista rezerwowa | najwięcej pieniędzy dla pary, wszystkie dane już mamy |
| 2 | 9. Pakiety dla usługodawców z wersjami | rozwija istniejące linki, widoczny efekt w dniu ślubu |
| 3 | 6. Portfel sponsorów | bardzo polskie, dobry argument za Premium |
| 4 | 7. Licznik ważności dokumentów | mały nakład, po weryfikacji terminów |
| 5 | 1. Strażnik waloryzacji | ważny przy rezerwacji z dużym wyprzedzeniem |
| 6 | 2. Umowa zgodna z ofertą | gdy AI będzie włączone (decyzja o hostingu) |
| 7–10 | 4, 8, 10, 5 | po wywiadach z parami (etap B) |

Decyzje właściciela: wybór i kolejność; czy funkcje 1, 5, 6, 8 mają być Premium; zakres ⚖️ dla prawnika
(5, 7, 10). Wywiady z parami (etap B) warto wykorzystać do sprawdzenia propozycji 3, 4, 5 i 6.
