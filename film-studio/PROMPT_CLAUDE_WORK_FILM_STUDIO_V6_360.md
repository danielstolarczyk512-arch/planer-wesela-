# PROMPT DLA CLAUDE CODE / CHATGPT WORK — NASZ DZIEŃ FILM STUDIO V6

Działaj jako senior Python developer, animation art director, reżyser filmowy oraz QA engineer. Otrzymujesz `Nasz_Dzien_AI_Film_Director_Studio_V6_CAMERA_360.zip` zawierający program oraz 60 obrazów referencyjnych.

## Cel

Przeprowadź **prawdziwą**, bezpieczną produkcję 15–30-sekundowego pilota w firmowym stylu **Golden Storybook 3D** z dwiema niezmienionymi postaciami Nasz Dzień. Wykorzystaj nowy panel Camera 360 Lab tylko tam, gdzie poprawia reżyserię. Nie twórz pełnego obrotu 360° z obowiązku. Nie zamieniaj filmu w pokaz techniczny kamery.

## Etapy

1. Rozpakuj program, odczytaj `README_V6.md`, `INSTRUKCJA_V6_360.md`, `REPORT_V6.md` oraz kod źródłowy. Uruchom testy. Zweryfikuj w prawdziwej przeglądarce karty `Referencje V6` i `Kamera 360`.
2. Przejrzyj 60 PNG w checkpointcie. Nie zakładaj, że mają identyczne twarze. Zwróć uwagę na cztery obrazy wymagające korekty. Zatwierdzaj tylko faktycznie zgodne.
3. Wybierz 2–3 perspektywy w scenie pary przy laptopie (np. front → 3/4 front). W scenie z telefonem przygotuj ruch w stronę ramienia, ale prawdziwy interfejs Nasz Dzień nakładaj w postprodukcji.
4. Sprawdź Sogni API i oficjalny CLI `sogni-agent`, w tym aktywne Unlimited oraz rozliczenia. Nie uruchamiaj niczego, co może kosztować poza abonamentem. Wymagaj `billing_mode: subscription`/`--billing-mode subscription`, bez auto-fallbacku na tokeny. Jeśli nie możesz potwierdzić abonamentu, nie generuj.
5. Wygeneruj najpierw **JEDEN** kąt w Sogni 360 i sprawdź tożsamość postaci, ciągłość garderoby, zegarek, okulary, kształt twarzy, dłonie oraz tło. Jeśli wynik jest nieudany, popraw tylko ten kąt.
6. Zatwierdzony kąt przypisz w programie do ujęcia jako pierwszą klatkę i animuj przez H3 Image-to-Video po oddzielnej zgodzie abonamentowej. Zachowaj style lock.
7. Przygotuj 15–30 s reklamy. Łącz atrakcyjny ruch kamery ze spokojnymi ujęciami reakcji, cięciami pod emocje oraz naturalnymi krótkimi dialogami. Nie pozwól generatorowi wymyślać tekstu aplikacji.
8. Wykonaj pełny ogląd i odsłuch: nie tylko ffprobe i rozpoznanie mowy. Kontroluj przerysowaną mimikę, podwójne kadry, przejścia, głośność, lip-sync, klarowność narracji i puentę.
9. Napraw błędy programu, dodaj regresję, zapisz poprawione źródła. Nie zgłaszaj testu LIVE, jeśli był mockowany.

## Rezultaty

- Prawdziwy MP4 z wygenerowanych ujęć, jeśli uda się bezpiecznie przeprowadzić Sogni Unlimited;
- Raport porównania: ujęcie I2V bez 360 vs kamera pośrednia 360, bez automatycznego przyznawania wysokich ocen;
- Lista zaakceptowanych i odrzuconych referencji, wraz z powodami;
- Protokół kosztowy (czy `paymentModel` faktycznie potwierdził abonament);
- Zaktualizowany kod, testy i paczka ZIP.

Nie przedstawiaj obrazów statycznych jako gotowego filmu. Nie pomijaj sprawdzenia autentycznego wyglądu produktu. Jeżeli środowisko lub dostawca uniemożliwia generowanie, dostarcz faktyczny postęp, raport blokady i działający program, bez fikcyjnego MP4.
