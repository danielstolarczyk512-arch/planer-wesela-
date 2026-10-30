# Changelog V5

- Własny lokalny Character Library (SQLite), 2 wbudowane persony i 24 referencje PNG z wcześniej przygotowanych przez nas arkuszy.
- Nowe postacie: imię, rola, opis, ograniczenia spójności; lokalne przesyłanie portretów, arkuszy, 4 widoków i 6 mimik.
- Zakładka „Postacie” na komputerze i telefonie, wybór obsady do ról w filmie, podgląd promptów i obrazy referencyjne.
- Wersjonowany styl Golden Storybook 3D i kontrola tekstu przeciwko niezamierzonemu live action.
- Wzorcowy obraz stylistyczny jako lokalna referencja + opcjonalna synchronizacja do Sogni.
- Obsługa oficjalnego przepływu Sogni image/uploadUrl → podpisany PUT → image/downloadUrl; wymaga zgody, aktywnego abonamentu i sieci.
- Przy istniejących HTTPS referencjach przygotowanie `media_references` i indeksów H3 Reference-to-Video.
- Lokalna klatka startowa ujęcia + ręczne przesłanie do H3 Image-to-Video.
- Zabezpieczenie wersjonowania: zmiana obsady unieważnia stare wyceny/rendery.
- Zachowano V4: montaż MP4, FFmpeg, QC, storyboard, ścieżki audio, automatyczne ograniczenie rozliczeń do `subscription`.
- Brak nieudokumentowanych operacji na chmurowej bibliotece Sogni Personas; własna biblioteka działa niezależnie od niej.
