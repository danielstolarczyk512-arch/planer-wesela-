# V8.7 — Kreator referencji (nowe postacie i lokalizacje)

Nowy moduł `studio/reference_forge_v87.py` tworzy **zestawy referencji** dla postaci i lokalizacji w stylu **realistycznym** (jak prawdziwa reklama aktorska) albo **animowanym** (Golden Storybook).

## Przebieg
1. **Utwórz zestaw** — opis + do 3 obrazów źródłowych (np. stylizowane portrety, zdjęcie miejsca). Bez obrazu źródłowego obraz powstaje z samego opisu.
2. **Kotwica** — 3 kandydaci na widok główny (postać: „przód”, lokalizacja: „plan ogólny, wieczór”). Człowiek ogląda i zatwierdza jeden.
3. **Reszta zestawu** — postać: 3/4 w lewo i w prawo, profil, uśmiech, zdziwienie, powaga, cała sylwetka; lokalizacja: dzień, dwa plany średnie, detal, widok z góry. Każdy widok powstaje z kotwicą jako pierwszą referencją.
4. **Zatwierdzenie i manifest** — `manifest.json` z SHA-256 zatwierdzonych plików. SHA to kontrola pliku, nie gwarancja tożsamości twarzy w filmie — zgodność ocenia człowiek.

## Użycie
CLI (z katalogu programu, `SOGNI_API_KEY` w środowisku):

```
python -m tools.reference_forge create character "Ona" "opis..." --style realistic --src portret.png
python -m tools.reference_forge anchor ona --cands 3
python -m tools.reference_forge approve ona front_c --viewed
python -m tools.reference_forge set ona
python -m tools.reference_forge sheet ona
python -m tools.reference_forge manifest ona
```

API (nagłówek `X-Studio-Token`): `GET/POST /api/v87/forge`, `GET /api/v87/forge/<id>`, `POST …/generate` (wymaga `confirm_cost: true`), `POST …/approve` (wymaga `viewed: true`), `GET …/image/<klucz>`, `POST …/manifest`. Generowanie w API blokuje żądanie do końca partii. Interfejsu graficznego jeszcze nie ma.

## Koszty
Tylko `billing_mode: subscription` (Unlimited): wycena przed startem, limit jednostek, kontrola fair-use (stop od 92%), porównanie salda Spark i `sparkSpent` przed i po partii. Bez Premium Spark i płatnych tokenów. Dane w `data/references_forge/` są poza gitem.

## Ograniczenia
- Twarz w stylu realistycznym potrafi dryfować między widokami; kotwica pomaga, ale nie gwarantuje.
- Źródło w stylu animowanym przy stylu realistycznym trzeba „przetłumaczyć”; kotwicę trzeba obejrzeć.
- Brak interfejsu graficznego w zakładce; brak widoku z tyłu (filtr treści Sogni blokował takie próby).
- Testy (`tests/test_v87_forge.py`) nie wywołują Sogni.
