# Raport: zaproszenia i konta dla gości (audyt 2026-10-25)

Audyt tylko do odczytu i testu, bez zmian w kodzie. Demonstracja na środowisku E2E (API 8011,
Vite 5174) na tymczasowym weselu „AUDYT zaproszeń”, które po teście usunięto. Baza dev nie
była używana. Zrzuty ekranu: `docs/gui/zaproszenia-audyt/`.

## 1. Krótko

**Gość nie ma konta.** Zaproszenie wesela to link z tokenem przypisany do *gospodarstwa*
(rodziny). Konta mają tylko członkowie wesela (właściciel, koordynator, sponsor…), zapraszani
osobnym mechanizmem. Poniżej oba mechanizmy i dodatkowe linki bez konta.

| Kto | Dostęp | Jak się uwierzytelnia | Co widzi / robi |
|---|---|---|---|
| Gość (rodzina) | `/rsvp/:token` | token w ścieżce, bez konta | swoje wydarzenia, odpowiedź per osoba, dieta, nocleg, transport, osoba towarzysząca, kurs autokaru, muzyka, prezenty, życzenia, informacje od pary |
| Członek wesela (np. koordynator) | `/invitations/accept?token=…` | konto z adresem z zaproszenia, e-mail zweryfikowany | zakres wg roli (koordynator: tylko Dzień) |
| Pomocnik / koordynator dnia / usługodawca | `/pomocnik/:token`, `/dzien/:token`, linki usługodawców | token, ważność ograniczona | wąski wycinek (zadanie, program, lista dla DJ-a itd.) |

## 2. Jak to jest zbudowane (kod)

**Link RSVP gościa**
- `app/core/security.py:291` — `new_token()`: `secrets.token_urlsafe(32)` (43 znaki, 256 bitów),
  w bazie tylko `sha256` (`hash_token`, `security.py:287`). Tokenu nie da się odczytać z bazy.
- `app/modules/guests/service.py:551` `create_rsvp_link` — nowy link **unieważnia poprzedni**
  tego gospodarstwa (`revoked_at`).
- `service.py:639` `revoke_rsvp_link` — ręczne wyłączenie (DELETE `/households/{id}/rsvp-link`).
- `service.py:526` `_rsvp_expiry` — ważny do 7 dni po ostatnim dniu wesela (bez daty: rok).
  `service.py:540` `_token_valid` — ważność liczona od *aktualnej* daty wesela.
- `service.py:655` `_resolve_token` — limit prób na IP (`WP_RSVP_RATE_LIMIT`, domyślnie 60 / 10 min,
  `service.py:657`) liczony **przed** sprawdzeniem tokenu, jedna odpowiedź `rsvp.not_found`
  dla tokenu nieistniejącego, odwołanego i wygasłego.
- `service.py:576` `rsvp_qr` (druk hurtowy: nowe linki) i `service.py:~1466` wysyłka e-mailem
  (też nowy link).
- Router: `app/modules/guests/router.py:221` (rsvp-link), `:428` (rsvp-emails), `:447` (rsvp-qr),
  `:560` (invitation-delivery), `:369–386` (guest-info). Strona gościa: `frontend/src/features/rsvp/RsvpPage.tsx`.
- Termin odpowiedzi zamyka tylko edycję (`_is_open`, `service.py:670`), nie dostęp do strony.

**Zaproszenia członków**
- `app/modules/workspace/service.py:419` `create_invitation`: tylko `MANAGE_MEMBERS`, wymaga
  zweryfikowanego e-maila zapraszającego, limit 20 zaproszeń/dobę/użytkownika, limit oczekujących,
  ważność `invitation_ttl_days` (14).
- `service.py:524` `accept_invitation`: jeden komunikat dla tokenu błędnego, wygasłego, odwołanego,
  przyjętego i **cudzego adresu** (`invitation.email != user.email`) — nie ujawnia szczegółów.
  Wymaga zweryfikowanego e-maila konta.
- `service.py:499` `revoke_invitation`. Router: `workspace/router.py:293–342`.
  UI: `AcceptInvitationPage.tsx`.

**Logi.** `deploy/Caddyfile:51–66` zamienia tokeny (40+ znaków base64url, w ścieżce i w query) na
`REDACTED`, usuwa `Authorization`, `Cookie`, `Referer`. Przeglądarkowe narzędzie audytu też
pokazało tokeny jako `REDACTED`.

## 3. Co sprawdzono w działaniu

1. **Link RSVP na telefonie 390 px**, jasny i ciemny motyw (zrzuty 02, 03, 05). Zapisanie
   odpowiedzi działa; po przeładowaniu zaznaczenia wracają (potwierdzone w API).
