# NASZ DZIEŃ — Film Studio V6 | Camera 360 Lab

## Dlaczego warto — i czego 360 NIE robi

Tryb Sogni 360 przekształca **pojedynczy obraz** w syntetyczne ujęcia z innych perspektyw (nie tworzy prawdziwego modelu geometrii 3D). W oficjalnej dokumentacji: **8 azymutów × 4 wysokości × 3 odległości = 96 konfiguracji**, do 64 waypointów na projekt. Nowe klatki są generowane przez **Qwen Image Edit 2511 + Multiple Angles LoRA**, a przejścia w Sogni 360 przez **WAN 2.2 lub LTX-2.3**. Nie utożsamiać tego z funkcją MiniMax H3: H3 może potem animować zatwierdzoną klatkę jako Image-to-Video.

Źródła: https://docs.sogni.ai/sogni-360/ oraz https://github.com/Sogni-AI/sogni-creative-agent-skill/blob/main/references/video-editing.md

## JAK TO ROBIĆ W REKLAMACH

| Przypadek | Preset V6 | Kadry | Co zyskujesz | Największe ryzyko |
|---|---|---|---|---|
| Pierwsze pokazanie naszych bohaterów | Portrait Trio | front → 3/4 prawo → 3/4 lewo → lekko z góry | gotowe alternatywne spojrzenia, orientacja kamery | nowe rysy twarzy, pozycja okularów i zegarka |
| Reakcja pary po rozwiązaniu problemu | Dialogue Reveal | front → 3/4 prawo | delikatne wrażenie obejścia stolika | ręce i twarze dwóch osób mogą się zdeformować |
| Ekran telefonu z planerem | Phone Reveal | 3/4 prawo → prawy wyższy zbliżony | atrakcyjny ruch do detalu | tekst w telefonie będzie zmyślony — PRZYKLEJ prawdziwe nagranie UI w montażu |
| Sala weselna | Wedding Room | szeroko na wprost → szeroko 3/4 z góry | dynamiczny establishing shot | zmieniająca się architektura i liczba stołów |
| Sam portret lub produkt | Hero Orbit | przód → 3/4 → profil | atrakcyjne krótkie przejście, wyraźna forma | utrata zgodności odleglejszego profilu |
| Pokaz testowy do Character Bible | Full 360 | 8×45° + punkt startowy | kontrola widoków i krótki turntable | dużo generacji, przesadnie sztuczny efekt w reklamie |

### Krytyczny plan produkcji

1. W `Referencje V6` przejrzyj 60 obrazów; **nie akceptuj automatycznie**. W checkpointcie 56 ma status oczekujący na weryfikację i 4 wymagają korekty.
2. Wybierz 1 portret `MASTER` i dobrany profil. Dla wspólnych ujęć wybierz zatwierdzone referencje obojga i wspólny kadr pary.
3. Wybierz w `Kamera 360` 2–3 punkty. **Nie generuj w ciemno 360°**.
4. Wygeneruj **jedną nową klatkę** przez przycisk Sogni 360 po potwierdzeniu planu Unlimited. System musi mieć `sogni-agent`, `SOGNI_API_KEY`, aktywne Unlimited; komenda wymusza `--billing-mode subscription`.
5. Obejrzyj nowy kąt: czy oczy, nos, fryzura, zegarek, ubranie i relacja pary nie uległy zmianie?
6. Jeśli klatka jest dobra, wybierz `Użyj klatki jako startowej` dla danego ujęcia. Następnie przejdź do Storyboardu: wyślij zatwierdzoną klatkę i użyj H3 I2V, **oddzielnie potwierdzając generację**.
7. Podczas montażu wycinaj krótkie fragmenty (około 1–3 s) i łącz je z reakcjami, detalami oraz prawdziwym nagraniem aplikacji. Unikaj bezcelowego obrotu kamery.
8. Po renderze sprawdź audio, twarze i ruch. Test lokalny V6 nie jest testem rzeczywistego Sogni.

### Bezpieczeństwo

- Wgranie nowej referencji do Sogni i uruchomienie generacji 360 są **oddzielnymi operacjami**.
- `--billing-mode subscription` jest twardą blokadą żądań nieobjętych Unlimited. Aplikacja dodatkowo sprawdza aktywny abonament. Nie uruchamia płatnego fallbacku ani nie składa pełnego obrotu automatycznie.
- W raporcie lokalnym `payment_model_reported` może być `not_reported`. To nie jest dowód opłaty ani bezpłatności. Zobacz historię w Sogni i potwierdź `paymentModel: subscription` jeśli dostawca udostępnia tę informację.
- Nie stosuj `--billing-mode auto`, `tokens`, dodatkowych Premium Spark, płatnego upscalingu ani zewnętrznych API.
- Opcjonalne `Pillow` w lokalnej kontroli klipów oznacza tylko **heurystyki**, nie gwarancję identyczności twarzy.

## Czego w V6 NIE zaimplementowano

- Pełnego chmurowego workflow z automatycznymi przejściami WAN/LTX pomiędzy wszystkimi klatkami.
- Prawdziwego trenowania LoRA, fotogrametrii lub rigowanej postaci 3D.
- Zaawansowanej identyfikacji twarzy i nieomylnego testu jakości ruchu.
- Automatycznej obróbki polskich dialogów, lip-sync i wieloetapowej regresji filmu 120 s.

Dostępny jest natomiast lokalny **plan**, **RĘCZNY render pojedynczego kąta** przez oficjalny CLI, **podgląd**, **przypisanie PNG jako klatki startowej** do istniejącego pipeline H3 i **kontrola zatwierdzania referencji**.
