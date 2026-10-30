# Nasz Dzień — AI Film Director Studio V8.0

## Instalacja / aktualizacja z V7

Jest to **prawdziwa wersja V8 aplikacji** z zachowanymi modułami V7: biblioteka stałych postaci, Golden Storybook 3D, 60 referencji w wariancie FULL, Reżyser IA2V oraz Kamera 360. Rozpakuj ZIP i uruchom `start_windows.bat` lub `python server.py`. Otwórz `http://127.0.0.1:8765` i zakładkę **Studio V8 · głos i montaż**.

Przy aktualizacji ze starszego folderu **zachowaj jego katalog `data/`** (projekty, zatwierdzenia, referencje, dźwięki i MP4). Nie nadpisuj swoich aktywnych danych przykładową bazą z archiwum. Najpierw wykonaj kopię zapasową.

## Nowe funkcje

1. **Voice Studio 8.0**: wybór postaci ONA/ON, polskiego tekstu i emocji, przygotowanie dwóch wariantów lokalnego Chatterbox Multilingual V3, odsłuch i wybór A/B, zatwierdzenie dopiero po sprawdzeniu wymowy. Generacja nie zaczyna się bez osobnej zgody.
2. **Audio-first**: zatwierdzony wariant jest kopiowany do folderu V7 Audio. Następnie przejdź do `Reżyser V7 → voice-plan → Image+Audio-to-Video`, obejrzyj i zatwierdź lip-sync. **V8 nie generuje w pełni zweryfikowanej synchronizacji ust bez wykonania tego etapu**.
3. **Pace Director**: wykrywanie długich scen, podobnych kolejnych ustawień kamery, zbyt późnego pojawienia się prawdziwej aplikacji i proponowanie skrótów, które **nie zmieniają automatycznie dialogów i EDL**.
4. **Motion Diagnostics**: FFmpeg wylicza udział prawie identycznych próbek klatek i jednolitych plansz z gotowego lokalnego MP4. Analiza klatek nie ocenia artystycznej jakości ani poprawnego ruchu ust.
5. **Product Demo Reframe**: kadrowanie autentycznego nagrania UI pionowo bez szarych pasów. Wymaga potwierdzonego pochodzenia, ręcznej akceptacji po zmianach i prawdziwego pliku MP4.
6. **Zabezpieczenia**: nigdy nie wysyła głosu do płatnego dostawcy TTS, nie zmienia istniejących mechanizmów `subscription` Sogni, pilnuje ręcznej zgody przed lokalnym TTS, zatwierdzenia wariantu i odsłuchu.

## Opcjonalny Chatterbox — instalacja bez opłat API

**Nie jest dołączony do ZIP** — jego wagi i zależności są duże. Oficjalny projekt: https://github.com/resemble-ai/chatterbox (licencja MIT; przy użyciu komercyjnym sprawdź również licencje używanych nagrań referencyjnych).

Na komputerze z kompatybilną NVIDIA CUDA i Pythonem 3.11:

```powershell
py -3.11 -m venv .venv-tts
.\.venv-tts\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install chatterbox-tts
```

Gdy serwer V8 używa innego interpretera, ustaw ścieżkę do Python 3.11:

```powershell
$env:V8_TTS_PYTHON=(Resolve-Path ".\.venv-tts\Scripts\python.exe").Path
```

Po pierwszym wyraźnym zleceniu generacji Chatterbox może pobrać własne wagi modelu; nie jest to koszt płatnego API. Jeśli brakuje GPU lub są problemy z instalacją, nagraj legalny polski dialog telefonem i użyj importu w Reżyserze V7. Powyższego opcjonalnego syntezatora **nie uruchamialiśmy w tej sesji na GPU**, więc nie obiecujemy, że na każdej konfiguracji zadziała bez dostrojenia zależności.

**Sposób pracy**: w Reżyserze V7 wgraj plik z próbką głosu, jeśli chcesz jej użyć jako referencji. W Studio V8 wybierz ujęcie, mówcę, emocję, zaznacz zgodę i kliknij „Zapisz instrukcję TTS”. Następnie oddzielnie uruchom lokalne warianty A/B, odsłuchaj i zatwierdź jeden. W Reżyserze V7 ustaw transkrypt, wygeneruj wideo IA2V wyłącznie po potwierdzeniu abonamentu i zatwierdź zgodność ust. Nie używaj niezgodnej z prawami nagranej osoby próbki głosu.

## Montaż i UI

„Analizuj rytm” nie wykonuje żadnych renderów i nie skraca klipów sam. „Kadrowanie UI” można ustawić na prawdziwym ujęciu z potwierdzonym pochodzeniem. Po zmianie wymagana jest ponowna kontrola. Przeskalowanie nie tworzy nowych detali obrazu; może wyciąć istotne elementy menu, sprawdź więc cały efekt.

## Testy

```powershell
python -m unittest discover -s tests -q
```

Zaliczone testy kodu nie są dowodem, że **polski głos brzmi już naturalnie** lub że automatycznie otrzymujemy poprawny lip-sync. Przetestuj rzeczywiste ujęcie z audio i obejrzyj je przed produkcją 180 sekund.

## Koszty i klucze

Nie umieszczaj klucza w archiwum, tekstach promptów ani repozytorium. Warianty TTS powstają lokalnie; Sogni nadal działa wyłącznie w trybie abonamentowym. Zgodnie z poprzednimi wersjami nie ma automatycznego fallbacku na Spark. Limity fair-use i dostępność modeli mogą się zmieniać; każde realne zlecenie Sogni wymaga osobnego sprawdzenia uprawnień.
