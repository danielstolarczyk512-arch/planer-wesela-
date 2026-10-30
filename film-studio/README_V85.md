# Nasz Dzień — AI Film Director Studio V8.5

Wersja oparta bezpośrednio na V8.4, z nowym MASTER STYLE wskazanym przez użytkownika.

## Zmiany

1. **Nowy styl Golden Master** `assets/style/visual_reference.png`, **1122×1402 px**. Ten obraz został wskazany przez użytkownika jako podstawowy styl. Drugi przesłany obraz to zrzut poprzedniego panelu, nie jest używany jako nowa referencja. Kopia nowego wzorca: `assets/style/MASTER_GOLDEN_STORYBOOK_V85.png`.
2. **Nieaktualne linki referencji**: lokalny kod SHA-256 sprawdza, czy zapisany adres referencji Sogni dotyczy tego samego obrazu. W przypadku zmiany Golden Master nie używa starego adresu.
3. **Voice & Subtitle Timeline V8.5**: w zakładce V8.5 do każdej kwestii można wgrać WAV 16-bit PCM (max 25 MB), odsłuchać go, zatwierdzić i ewentualnie przesunąć o +/-2 s względem początku ujęcia. Zmiana WAV unieważnia zaakceptowany lip-sync i stary klip. Montaż obsługuje osobną ścieżkę głosu, źródłowe audio z klipów i opcjonalnie muzykę. Można wyłączyć audio źródłowych klipów. Napisy SRT wykorzystują realne czasy zatwierdzonych WAV.
4. **V8.5 Continuity Contact Sheet**: lokalnie tworzy zestawienie MASTER + 3 rzeczywiste klatki MP4 do manualnej oceny. Nie gwarantuje rozpoznania twarzy.
5. **Cinematic QA**: wykrywanie zbyt długich monologów i plansz w krótkich reklamach, powtarzalnych ujęć, braków autentycznego UI.
6. **Backup projektu**: przenosi dodatkowo `data/v85_audio/<ID>`, ale przy przywracaniu wymaga ponownego odsłuchu i akceptacji.
7. Zachowane moduły V8.4: storyboard 180 s, Character Bible, Visual Lock, Image Edit referencyjny, Camera 360, Sogni Unlimited, Voice Studio i stare tryby montażu.

## Instalacja Windows

1. Rozpakuj archiwum do **nowego folderu** `D:\film-studio\V8.5\Nasz_Dzien_Film_Studio_V8_5`.
2. Uruchom `start_windows.bat` i otwórz `http://127.0.0.1:8765`.
3. Przejdź do **V8.5 · styl, dubbing i montaż**.
4. W **Master Visual Lock V8.2** przejrzyj nowe referencje i zatwierdź je. W przypadku istniejących projektów trzeba ponownie przypiąć zaktualizowany wzorzec. Dotychczasowe klipy pozostają w archiwum, ale należy sprawdzić je względem nowego stylu.
5. Wybierz scenę z dialogiem, wgraj PCM WAV, odsłuchaj i zatwierdź. Potem uruchom nowy render audio-driven i obejrzyj ruch ust na wideo. Nie akceptuj dawnego klipu po zmianie dubbingu.
6. Wybierz **Włącz montaż wielościeżkowy**, a następnie, jeśli nowy dubbing ma całkowicie zastąpić oryginalne audio, również **Wycisz dźwięk źródłowych klipów**. Bez zatwierdzonych WAV nie można wyciszyć wszystkich klipów.
7. Zmontuj film w dotychczasowym panelu **Produkcja**, a plik SRT znajdziesz obok MP4 albo pobierzesz z panelu V8.5. Napisy są **osobnym plikiem**, nie są automatycznie wypalane w MP4.

### Migracja z V8.4

**Najpierw zamknij oba programy i zachowaj kopię danych.** W PowerShell wewnątrz nowego folderu uruchom:

```powershell
.\MIGRUJ_Z_V84.ps1 -Source "D:\film-studio\V8.4\Nasz_Dzien_Film_Studio_V8_4"
```

Skrypt kopiuje tylko `data`, nie nadpisuje kodu i nowego wzorca STYLE. Robi kopię zastępowanych danych. `tools/install_master_v85.py` aktualizuje status STYLE, ale **nie zmienia automatycznie istniejących przypięć w projektach**. Po migracji otwórz panel i ponownie przypnij wzorce do każdej produkcji.

### Zależności

- Python 3.10+ (jak w V8.4).
- FFmpeg + FFprobe w PATH wymagane do montażu, analizy nagrań i WAV.
- Pillow opcjonalny do generowania plansz porównawczych (sprawdź `pip install Pillow`).
- Chatterbox, model polskiej mowy, NIE jest częścią paczki i nie został tutaj uruchomiony.

## Testy

```powershell
py -3 -m unittest discover -s tests -q
```

Testy V8.5 obejmują lokalne WAV, zatwierdzanie, wykrywanie zmiany audio, SRT, rzeczywisty miks FFmpeg, backup/restore i HTTP API. Nie uruchamiają żadnej generacji Sogni.

## Ograniczenia

- SHA-256 obrazu to kontrola pliku, a nie gwarancja tożsamości twarzy w filmie.
- Plansze kontaktowe wymagają rzeczywistego obejrzenia przez człowieka.
- Lip-sync trzeba obejrzeć z dźwiękiem; brak niezawodnej automatycznej oceny polskich fonemów.
- V8.5 nie instaluje nowego TTS, nie gwarantuje poprawy polskich głosów i nie generuje bezpłatnych klipów Sogni.
- V8.5 nie jest pełną wielościeżkową aplikacją NLE: obsługuje warstwę dubla WAV na wspólnej osi filmu oraz opcjonalną muzykę, nie ma dowolnego edytora SFX czy keyframe'ów głośności.
- Nie testowano renderów na Twoim koncie Sogni ani GUI w docelowym Windows. Nie pobrano Spark i nie wywołano płatnych modeli.
