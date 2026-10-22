# Raport: przegląd przed wdrożeniem — plan dalszej pracy, A7

Data: 2026-10-21. Stan po v1.1, jej dokończeniu i punktach A1–A4.

## Zależności i licencje
| Sprawdzenie | Wynik |
|---|---|
| `pip-audit` | 1 podatność: `certifi 2026.10.18` (GHSA-6q48-6c7w-9gw2) → **zaktualizowane do 2026.10.19**, ponownie: brak znanych podatności |
| `npm audit` (całość i produkcja) | 0 podatności |
| `bandit -ll` (kod aplikacji) | brak zgłoszeń (tylko informacje o istniejących `nosec`) |
| licencje Python (`pip-licenses --fail-on` AGPL/SSPL/GPL) | OK |
| licencje frontendu (`check-licenses.mjs`) | OK — MIT, Apache-2.0, ISC, BSD, MPL-2.0 (bez modyfikacji), OFL (czcionki), CC0/CC-BY (dane) |
| ClamAV (GPL) | tylko osobny kontener, rozmowa przez TCP (ADR-0006) |

## Bezpieczeństwo nowych funkcji (przegląd kodu)
- **Publiczne adresy** (`/rsvp/{token}` z dopisywaniem osób, `/day/{token}`, ICS): token w ścieżce,
  w bazie tylko skrót; limity zapytań na IP; odpowiedzi API `Cache-Control: no-store` (globalnie),
  `/day` i ICS dodatkowo `noindex`; Caddy `Referrer-Policy: no-referrer`.
- **Osoba towarzysząca:** tylko w swoim zaproszeniu, do terminu RSVP, bezpiecznik 20 osób,
  usuwanie tylko osób dopisanych przez gościa.
- **Link dla sali:** imiona i uwagi dietetyczne (dane o zdrowiu) tylko za zgodą pary
  (`share_catering`), zgoda w audycie; bez zgody same liczby (test sprawdza brak imion w odpowiedzi).
- **Kody QR / e-maile HTML:** SVG z serwera wyświetlany jako obraz (`data:`), nie wstawiany do DOM;
  w e-mailach każda wartość od użytkownika escapowana, brak zewnętrznych zasobów.
- **Skan plików:** plik niesprawdzony lub zainfekowany nie jest pobierany ani przetwarzany;
  zainfekowany usuwany z magazynu; skaner w osobnej sieci (`scan`).
- **Uprawnienia:** nowe trasy zapisu wymagają `wedding:write` (koordynator dnia i osoba z podglądem
  ich nie mają); test kompletności IDOR obejmuje każdą trasę wesela (404 dla obcych, 401 bez logowania).
- **Kopia programu offline:** w `localStorage` tylko tytuły, godziny, miejsca, plan B, przygotowania
  i nazwy usługodawców; wygasa dzień po ślubie, czyszczona przy wylogowaniu. Uwaga: tytuły punktów
  programu wpisuje para (mogą zawierać imiona, np. „przemówienie wujka”) — opisane w polityce.

## Kopie zapasowe
- `scripts.backup_db drill` (osobna baza `wedding_restore_drill`): kopia → pusta baza + pliki →
  porównanie liczby wierszy w kluczowych tabelach i plików — **OK** (0 brakujących plików).

## Testy
- Backend, vitest, E2E dev (8 profili) i E2E produkcyjne z CSP — wyniki w sekcji „Weryfikacja” niżej.
- Budżet startu: 140,9 KB gzip (limit 170 KB).

## Nie wykonano (wymaga decyzji lub sprzętu właściciela)
- **Test obciążenia:** skrypt zostawia w bazie dev wesela „Obciążenie N” (już ponad 300) — najpierw
  decyzja A5 (usunięcie starych, sprzątanie w skrypcie), potem ponowny pomiar.
- **Dostępność na prawdziwych telefonach** (TalkBack, VoiceOver) i **HEIC na iPhonie** (A2).
- Przegląd przez zewnętrzny zespół bezpieczeństwa / test penetracyjny — przed otwarciem rejestracji.

## Weryfikacja
- Backend: `pytest` 739 zaliczonych, 6 pominiętych (OCR, Ollama, prawdziwy ClamAV — na żądanie).
- Frontend: vitest 86; `tsc`, `eslint` czyste.
- E2E dev (8 profili): 248 zaliczonych, bez błędów.
- E2E produkcyjne z CSP: 221 zaliczonych, 1 błąd chwilowy; ten test powtórzony 9/9.
- **Do obserwacji:** w buildzie produkcyjnym (`vite preview` + service worker) średnio raz na pełny
  przebieg pierwsze wczytanie `/logowanie` nie renderuje formularza w limicie czasu (za każdym
  razem inny test, pierwszy krok logowania). Po powtórzeniu test przechodzi. Prawdopodobnie
  wyścig rejestracji service workera przy równoległych kontekstach; do zbadania przy wdrożeniu
  na docelowym serwerze (Caddy), nie występuje w dev.
