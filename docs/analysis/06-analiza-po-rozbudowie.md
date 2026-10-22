# 06. Analiza po rozbudowie (2026-10-22) — luki i kolejne usprawnienia

Stan: zrobione propozycje 1, 3, 4, 6, 7, 8, 9, 10 z `05-propozycje-nowych-funkcji.md`, „Wymaga uwagi” na ekranie
Dziś, przypomnienia w kalendarzu i ICS oraz wybór kursu przez gościa w RSVP. Czekają na decyzje: propozycja 2
(AI: umowa zgodna z ofertą — gdy AI zostanie włączone) i 5 (koperty — RODO).

## Metoda

Przegląd ścieżek pary od ekranu Dziś przez Plan, Budżet, Gości i Dzień do Po weselu. Szukałem miejsc, gdzie
nowe moduły nie rozmawiają ze sobą, gdzie informacja nie dociera do właściwej osoby (para, koordynator, sponsor,
usługodawca, gość) albo gdzie para musi coś przepisywać ręcznie.

## Luki i usprawnienia (bez decyzji właściciela) — w kolejności

| # | Luka | Usprawnienie | Nakład |
|---|---|---|---|
| U1 ✅ | Alerty frekwencji (termin dla sali, minimum) są tylko w aplikacji | Sekcja „Frekwencja” w e-mailowym podsumowaniu | S |
| U2 ✅ | Koordynator dnia (świadek) nie widzi kursów autokaru, choć to on pilnuje odjazdów | Kursy (godziny, trasy, liczby osób, bez nazwisk) na ekranie Dzień dla roli z `DAY_READ` | S |
| U3 ✅ | Objazd z zaproszeniami odbywa się „w terenie”, często bez zasięgu | Wydruk listy objazdu: miejscowości, zaproszenia, kto wręcza (`/druk/objazd`) | S |
| U4 ✅ | Sponsor nie może zgłosić przelewu; para wpisuje go ręcznie | „Zgłoś przelew” w widoku sponsora → wpłata do potwierdzenia przez parę | M |
| U5 ✅ | Plan stołów a goście, którzy odmówili | Już jest: walidacja planu zgłasza `not_attending_seated` | — |
| U6 ✅ | Lista gości nie pokazuje kursu ani pokoju przy osobie | Znaczniki „kurs / pokój” w szczegółach gościa | S |

## Do decyzji (nie robię sam)

- Czy „Wymaga uwagi” ma też trafiać do powiadomień push (C4), gdy będzie HTTPS.
- Czy sponsor ma widzieć program dnia (dziś nie widzi niczego poza swoim wkładem).

## Druga runda (2026-10-22, później) — zrobione

| # | Usprawnienie | Raport |
|---|---|---|
| U7 ✅ | Przy płatności widać, kto płaci („płacą: Rodzice”) | `docs/gui/raport-usprawnienia-u7-u9.md` |
| U8 ✅ | Wydruk list pasażerów kursów (`/druk/kursy`) | jw. |
| U9 ✅ | „Po weselu”: podpowiedzi od zarezerwowanego fotografa, filmowca, fotobudki | jw. |
| U10 ✅ | Filtry listy gości: „Do wręczenia”, „Nocleg / transport” | jw. |
| U11 ✅ | Eksport gości do Excela z wręczeniem, miejscowością, kursem i pokojem | commit `3cedb48` |
| U12 ✅ | „Co zabrać” na dzień ślubu (koordynator odhacza, koperty bez kwot) | `docs/gui/raport-co-zabrac.md` |
| U13 ✅ | Podsumowanie e-mail dla sponsora (tylko jego płatności) | `docs/gui/raport-portfel-sponsorow.md` |
| U14 ✅ | Strona gościa: rozkład przejazdów udostępnionych przez parę (PL/EN) | — |
| U15 ✅ | W dniu ślubu ekran Dziś prowadzi do programu dnia („Dziś Wasz dzień!”) | — |

Przegląd bezpieczeństwa po rozbudowie: `bandit`, `pip-audit`, `npm audit` — bez zgłoszeń; E2E produkcyjne (CSP) 320 zielonych.

## Pomysły na kolejne rundy (do oceny)

- Wybór pokoju przez gościa w RSVP (dziś przydziela para) — po opiniach par.
- Link dla hotelu z listą pokoi (jak link dla sali) — po opiniach par.
- Kalibracja prognozy frekwencji na zanonimizowanych danych — wymaga zgody i opinii prawnej.

## Trzecia runda (plan, 2026-10-22)

| # | Luka | Usprawnienie | Nakład |
|---|---|---|---|
| U16 ✅ | Ile zaproszeń zamówić w drukarni — para liczy ręcznie | Na ekranie Zaproszenia: „do zamówienia N zaproszeń (rodziny) + zapas” i liczba wg sposobu wręczenia | S |
| U17 ✅ | Prognoza frekwencji liczy tylko przyjęcie; poprawiny mają inną liczbę gości i cenę | Prognoza także dla poprawin (osobny wynik, gdy jest wydarzenie „poprawiny”) | M |
| U18 ✅ | Waloryzacja nie jest widoczna na ekranie Dziś | Kafelek kosztu: „z podwyżkami do X zł”, gdy są klauzule | S |

U16–U18 zrobione — raport `docs/gui/raport-runda-3.md`.
