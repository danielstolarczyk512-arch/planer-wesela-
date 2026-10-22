# ADR-0007: Środowiska: laptop (dev), Synology DS225+ (backup/staging), VPS UE (prod)

- Status: zaakceptowany, Data: 2026-10-19

## Decyzja
- Development: Docker Desktop na laptopie (najszybsza pętla, reset bazy w sekundy, praca offline).
- Synology DS225+: nocne kopie `pg_dump` + plików z dev (od Etapu 2), później opcjonalny staging w sieci LAN przez Container Manager. Dostęp zdalny tylko przez VPN.
- Produkcja: VPS w UE + backup off-site szyfrowany. Nie domowy NAS (łącze, brak SLA, RODO, ekspozycja do internetu).

## Konsekwencje
Konfiguracja wyłącznie przez zmienne środowiskowe, obrazy niezależne od hosta, więc to samo `compose.yaml` (z profilami) działa na laptopie i NAS.
