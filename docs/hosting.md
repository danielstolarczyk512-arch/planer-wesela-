# Decyzja o hostingu (do akceptacji właściciela)

Status: **propozycja**. Decyzję podejmuje właściciel produktu. Technicznie aplikacja jest gotowa na każdy wariant poniżej (Docker Compose, S3-compatible, konfiguracja przez zmienne).

> Ceny: narzędzia do wyszukiwania w sieci nie działały w tej sesji, a cenniki dostawców ładują kwoty dynamicznie. Kwot **nie podaję z pamięci**. Przed decyzją trzeba je sprawdzić w linkach z sekcji 5 (ceny zmieniają się co kilka miesięcy).

## 1. Wymagania (z testów i architektury)

| Wymaganie | Wartość | Skąd |
|---|---|---|
| Serwer aplikacji | 4 vCPU, 8 GB RAM, 80 GB NVMe, Linux + Docker | test obciążeniowy 100 par bez błędów na 2 procesach API; OCR i automat stołów |
| Lokalizacja danych | UE (najlepiej PL lub DE), umowa powierzenia (art. 28 RODO) | dane gości, w tym potencjalnie o zdrowiu |
| Pliki | magazyn S3-compatible w UE, prywatny kubełek, szyfrowanie po stronie serwera | `WP_STORAGE_BACKEND=s3` |
| Kopie | druga lokalizacja (Synology albo kubełek w innym regionie) | runbook, sekcja 5 |
| SMTP | dostawca transakcyjny z serwerami w UE i umową powierzenia | weryfikacja e-maili, przypomnienia |
| AI (opcjonalnie) | GPU ≥ 8 GB VRAM dla Qwen 2.5 7B **albo** zewnętrzny dostawca z umową powierzenia **albo** AI wyłączone | ewaluacja: ok. 1–2 min na dokument na laptopowym GPU 4 GB |

## 2. Warianty serwera aplikacji

| Wariant | Zalety | Wady | Dla kogo |
|---|---|---|---|
| **A. VPS w UE** (np. Hetzner Cloud: Niemcy/Finlandia; OVHcloud: centrum danych w Polsce) | najniższy koszt, pełna kontrola, Docker 1:1 jak na laptopie, proste kopie | administracja po naszej stronie (aktualizacje systemu, zapora) | **rekomendowany na start** |
| B. PaaS z kontenerami (np. regionalne usługi „app platform” dostawców chmurowych w UE) | mniej administracji, automatyczne skalowanie | wyższy koszt, mniej kontroli; worker i OCR wymagają dopasowania | gdy zabraknie czasu na administrację |
| C. Synology DS225+ w domu | brak dodatkowych kosztów | łącze domowe, brak SLA, bezpieczeństwo fizyczne, RODO | **tylko staging i kopie** |

Baza: na start PostgreSQL w kontenerze na tym samym VPS, z nocnymi kopiami i comiesięczną próbą odtworzenia. Zarządzana baza (managed PostgreSQL w UE) ma sens po pierwszych płacących użytkownikach.

## 3. Warianty AI

| Wariant | Prywatność | Koszt | Uwagi |
|---|---|---|---|
| **1. AI wyłączone na start** (`WP_AI_ENABLED=false`) | pełna | 0 | para wpisuje oferty ręcznie; porównanie, budżet i reszta działają w pełni |
| 2. Serwer z GPU w UE + Ollama | dane nie opuszczają naszej infrastruktury | wysoki stały koszt miesięczny | opłacalne dopiero przy dużym wolumenie analiz |
| 3. Zewnętrzny dostawca LLM (region UE, umowa powierzenia, brak trenowania na danych) | wymaga zgody pary i redakcji PII (gotowe w kodzie, ADR-0005) | płatność za użycie | wymaga implementacji dostawcy (interfejs gotowy) i opinii prawnej |

**Rekomendacja:** start z wariantem A + AI 1. Gdy pierwsze pary potwierdzą, że chcą odczytu ofert, przejść na AI 3 (koszt rośnie razem z użyciem) albo AI 2 przy dużym wolumenie.

## 4. Szacowanie kosztu (do uzupełnienia aktualnymi cenami)

| Pozycja | Wariant startowy | Cena miesięczna |
|---|---|---|
| VPS 4 vCPU / 8 GB (A) | 1 szt. | sprawdzić |
| Kopie/snapshoty dostawcy | opcjonalnie | sprawdzić |
| Magazyn S3 w UE | ok. 10–50 GB na start | sprawdzić |
| SMTP transakcyjny | darmowy próg zwykle wystarcza na start | sprawdzić |
| Domena | 1 | sprawdzić |
| AI | wyłączone | 0 |

## 5. Gdzie sprawdzić ceny

- Hetzner Cloud: https://www.hetzner.com/cloud/ (Object Storage: https://www.hetzner.com/storage/object-storage/)
- OVHcloud (Polska): https://www.ovhcloud.com/pl/vps/ oraz https://www.ovhcloud.com/pl/public-cloud/object-storage/
- Przy każdym dostawcy sprawdzić: lokalizację centrum danych, umowę powierzenia (DPA), certyfikat ISO 27001, kopie/snapshoty, cenę transferu.

## 6. Do decyzji

1. Dostawca VPS (A): Hetzner (DE/FI) czy OVHcloud (PL)?
2. AI na start: wyłączone (rekomendacja) czy od razu wariant 2 albo 3?
3. Domena i dostawca SMTP.
