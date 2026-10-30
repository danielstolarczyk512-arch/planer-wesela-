# NASZ DZIEŃ — Film Director Studio V7 (Audio-First + Cinematic Camera)

## Po co powstała V7

Błąd poprzednich produkcji: film generowany niezależnie od polskiej ścieżki dialogowej, potem głos dokładany w montażu. Dlatego ruch ust nie odpowiadał mowie. V7 dodaje produkcję **audio-first**: zatwierdzona wypowiedź (WAV/MP3/M4A) + zatwierdzony portret → Sogni FastH3 **Image+Audio-to-Video**. Ruch ust *może* być sterowany nagraniem, ale wynik należy obejrzeć i odsłuchać. Nie gwarantuje synchronizacji.

## Co jest zaimplementowane

- Nowa zakładka **Reżyser V7 · głos i kamera** w aplikacji Python/JS.
- Wybór mówiącego ONA / ON; powiązanie głosu z postacią, tekstem po polsku oraz zatwierdzonym zdjęciem V6.
- Import własnej wypowiedzi polskiej WAV, MP3, M4A. Plik pozostaje lokalny do wyraźnej zgody.
- Przegląd i walidacja metadanych dźwięku (FFprobe), limit 25 MB, 60 s; pojedyncze ujęcie H3 do 15,08 s.
- Lokalna receptura CLI IA2V z `--billing-mode subscription`, bez automatycznego fallbacku; **jedno zadanie na wyraźną zgodę**.
- Dla krótkich dialogów (<5,17 s) podczas renderu dodawana jest cisza do 5,2 s, oryginalne audio pozostaje nienaruszone.
- Import powstałego klipu do projektu po obejrzeniu; obowiązkowy, oddzielny przegląd ruchu ust, polszczyzny i tożsamości.
- Opcjonalna diagnostyka ruchu pikseli w ręcznie wskazanym obszarze ust (`opencv-python`, `numpy`). Nie jest testem synchronizacji fonemów.
- Cinematic Coverage: plan planu wspólnego, zbliżenia na mówiącą osobę i ujęcia reakcji. Każda zmiana kąta wymaga osobnego ujęcia źródłowego.
- Reżyserskie presety zbliżenia, przez ramię, reakcji, planu wspólnego, 45° orbit i odkrycia sali. Pełny obrót 360 tylko referencyjnie, nie podczas dialogu.
- Zgodność z biblioteką 60 PNG i poprzednią obsługą Sogni 360 (z `orbit.zip`).
- Blokada montażu V7 dla ujęć dialogowych bez odpowiedniego planu audio i zaakceptowanego lip-sync.
- Testy automatyczne API, importu audio, rozliczeń i reguł kamery.

## Uruchomienie Windows

1. Zainstaluj Python 3.10+ i FFmpeg + FFprobe. Uruchom `start_windows.bat` dla trybu lokalnego.
2. W przeglądarce `http://127.0.0.1:8765`. Utwórz / otwórz projekt, kliknij **Referencje V6** i zatwierdź właściwe obrazy twarzy.
3. Kliknij **Reżyser V7 · głos i kamera**. Wybierz ujęcie i mówiącą postać, zaplanuj zbliżenie.
4. Nagraj krótki polski dialog (najlepiej naturalny głos z telefonu, za zgodą mówiącej osoby); zaimportuj WAV/MP3/M4A i wpisz dokładny tekst.
5. Zatwierdź plan. Wybierz zatwierdzoną referencję mówiącej osoby. Pokaż bezpłatny przepis generacji.
6. Aby użyć Sogni: ustaw **nowy** `SOGNI_API_KEY` jako zmienną środowiskową i zainstaluj Node.js >=22.11 oraz oficjalny `@sogni-ai/sogni-creative-agent-skill`; użyj `start_sogni_windows.bat`.
7. Po potwierdzeniu planu Unlimited możesz zatwierdzić **jedną** generację H3 IA2V. Obejrzyj wynik, zaimportuj, oceń ręcznie usta oraz sprawdź cały klip w Produkcji.
8. Kontynuuj montaż dopiero po zatwierdzeniu.

Nie wklejaj klucza API do kodu ani do publicznych repozytoriów.

## Język polski

Do jakości premium zalecamy **własne nagrania mówione po polsku**, z autoryzacją osób nagrywających. Zewnętrzny Piper może brzmieć sztucznie. Oryginalna rodzina Qwen3-TTS zgodnie z oficjalnym repozytorium nie wymienia języka polskiego na liście 10 wspieranych języków (stan październik 2026), więc nie należy polegać na niej jako gwarantowanym silniku polszczyzny. Studio nie używa płatnych dostawców mowy.

## Wideo 360

W `orbit.zip` przesłano zbiór 8 perspektyw postaci i klip obrotowy. To dobra baza do przeglądania turntable, ale nie oznacza rzeczywistej, trójwymiarowej pracy kamery w kuchni. Do reklamy zalecamy osobne bliskie kadry mówiącego i reakcji partnera; orbit 30–45° tylko między wypowiedziami. W razie krzyżowania sylwetek, rąk i ekranu smartfonu generacja 360 ma podwyższone ryzyko zniekształceń.

## Ograniczenia i stan testów

- Nie wykonywano na tym komputerze płatnych ani abonamentowych generacji w prawdziwym Sogni. **Nie potwierdzono na żywo jakości warg ani polskiego głosu.**
- Interfejs web ma sprawdzoną składnię JS i testy HTTP backendu. Chromium w tym środowisku zablokowało nawigację do lokalnego serwera (`ERR_BLOCKED_BY_ADMINISTRATOR`); test wizualny przeglądarki jest NIEZALICZONY.
- Plany `coverage` nie renderują automatycznie przebitek. Można przygotować prompt/ujęcie, ale potrzebne są oddzielne zatwierdzone materiały, aby wykonać filmowy montaż.
- Pomiar ruchu pikseli ust jest heurystyką, a **nie automatyczną oceną dopasowania fonemów**.
- Bez sprawdzenia aktywności subskrypcji, bez zgody na pojedynczy render, bez zatwierdzonego obrazu i audio proces nie przechodzi do chmury.

Dalszy plan wdrożenia: automatyczne porównanie fonemów po polsku z lokalną ekstrakcją punktów ust i poprawa polskiego TTS/voicedesign po zweryfikowaniu licencji, jakości i kosztów. Nie udawaj, że te etapy są już w V7.