2. **Osoba towarzysząca** dopisana przez gościa („Marek”) trafia na listę pary z oznaczeniem
   „dopisana przez gości”. Limit: 19 kolejnych dopisań OK, 20. → `409 rsvp.companions_limit`
   z czytelnym komunikatem po polsku.
3. **E-mail z linkiem RSVP** i **e-mail z zaproszeniem koordynatora** obejrzane w Mailpit:
   wersja tekstowa i HTML, tokeny w treści, stopka „jeśli to pomyłka, zignoruj”.
4. **Przyjęcie zaproszenia**: niezalogowany → przekierowanie na logowanie z powrotem na
   `/invitations/accept` → ekran „Dołącz do wesela” (zrzut 06) → wejście do wesela jako koordynator.
5. **Rola koordynatora w API**: `/households`, `/guests`, `/members`, `/invitations`, `/documents`,
   `/offers`, `/guest-info` → `403`; `/schedule` → `200`; wydanie linku RSVP → `403`.
6. **Przypadki brzegowe tokenów** (API):

| Przypadek | Wynik |
|---|---|
| losowy poprawny token / śmieci (`abc`) | `404 rsvp.not_found`, ten sam tekst |
| token odwołany (GET i PUT) | `404`, ten sam tekst |
| stary token po wydaniu nowego | `404`, ten sam tekst |
| zmiana daty wesela na przeszłą | `422` (data przeszła jest odrzucana), więc wygaśnięcia nie dało się wywołać przez API |
| przekroczony limit na IP | **nie sprawdzone**: w E2E limit to 2000; odczytano tylko z kodu |

   Odpowiedzi na token nieistniejący, odwołany i wygasły są nierozróżnialne, czyli
   komunikaty nie ujawniają, czy token kiedykolwiek istniał.
7. **Widok pary**: lista gości, zakładka Strona gościa (co widzą goście, „Zobacz jak gość”),
   karty QR (zrzuty 07–10).

## 4. Luki i ryzyka

Oznaczenia: **[błąd]** coś działa źle, **[brak]** funkcji nie ma, **[ryzyko]** projekt wymaga decyzji.

### P1
1. **[błąd] Kod QR na kartach do druku nie wyświetla się** (zrzut 10). `qr_svg` z `segno.svg_inline`
   (`service.py:573`) nie ma atrybutu `xmlns`, a front wstawia go jako `<img src="data:image/svg+xml…">`
   (`EditGuestSheet.tsx:652`, `PrintView.tsx:422`). Przeglądarka nie renderuje takiego SVG:
   `naturalWidth = 0`, widać tylko tekst alternatywny. Link pod kodem jest poprawny (token działa).
   Wydrukowanie takiej karty = zaproszenie bez QR. Poprawka: `svgns=True` w segno albo dopisanie
   `xmlns` w `svgDataUri`. Warto dodać test, który sprawdza `naturalWidth > 0`.
2. **[ryzyko] Wysyłka e-mailem i druk QR unieważniają wcześniej rozdane linki.** Każda wysyłka tworzy
   nowy link, a stary przestaje działać. Para, która najpierw wręczy QR, a potem „dośle” e-mail
   (albo odwrotnie), unieważnia własne papierowe zaproszenia. Ekran QR to ostrzega
   („stare przestają działać”), ekran e-maili tylko w uwadze, a wywołanie z `include_with_link: true`
   wysłało e-mail także rodzinie, która już odpowiedziała, bez dodatkowego potwierdzenia
   w API. Propozycja: wysyłać ponownie ten sam link (przechowywać zaszyfrowany token albo wydawać
   drugi równoległy link) zamiast unieważniać.
3. **[ryzyko] Limit prób na IP (60 / 10 min) a sala weselna.** Licznik rośnie przy *każdym* żądaniu
   (także poprawnym, także po każdej akcji, bo każda zwraca pełny widok). Wiele osób na jednym
   Wi-Fi sali albo za jednym adresem operatora (CGNAT) może wyczerpać limit; gość zobaczy
   błąd zamiast formularza. Nie sprawdzone empirycznie. Propozycja: liczyć tylko *nieudane* próby
   (trafienia w nieistniejący token) albo limit na token + osobny, wyższy na IP.

### P2
4. **[brak] Gość 70+ musi kliknąć 2 × (liczba osób) × (liczba wydarzeń) pól** (np. 8 kliknięć dla
   4 odpowiedzi). Brak skrótu „Wszyscy będziemy na wszystkim”. Przycisk wysyłania dobrze mówi
   „Wyślij 4 odpowiedzi”. **Niepewne, do sprawdzenia:** po wysłaniu nie zauważyłem komunikatu
   „zapisano” (zrzut po kliknięciu go nie pokazał, ale mógł zniknąć), a po przeładowaniu przycisk
   nadal brzmi „Wyślij 4 odpowiedzi”, więc gość nie widzi, że już odpowiedział. Pole „Dieta”
   pojawia się po zaznaczeniu „Będę” i przesuwa resztę formularza, co utrudnia klikanie osobom
   starszym.
