# NASZ DZIEŃ — FILM DIRECTOR STUDIO V8.3

**Wydanie:** 29.10.2026 · **Instalacja:** Windows 10/11 · Python 3.10+ · przeglądarka Chromium/Edge/Chrome · FFmpeg wymagany do renderu montażowego.

To kompletna, lokalna aktualizacja V8.2: 60 referencji postaci, istniejące Studio Głosu, Camera 360, kontrola ust, storyboard, montaż i nowe moduły V8.3. Przed zakupami modelu lub generacjami nic nie pobiera z Sogni.

## Uruchomienie

1. Rozpakuj pełny ZIP do `D:\film-studio\V8.3\Nasz_Dzien_Film_Studio_V8_3`.
2. Jeżeli masz stare projekty V8.2, wykonaj kopię folderu V8.2. Następnie użyj `MIGRUJ_Z_V82.ps1 -Source "D:\film-studio\V8.2\Nasz_Dzien_Film_Studio_V8_2"` w PowerShell albo skopiuj własne pliki `data/` ręcznie (nie nadpisuj nowszych).
3. Uruchom `start_windows.bat`. Otwórz `http://127.0.0.1:8765`.
4. W nowym kreatorze wybierz **180 sekund**. Program stworzy offline plan 46 ujęć w 4 aktach. To storyboard do poprawiania, nie 180 sekund gotowych renderów.
5. Wejdź do **Master Visual Lock V8.2**, obejrzyj i zatwierdź cztery obrazy: styl, kobieta, mężczyzna i para. Zalecane są wysokiej jakości wzorce. Obecny wzorzec stylu 180×206 px wymaga wymiany, aby szczegóły twarzy były czytelne.
6. Włącz blokadę wzorców w projekcie. Następnie wejdź do **Produkcja V8.3 · film i referencje** i wybierz **Włącz tryb V8.3**.
7. Wybierz ujęcie i kliknij **Sprawdź referencje** — to jest lokalne i bezpłatne. Po świadomej zgodzie **Wyślij zatwierdzone obrazy**. Dane opuszczą wtedy komputer i zostaną przesłane do Sogni, bez automatycznej generacji obrazu.
8. Na storyboardzie kliknij **Wycena klatki AI**. V8.3 zwraca tylko **lokalny plan bez prawdziwej kwoty** i nie wysyła zapytania do Sogni. Dopiero ręczna zgoda i limit capacity units uruchamiają workflow w trybie `billing_mode=subscription`. Jeśli operacja nie jest objęta abonamentem, powinna zostać odrzucona przez dostawcę; zweryfikuj dostępność modelu w swoim koncie.
9. Pobierz wynikowy obraz, obejrzyj go, wgraj jako klatkę startową ujęcia, zatwierdź w Master Visual Lock, zsynchronizuj klatkę i dopiero wtedy przygotuj animację Image-to-Video. Każdy z tych kroków wymaga osobnej decyzji.
10. Dla długiej produkcji korzystaj z **Pokaż kolejkę** w V8.3; po utracie łączności odzyskaj istniejący `workflow_id` i nie rozpoczynaj ponownie gotowego ujęcia.

## Nowe funkcje

- **180s Story Film:** prawdziwy projekt 180 s, podział na akty i 46 krótkich ujęć, pięć rzeczywistych przebitek UI (pierwsza około 27,5 s), finalny overlay.
- **Character Bible 8.3:** kanoniczne opisy dwóch bohaterów (jedno źródło). Nie zastępuje klatek referencyjnych.
- **Referencyjna edycja klatek:** oficjalny hosted tool `edit_image` z `sourceImageIndex=-1` oraz dodatkowymi `referenceImageIndices`. Do modelu przekazywane są rzeczywiste obrazy HTTPS (po przesłaniu i zatwierdzeniu).
- **Ochrona przed dryftem:** SHA256 i wersje wzorców; po edycji ujęcia stare przesyłki referencji przestają obowiązywać.
- **Bezpieczna kontrola kosztu:** podgląd offline. Stare `confirm_cost=false` mogło uruchamiać workflow z zerową wyceną, dlatego V8.3 tego nie robi. Brak automatycznie sprawdzonej ceny; użytkownik wybiera limit przed startem.
- **Kopia przenośna:** przyciski *ZIP z klipami* oraz *ZIP bez MP4*. Kopia zawiera bieżący projekt, zdjęcia, nagrania, lokalne materiały i manifest SHA256; nie zawiera kluczy i z założenia nie przenosi czasowych linków chmurowych.
- **Przywracanie:** `python tools/restore_portable_v83.py <backup.zip> --target <folder V8.3>`; istniejące projekty nie są nadpisywane, a akceptacje wizualne muszą zostać przeprowadzone ponownie na docelowym komputerze.

## Ważne ograniczenia

- **Realne renderowanie `edit_image` nie zostało wykonane** — nie miałem Twojego aktualnego, zatwierdzonego dostępu do konta Sogni i nie uruchamiałem płatnych operacji. Model `krea-identity-edit` ma udokumentowany selektor, ale dostępność w Twoim Unlimited nie jest zweryfikowana. Nie ma automatycznego fallbacku na Premium Spark.
- Zatwierdzenie obrazów jest świadomą decyzją użytkownika. Hashowanie pliku nie dowodzi podobieństwa twarzy; model wideo nadal może ją zmieniać.
- Polskie TTS i synchronizacja ust zachowały funkcje V8; **nie stwierdzam**, że V8.3 poprawia jakość polskich głosów. Integracja Chatterbox nadal jest opcjonalna i nieprzetestowana na Twoim GPU.
- „Film 180 s” to dokładny, edytowalny harmonogram produkcji. Pełny MP4 wymaga autentycznych klipów, UI i ręcznych ocen.
- Testy lokalnego backendu i tworzenia ZIP przechodzą; **test wizualny w Chromium nie mógł się odbyć** (`ERR_BLOCKED_BY_ADMINISTRATOR`).
- Nie wystawiaj serwera 8765 na internet bez HTTPS i uwierzytelnienia.

## Testy

```powershell
py -3 -m unittest discover -s tests -q
```

Dokument: `TEST_REPORT_V83.md`.

## Dokumentacja dostawcy (stan 29.10.2026)

- https://docs.sogni.ai/sogni-intelligence/creative-agent-workflows/
- https://docs.sogni.ai/sogni-intelligence/media-upload-urls/
- https://docs.sogni.ai/api-reference/workflows/
- https://docs.sogni.ai/api-reference/personal-loras/

Aktualny stan licencji, rozliczenia i kompatybilności modeli należy zweryfikować na koncie przed generacją.
