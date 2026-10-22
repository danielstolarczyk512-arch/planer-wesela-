# Raport: informacje dla usługodawców i potwierdzanie wersji programu

Data: 2026-10-22. Propozycja 9 z `docs/analysis/05-propozycje-nowych-funkcji.md`.
Migracja `e5a7c9b1d3f4` (tabela `vendor_briefs`).

## Problem

Po zmianie godziny w programie para pisze do kilku firm i nie wie, czy zespół i fotograf to przeczytali.
Link z programem dnia dla usługodawcy (`/dzien/:token`) już był. Brakowało dwóch rzeczy: miejsca na
informacje konkretnie dla tej firmy i sprawdzenia, czy ją przeczytała.

## Co zrobiono

1. **Informacje dla usługodawcy** (karta usługodawcy, pod linkiem z programem): listy „jedna pozycja w wierszu”
   z nazwami zależnymi od rodzaju firmy. Muzyka: „Utwory obowiązkowe” / „Nie grać”. Foto i wideo:
   „Ujęcia obowiązkowe” / „Czego nie fotografować”. Transport: „Trasa i przystanki”. Pozostali:
   „Koniecznie” / „Czego unikać”. Do tego „Kto jest kim” (imię — kim jest), inne uwagi i kontakt w dniu ślubu.
   Zapis z `If-Match`.
2. **Wersje:** treść linku usługodawcy (program dnia, wydarzenia, informacje dla niego) ma numer wersji.
   Nowy numer powstaje przy pierwszym odczycie po zmianie, więc kilka zmian między odczytami daje jedną wersję.
   Liczby dla kuchni nie zmieniają wersji, bo zmieniają się po każdej odpowiedzi gości.
3. **Potwierdzenie na stronie usługodawcy:** przycisk „Potwierdzam, że znam wersję N”. Jeśli program zmienił się
   od otwarcia strony, serwer odrzuca potwierdzenie (409 `day_link.version_changed`), a strona prosi o przeczytanie
   zmian. Po zmianie widać „Od Waszego potwierdzenia (wersja 2) program się zmienił”.
4. **„Kto zna aktualny program”** (Harmonogram dnia): lista usługodawców z aktywnym linkiem, ich status
   („Potwierdził wersję 3” / „Zna wersję 2, a aktualna to 3”) i link do karty usługodawcy. Ten sam status
   jest na karcie usługodawcy.

## API

- `GET|PUT /weddings/{id}/vendors/{vendor}/brief` (PUT z `If-Match`; odczyt także dla roli podglądu
  i koordynatora dnia, jak program dnia).
- `GET /weddings/{id}/vendor-briefs`: statusy wersji usługodawców z aktywnym linkiem.
- `POST /day/{token}/ack` `{version}`: potwierdzenie (bez logowania, ten sam limit na IP co odczyt linku).
- `GET /day/{token}` ma nowe pola: `brief`, `version`, `acknowledged_version`, `acknowledged_at`, `up_to_date`,
  `vendor_category`.

## Decyzje projektowe

- Wersja rekordu do `If-Match` zmienia się tylko przy zapisie przez parę (ręcznie, z blokadą wiersza).
  Odczyty linku podbijają tylko `content_version`, więc para nie dostaje fałszywych konfliktów, gdy firma
  otwiera link.
- Potwierdzenie przetrwa wygenerowanie nowego linku (stan jest przy usługodawcy, nie przy tokenie).
- Nie ma wysyłki przypomnienia z aplikacji: token linku jest widoczny tylko raz, więc nie da się go wysłać
  ponownie bez nowego linku. Para dostaje komunikat „Dajcie znać usługodawcy…”.

## Prywatność

- „Kto jest kim” i kontakt to dane osób z rodziny wpisane przez parę: widzi je tylko ten usługodawca,
  są w eksporcie wesela (`vendor_briefs`) i **są czyszczone** (pusta lista, brak kontaktu) przy anonimizacji
  gości 90 dni po weselu. Listy utworów i ujęć zostają.
- Audyt: zapis informacji tylko z nazwami pól (bez treści), potwierdzenie jako działanie zewnętrzne
  (`actor_type=guest`) z numerem wersji.

## Weryfikacja

- Backend: nowe `tests/api/test_vendor_briefs.py` (wersje, 409 przy starej wersji, `If-Match`, cudze informacje
  niewidoczne, rola podglądu, eksport i czyszczenie po weselu), trasy w `test_idor.py`. Cały backend: **821 passed**, 6 pominiętych;
  vitest **106**.
- Frontend: `lib/vendorBrief.test.ts` (nazwy sekcji, wiersze → lista, „imię — rola”). Nowy komponent
  `TextAreaField`. E2E „Usługodawca: informacje od pary, wersja programu i potwierdzenie” zielony na 8 profilach
  (axe, bez poziomego przewijania, także strona publiczna).
- Baza dev: kopia przed migracją `backups/wedding-20261021-235034-przed-vendor-briefs.dump`. Migracja tylko
  dodaje tabelę.
