# Test dla znajomych — aplikacja z laptopa przez darmowy tunel

Cel: znajomi w innej miejscowości testują aplikację i stronę gościa, zanim wybierzemy hosting
(`docs/hosting.md`). Koszt: 0 zł — bez konta w chmurze, bez domeny, bez karty.

## Jak to działa

```
kolega (telefon/komputer) ──HTTPS──▶ *.trycloudflare.com ──tunel──▶ cloudflared na laptopie
                                                                       │
                                                       Caddy 127.0.0.1:8090 (konfiguracja produkcyjna)
                                                       api, worker, PostgreSQL, ClamAV, Mailpit
```

- Osobny projekt Dockera `naszdzien-test` z **własną, pustą bazą**. Baza dev (prawdziwe wesele) i środowisko E2E nie są używane.
- Ustawienia produkcyjne (`WP_ENV=prod`, skan plików, dokumentacja API wyłączona), AI wyłączone.
- Konfiguracja w `deploy/.env.test` (poza repozytorium, sekrety wygenerowane losowo).
- E-maile nie wychodzą do internetu — trafiają do Mailpit, podgląd tylko z laptopa: http://127.0.0.1:8026.
  Link potwierdzający konto czy reset hasła można przekazać testerowi ręcznie. Logowanie działa bez potwierdzenia adresu.
- Szybki tunel Cloudflare (Apache-2.0) jest darmowy i bez konta, ale **adres zmienia się przy każdym uruchomieniu**
  i działa tylko, gdy laptop jest włączony, a okno skryptu otwarte.

## Pierwsze uruchomienie (raz)

1. Docker Desktop włączony.
2. Zainstaluj tunel:

```powershell
winget install --id Cloudflare.cloudflared -e
```

3. Zamknij i otwórz ponownie okno PowerShell.

## Każde udostępnienie

```powershell
powershell -ExecutionPolicy Bypass -File scripts\udostepnij-test.ps1
```

Skrypt uruchamia aplikację, otwiera tunel, wpisuje publiczny adres do linków w e-mailach i kodach QR
(`WP_PUBLIC_APP_URL`) i wypisuje adres `https://….trycloudflare.com` — ten wysyłasz koledze.
Ctrl+C zamyka tunel; aplikacja dalej działa lokalnie (http://localhost:8090).

Zatrzymanie aplikacji testowej (dane zostają):

```powershell
cd deploy; docker compose -p naszdzien-test -f compose.prod.yaml -f compose.test.yaml --env-file .env.test stop
```

Po zmianach w kodzie: `npm --prefix frontend run build`, potem w `deploy/` to samo polecenie z `up -d --build`.

## Zasady dla testerów

- Wpisywać **zmyślonych gości** i dane — regulamin i polityka prywatności są robocze, brak umowy powierzenia.
- Pliki do 20 MB; każdy plik sprawdza ClamAV (pierwsze uruchomienie pobiera sygnatury kilka minut).
- Gdy laptop śpi albo skrypt jest zamknięty, aplikacja jest niedostępna.

## Gdy test ma działać 24/7

Darmowo: serwer Oracle Cloud Always Free (Frankfurt) z tą samą konfiguracją `deploy/compose.prod.yaml`
i adresem DuckDNS — wymaga założenia konta przez właściciela (weryfikacja kartą, bez opłat).
