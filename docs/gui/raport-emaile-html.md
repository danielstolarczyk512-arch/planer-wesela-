# Raport: e-maile HTML — plan dalszej pracy, A4

Data: 2026-10-21. Znane ograniczenie nr 6 zawężone do „tylko po polsku”.

## Co zmieniono
- `app/core/mail_templates.py`: jedna funkcja `build(...)` daje **dwie wersje tej samej treści**
  — tekst i HTML (nagłówek, akapity, przycisk z adresem zapasowym, sekcje z listami, uwaga,
  stopka). HTML: style w atrybutach, układ tabelowy (klienci poczty), `lang="pl"`, kolory
  z tokenów projektu (tekst drugorzędny `#6F656B` ma kontrast AA na białym), **bez zewnętrznych
  obrazów, czcionek, arkuszy i skryptów**. Każda wartość od użytkownika (nazwa wesela, imię)
  jest escapowana.
- `app/core/email.py`: `queue_mail(db, to, mail)`; wiadomość `multipart/alternative`
  (najpierw tekst, potem HTML). Stare wywołania tylko tekstowe nadal działają.
- Szablony: weryfikacja e-mail, próba rejestracji na istniejący adres, reset hasła, zaplanowane
  usunięcie konta, MFA włączone/wyłączone, zaproszenie do wesela, podsumowanie przygotowań
  (zadania, płatności, RSVP + „Otwórz plan wesela”), link RSVP do gości.
- Link „Zmień powiadomienia” tylko w podsumowaniu (wiadomości o koncie i do gości go nie mają —
  gość nie ma konta).
- Linki wskazują bezpośrednio polskie trasy GUI (`/potwierdz-email`, `/nowe-haslo`,
  `/zapomniane-haslo`, `/ustawienia`); stare adresy nadal przekierowują.
- **Poprawka konfiguracji dev:** domyślny `WP_PUBLIC_APP_URL` (oraz `.env.example` i lokalny
  `.env`) wskazywał `http://localhost:8000` — port innej aplikacji właściciela. Teraz
  `http://localhost:5173` (GUI w Vite). Produkcja bez zmian (`deploy/.env.prod.example`).

## Testy
- `tests/unit/test_mail_templates.py`: ta sama treść w obu częściach, pominięcie pustych sekcji,
  escapowanie (`<script>`, `&` w adresie), brak `<img>/<link>/<script>/url(`, brak linku do ustawień
  w wiadomościach do gości, struktura `multipart/alternative` (tekst przed HTML).
- `test_rsvp_emails_preview_and_send`: wersja HTML ma ten sam link z tokenem.
- Podgląd w Mailpit (dev): wiadomość „Reset hasła” — przycisk, adres zapasowy, stopka; poprawne
  polskie znaki.
