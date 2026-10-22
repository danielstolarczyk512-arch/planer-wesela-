# Raport: usprawnienia U7–U9 (druga runda analizy)

Data: 2026-10-22. Drobne usprawnienia łączące nowe moduły z codzienną pracą pary. Bez zmian w bazie danych.

## U7. Kto płaci — widoczne przy płatności

W płatnościach wydatku (Budżet → wydatek) obok terminu widać „płacą: Rodzice Panny Młodej”, gdy płatność jest
przypisana do sponsora. Wcześniej było to widać tylko w formularzu edycji i na ekranie „Kto płaci”.

## U8. Listy pasażerów do druku

`/w/:id/druk/kursy` (link „Listy pasażerów” na ekranie Transport i noclegi): dla każdego kursu dzień, godzina,
trasa, zajętość i lista osób z rubryką ☐ „Wsiadł(a)”. Dla pary albo świadka przy autokarze. Przewoźnik nadal
widzi tylko liczby na swoim linku. Listy z nazwiskami drukuje i przekazuje sama para.

## U9. „Po weselu”: podpowiedzi od zarezerwowanych usługodawców

Nad listą „Od usługodawców” przyciski „Zdjęcia — Foto Jan”, „Film — Kamera Jan”, „Zdjęcia z fotobudki — …” dla
zarezerwowanych fotografów, filmowców i fotobudek, których jeszcze nie ma na liście. Kliknięcie dodaje pozycję
z usługodawcą, a para wpisuje termin z umowy.

## U10. Filtry listy gości: „Do wręczenia” i „Nocleg / transport”

Dwa nowe filtry na liście gości: niewręczone zaproszenia osobiste oraz rodziny, w których ktoś potrzebuje noclegu
lub transportu (adres `?filtr=do-wreczenia`, `?filtr=nocleg-transport`).

## Weryfikacja

- E2E: „Po weselu…” (podpowiedź filmowca znika po dodaniu), „Transport i noclegi…” (wydruk list pasażerów),
  „Zaproszenia…” (filtr „Do wręczenia”) na 8 profilach; testy gości 38/38.
- Pełny przebieg: backend **945 passed**, vitest **120**, E2E dev **346 passed** bez błędów.
