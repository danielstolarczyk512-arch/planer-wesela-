# Jak w V5 uzyskać efekt graficzny jak w naszych wzorcowych obrazach?

## 1. Rozpoznanie stylu

Oryginalny wzorzec **nie jest fotorealistycznym filmem aktorskim** ani klasyczną, błyszczącą kreskówką 3D. To ilustracyjna, ciepła **stylizowana animacja CGI / storybook 3D**. Warstwa obrazu przypomina ręcznie malowaną grafikę filmową:

- **Twarz:** uproszczone, artystycznie modelowane płaszczyzny; naturalnie lekko powiększone oczy, gęste brwi, delikatny rumieniec, wyraźnie czytelna mimika. Urocze, ale nie infantylne.
- **Kontury:** subtelne, rysunkowe linie i miękkie przejścia, bez ostrych fotorealistycznych detali skóry.
- **Włosy:** większe, plastyczne pasma z pojedynczymi rozświetlonymi kosmykami i bursztynową poświatą.
- **Światło:** mocny golden hour przez okno, ciepłe lampy wiszące, bursztynowa obwódka postaci, objętościowa poświata i pyłki w świetle.
- **Kolor:** miodowy / pomarańczowy / brąz / złamane beże; głębokie cienie, bez prześwietlonych bieli i zimnych tonów.
- **Kadry:** bliskie plany dwojga bohaterów, miękki bokeh, wyraźny plan przedni, ciepłe przytulne otoczenie.
- **Animacja:** krótkie, wyczuwalne pauzy, spojrzenia między postaciami, jedna prosta czynność na ujęcie, brak przesadnej gestykulacji.

## 2. Co wcześniej powodowało utratę stylu

V4 i wcześniejsze scenariusze miały w promptach określenia `Cinematic realistic live action`, `believable skin texture` i podobne. Generator miał więc sprzeczne wskazówki. Dodatkowo w kolejnych obrazach mężczyzna stawał się zbyt realistyczny i tracił kreskówkowe proporcje. Sama fraza „Disney/Pixar” nie jest precyzyjną instrukcją stylu; lepiej zdefiniować mierzalne cechy własnego wzorca.

## 3. Co robi V5

1. Stosuje jeden stały, **wersjonowany** preset `golden_storybook_3d` we wszystkich scenach.
2. Usuwa z *efektywnych promptów produkcyjnych* sprzeczne formuły live action, nie kasując oryginalnego scenariusza.
3. Przypisuje bohaterów po ID do konkretnych scen. Twarz, fryzura, ubiór i styl są opisywane na podstawie wybranego arkusza postaci.
4. Przechowuje gotowe **osobne referencje kobiety i mężczyzny** (przód, 3/4, profil, tył, mimika).
5. Umożliwia przesłanie osobnych portretów oraz wzorca samego stylu do Sogni jako HTTPS media references. Przy dozwolonym H3 R2V referencje trafiają do faktycznego żądania wideo.
6. Umożliwia użycie klatki początkowej do H3 I2V — najlepszy praktyczny sposób kontroli *dokładnego wyglądu pierwszej klatki*.
7. Zachowuje QC i wymaganą ręczną akceptację klipów, aby wykryć zmianę twarzy lub stylu.

## 4. Zalecany workflow produkcyjny

A. **Zatwierdź model sheets**. Kobieta i mężczyzna muszą mieć ten sam stopień animowanej stylizacji. Nie mieszaj kadru mężczyzny wyglądającego jak zdjęcie z rysunkową kobietą.

B. **Przygotuj najpierw klatkę wzorcową 2-osobową.** Wystarczy jedno piękne ujęcie pary w zbliżonym kadrze z takim samym kontrastem, oczami, materiałami i oświetleniem jak załączony wzorzec. Zatwierdź to jako referencyjny „master frame”.

C. **Własne referencje:** prześlij portrety bohaterów przez zakładkę Postacie, ewentualnie wzorzec stylu; ponownie zastosuj obsadę. W H3 Reference-to-Video wybierz minimalną liczbę pomocnych obrazów, zaczynając od 1 na bohatera + 1 stylu. Zbyt wiele niezgodnych ilustracji może pogorszyć rezultat.

D. **Najlepiej I2V**: do kluczowych scen wgraj lokalnie zatwierdzony master frame jako klatkę początkową. Wyślij do Sogni; V5 ustawi H3 I2V. To mocniejsza kotwica graficzna niż tekst, choć **nie gwarantuje** zachowania wszystkich szczegółów w ruchu.

E. **Krótki, jednoznaczny ruch.** Generuj 5–8 sekund źródła, a w montażu zostaw 1–3 najlepsze sekundy. Jedna scena = jedno główne działanie. Zbyt wiele działań w jednym promptcie daje deformacje.

F. **Kontrola jakości:** patrz na czoło, nos, linię szczęki, oczy, fryzurę, dłonie, strój, kontrast i pozycję lamp. Jeśli zmieniła się twarz, wymień tylko ujęcie, nie cały film.

G. **Autentyczny produkt:** prawdziwy ekran aplikacji nagrany osobno i nałożony w montażu; nie generuj UI z AI.

## 5. Zasady „NIE” dla naszego presetu

Nie używaj `photorealistic`, `live-action`, `hyper-real skin pores`, `high fashion portrait`, `real human actor`. Nie zmieniaj stylu w obrębie reklamy. Unikaj migotania tekstur, przesadnych ust, plastikowych oczu, wysycenia pomarańczu do bieli i różnic w tonacji między scenami.

## 6. Jak ocenić, czy rzeczywiście udało się odtworzyć efekt

Porównaj klatkę z wynikiem z pięciu względów: **(1) podobieństwo twarzy, (2) stopień kreskówkowej stylizacji, (3) bursztynowe światło, (4) materiałowość i cienie, (5) nastrój pary**. Sam lepszy bitrate czy wyższe 1080p nie wystarczy. Nie deklaruj sukcesu, dopóki nie sprawdzisz prawdziwego wideo w ruchu.

## 7. Ograniczenia kosztowe

Nie każdy nowy model obrazu wspiera referencje. Nie przełączaj się automatycznie na premium. Sprawdź w API dostępność modelu i plan, wycenę, oraz wymuś `billing_mode: subscription`. Brak aktywnego Unlimited albo brak zgodnej operacji = wstrzymanie bez wydatków Spark.
