# Nasz Dzień — AI Film Director Studio V8.6

## Zmiany V8.6

**W pełnym ZIP-ie znajduje się oryginalny pakiet Wujek Boguś/Bogdan V1 z wcześniejszej rozmowy.** 18 obrazów PNG z manifestu zostało zweryfikowanych z SHA-256. Bohater ma stałe ID `33333333-3333-4333-8333-333333333333` i zachowuje charakterystyczną wąską twarz, wąsy, włosy z siwiejącymi skroniami, śliwkowy garnitur, bladoróżową koszulę i złoty łańcuszek. Nie nadpisuje postaci Daniela.

- Oryginalne 60 referencji pary pozostaje nietknięte, w katalogu `assets/reference_v6` jest teraz **78** zdjęć (`KOBIETA` 25, `MEZCZYZNA` 25, `PARA` 10, `WUJEK` 18).
- Wujek jest importowany do **Postacie** podczas pierwszego uruchomienia, bez internetu. Dostępnych jest 12 standardowych slotów (portret, pełna sylwetka, profile, ekspresje) oraz 6 dodatkowych obrazów w galerii V6.
- Pełne obrazy nie są automatycznie zatwierdzane do generacji. Każda referencja Bogusia ma status `pending_final_review`. Jego użytkowy master to `WUJEK__PORTRAIT`.
- Trzyosobowe ujęcia `ONA+ON+WUJEK` korzystają z trzech osobnych referencji (po jednej na postać), bez pomylenia twarzy Daniela i Bogusia. Przy przekroczeniu czterech URL referencyjnych adapter zatrzymuje zadanie i wyświetla komunikat.
- Wbudowana lista postaci w **Postacie** filtruje ID po prawdziwej roli. Również API odrzuca przypisanie Bogusia pod `ON`.
- Wujek może być mówcą w Voice Studio V8, scenariuszu, uploadzie WAV V8.5 i Reżyserze Audio-to-Video V7; jakość dubbingu nadal zależy od konkretnego nagrania.
- **Rendered Film Inspector V8.6** bada prawdziwy lokalny MP4, nie tylko opis storyboardu: długość, rozdzielczość, FPS, kodeki, metadane kolorów, orientacyjny procent mało ruchliwych klatek, dłuższe przestoje i ciszę na końcu. Obejmuje także film 180 s. Działa przez FFmpeg i FFprobe, bez generacji Sogni.
- Bezpieczny lokalny import MP4 do pojedynczego projektu (maks. 200 MB) jest dostępny w nowej zakładce. Wymaga potwierdzenia użytkownika. Plik jest przechowywany pod `data/v86_films/<project-id>/source.mp4` i może zostać przeniesiony przez backup projektu.
- Kontrola SHA-256 plików przy ich zatwierdzaniu i wykorzystaniu. Zmiana faktycznej zawartości z unieważnioną sumą powoduje odmowę dalszego użycia referencji.
- PWA: nowa wersja cache `nd-film-v86-shell-1`, aby ograniczyć ryzyko pokazywania starego panelu.

## Windows

1. Zapisz backup V8.5. Rozpakuj **FULL** do oddzielnego folderu, np. `D:\film-studio\V8.6\Nasz_Dzien_Film_Studio_V8_6`.
2. Jeśli masz dotychczasowe projekty, przy **zamkniętych obu aplikacjach** uruchom w PowerShell: `./MIGRUJ_Z_V85.ps1 -Source 'D:\film-studio\V8.5\Nasz_Dzien_Film_Studio_V8_5'`. Skrypt sporządzi backup bieżących danych docelowych i skopiuje `data` ze starej instalacji; nie kopiuje przestarzałego kodu ani obrazów wzorcowych.
3. Uruchom `start_windows.bat`, potem w przeglądarce `http://127.0.0.1:8765`.
4. Otwórz **Postacie**, wybierz Wujka Bogusia w roli `WUJEK`; otwórz **Referencje V6**, filtr **Wujek Boguś**, obejrzyj i zaakceptuj odpowiednie zdjęcia. Dopiero potem dodaj `WUJEK` do `characters` konkretnego ujęcia.
5. Nowa zakładka **V8.6 · Wujek Boguś i audyt filmu** pozwala wgrać końcowy MP4 oraz uzyskać analizę jego rzeczywistego przebiegu.

Przykład scenariusza: gdy Boguś zjawia się przy planie stołów, zaczyna „Ja tylko jedną rzecz podpowiem…” — obraz `signature_gesture.png` najlepiej odpowiada gestowi, a `portrait.png` zbliżeniu z dialogiem. **Nie zmieniaj wzorca Golden Master pary na portret Bogusia.** Każda postać ma swoją tożsamość, a styl renderu pozostaje wspólny.

## Faktyczny zakres weryfikacji

- 148/148 testów jednostkowych/integracyjnych w środowisku lokalnym; podstawowe testy HTTP z uploadem MP4 i bez zgody, 18 zgodnych sum obrazów, wybór trzech ról, ochronę referencji, uruchamianie modułu FFmpeg na rzeczywistym wideo.
- Node `--check` i Python `compileall` przechodzą.
- Nie wykonano generacji w Sogni, nie instalowano dużego modelu dubbingowego, nie przeprowadzono pełnego testu wizualnego GUI w przeglądarce Windows.
- **Inspektor nie ocenia automatycznie stylu, tożsamości postaci, polszczyzny, fonemów, poprawności ust ani komediowego aktorstwa**. Te elementy wymagają ręcznej akceptacji. Interpretuj pomiar ruchu jako wskaźnik techniczny, nie jako metrykę jakości animacji.
- Nie wszystkie referencje są automatycznie zatwierdzone. To zamierzone zabezpieczenie.

## Bezpieczeństwo

Brak działań Sogni w nowych endpointach V8.6; bezpłatna analiza lokalna. Stara obsługa Sogni pozostaje z obowiązkiem `billing_mode=subscription` i wcześniejszej zgody. Nie kopiuj kluczy API do ZIP ani projektu; ustaw je przez `.env` / zmienne środowiskowe zgodnie z dotychczasową instrukcją.

## Powtórz własną kontrolę

```bash
python -m unittest discover -s tests -q
node --check web/app.js
python -m compileall -q studio server.py director
```
