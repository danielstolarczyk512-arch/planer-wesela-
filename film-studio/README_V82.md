# Nasz Dzień — AI Film Director Studio **8.2**

**Działająca aktualizacja aplikacji V8**. Wersja 8.2 zachowuje moduły głosu, lip-sync, kamerę 360, 60 referencji postaci, montaż i Sogni Unlimited. Dodano **Master Visual Lock V8.2** do pracy z zatwierdzonymi wzorcami stylu i wyglądu bohaterów oraz blokowania animacji z niezaakceptowanych klatek.

## Instalacja na Windows

1. **Zrób kopię całego folderu** `D:\film-studio\V8\Nasz_Dzien_Film_Studio_V8`, w szczególności folderu `data/`. **Nie usuwaj go** — zawiera Twoje projekty, referencje, audio, klipy i decyzje QA.
2. Rozpakuj `Nasz_Dzien_AI_Film_Director_Studio_V8_2_FULL.zip` do nowego folderu, np. `D:\film-studio\V8.2\Nasz_Dzien_Film_Studio_V8_2`.
3. Jeśli chcesz kontynuować projekty z V8, przy wyłączonym serwerze **skopiuj `data/` ze starej instalacji do nowej**, z zachowaniem oryginalnych plików. Utwórz kopię zapasową również przed kopiowaniem. Dane w folderze V8 pozostaną nietknięte.
4. Uruchom `start_windows.bat` (lub `python server.py`) i otwórz `http://127.0.0.1:8765`.
5. Przejdź do zakładki **„Master Visual Lock V8.2”**.

Przy pracy z telefonu korzystaj ze znanego już trybu z hasłem `STUDIO_ACCESS_TOKEN` tylko w prywatnej sieci; nie otwieraj niezabezpieczonego HTTP na publiczny internet.

## Procedura przed nową generacją

1. **Odśwież wzorce**. Zobaczysz cztery niezależne obrazy: `style`, `woman`, `man`, `couple`.
2. `style` wskazuje dotychczas zatwierdzone `assets/style/visual_reference.png` (180 × 206 px). Oryginalny obraz jest zachowany. **To bardzo mała rozdzielczość**; nie traktuj automatycznego upscalingu jako odzyskania szczegółów. Możesz wybrać dokładnie odpowiadający oryginał wysokiej jakości, ale tylko jeśli go posiadasz.
3. Pozostałe trzy obrazy są **kandydatami z checkpointu V6 i wymagają osobnej ręcznej akceptacji**. Obejrzyj każdy i kliknij „Zatwierdź wzorzec”, tylko jeśli twarz i estetyka naprawdę odpowiadają zaakceptowanej parze. W przeciwnym razie wybierz właściwy PNG/JPG. Nie aprobuj źle dopasowanego zdjęcia tylko po to, by odblokować produkcję.
4. Otwórz projekt i kliknij **„Włącz / przypnij wzorce do projektu”**. Program zapisuje niezmienne sumy SHA-256 całego zestawu. Sprawdzanie jest lokalne i nie wydaje Spark.
5. Przejdź do **Storyboardu**; dla każdej animowanej sceny prześlij kadr `PNG/JPG` (z właściwym stylem i twarzami). Obraz może powstać w dowolnym zgodnym, legalnym narzędziu. Użyj istniejącej funkcji „Wyślij klatkę”.
6. W zakładce V8.2 kliknij **„Obejrzyj wgraną klatkę”**, oceń styl i twarze, zaznacz oba potwierdzenia i kliknij **„Zatwierdź klatkę”**.
7. W storyboardzie użyj **„Synchronizuj klatkę”** z Sogni. To ręczna operacja przesyłania obrazu, bez automatycznego zlecania filmu. Zatwierdzony hash wiąże się z tym konkretnym obrazem i wersją ujęcia.
8. Wyceniaj i generuj wideo **przez H3 Image-to-Video**. V8.2 odrzuca T2V i niezatwierdzone / zmodyfikowane pierwsze klatki dla projektów z włączoną blokadą. Zwróć uwagę na czasowe linki Sogni — po 40 godzinach wymagane jest ponowne przesłanie.
9. Obejrzyj **cały gotowy klip** przed zatwierdzeniem stylu, głosów, ruchu ust i spójności. Zmiana projektu lub pliku unieważnia wcześniejsze akceptacje.

**Ważne:** nie wszystkie tryby Sogni gwarantują użycie odrębnych referencji postaci podczas animacji. W H3 I2V najważniejszym wejściem wizualnym jest zatwierdzona klatka startowa. Nie używamy nieudokumentowanych argumentów API. W projektach V8.2 moduł V7 Audio-to-Video otrzymuje lokalnie zatwierdzoną klatkę zamiast losowej referencji V6. Prawidłowe ruchy ust i końcowa stabilność twarzy w czasie trwania klipu muszą zostać sprawdzone osobno.

## Zachowanie istniejących projektów

- Projekty V8 są **domyślnie nietknięte** i nie dostają automatycznej blokady, aby nie wywołać regresji ani nie stracić klipów.
- Po świadomym włączeniu V8.2 konkretne dotychczasowe akceptacje i wyceny w tym projekcie zostaną unieważnione. **Pliki mediów nie są usuwane**.
- Gdy zmieni się którykolwiek z czterech wzorców lub hash lokalnej klatki, system zablokuje nową generację, zanim uruchomi operację Sogni.
- Można wyłączyć blokadę dla danego projektu; rezygnacja z niej oznacza pracę na starszych zabezpieczeniach.

## Co jest, a czego nie ma

**Jest:** realny backend i zakładka przeglądarkowa, SHA-256 masterów, ręczne zatwierdzanie, bezpieczne wczytywanie obrazów PNG/JPG, blokowanie wycen/renderów przed poprawnym preflightem, powiązanie akceptacji z wersją ujęcia, zabezpieczenie starych ujęć V7 Audio-to-Video, dodatkowe testy API.

**Nie ma:** automatycznego rozpoznawania tych samych twarzy na filmie, trenowania LoRA, generowania nowych obrazów bezpośrednio z Golden Master, dowodu zachowania stylu wyłącznie za pomocą hashów, realnego renderu Sogni ani automatycznej oceny artystycznej. SHA-256 zapewnia, że **nie podmieniono zaakceptowanego pliku**, ale nie mierzy jego jakości. Z tego powodu wymagana jest ręczna ocena.

## Testy

```
python -m unittest discover -s tests -q
```

Zalecany następny test: **trzy zatwierdzone klatki — kobieta, mężczyzna, para — oraz jeden krótki render z każdym bohaterem**, wykonany dopiero po sprawdzeniu dostępności abonamentowej. To pozwoli oddzielić problem generowania klatek od driftu, który może pojawić się dopiero podczas animacji.

## Bezpieczeństwo

V8.2 nie odczytuje ani nie zapisuje kluczy API w ZIP i nie uruchamia w tle żadnych operacji płatnych. Sogni nadal ma `billing_mode: subscription`, bez płatnego fallbacku na Spark. Przed prawdziwym użyciem wymagane jest potwierdzenie operacji i aktualnego limitu.
