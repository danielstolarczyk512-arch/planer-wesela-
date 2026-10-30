# RAPORT WDROŻENIA NASZ DZIEŃ — FILM STUDIO V6

## Zakres wdrożenia

Podstawa: rzeczywisty kod Film Studio V5 (lokalna aplikacja Python/SQLite/JS) oraz użytkownika ZIP `NASZ_DZIEN_CHARACTER_REFERENCE_LIBRARY_V6_CHECKPOINT(1).zip`.

### Implementacja zakończona

1. Import **60 osobnych plików PNG** do `assets/reference_v6` oraz `index.json` z danymi ze źródłowego checkpointu (25 kobieta, 25 mężczyzna, 10 para).
2. Zachowane statusy jakościowe: **56 `pending_final_review` i 4 `pending_correction`**, zero fikcyjnie zaakceptowanych. Ręczne zatwierdzenie / odrzucenie i zapisywanie decyzji lokalnie poza źródłowymi assetami.
3. `studio/reference_v6.py`: wybór zatwierdzonych referencji per ujęcie i kontrola kategorii obsady, pilnowanie czasowych adresów HTTPS, jawne przesyłanie po zgodzie. Możliwość ręcznej selekcji maksymalnie 3 obrazów na scenę, blokada scen bez zatwierdzonej obsady (V6 Identity Lock).
4. `studio/camera360.py`: 6 presetów (Portrait Trio, Dialogue Reveal, Phone Reveal, Wedding Room, Hero Orbit, Full 360), przestrzeń 96 kątów, ocena skoków perspektywy, ostrzeżenia przy dwóch bohaterach i UI, brak automatycznych generacji.
5. `studio/camera360_cli.py`: generacja **jednego** nowego kąta z zatwierdzonego lokalnego obrazu przez oficjalne narzędzie `sogni-agent` (o ile jest zainstalowane na komputerze). Wymagane `SOGNI_API_KEY`, aktywny Unlimited, wyraźna zgoda i argument `--billing-mode subscription`. Render nie jest uruchamiany podczas przeglądania strony.
6. Możliwość obejrzenia wyniku 360 i jawnego przypisania go jako `firstframe_local` do istniejącego pipeline H3 Image-to-Video.
7. Panel HTML/JS z osobnymi zakładkami `Referencje V6` i `Kamera 360`, paginacją zdjęć, presetami, przyciskiem pojedynczej generacji oraz podglądem.
8. Dodatkowa `qc/visual_v6.py`: lekka lokalna analiza heurystyczna statycznych i podejrzanie zdublowanych klatek. Nie twierdzi, że identyfikuje twarze lub anomalie anatomiczne.
9. Nowe testy i dokumentacja, gotowy preset JSON i polecenie dla Claude/Work.

## Testy i ograniczenia

- **70/70** testów przeszło. Szczegółowe wyniki uruchomienia w `TEST_REPORT_V6.txt`.
- Testy API i CLI obejmują symulowane wykonanie narzędzia oraz asercję `--billing-mode subscription` i pojedynczego kąta. **Nie są testem generacji z konta użytkownika**.
- W tej sesji nie wykonywano prawdziwego zlecenia Sogni 360, WAN 2.2, LTX ani H3; nie znamy aktualnego stanu Unlimited na koncie użytkownika.
- Nie istnieje jeszcze automatyczny eksport gotowego płynnego `orbit.mp4` ze wszystkich punktów 360, bo takie renderowanie wymaga wielu osobno uprawnionych operacji i osobnych kontroli QC. V6 świadomie ogranicza domyślny flow do krótkiego ruchu i jednej klatki.
- Brak zweryfikowanego testu interfejsu w prawdziwej przeglądarce; JS sprawdzono składniowo przez Node, API testowano HTTP.
- Brak automatycznego audio-first lip sync oraz działającego zaawansowanego rozpoznawania zmiany tożsamości postaci. To wymagania dla kolejnej iteracji, nie funkcje do deklarowania jako wykonane.

## Ocena krytyczna Sogni 360

**Zalety:** szeroka przestrzeń kątów, zewnętrzny API/CLI, możliwość przygotowania wielu ujęć z jednej zatwierdzonej sceny, efektywny parallax/krótkie orbitalne ruchy w 1–3-sekundowym montażu.

**Ograniczenia:** AI *dopowiada tył postaci i tło*, więc między punktami mogą zmienić się fryzura, pieprzyki, guziki, ułożenie rąk, zegarek, architektura i proporcje twarzy. Sytuacja pogarsza się przy dwóch osobach i ekranie telefonu. Obietnica absolutnej spójności 360 nie jest wiarygodna. Nie używaj 360 jako rozwiązania problemu mówionych dialogów i lip sync.

**Rekomendacja:** dla reklam stosować 2–3 zaakceptowane kąty, ruch 45–90°, mocne close-upy reakcyjne i realistyczne działanie produktu wstawione w postprodukcji. Pełny obrót 360° traktować jako test biblioteki postaci, nie domyślny język filmu.

## Dalsze cele

- Jednorazowy pilot na prawdziwym Unlimited: pojedyncze 3/4 kobiety i mężczyzny, następnie wybrane animowane ujęcie 5–8 s z H3; sprawdzić raporty rozliczeń.
- Własny selektor *zachowania tożsamości* oparty na zaakceptowanych obrazach, bez automatycznej zmiany „prawidłowej twarzy” na podobną.
- Zachowanie PRAWIDŁOWEGO interfejsu aplikacji i kontrola polskiej mowy/lip sync.
