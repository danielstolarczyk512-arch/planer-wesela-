# Raport testów V5 — 29.10.2026

## Wykonane

**50/50 testów automatycznych zaliczonych** (`python -m unittest discover -s tests -q`), w tym:
- 41 odziedziczonych testów V2/V3/V4: scenariusze, testy ochrony opłat, API projektów, kontrola ujęć, ścieżka montażu MP4, akceptacje klipów.
- 9 nowych testów V5: seed dwóch niezależnych postaci, widoki 4 stron/mimiki, autoobsada starego projektu, przypisanie postaci do promptu, usuwanie sprzecznych wskazówek `live action`, R2V refs oraz `billing_mode: subscription`, odrzucanie modeli premium i braku aktywnego planu, unieważnianie renderów po zmianie obsady, stabilna migracja.
- `python -m compileall` — kod poprawny składniowo.
- `node --check web/app.js` — frontend poprawny składniowo.

## Testy HTTP na działającym lokalnym serwerze

- `GET /api/health` — 200, V5.
- `GET /api/personas` — 200, dwie wbudowane postacie.
- `GET /api/personas/{id}/assets/...` — 200 dla portretu, arkusza, przodu, profilu, tyłu i mimiki.
- `POST /api/personas` — 201, utworzenie nowej postaci.
- `PUT /api/personas/{id}/assets/portrait` — 200, przesłanie prawdziwego PNG, następnie odczyt.
- `POST /api/projects` + `/develop` — 201/200, projekt z automatycznie wybraną obsadą.
- `PUT /api/projects/{id}/casting` — 200, przypisanie nowej postaci do roli.
- `GET /api/projects/{id}/visual-preview` — 200, prompty scen z stylem V5.
- `PUT /api/projects/{id}/shots/S01/keyframe` — 200, lokalny obraz początkowy.
- `POST /api/projects/{id}/shots/S01/keyframe/sync` bez klucza — bezpieczne odrzucenie 502.
- `POST /api/style-guide/sync` bez klucza — bezpieczne odrzucenie 502.

## Nieprzeprowadzone / ograniczenia

- **Nie uzyskano połączenia z rzeczywistym Sogni API ani nie wygenerowano obrazu/wideo na koncie użytkownika.** Operacje podpisanego uploadu zostały zaimplementowane według oficjalnej dokumentacji; bez klucza i sieci nie potwierdzono ich wykonania.
- Próba otwarcia lokalnego serwera w automatyzowanym Chromium została zablokowana (`net::ERR_BLOCKED_BY_ADMINISTRATOR`). **Nie zaliczamy testu przeglądarkowego.** UI przeszło kontrolę składni JS i HTTP backendu.
- Nie potwierdzono, że Sogni udostępnia publiczne API synchronizacji katalogu chmurowego `Personas`; V5 korzysta z własnej biblioteki.
- **Brak gwarancji, że render da dokładnie taki sam styl**. To wymagające zadanie wizualne, a generatywne modele mogą zmieniać twarz i styl. Ręczna kontrola QC pozostaje obowiązkowa.

## Koszty

- Wywołania testowe nie uruchamiały generacji Sogni. Koszt zewnętrzny testów = 0 USD.
- Wykorzystywany kod Sogni wymusza `billing_mode: subscription`; nie przełącza się automatycznie na Spark.
- Faktyczne uprawnienia konkretnego modelu i wykorzystanie abonamentu nadal należy sprawdzić na prawdziwym koncie przed zleceniem renderu.
