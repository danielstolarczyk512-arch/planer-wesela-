# Kontrast tokenów (generowane: `task gui:contrast`)

WCAG 2.2: tekst ≥ 4,5:1 (1.4.3), duży tekst i elementy interfejsu ≥ 3:1 (1.4.11). To kontrola tokenów, nie audyt ekranów: po implementacji obowiązuje test axe + ręczny.

| Motyw | Pierwszy plan | Tło | Kontrast | Próg | Wynik | Gdzie |
|---|---|---|---|---|---|---|
| light | `textPrimary` | `background` | 14.91 | 4.5 | ✅ | treść na tle aplikacji |
| light | `textPrimary` | `surface` | 15.93 | 4.5 | ✅ | treść na karcie |
| light | `textPrimary` | `surfaceRaised` | 15.93 | 4.5 | ✅ | treść w panelu/dialogu |
| light | `textPrimary` | `accentSurface` | 13.26 | 4.5 | ✅ | treść na karcie akcentowej |
| light | `textSecondary` | `background` | 5.24 | 4.5 | ✅ | tekst pomocniczy, etykiety nawigacji |
| light | `textSecondary` | `surface` | 5.60 | 4.5 | ✅ | tekst pomocniczy na karcie |
| light | `textSecondary` | `surfaceRaised` | 5.60 | 4.5 | ✅ | tekst pomocniczy w panelu |
| light | `textSecondary` | `accentSurface` | 4.66 | 4.5 | ✅ | tekst pomocniczy na karcie akcentowej |
| light | `textSecondary` | `warningBackground` | 4.94 | 4.5 | ✅ | opis w komunikacie ostrzeżenia |
| light | `textSecondary` | `successBackground` | 4.91 | 4.5 | ✅ | opis w komunikacie sukcesu |
| light | `textSecondary` | `errorBackground` | 4.90 | 4.5 | ✅ | opis w komunikacie błędu |
| light | `textOnPrimary` | `actionPrimary` | 9.74 | 4.5 | ✅ | przycisk główny |
| light | `textOnDanger` | `actionDanger` | 7.70 | 4.5 | ✅ | przycisk usuwania |
| light | `actionPrimary` | `background` | 9.11 | 4.5 | ✅ | link / przycisk tekstowy na tle |
| light | `actionPrimary` | `surface` | 9.74 | 4.5 | ✅ | link na karcie |
| light | `actionPrimary` | `accentSurface` | 8.10 | 4.5 | ✅ | aktywna zakładka, link na karcie akcentowej |
| light | `textGold` | `background` | 5.07 | 4.5 | ✅ | złoto jako tekst na tle |
| light | `textGold` | `surface` | 5.42 | 4.5 | ✅ | złoto jako tekst na karcie |
| light | `goldDecorative` | `background` | 3.14 | 3.0 | ✅ | złoto: tylko tekst ≥ 24 px lub ornament |
| light | `successText` | `successBackground` | 6.96 | 4.5 | ✅ | status: potwierdzone |
| light | `warningText` | `warningBackground` | 5.95 | 4.5 | ✅ | status: oczekuje / do uzupełnienia |
| light | `errorText` | `errorBackground` | 6.74 | 4.5 | ✅ | status / komunikat błędu |
| light | `errorText` | `surface` | 7.70 | 4.5 | ✅ | tekst błędu pod polem formularza |
| light | `infoText` | `infoBackground` | 8.10 | 4.5 | ✅ | komunikat informacyjny |
| light | `neutralText` | `neutralBackground` | 4.77 | 4.5 | ✅ | status: brak odpowiedzi / brak wyceny |
| light | `successText` | `background` | 7.44 | 4.5 | ✅ | liczba potwierdzonych (duża, ale sprawdzamy jak tekst) |
| light | `warningText` | `background` | 6.31 | 4.5 | ✅ | liczba oczekujących |
| light | `controlBorder` | `background` | 3.74 | 3.0 | ✅ | obrys pola na tle aplikacji |
| light | `controlBorder` | `surface` | 3.99 | 3.0 | ✅ | obrys pola / checkboxa na karcie |
| light | `controlBorder` | `surfaceRaised` | 3.99 | 3.0 | ✅ | obrys pola w panelu |
| light | `controlBorder` | `accentSurface` | 3.32 | 3.0 | ✅ | obrys chipa na tle akcentowym |
| light | `selectedBorder` | `surface` | 9.74 | 3.0 | ✅ | obrys wybranej karty |
| light | `focusRing` | `background` | 9.11 | 3.0 | ✅ | fokus na tle |
| light | `focusRing` | `surface` | 9.74 | 3.0 | ✅ | fokus na karcie |
| light | `focusRing` | `surfaceRaised` | 9.74 | 3.0 | ✅ | fokus w panelu |
| light | `focusRing` | `accentSurface` | 8.10 | 3.0 | ✅ | fokus na karcie akcentowej |
| light | `actionPrimary` | `surface` | 9.74 | 3.0 | ✅ | zaznaczony checkbox / radio (wypełnienie) |
| light | `textDisabled` | `surface` | 3.58 | 3.0 | ✅ | nieaktywne (cel czytelności, WCAG nie wymaga) |
| light | `separator` | `surface` | 1.33 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| light | `separator` | `background` | 1.25 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| dark | `textPrimary` | `background` | 15.33 | 4.5 | ✅ | treść na tle aplikacji |
| dark | `textPrimary` | `surface` | 13.51 | 4.5 | ✅ | treść na karcie |
| dark | `textPrimary` | `surfaceRaised` | 12.20 | 4.5 | ✅ | treść w panelu/dialogu |
| dark | `textPrimary` | `accentSurface` | 12.13 | 4.5 | ✅ | treść na karcie akcentowej |
| dark | `textSecondary` | `background` | 8.03 | 4.5 | ✅ | tekst pomocniczy, etykiety nawigacji |
| dark | `textSecondary` | `surface` | 7.08 | 4.5 | ✅ | tekst pomocniczy na karcie |
| dark | `textSecondary` | `surfaceRaised` | 6.39 | 4.5 | ✅ | tekst pomocniczy w panelu |
| dark | `textSecondary` | `accentSurface` | 6.36 | 4.5 | ✅ | tekst pomocniczy na karcie akcentowej |
| dark | `textSecondary` | `warningBackground` | 5.49 | 4.5 | ✅ | opis w komunikacie ostrzeżenia |
| dark | `textSecondary` | `successBackground` | 5.42 | 4.5 | ✅ | opis w komunikacie sukcesu |
| dark | `textSecondary` | `errorBackground` | 5.82 | 4.5 | ✅ | opis w komunikacie błędu |
| dark | `textOnPrimary` | `actionPrimary` | 8.82 | 4.5 | ✅ | przycisk główny |
| dark | `textOnDanger` | `actionDanger` | 10.86 | 4.5 | ✅ | przycisk usuwania |
| dark | `actionPrimary` | `background` | 9.39 | 4.5 | ✅ | link / przycisk tekstowy na tle |
| dark | `actionPrimary` | `surface` | 8.27 | 4.5 | ✅ | link na karcie |
| dark | `actionPrimary` | `accentSurface` | 7.43 | 4.5 | ✅ | aktywna zakładka, link na karcie akcentowej |
| dark | `textGold` | `background` | 9.39 | 4.5 | ✅ | złoto jako tekst na tle |
| dark | `textGold` | `surface` | 8.27 | 4.5 | ✅ | złoto jako tekst na karcie |
| dark | `goldDecorative` | `background` | 9.39 | 3.0 | ✅ | złoto: tylko tekst ≥ 24 px lub ornament |
| dark | `successText` | `successBackground` | 8.01 | 4.5 | ✅ | status: potwierdzone |
| dark | `warningText` | `warningBackground` | 8.51 | 4.5 | ✅ | status: oczekuje / do uzupełnienia |
| dark | `errorText` | `errorBackground` | 8.42 | 4.5 | ✅ | status / komunikat błędu |
| dark | `errorText` | `surface` | 10.24 | 4.5 | ✅ | tekst błędu pod polem formularza |
| dark | `infoText` | `infoBackground` | 9.74 | 4.5 | ✅ | komunikat informacyjny |
| dark | `neutralText` | `neutralBackground` | 6.39 | 4.5 | ✅ | status: brak odpowiedzi / brak wyceny |
| dark | `successText` | `background` | 11.87 | 4.5 | ✅ | liczba potwierdzonych (duża, ale sprawdzamy jak tekst) |
| dark | `warningText` | `background` | 12.45 | 4.5 | ✅ | liczba oczekujących |
| dark | `controlBorder` | `background` | 5.51 | 3.0 | ✅ | obrys pola na tle aplikacji |
| dark | `controlBorder` | `surface` | 4.86 | 3.0 | ✅ | obrys pola / checkboxa na karcie |
| dark | `controlBorder` | `surfaceRaised` | 4.38 | 3.0 | ✅ | obrys pola w panelu |
| dark | `controlBorder` | `accentSurface` | 4.36 | 3.0 | ✅ | obrys chipa na tle akcentowym |
| dark | `selectedBorder` | `surface` | 8.27 | 3.0 | ✅ | obrys wybranej karty |
| dark | `focusRing` | `background` | 9.39 | 3.0 | ✅ | fokus na tle |
| dark | `focusRing` | `surface` | 8.27 | 3.0 | ✅ | fokus na karcie |
| dark | `focusRing` | `surfaceRaised` | 7.47 | 3.0 | ✅ | fokus w panelu |
| dark | `focusRing` | `accentSurface` | 7.43 | 3.0 | ✅ | fokus na karcie akcentowej |
| dark | `actionPrimary` | `surface` | 8.27 | 3.0 | ✅ | zaznaczony checkbox / radio (wypełnienie) |
| dark | `textDisabled` | `surface` | 4.10 | 3.0 | ✅ | nieaktywne (cel czytelności, WCAG nie wymaga) |
| dark | `separator` | `surface` | 1.54 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| dark | `separator` | `background` | 1.74 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| gold | `textPrimary` | `background` | 14.59 | 4.5 | ✅ | treść na tle aplikacji |
| gold | `textPrimary` | `surface` | 15.09 | 4.5 | ✅ | treść na karcie |
| gold | `textPrimary` | `surfaceRaised` | 15.09 | 4.5 | ✅ | treść w panelu/dialogu |
| gold | `textPrimary` | `accentSurface` | 13.04 | 4.5 | ✅ | treść na karcie akcentowej |
| gold | `textSecondary` | `background` | 5.56 | 4.5 | ✅ | tekst pomocniczy, etykiety nawigacji |
| gold | `textSecondary` | `surface` | 5.75 | 4.5 | ✅ | tekst pomocniczy na karcie |
| gold | `textSecondary` | `surfaceRaised` | 5.75 | 4.5 | ✅ | tekst pomocniczy w panelu |
| gold | `textSecondary` | `accentSurface` | 4.97 | 4.5 | ✅ | tekst pomocniczy na karcie akcentowej |
| gold | `textSecondary` | `warningBackground` | 5.08 | 4.5 | ✅ | opis w komunikacie ostrzeżenia |
| gold | `textSecondary` | `successBackground` | 5.04 | 4.5 | ✅ | opis w komunikacie sukcesu |
| gold | `textSecondary` | `errorBackground` | 5.04 | 4.5 | ✅ | opis w komunikacie błędu |
| gold | `textOnPrimary` | `actionPrimary` | 5.98 | 4.5 | ✅ | przycisk główny |
| gold | `textOnDanger` | `actionDanger` | 7.70 | 4.5 | ✅ | przycisk usuwania |
| gold | `actionPrimary` | `background` | 5.78 | 4.5 | ✅ | link / przycisk tekstowy na tle |
| gold | `actionPrimary` | `surface` | 5.98 | 4.5 | ✅ | link na karcie |
| gold | `actionPrimary` | `accentSurface` | 5.17 | 4.5 | ✅ | aktywna zakładka, link na karcie akcentowej |
| gold | `textGold` | `background` | 5.78 | 4.5 | ✅ | złoto jako tekst na tle |
| gold | `textGold` | `surface` | 5.98 | 4.5 | ✅ | złoto jako tekst na karcie |
| gold | `goldDecorative` | `background` | 3.21 | 3.0 | ✅ | złoto: tylko tekst ≥ 24 px lub ornament |
| gold | `successText` | `successBackground` | 6.96 | 4.5 | ✅ | status: potwierdzone |
| gold | `warningText` | `warningBackground` | 5.95 | 4.5 | ✅ | status: oczekuje / do uzupełnienia |
| gold | `errorText` | `errorBackground` | 6.74 | 4.5 | ✅ | status / komunikat błędu |
| gold | `errorText` | `surface` | 7.70 | 4.5 | ✅ | tekst błędu pod polem formularza |
| gold | `infoText` | `infoBackground` | 5.17 | 4.5 | ✅ | komunikat informacyjny |
| gold | `neutralText` | `neutralBackground` | 4.77 | 4.5 | ✅ | status: brak odpowiedzi / brak wyceny |
| gold | `successText` | `background` | 7.68 | 4.5 | ✅ | liczba potwierdzonych (duża, ale sprawdzamy jak tekst) |
| gold | `warningText` | `background` | 6.51 | 4.5 | ✅ | liczba oczekujących |
| gold | `controlBorder` | `background` | 3.58 | 3.0 | ✅ | obrys pola na tle aplikacji |
| gold | `controlBorder` | `surface` | 3.70 | 3.0 | ✅ | obrys pola / checkboxa na karcie |
| gold | `controlBorder` | `surfaceRaised` | 3.70 | 3.0 | ✅ | obrys pola w panelu |
| gold | `controlBorder` | `accentSurface` | 3.20 | 3.0 | ✅ | obrys chipa na tle akcentowym |
| gold | `selectedBorder` | `surface` | 5.98 | 3.0 | ✅ | obrys wybranej karty |
| gold | `focusRing` | `background` | 5.78 | 3.0 | ✅ | fokus na tle |
| gold | `focusRing` | `surface` | 5.98 | 3.0 | ✅ | fokus na karcie |
| gold | `focusRing` | `surfaceRaised` | 5.98 | 3.0 | ✅ | fokus w panelu |
| gold | `focusRing` | `accentSurface` | 5.17 | 3.0 | ✅ | fokus na karcie akcentowej |
| gold | `actionPrimary` | `surface` | 5.98 | 3.0 | ✅ | zaznaczony checkbox / radio (wypełnienie) |
| gold | `textDisabled` | `surface` | 3.58 | 3.0 | ✅ | nieaktywne (cel czytelności, WCAG nie wymaga) |
| gold | `separator` | `surface` | 1.30 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| gold | `separator` | `background` | 1.26 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| romantic | `textPrimary` | `background` | 13.60 | 4.5 | ✅ | treść na tle aplikacji |
| romantic | `textPrimary` | `surface` | 14.40 | 4.5 | ✅ | treść na karcie |
| romantic | `textPrimary` | `surfaceRaised` | 14.40 | 4.5 | ✅ | treść w panelu/dialogu |
| romantic | `textPrimary` | `accentSurface` | 12.41 | 4.5 | ✅ | treść na karcie akcentowej |
| romantic | `textSecondary` | `background` | 6.32 | 4.5 | ✅ | tekst pomocniczy, etykiety nawigacji |
| romantic | `textSecondary` | `surface` | 6.69 | 4.5 | ✅ | tekst pomocniczy na karcie |
| romantic | `textSecondary` | `surfaceRaised` | 6.69 | 4.5 | ✅ | tekst pomocniczy w panelu |
| romantic | `textSecondary` | `accentSurface` | 5.77 | 4.5 | ✅ | tekst pomocniczy na karcie akcentowej |
| romantic | `textSecondary` | `warningBackground` | 5.87 | 4.5 | ✅ | opis w komunikacie ostrzeżenia |
| romantic | `textSecondary` | `successBackground` | 5.88 | 4.5 | ✅ | opis w komunikacie sukcesu |
| romantic | `textSecondary` | `errorBackground` | 5.80 | 4.5 | ✅ | opis w komunikacie błędu |
| romantic | `textOnPrimary` | `actionPrimary` | 6.21 | 4.5 | ✅ | przycisk główny |
| romantic | `textOnDanger` | `actionDanger` | 7.70 | 4.5 | ✅ | przycisk usuwania |
| romantic | `actionPrimary` | `background` | 5.87 | 4.5 | ✅ | link / przycisk tekstowy na tle |
| romantic | `actionPrimary` | `surface` | 6.21 | 4.5 | ✅ | link na karcie |
| romantic | `actionPrimary` | `accentSurface` | 5.35 | 4.5 | ✅ | aktywna zakładka, link na karcie akcentowej |
| romantic | `textGold` | `background` | 5.64 | 4.5 | ✅ | złoto jako tekst na tle |
| romantic | `textGold` | `surface` | 5.97 | 4.5 | ✅ | złoto jako tekst na karcie |
| romantic | `goldDecorative` | `background` | 3.48 | 3.0 | ✅ | złoto: tylko tekst ≥ 24 px lub ornament |
| romantic | `successText` | `successBackground` | 6.56 | 4.5 | ✅ | status: potwierdzone |
| romantic | `warningText` | `warningBackground` | 6.14 | 4.5 | ✅ | status: oczekuje / do uzupełnienia |
| romantic | `errorText` | `errorBackground` | 6.67 | 4.5 | ✅ | status / komunikat błędu |
| romantic | `errorText` | `surface` | 7.70 | 4.5 | ✅ | tekst błędu pod polem formularza |
| romantic | `infoText` | `infoBackground` | 5.11 | 4.5 | ✅ | komunikat informacyjny |
| romantic | `neutralText` | `neutralBackground` | 5.72 | 4.5 | ✅ | status: brak odpowiedzi / brak wyceny |
| romantic | `successText` | `background` | 7.05 | 4.5 | ✅ | liczba potwierdzonych (duża, ale sprawdzamy jak tekst) |
| romantic | `warningText` | `background` | 6.62 | 4.5 | ✅ | liczba oczekujących |
| romantic | `controlBorder` | `background` | 3.37 | 3.0 | ✅ | obrys pola na tle aplikacji |
| romantic | `controlBorder` | `surface` | 3.56 | 3.0 | ✅ | obrys pola / checkboxa na karcie |
| romantic | `controlBorder` | `surfaceRaised` | 3.56 | 3.0 | ✅ | obrys pola w panelu |
| romantic | `controlBorder` | `accentSurface` | 3.07 | 3.0 | ✅ | obrys chipa na tle akcentowym |
| romantic | `selectedBorder` | `surface` | 6.21 | 3.0 | ✅ | obrys wybranej karty |
| romantic | `focusRing` | `background` | 5.87 | 3.0 | ✅ | fokus na tle |
| romantic | `focusRing` | `surface` | 6.21 | 3.0 | ✅ | fokus na karcie |
| romantic | `focusRing` | `surfaceRaised` | 6.21 | 3.0 | ✅ | fokus w panelu |
| romantic | `focusRing` | `accentSurface` | 5.35 | 3.0 | ✅ | fokus na karcie akcentowej |
| romantic | `actionPrimary` | `surface` | 6.21 | 3.0 | ✅ | zaznaczony checkbox / radio (wypełnienie) |
| romantic | `textDisabled` | `surface` | 3.88 | 3.0 | ✅ | nieaktywne (cel czytelności, WCAG nie wymaga) |
| romantic | `separator` | `surface` | 1.31 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| romantic | `separator` | `background` | 1.24 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| romanticDark | `textPrimary` | `background` | 15.58 | 4.5 | ✅ | treść na tle aplikacji |
| romanticDark | `textPrimary` | `surface` | 14.07 | 4.5 | ✅ | treść na karcie |
| romanticDark | `textPrimary` | `surfaceRaised` | 12.67 | 4.5 | ✅ | treść w panelu/dialogu |
| romanticDark | `textPrimary` | `accentSurface` | 12.77 | 4.5 | ✅ | treść na karcie akcentowej |
| romanticDark | `textSecondary` | `background` | 9.64 | 4.5 | ✅ | tekst pomocniczy, etykiety nawigacji |
| romanticDark | `textSecondary` | `surface` | 8.70 | 4.5 | ✅ | tekst pomocniczy na karcie |
| romanticDark | `textSecondary` | `surfaceRaised` | 7.84 | 4.5 | ✅ | tekst pomocniczy w panelu |
| romanticDark | `textSecondary` | `accentSurface` | 7.90 | 4.5 | ✅ | tekst pomocniczy na karcie akcentowej |
| romanticDark | `textSecondary` | `warningBackground` | 7.76 | 4.5 | ✅ | opis w komunikacie ostrzeżenia |
| romanticDark | `textSecondary` | `successBackground` | 7.77 | 4.5 | ✅ | opis w komunikacie sukcesu |
| romanticDark | `textSecondary` | `errorBackground` | 8.49 | 4.5 | ✅ | opis w komunikacie błędu |
| romanticDark | `textOnPrimary` | `actionPrimary` | 9.35 | 4.5 | ✅ | przycisk główny |
| romanticDark | `textOnDanger` | `actionDanger` | 9.77 | 4.5 | ✅ | przycisk usuwania |
| romanticDark | `actionPrimary` | `background` | 10.10 | 4.5 | ✅ | link / przycisk tekstowy na tle |
| romanticDark | `actionPrimary` | `surface` | 9.12 | 4.5 | ✅ | link na karcie |
| romanticDark | `actionPrimary` | `accentSurface` | 8.28 | 4.5 | ✅ | aktywna zakładka, link na karcie akcentowej |
| romanticDark | `textGold` | `background` | 9.85 | 4.5 | ✅ | złoto jako tekst na tle |
| romanticDark | `textGold` | `surface` | 8.90 | 4.5 | ✅ | złoto jako tekst na karcie |
| romanticDark | `goldDecorative` | `background` | 7.66 | 3.0 | ✅ | złoto: tylko tekst ≥ 24 px lub ornament |
| romanticDark | `successText` | `successBackground` | 8.61 | 4.5 | ✅ | status: potwierdzone |
| romanticDark | `warningText` | `warningBackground` | 9.27 | 4.5 | ✅ | status: oczekuje / do uzupełnienia |
| romanticDark | `errorText` | `errorBackground` | 9.29 | 4.5 | ✅ | status / komunikat błędu |
| romanticDark | `errorText` | `surface` | 9.52 | 4.5 | ✅ | tekst błędu pod polem formularza |
| romanticDark | `infoText` | `infoBackground` | 8.28 | 4.5 | ✅ | komunikat informacyjny |
| romanticDark | `neutralText` | `neutralBackground` | 7.98 | 4.5 | ✅ | status: brak odpowiedzi / brak wyceny |
| romanticDark | `successText` | `background` | 10.67 | 4.5 | ✅ | liczba potwierdzonych (duża, ale sprawdzamy jak tekst) |
| romanticDark | `warningText` | `background` | 11.51 | 4.5 | ✅ | liczba oczekujących |
| romanticDark | `controlBorder` | `background` | 5.60 | 3.0 | ✅ | obrys pola na tle aplikacji |
| romanticDark | `controlBorder` | `surface` | 5.06 | 3.0 | ✅ | obrys pola / checkboxa na karcie |
| romanticDark | `controlBorder` | `surfaceRaised` | 4.55 | 3.0 | ✅ | obrys pola w panelu |
| romanticDark | `controlBorder` | `accentSurface` | 4.59 | 3.0 | ✅ | obrys chipa na tle akcentowym |
| romanticDark | `selectedBorder` | `surface` | 9.12 | 3.0 | ✅ | obrys wybranej karty |
| romanticDark | `focusRing` | `background` | 10.10 | 3.0 | ✅ | fokus na tle |
| romanticDark | `focusRing` | `surface` | 9.12 | 3.0 | ✅ | fokus na karcie |
| romanticDark | `focusRing` | `surfaceRaised` | 8.22 | 3.0 | ✅ | fokus w panelu |
| romanticDark | `focusRing` | `accentSurface` | 8.28 | 3.0 | ✅ | fokus na karcie akcentowej |
| romanticDark | `actionPrimary` | `surface` | 9.12 | 3.0 | ✅ | zaznaczony checkbox / radio (wypełnienie) |
| romanticDark | `textDisabled` | `surface` | 4.33 | 3.0 | ✅ | nieaktywne (cel czytelności, WCAG nie wymaga) |
| romanticDark | `separator` | `surface` | 1.31 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
| romanticDark | `separator` | `background` | 1.45 | — | dekoracja | nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |
