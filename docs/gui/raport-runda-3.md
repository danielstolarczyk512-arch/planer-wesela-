# Raport: trzecia runda usprawnień (U16–U18)

Data: 2026-10-22. Bez migracji (tylko nowe pola w odpowiedziach API).

## U16. Ile zaproszeń zamówić w drukarni

**Problem:** para liczy ręcznie, ile zaproszeń zamówić, i zwykle zapomina o zapasie.

**Co zrobiono:** na ekranie Goście → Zaproszenia jest kafelek „Do zamówienia w drukarni”, np. „6: 3 zaproszenia
dla rodzin + 3 zapasu”. Zasady liczenia:

- jedno zaproszenie na rodzinę;
- bez rodzin wysyłanych online;
- rodziny bez ustalonego sposobu wręczenia liczą się jako papierowe;
- zapas to 10%, ale co najmniej 3 (pomyłki, dopisani goście, pamiątka);
- osobno doliczamy osoby czekające na liście rezerwowej.

API: pole `print_order` w `GET /invitation-delivery`.

## U17. Prognoza frekwencji dla poprawin

**Problem:** poprawiny mają zwykle mniej gości i osobną cenę u sali, a prognoza liczyła tylko przyjęcie.

**Co zrobiono:** gdy w wydarzeniach są poprawiny (`after_party`), ekran Frekwencja pokazuje osobną kartę
„Prognoza: Poprawiny” z liczbą i przedziałem. Liczenie:

- poprawiny liczymy tym samym modelem co przyjęcie;
- kto odmówił przyjęcia, liczy się na poprawinach jako odmowa;
- odpowiedzi o poprawinach nie zmieniają już prognozy przyjęcia. Wcześniej, gdy nie było wydarzenia typu
  „przyjęcie”, prognoza brała pod uwagę wszystkie wydarzenia, także poprawiny.

API: pole `after_party` w `GET /attendance-forecast`.

## U18. Koszt z podwyżkami na ekranie Dziś

**Problem:** gdy umowy pozwalają podnieść cenę, ekran Dziś pokazywał tylko koszt według dzisiejszych cen.

**Co zrobiono:** w kafelku „Przewidywany koszt” jest link „z podwyżkami cen do X zł”. Wartość to najgorszy
wariant z ekranu Budżet (te same założenia: 5% i 10% rocznie). Link prowadzi do sekcji „Podwyżki cen w umowach”.
Kafelek pokazuje link tylko wtedy, gdy któraś umowa ma klauzulę podwyżki.

## Weryfikacja

- Backend:
  - `test_invitation_delivery.py`: liczba do drukarni, zapas i rezerwa;
  - `test_reserve_forecast.py`: poprawiny osobno, odmowa przyjęcia, prognoza przyjęcia bez zmian.
- Frontend: `invitations.test.ts` (`printBreakdown`).
- E2E rozszerzone o te funkcje, zielone na 8 profilach:
  - „Zaproszenia: objazdy…”: kafelek drukarni;
  - „Frekwencja: prognoza…”: karta poprawin;
  - „Budżet: podwyżka ceny…”: link z ekranu Dziś.
