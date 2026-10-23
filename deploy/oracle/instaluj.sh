#!/usr/bin/env bash
# Instalacja „Nasz dzień” na serwerze Oracle Cloud Always Free (Ubuntu 24.04, ARM Ampere A1).
# Instrukcja krok po kroku: docs/oracle-cloud.md. Uruchomienie na serwerze, z katalogu repozytorium:
#   sudo bash deploy/oracle/instaluj.sh <subdomena>.duckdns.org <e-mail do Let's Encrypt> [token DuckDNS]
# Skrypt można uruchamiać wielokrotnie: istniejący deploy/.env.prod (sekrety) nie jest nadpisywany.
set -euo pipefail

DOMAIN="${1:?Podaj domenę, np. naszdzien.duckdns.org}"
ACME_EMAIL="${2:?Podaj e-mail do powiadomień o certyfikacie HTTPS}"
DUCKDNS_TOKEN="${3:-}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY="$REPO/deploy"
COMPOSE=(docker compose -f compose.prod.yaml -f compose.oracle.yaml --env-file .env.prod)

[ "$(id -u)" -eq 0 ] || { echo "Uruchom przez sudo."; exit 1; }

echo "== 1/7 Pamięć wymiany (4 GB) — zapas przy budowaniu obrazów"
if ! swapon --show | grep -q .; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== 2/7 Docker i zapora"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 git curl iptables-persistent netfilter-persistent unattended-upgrades
systemctl enable --now docker
id ubuntu >/dev/null 2>&1 && usermod -aG docker ubuntu
# Obrazy Ubuntu w Oracle odrzucają w iptables wszystko poza SSH — otwieramy 80 i 443.
# (Drugą zaporę, „Security List” w konsoli Oracle, otwiera się ręcznie — docs/oracle-cloud.md.)
for port in 80 443; do
  iptables -C INPUT -p tcp -m state --state NEW --dport "$port" -j ACCEPT 2>/dev/null \
    || iptables -I INPUT 5 -p tcp -m state --state NEW --dport "$port" -j ACCEPT
done
netfilter-persistent save >/dev/null

echo "== 3/7 Konfiguracja (deploy/.env.prod)"
if [ ! -f "$DEPLOY/.env.prod" ]; then
  rnd() { python3 -c "import secrets,sys; print(secrets.token_urlsafe(int(sys.argv[1])))" "$1"; }
  KEY="$(python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")"
  CPUS="$(nproc)"; [ "$CPUS" -gt 4 ] && CPUS=4
  umask 077
  cat > "$DEPLOY/.env.prod" <<EOF
# Wygenerowane przez deploy/oracle/instaluj.sh. Sekrety — nie kopiuj do repozytorium.
# Klucz szyfrowania trzymaj też w menedżerze haseł (bez niego kopia bazy jest nieczytelna).
DOMAIN=$DOMAIN
ACME_EMAIL=$ACME_EMAIL
HTTP_PORT=80
HTTPS_PORT=443
POSTGRES_USER=wedding
POSTGRES_PASSWORD=$(rnd 24)
POSTGRES_DB=wedding
WEB_CONCURRENCY=$CPUS
WP_JWT_SECRET=$(rnd 48)
WP_DATA_ENCRYPTION_KEY=$KEY
WP_DATA_ENCRYPTION_KEY_VERSION=1
WP_EXPOSE_DOCS=false
WP_PUBLIC_APP_URL=https://$DOMAIN
WP_LOG_JSON=true
WP_LOG_LEVEL=INFO
WP_RATE_LIMIT_PER_MINUTE=600
WP_DB_POOL_SIZE=10
WP_DB_MAX_OVERFLOW=5
# Bez dostawcy SMTP e-maile trafiają do Mailpit (compose.oracle.yaml).
WP_SMTP_HOST=mailpit
WP_SMTP_PORT=1025
WP_SMTP_STARTTLS=false
WP_MAIL_FROM=Nasz dzień <no-reply@$DOMAIN>
WP_STORAGE_BACKEND=local
WP_AI_ENABLED=false
WP_TERMS_VERSION=2026-10-draft
WP_PRIVACY_VERSION=2026-10-draft
EOF
  umask 022
  echo "   zapisano deploy/.env.prod (nowe sekrety)"
else
  echo "   deploy/.env.prod już jest — zostaje bez zmian"
fi

echo "== 4/7 Budowanie aplikacji webowej (Node w kontenerze)"
docker run --rm -v "$REPO/frontend:/app" -w /app node:22-bookworm-slim \
  sh -c "npm ci --ignore-scripts --no-audit --no-fund && npm run build"

echo "== 5/7 Uruchomienie (pierwsze budowanie obrazu trwa kilka minut)"
cd "$DEPLOY"
"${COMPOSE[@]}" up -d --build

echo "== 6/7 Kopie bazy co noc (14 dni) i odświeżanie adresu w DuckDNS"
install -d -m 700 /var/backups/naszdzien
cat > /usr/local/bin/naszdzien-kopia <<'EOF'
#!/bin/sh
# Nocna kopia bazy „Nasz dzień” (pg_dump, format custom), rotacja 14 dni.
set -e
out="/var/backups/naszdzien/wedding-$(date +%F).dump"
docker exec wedding-planner-prod-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$out.tmp"
mv "$out.tmp" "$out"
find /var/backups/naszdzien -name 'wedding-*.dump' -mtime +14 -delete
EOF
chmod 700 /usr/local/bin/naszdzien-kopia
echo "15 3 * * * root /usr/local/bin/naszdzien-kopia" > /etc/cron.d/naszdzien-kopia
if [ -n "$DUCKDNS_TOKEN" ]; then
  install -d -m 700 /etc/naszdzien
  printf 'SUB=%s\nTOKEN=%s\n' "${DOMAIN%%.duckdns.org}" "$DUCKDNS_TOKEN" > /etc/naszdzien/duckdns
  chmod 600 /etc/naszdzien/duckdns
  cat > /usr/local/bin/naszdzien-duckdns <<'EOF'
#!/bin/sh
# Aktualizuje rekord DuckDNS adresem publicznym serwera (token tylko w /etc/naszdzien/duckdns).
. /etc/naszdzien/duckdns
curl -fsS "https://www.duckdns.org/update?domains=$SUB&token=$TOKEN&ip=" -o /dev/null
EOF
  chmod 700 /usr/local/bin/naszdzien-duckdns
  echo "*/10 * * * * root /usr/local/bin/naszdzien-duckdns" > /etc/cron.d/naszdzien-duckdns
  /usr/local/bin/naszdzien-duckdns || echo "   UWAGA: DuckDNS nie przyjął aktualizacji — sprawdź token"
fi

echo "== 7/7 Sprawdzenie https://$DOMAIN (certyfikat może potrwać do 2 min)"
for _ in $(seq 1 24); do
  if curl -fsS "https://$DOMAIN/health/live" >/dev/null 2>&1; then
    echo
    echo "Gotowe: https://$DOMAIN"
    echo "E-maile (Mailpit): ssh -L 8025:127.0.0.1:8025 ubuntu@<adres serwera>, potem http://127.0.0.1:8025"
    exit 0
  fi
  sleep 5
done
echo "Aplikacja jeszcze nie odpowiada pod https://$DOMAIN."
echo "Sprawdź: Security List w Oracle (porty 80 i 443), adres IP w DuckDNS, logi: cd $DEPLOY && ${COMPOSE[*]} logs caddy"
exit 1
