# 08. Spójność aplikacji i kolejne funkcje (2026-10-22)

Prośba właściciela: znaleźć niespójności w aplikacji, a potem dodać funkcje, które ułatwią parom planowanie — tak,
żeby to była najlepsza aplikacja na rynku.

## Część 1. Niespójności (audyt kodu i ekranów)

| # | Niespójność | Poprawka |
|---|---|---|
| S1 ✅ | Tekst pomocniczy 16 px zamiast 14 px (kolizja nazw tokenów koloru i kroju) | tokeny typografii `--wp-type-*` (zrobione przed tą analizą) |
| S2 ✅ | Plan ma nagłówek „Plan przygotowań”, a w Dniu jest zakładka „Przygotowania” (fryzura i makijaż) — dwa różne „przygotowania” | zakładka i ekran: **„Fryzura i makijaż”** |
| S3 ✅ | Ustawienia strony gościa w 5 miejscach: arkusz „Strona dla gości” (informacje, motyw), ekran „Komunikat, stół i życzenia”, przełącznik propozycji utworów (Muzyka), menu (Menu), kursy (Transport), podgląd osobno | jedna podzakładka **„Strona gościa”**: co widzą goście (stan i link do każdej części), informacje, podgląd, komunikat, stół, życzenia |
| S4 ✅ | Usuwanie: część list pyta o potwierdzenie, część usuwa od razu bez możliwości cofnięcia („Co zabrać”, Muzyka, Przygotowania) | krótkie listy: usuwanie od razu z **„Cofnij”** w powiadomieniu (jak przy odhaczaniu zadań); większe obiekty: okno potwierdzenia |
| S5 ✅ | Słownictwo: w interfejsie „zaproszenie / rodzina”, ale w jednym miejscu „gospodarstwa” (język bazy danych) | „rodziny” |

Bez zmian (świadomie):
- przełączniki widoczności (np. „pokaż menu gościom”) nie wymagają If-Match — to pojedyncze wartości tak/nie;
- edycje treści wymagają If-Match.

## Część 2. Nowe funkcje

Kryteria wyboru:
- **codzienna wartość dla pary** (żeby wracała do aplikacji);
- **powód do polecenia** (rodzice, goście widzą aplikację);
- korzystamy z danych, które już mamy;
- bez płatnych usług, AI i decyzji prawnych.

| # | Funkcja | Po co | Nakład |
|---|---|---|---|
| N1 ✅ | **Wyszukiwarka** (zadania, goście, usługodawcy, płatności) dostępna z każdego ekranu | przy 70+ zadaniach i 150 gościach para szuka, zamiast przewijać | S |
| N2 ✅ | **Plan wydatków po miesiącach**: ile trzeba zapłacić w każdym miesiącu do ślubu i ile odkładać miesięcznie | największy stres to „czy nam starczy”; widać miesiące szczytu | S/M |
| N3 ✅ | **Koszt jednego gościa**: średni koszt gościa i ile kosztuje każda dodatkowa osoba (z cen „za osobę” w wybranych ofertach) | ułatwia trudne decyzje „zapraszamy kuzynostwo czy nie” | S |
| N4 ✅ | **Lista prezentów z rezerwacją**: para dodaje pomysły (także „wkład w podróż poślubną”), gość na swojej stronie rezerwuje prezent; inni widzą tylko „zarezerwowane” | koniec dublowania prezentów; goście widzą aplikację → polecenia | M |
| N5 ✅ | **Gotowe wiadomości do usługodawców**: zapytanie o termin i ofertę, potwierdzenie rezerwacji, prośba o umowę, przypomnienie o płatności, podziękowanie — z danymi wesela, do skopiowania | para nie wie, jak napisać do sali czy zespołu; oszczędza czas | S |
| N6 ✅ | **Komentarze przy zadaniach**: krótka rozmowa pary (i współorganizatorów) przy zadaniu | ustalenia nie giną w komunikatorach | S/M |
| N7 ✅ | **Podsumowanie dla rodziców (wydruk)**: jedna strona — data, miejsce, liczba gości, budżet i wkład sponsorów, najbliższe terminy | rodzice pytają „jak idzie” — para drukuje lub wysyła PDF | S |

## Status

Wszystko zrobione 2026-10-22 — raport `docs/gui/raport-spojnosc-i-funkcje-08.md`.
