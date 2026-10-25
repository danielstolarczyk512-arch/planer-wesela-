# Prawdziwa poczta przez Gmail (rejestracja, weryfikacja e-maila)

Aplikacja wysyła e-maile przez SMTP (worker, kolejka `send_email`). Domyślnie trafiają do Mailpit
(`http://localhost:8025`). Żeby wychodziły z prawdziwego konta Gmail:

## 1. Hasło aplikacji (robi właściciel konta — to ustawienie bezpieczeństwa Google)

1. Zaloguj się na konto Gmail aplikacji, wejdź na https://myaccount.google.com/security
2. Włącz **weryfikację dwuetapową** (wymagana przez Google).
3. Wejdź na https://myaccount.google.com/apppasswords, utwórz hasło aplikacji (nazwa np. „Nasz dzień”).
   Google pokaże 16 znaków — to jest `WP_SMTP_PASSWORD_DOCKER`. Nie wpisuj go do repozytorium ani czatu.

## 2. Konfiguracja w `.env` (plik jest w .gitignore)

```
WP_SMTP_HOST_DOCKER=smtp.gmail.com
WP_SMTP_PORT_DOCKER=587
WP_SMTP_STARTTLS_DOCKER=true
WP_SMTP_USER_DOCKER=adres@gmail.com
WP_SMTP_PASSWORD_DOCKER=szesnastoznakowehaslo
WP_MAIL_FROM=Nasz dzień <adres@gmail.com>
```

Gmail zawsze podpisuje wiadomość adresem konta, więc `WP_MAIL_FROM` musi być tym samym adresem.
Hasło aplikacji wpisz bez spacji.

## 3. Restart

```
docker compose up -d --force-recreate api worker
```

## 4. Sprawdzenie

Zarejestruj konto w aplikacji na prawdziwy adres e-mail — wiadomość z linkiem potwierdzającym
przychodzi z Gmaila (folder Wysłane na koncie pokaże kopię). Błędy wysyłki: `docker compose logs worker`.

## Uwagi

- Limit darmowego Gmaila to ok. 500 wiadomości na dobę — do testów wystarczy, do startu komercyjnego
  potrzebna własna domena i usługa pocztowa (SPF/DKIM/DMARC; zob. `docs/hosting.md`).
- Zapytania do firm (moduł `inquiries`) nadal NIE wychodzą na zewnątrz: blokuje je
  `WP_INQUIRY_REAL_SMTP=false` (decyzja właściciela, etap 4).
- Wiadomość rejestracyjna zawiera link oraz 6-cyfrowy kod (ważny 30 min); kod wpisuje się w Ustawienia → Konto (limit 5 prób na 15 min).
