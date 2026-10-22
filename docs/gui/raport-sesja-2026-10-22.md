# Raport zbiorczy: rozbudowa 21/22.10.2026

Praca samodzielna na prośbę właściciela („rozwijaj program do mojego znaku”). Każda zmiana miała testy
backendu, typy API, GUI, E2E na 8 profilach (axe), raport i osobny commit. Przed każdą migracją powstała kopia
bazy dev w `backups/` (wesele właściciela nietknięte). Testy E2E działają na osobnej bazie `wedding_e2e`,
a dane tymczasowe były usuwane.

## Nowe funkcje (z analizy `docs/analysis/05`)

| Propozycja | Gdzie w aplikacji | Raport |
|---|---|---|
| 3. Prognoza frekwencji i lista rezerwowa | Goście → Frekwencja | `raport-prognoza-frekwencji.md` |
| 9. Informacje dla usługodawców i potwierdzanie wersji programu | karta usługodawcy, Harmonogram, `/dzien/:token` | `raport-pakiety-uslugodawcow.md` |
| 6. Portfel sponsorów i rola „sponsor” | Budżet → Kto płaci; widok „Nasz wkład” | `raport-portfel-sponsorow.md` |
| 7. Licznik ważności dokumentów do ślubu | Plan → Dokumenty do ślubu | `raport-dokumenty-do-slubu.md` |
| 1. Strażnik waloryzacji cen | Budżet: „Podwyżki cen w umowach” | `raport-waloryzacja.md` |
| 4. Wręczanie zaproszeń osobiście (objazdy) | Goście → Zaproszenia | `raport-wreczanie-zaproszen.md` |
| 8. Transport i noclegi gości | Goście → Transport i noclegi | `raport-transport-noclegi.md` |
| 10. Po weselu | Więcej → Po weselu | `raport-po-weselu.md` |

## Usprawnienia z analizy `docs/analysis/06`

„Wymaga uwagi” na ekranie Dziś i przypomnienia w kalendarzu/ICS; gość wybiera kurs w RSVP; frekwencja
w e-mailu; kursy na ekranie Dzień dla koordynatora; wydruki objazdu i list pasażerów; sponsor zgłasza przelew;
kurs i pokój przy gościu; „kto płaci” przy płatności; podpowiedzi „po weselu”; filtry gości; eksport gości
z wręczeniem, kursem i pokojem; „Co zabrać” na dzień ślubu; e-mail dla sponsora; rozkład przejazdów na stronie
gościa; „Dziś Wasz dzień!”; rodzice-sponsorzy w kreatorze; prognoza w kafelku gości.

## Poprawki znalezione przy okazji

- E-mailowe podsumowanie wysłałoby sponsorowi zadania i płatności całego wesela. Naprawione, sponsor ma własne
  podsumowanie.
- Rejestr modeli `app/models.py` nie zawierał części tabel (także starszych: `SeatingRoom`, `SeatingAutoRun`,
  `UserMfa`, `MfaRecoveryCode`). Autogenerowana migracja mogłaby je usunąć. Uzupełniony i sprawdzony skryptem.
- Wyścig o ostatnie miejsce w kursie: blokada wiersza kursu.
- Długie etykiety stanu na 320 px i zasłonięte przyciski: poprawione (testy E2E na 8 profilach je wychwyciły).

## Bezpieczeństwo i jakość

`bandit`, `pip-audit`, `npm audit` bez zgłoszeń; testy IDOR obejmują wszystkie nowe trasy (test pilnuje, by
żadna trasa wesela nie została bez testu); E2E na buildzie produkcyjnym z CSP zielone. Start aplikacji ok. 142 KB
gzip (limit 170 KB).

## Czeka na decyzje właściciela

1. **Propozycja 2 (AI: umowa zgodna z ofertą):** gdy AI zostanie włączone (decyzja o hostingu).
2. **Propozycja 5 (bilans kopert):** dane o darowiznach od gości wymagają decyzji RODO i prawnika.
3. **Czy sponsor ma widzieć program dnia** (dziś widzi tylko swój wkład).
4. **Czy „Wymaga uwagi” ma trafiać do powiadomień push** (po HTTPS).
5. **Do przeglądu przez prawnika** (etap B), razem z regulaminem: zasady dokumentów do ślubu
   (`planner/documents.py`) i lista zmiany nazwiska (`aftercare/service.py`). Źródła: gov.pl, przykład diecezji.
6. Wcześniejsze: A6 (dopłata przy „Wybieram tę ofertę”), A2 (HEIC na iPhonie), hosting, prawnik, Premium.

## Do obserwacji

Sporadycznie (1 na ok. 350) niestabilny test E2E na profilu 768-light przy pełnym przebiegu pod obciążeniem.
Po powtórzeniach zawsze zielony.
