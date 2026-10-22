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
