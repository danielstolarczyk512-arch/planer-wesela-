# Serwer testowy 24/7: Oracle Cloud Always Free + DuckDNS

Stały adres `https://<subdomena>.duckdns.org`, działa bez laptopa. Koszt: 0 zł (Oracle „Always Free”:
serwer ARM Ampere A1 do 4 rdzeni i 24 GB RAM, dysk do 200 GB; DuckDNS — darmowa subdomena).
Konfiguracja jak produkcja (`deploy/compose.prod.yaml`: Caddy z certyfikatem Let's Encrypt, ClamAV,
AI wyłączone); różnice w `deploy/compose.oracle.yaml` (ClamAV w wariancie ARM, Mailpit zamiast SMTP).

Konta zakłada właściciel. Skrypt `deploy/oracle/instaluj.sh` robi resztę na serwerze.

## 1. DuckDNS (2 min)

1. https://www.duckdns.org → zaloguj się (np. kontem GitHub albo Google).
2. W polu „sub domain” wpisz nazwę, np. `naszdzien` → **add domain**. Adres: `naszdzien.duckdns.org`.
3. Zapisz **token** z górnej części strony (to sekret — nie wklejaj go do repozytorium).

## 2. Konto Oracle Cloud (10 min)

1. https://signup.cloud.oracle.com → konto „Free Tier”.
2. **Home region: Germany Central (Frankfurt)** — nie da się go później zmienić (dane w UE).
3. Karta służy tylko do weryfikacji tożsamości. **Nie przechodź na „Pay As You Go”** — wtedy pojawiają się koszty.

## 3. Serwer (5 min)

Menu → Compute → Instances → **Create instance**:

| Pole | Wartość |
|---|---|
| Name | `naszdzien` |
| Image | **Canonical Ubuntu 24.04** |
| Shape | **Ampere → VM.Standard.A1.Flex**, 4 OCPU, 24 GB (oznaczenie „Always Free-eligible”) |
| Networking | nowa sieć VCN z **publiczną** podsiecią, „Assign a public IPv4 address” włączone |
| Add SSH keys | **Upload public key files** → `C:\Users\<Ty>\.ssh\oracle_naszdzien.pub` |
| Boot volume | domyślnie (≈ 47 GB wystarczy) |

**Create.** Po minucie w szczegółach instancji jest **Public IP address** — zapisz go.

„Out of capacity for shape VM.Standard.A1.Flex” = chwilowy brak wolnych serwerów ARM w regionie. Spróbuj
innej „Availability domain” (AD-2, AD-3) albo później (często w nocy) — albo zmniejsz do 2 OCPU / 12 GB.

## 4. Zapora w Oracle (3 min)

Instancja → kliknij podsieć (Subnet) → **Security Lists** → Default Security List → **Add Ingress Rules**:

| Source CIDR | IP Protocol | Destination Port Range |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Port 22 dla SSH jest otwarty domyślnie. Zaporę w systemie Ubuntu otwiera skrypt instalacji.)

## 5. Adres w DuckDNS

Na duckdns.org przy swojej subdomenie wpisz **Public IP** serwera w pole „current ip” → **update ip**.
Skrypt instalacji (z tokenem) sam pilnuje adresu co 10 min.

## 6. Instalacja aplikacji (15–25 min, w większości czekanie)

Z laptopa (PowerShell):

```powershell
ssh -i $HOME\.ssh\oracle_naszdzien ubuntu@<Public IP>
```

Na serwerze:

```bash
git clone https://github.com/danielstolarczyk512-arch/planer-wesela-.git naszdzien
```

```bash
cd naszdzien && sudo bash deploy/oracle/instaluj.sh <subdomena>.duckdns.org <twój e-mail> <token DuckDNS>
```

E-mail jest potrzebny tylko Let's Encrypt (powiadomienia o certyfikacie). Skrypt: pamięć wymiany, Docker,
zapora, wygenerowane sekrety w `deploy/.env.prod`, budowa aplikacji, uruchomienie, nocne kopie bazy
(`/var/backups/naszdzien`, 14 dni), odświeżanie DuckDNS. Na końcu sprawdza `https://<subdomena>.duckdns.org`.

**Po instalacji** skopiuj z serwera `deploy/.env.prod` (przynajmniej `WP_DATA_ENCRYPTION_KEY`) do menedżera
haseł — bez klucza kopie bazy są nieczytelne:

```bash
sudo cat ~/naszdzien/deploy/.env.prod
```

## 7. Na co dzień

- **Adres dla znajomych:** `https://<subdomena>.duckdns.org` — stały.
- **E-maile** (potwierdzenie konta, reset hasła, zaproszenia RSVP) trafiają do Mailpit na serwerze. Podgląd z laptopa:

```powershell
ssh -i $HOME\.ssh\oracle_naszdzien -L 8025:127.0.0.1:8025 ubuntu@<Public IP>
```

  i w przeglądarce http://127.0.0.1:8025 (dopóki to okno SSH jest otwarte). Logowanie działa bez potwierdzania e-maila.
  Prawdziwa wysyłka: darmowy dostawca SMTP (np. Brevo) — wpisać `WP_SMTP_*` w `deploy/.env.prod` i uruchomić ponownie.
- **Aktualizacja do nowej wersji z GitHuba** (z kopią bazy przed aktualizacją):

```bash
cd ~/naszdzien && sudo bash deploy/oracle/aktualizuj.sh
```

- **Logi:** `cd ~/naszdzien/deploy && sudo docker compose -f compose.prod.yaml -f compose.oracle.yaml --env-file .env.prod logs -f api`
- **Kopia na laptop:** `scp -i $HOME\.ssh\oracle_naszdzien ubuntu@<Public IP>:/var/backups/naszdzien/*.dump .` (katalog
  jest tylko dla roota — najpierw na serwerze `sudo cp` do katalogu domowego) albo na Synology.

## Ograniczenia

- Oracle może **odzyskać bezczynną** instancję Always Free (bardzo niskie użycie CPU, sieci i pamięci przez 7 dni).
  ClamAV i worker zwykle wystarczają, ale przy dłuższej przerwie w testach sprawdź, czy serwer działa.
- Brak SLA i umowy powierzenia na tym etapie — **testerzy wpisują zmyślone dane** (regulamin i polityka są robocze).
- To serwer testowy, nie produkcja: decyzja o docelowym hostingu — `docs/hosting.md`.
