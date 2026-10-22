# 07. Dziesięć kolejnych funkcji (2026-10-22)

Prośba właściciela: przeanalizować naszą aplikację, inne programy weselne i potrzeby par, zaproponować 10 funkcji
i je wdrożyć.

## Metoda i źródła

- **Nasza aplikacja:** wszystkie ekrany (`frontend/src`), analizy 05 i 06. Z 05 zostały tylko propozycje
  czekające na decyzje (AI, koperty).
- **Rynek:** przegląd 22.10.2026 przez DuckDuckGo w przeglądarce, bo WebSearch nie działał. Czytaliśmy tylko
  publiczne artykuły, bez kont i bez pobierania danych:
  - porównania polskich serwisów (Strona Weselna — zestawienie 9 serwisów z sierpnia 2026, Weselio, Weselniak,
    Wedding Board);
  - zagraniczne aplikacje: Coordon (dzień ślubu i przesuwanie harmonogramu), Zola i Joy, przegląd RSVP'd 2026
    (The Knot, Aisle Planner, HoneyBook);
  - poradniki o błędach par: fotograf Kasolik („12 błędów”), studioweselne.pl (muzyka).
- **Co rynek robi dobrze, a czego u nas brakowało:**
  - tryb czytelny dla starszych gości (Strona Weselna);
  - menu z alergenami i plan stołów na stronie gościa (Weselio);
  - księga gości (Weselio);
  - wspólna praca bez zakładania kont (Planning.Wedding);
  - komunikat do gości przy zmianie (Strona Weselna);
  - lista utworów i „zakazanych” piosenek dla DJ-a (studioweselne);
  - lista zdjęć grupowych dla fotografa (narzędzia plannerów: Aisle Planner).
- **Potrzeby par z poradników:**
  - nie brać wszystkiego na siebie, tylko delegować bliskim;
  - dzień ucieka, więc plan musi być realny (przygotowania, zdjęcia grupowe);
  - za mało kierowców przy powrotach (to już mamy: kursy).

**Zasada:** każda funkcja korzysta z tego, co już mamy (prognoza frekwencji, goście z dietami, stoły,
harmonogram, linki dla usługodawców). Dzięki temu jest od razu „połączona”, a nie jest osobnym kalkulatorem.
Nie potrzebują decyzji prawnych ani płatnych usług. Żadna nie wysyła danych do AI.

| # | Funkcja | Inspiracja | Nakład |
|---|---|---|---|
| 1 ✅ | **Pomocnik wyboru daty**: dla kilku dat-kandydatów dzień tygodnia, święta i długie weekendy (droższe noclegi, goście na urlopach), Adwent i Wielki Post przy ślubie kościelnym, godzina zachodu słońca (zdjęcia w plenerze), ile zostało czasu na przygotowania | Bridebook (dostępność dat), poradniki o wyborze terminu. Uwaga: kalkulator napojów **już mamy** (Budżet), więc nie dublujemy | S/M |
| 2 ✅ | **Tryb czytelny na stronie gościa i w RSVP**: większa czcionka, mocniejszy kontrast, jedna rzecz na ekranie; zapamiętany na urządzeniu | Strona Weselna („strona dla babci”) | S |
| 3 ✅ | **Muzyka na momenty i propozycje gości**: utwory na wejście, pierwszy taniec, tort, oczepiny, ostatni taniec; gość proponuje utwór w RSVP, para akceptuje; wszystko trafia do informacji dla DJ-a lub zespołu (lista „nie grać” już jest w informacji dla usługodawcy) | studioweselne.pl, prośby o piosenki (WeddingGo) — u nas połączone z linkiem dla DJ-a | M |
| 4 ✅ | **Zdjęcia grupowe dla fotografa**: lista grup z osobami z listy gości, szacowany czas, kolejność; świadek odhacza w dniu ślubu; czas trafia do harmonogramu | narzędzia plannerów (shot list), Kasolik | M |
| 5 ✅ | **Plan przygotowań („getting ready”)**: fryzjer i makijaż liczone wstecz od wyjazdu na ceremonię, kto o której siada na fotel | kalkulatory „hair & makeup timeline” (USA) | S/M |
| 6 ✅ | **Menu z alergenami** (14 alergenów z rozporządzenia UE 1169/2011): dania, oznaczenia, ostrzeżenia przy dietach gości; menu na stronie gościa | Weselio (menu z alergenami) | M |
| 7 ✅ | **„Gdzie siedzimy” na stronie gościa**: każda rodzina widzi tylko swój stół, gdy para opublikuje plan | Weselio (plan stołów dla gości) — u nas bez publikowania cudzych nazwisk | S |
| 8 ✅ | **Komunikat do gości**: baner na stronie gościa i opcjonalnie e-mail do gości z adresem (np. „zmiana godziny”) | Strona Weselna („zmiana sali tuż przed weselem”) | M |
| 9 ✅ | **Księga życzeń**: gość zostawia życzenia na swojej stronie, para czyta i drukuje; ukrywanie | Weselio (księga gości) | S/M |
| 10 ✅ | **Zadania dla bliskich bez konta**: para przypisuje zadanie pomocnikowi (np. „Tata — kierowcy”), pomocnik dostaje link tylko ze swoimi zadaniami i odhacza | Planning.Wedding (praca bez kont), Kasolik („zbyt wiele brania na siebie”) | M |

## Czego świadomie nie robimy (wymaga decyzji)

- **Galeria zdjęć od gości:** przechowywanie dużej ilości plików, wizerunek osób trzecich (RODO) i koszt
  hostingu. Do decyzji przy wyborze hostingu.
- **SMS do gości:** płatna bramka SMS.
- **Generowanie treści przez AI:** AI na start wyłączone.

## Status

Wszystkie 10 zrobione 2026-10-22 — raport `docs/gui/raport-dziesiec-funkcji-07.md`.
