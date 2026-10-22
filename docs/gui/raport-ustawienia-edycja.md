# Raport: ustawienia wesela oraz edycja i usuwanie danych

Data: 2026-10-20. Zakres: zlecenie „ekran ustawień wesela (nazwa, data z podglądem przesunięć, typ ceremonii,
budżet, zaproszenie partnera) oraz edycja i usuwanie zadań, wydatków i gości”.

## Co jest gotowe

### Ustawienia wesela (`/w/:id/ustawienia`, wejście z „Więcej → Ustawienia wesela”)

- **Podstawowe:** nazwa, typ ceremonii, miejscowość, planowana liczba gości, limit budżetu. Zapis z kontrolą
  wersji (If-Match) — gdy partner zmienił dane w tym samym czasie, formularz pokazuje komunikat i wczytuje świeży stan.
- **Data ślubu:** dokładna data albo tylko miesiąc. Przycisk „Pokaż, co się zmieni” najpierw liczy przesunięcia
  (dry run) i pokazuje listę zadań ze starym i nowym terminem, ostrzega o zadaniach, które od razu będą po terminie,
  i podaje, ile zadań zostaje bez zmian (ręczny termin, zakończone). Zapis dopiero po „Zapisz nową datę”.
- **Osoby z dostępem:** lista członków, zmiana roli, usunięcie dostępu lub opuszczenie wesela (z potwierdzeniem),
  oczekujące zaproszenia z możliwością wycofania, formularz zaproszenia partnera / świadka (e-mail + rola).
- **Przyjęcie zaproszenia:** strona `/invitations/accept?token=…` (link z e-maila). Niezalogowana osoba trafia
  na logowanie i wraca na tę stronę.

### Edycja i usuwanie

| Co | Jak otworzyć | Pola | Usuwanie |
|---|---|---|---|
| Zadanie | dotknięcie treści zadania (Dziś, Plan) | tytuł, termin (lub bez terminu), osoba | „Nie dotyczy nas (pomiń)” / „Przywróć” albo usunięcie z potwierdzeniem |
| Wydatek | dotknięcie wydatku (Budżet) | nazwa, kategoria, status (szacunek / umowa / rezygnujemy), kwota | potwierdzenie z ostrzeżeniem, że znikną zapisane płatności; przy wpłatach podpowiedź „lepiej ustawić Rezygnujemy” |
| Gość | dotknięcie imienia w rozwiniętej karcie rodziny | imię, nazwisko, wiek, dieta, uwagi dla kuchni (z informacją RODO), nocleg, transport | dialog „Kogo usunąć?”: tylko ta osoba albo całe zaproszenie; jedyna osoba → usuwamy całe zaproszenie |
| Zaproszenie | „Edytuj zaproszenie” w karcie rodziny | nazwa, strona, status zaproszenia papierowego; dodawanie kolejnej osoby | potwierdzenie z liczbą osób, odpowiedziami i miejscami przy stołach |

Każdy zapis używa If-Match (konflikt wersji = czytelny komunikat), każda operacja kończy się powiadomieniem.
Kwoty kosztów „za osobę” nie są edytowane w tym arkuszu (zmienia się je w ofercie).

## Poprawki przy okazji

- **Pole kwoty:** po wejściu w pole tekst zmieniał się na „1200,00”, a kursor stał na końcu — wpisanie nowej
  kwoty doklejało ją („1200,001500”). Teraz pole pokazuje „1200” i zaznacza całość, więc wpisanie zastępuje kwotę.
- **Testy dostępności:** axe czeka na koniec animacji otwierania okna (wcześniej potrafił mierzyć kontrast
  półprzezroczystego okna). Wykluczony jest jeden węzeł biblioteki React Aria (ukryty region komunikatów
  odwołujący się przez kilka sekund do zamkniętego formularza) — to stan biblioteki, nie treść aplikacji.

## Weryfikacja

- TypeScript i ESLint: czysto.
- Vitest: 54 testy.
- Playwright (dev, 8 profili: 320/390/768/1280 px × jasny/ciemny): 144 testy, w tym nowe: ustawienia
  (podgląd daty bez zapisu), edycja i usunięcie zadania, wydatku, osoby i zaproszenia; axe bez naruszeń;
  brak poziomego przewijania przy 320 px.
- Playwright na buildzie produkcyjnym z CSP: 112 testów (32 pominięte — dane demo tylko w dev).
- Start aplikacji: 136,3 KB gzip (limit 170 KB). Licencje: bez zmian.
- Testy edycji tworzą własne dane z losowym dopiskiem i usuwają je; wesele właściciela nie jest dotykane.

## Uwagi dla właściciela

- Linki w e-mailach (zaproszenie partnera, RSVP) prowadzą pod `WP_PUBLIC_APP_URL`. W środowisku deweloperskim
  warto ustawić tam `http://localhost:5173`, żeby otwierały się w nowym GUI. Nie zmieniałem Twojego `.env`.
- Usunięcie jest nieodwracalne (w API nie ma kosza). Dla zadań i wydatków GUI podsuwa bezpieczniejszą
  alternatywę (pominięcie / „Rezygnujemy”). Jeśli chcesz kosza z możliwością przywrócenia — to decyzja produktowa
  na później.