5. **[błąd/UX] Wesele bez wydarzeń**: strona gościa pokazuje tylko komunikat „Para młoda jeszcze
   uzupełnia szczegóły” i **żadnego formularza**, a stopka mówi „Dane podane w formularzu…”
   (zrzut 01). Komunikat o niskim kontraście (jasnoróżowy tekst na jasnym tle). Para może wydać linki
   zanim doda wydarzenia, więc warto zablokować wysyłkę e-maili i QR, dopóki nie ma żadnego
   wydarzenia.
6. **[ryzyko] Dopisywanie osób przez link jest otwarte dla każdego, kto ma link.** Bezpiecznik
   20 osób chroni przed nadużyciem, ale test zapełnił rodzinę „osobami” bez żadnego powiadomienia
   pary; statystyki „Bez odpowiedzi” urosły z 1 do 21 (zrzut 07), a nagłówek wiersza rodziny
   wylistował wszystkie 22 imiona w jednym akapicie. Propozycje: powiadomienie pary,
   zwijanie długiej listy („+19 więcej”), osobny licznik „dopisani przez gości”.
7. **[ryzyko] Kto widzi link w e-mailu.** Token jest w treści i w URL (`/rsvp/<token>`); przy
   udostępnieniu w komunikatorze każdy z linkiem odpowiada za całą rodzinę (zgodne z założeniem
   „bez konta”). Nie ma bezpiecznego wskazania, kto ostatnio użył linku, poza `last_used_at`
   w bazie; para tego nie widzi w UI (nie sprawdzano, czy widzi).
8. **[brak] Ekran przyjęcia zaproszenia nie mówi, do jakiego wesela, od kogo i z jaką rolą**
   (zrzut 06: „Dołączysz do planowania wesela jako koordynator.audyt@example.com”). Wysłany
   e-mail ma te informacje częściowo („Konto demo zaprasza…”), ale nie rolę. Jeśli konto nie
   istnieje, ekran logowania nie tłumaczy, że to w związku z zaproszeniem (rejestracja na ten sam
   adres wymaga weryfikacji e-maila). Po przyjęciu koordynator trafia na „Dzień” z komunikatem
   „Harmonogram jest pusty”, bez objaśnienia swojej roli.
9. **[do sprawdzenia] E-mail weryfikacyjny rejestracji** w tym środowisku zawiera link, ale nie
   6-cyfrowy kod opisany w `CLAUDE.md`. Możliwe, że obraz E2E nie był przebudowany po
   niezatwierdzonych zmianach (`migrations/versions/…f6d2b8a4c1e5…`, `identity/*`). Nie ustalono.

### P3
10. **[RODO]** Link RSVP pozwala gościowi podać dietę i potrzeby noclegu/transportu (dane
    szczególnych kategorii przy diecie „inna”); formularz ma zgodę (`health_data_consent`)
    i notkę prywatności. Rola administratora wobec danych gości jest otwarta (znane
    ograniczenie nr 37), więc nie oceniam jej tutaj.
11. **[dostępność]** Nie uruchomiono axe w tym audycie. Elementy do sprawdzenia przez zwykłe
    testy: kontrast komunikatów informacyjnych (zrzut 01), cele dotykowe przycisków „Będę /
    Nie będę / Jeszcze nie wiem” (duże, dobrze), przełącznik „Wielkość tekstu” (jest, plus).

## 5. Czego nie sprawdzono
- Limit prób na IP w działaniu i wygaśnięcie tokenu po upływie czasu (wymaga zmiany daty systemowej
  albo bazy).
- axe na stronie gościa, widok desktopowy w ciemnym motywie, strona gościa po angielsku.
- Linki `/dzien/:token`, `/pomocnik/:token` i usługodawców, tylko odczyt kodu i komentarz Caddy;
  ich ważność po weselu opisuje CLAUDE.md (7 i 30 dni), nie została przetestowana w tym audycie.
- Wysyłka przez prawdziwy SMTP (E2E kieruje pocztę do Mailpit).

## 6. Porządki po teście
- Tymczasowe wesele usunięte (`delete` → 204; w `wedding_e2e` brak weseł „AUDYT…”).
- Konto testowe `koordynator.audyt@example.com` ma status `pending_deletion` (usunięcie konta
  w aplikacji ma 30 dni karencji, nie ruszano bazy ręcznie). Maile testowe w Mailpit usunięte.
- Zmiany w repozytorium: tylko ten raport i katalog `docs/gui/zaproszenia-audyt/` (niezacommitowane).
