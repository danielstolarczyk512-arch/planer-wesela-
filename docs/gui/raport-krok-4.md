# Raport GUI — krok 4

Data: 2026-10-20. Commity: `fd082ff` (RSVP, harmonogram, wydarzenia), `7fb1f16` (plan stołów),
`2fb43f6` (usługodawcy, oferty, porównanie), `ed6ff90` (dokumenty i AI). Wcześniej tego dnia:
`845005a` (ustawienia wesela, edycja i usuwanie — osobny raport `raport-ustawienia-edycja.md`).

## Nowe ekrany

| Ekran | Adres | Najważniejsze |
|---|---|---|
| Odpowiedź gości (RSVP) | `/rsvp/:token` | bez logowania; odpowiedź osobno na każde wydarzenie; dieta, nocleg, transport; zgoda na uwagi dietetyczne (dane o zdrowiu); „Dziękujemy” + możliwość zmiany; komunikat, gdy link wygasł lub para nie dodała jeszcze wydarzeń |
| Link do odpowiedzi | karta zaproszenia (Goście) | tworzenie, kopiowanie, udostępnianie (telefon), wyłączanie; link widoczny tylko raz (serwer trzyma skrót) |
| Wydarzenia | Ustawienia wesela | szybki start „ceremonia + przyjęcie”, godziny (koniec po północy liczony na następny dzień), adres widoczny dla gości |
| Harmonogram dnia | `/w/:id/dzien` | typowy program z podglądem, punkty z dniem/godziną/czasem trwania, konflikty, „przesuń ten i późniejsze” z podglądem, wydruk; noc po północy należy do tej samej doby (do 6:00) |
| Plan stołów | `/w/:id/stoly` | dodawanie wielu stołów, automat z podglądem przed zapisem, ręczne przenoszenie (przypina), odpinanie, reguły „razem/osobno”, problemy z planu |
| Usługodawcy | `/w/:id/uslugodawcy`, `/…/:vendorId` | kategorie, wyszukiwanie, kontakt (tel/mail/www), dokumenty usługodawcy |
| Oferta | `/w/:id/oferty/:offerId` | pozycje cenowe z cytatami i pewnością, warunki, zatwierdzenie (z potwierdzeniem niepewnych pól), odrzucenie |
| Porównanie | `/w/:id/oferty/porownanie` | realny koszt przy tej samej liczbie gości, „z czego to wynika”, ostrzeżenia o brakach; **wybór z dialogiem konsekwencji** (pozycja w budżecie, płatności z warunków, rezerwacja, odrzucenie konkurencji) |
| Dokumenty | `/w/:id/dokumenty` | wgrywanie PDF/DOCX/JPG/PNG, postęp odczytu tekstu, pobieranie, **„Odczytaj ofertę” przez lokalny model AI** |

Wejścia: „Więcej” (harmonogram, plan stołów, usługodawcy, dokumenty), „Goście → Plan stołów”.

## Zgodność z zasadami projektu

- **AI i dane:** analiza działa na lokalnym modelu (Ollama, qwen2.5:7b-instruct). Sprawdzone ręcznie:
  ok. 50 s, `external_processing: false`, każda kwota z cytatem z dokumentu, wynik jako szkic do sprawdzenia.
  Zewnętrzny dostawca wymaga zgody (serwer zwraca `ai.consent_required`) — GUI nie obiecuje więcej, niż robi serwer.
- **Dane o zdrowiu (RODO art. 9):** uwagi dietetyczne gościa wysyłane tylko z zaznaczoną zgodą; para widzi informację,
  że dane są szyfrowane i usuwane po weselu.
- **Zadatek vs zaliczka:** edytor oferty wyjaśnia różnicę; porównanie i wybór oferty nie udają porady prawnej
  (zastrzeżenie z API + „To nie jest podpisanie umowy”).
- **Link RSVP:** token tylko w ścieżce adresu, `Referrer-Policy: no-referrer` (Caddy), link pokazywany jeden raz.

## Znalezione i naprawione przy okazji

- Świeżo założone wesele nie ma wydarzeń, więc goście nie mieli na co odpowiadać, a GUI nie pozwalało ich dodać →
  sekcja „Wydarzenia” w ustawieniach + komunikat na stronie RSVP.
- Utworzenie linku RSVP zmienia wersję zaproszenia, co przemontowywało formularz i gubiło świeży link → stan linku
  trzymany nad formularzem.
- Godziny w harmonogramie łamały się w wąskiej kolumnie; oczepiny po północy trafiały do osobnego „dnia”.
- Nazwa „przypięty” była czytana przed imieniem gościa (czytniki ekranu) → po imieniu.
- Niestabilny pomiar kontrastu w testach (axe w trakcie animacji wejścia okna) → czekamy na start i koniec animacji.

## Weryfikacja

- TypeScript, ESLint: czysto. Vitest: 61 testów (m.in. czas polski lato/zima, doba weselna, ceny ofert, zapełnienie stołu).
- Playwright dev (8 profili: 320/390/768/1280 px × jasny/ciemny): 192 testy, axe bez naruszeń, brak poziomego
  przewijania przy 320 px. Nowe scenariusze działają na tymczasowych weselach zakładanych i usuwanych przez API.
- Playwright na buildzie produkcyjnym z CSP: 159 + powtórzenia niestabilnego testu (24/24 po poprawce).
- Start aplikacji: 137,2 KB gzip (limit 170 KB) — nowe ekrany ładowane osobno.

## Do decyzji właściciela (nie blokuje pracy)

1. **Treść zgody na uwagi dietetyczne** na stronie RSVP — szkic napisany przeze mnie; warto, by przejrzał go prawnik
   razem z polityką prywatności (kto jest administratorem danych gości: para czy platforma).
2. **Zewnętrzny model AI** (np. dla skanów słabej jakości) — dziś wyłącznie lokalny; włączenie wymaga zgody i umowy
   powierzenia z dostawcą.
3. **`WP_PUBLIC_APP_URL`** w środowisku deweloperskim warto ustawić na `http://localhost:5173`, żeby linki z e-maili
   otwierały nowe GUI (GUI samo buduje link RSVP z własnego adresu, więc ten jeden działa niezależnie).
