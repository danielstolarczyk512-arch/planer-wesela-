# Raport: „Co zabrać” na dzień ślubu

Data: 2026-10-22. Druga runda usprawnień. Migracja `b5d7f9a1c3e4` (tabela `day_checklist_items`).

## Problem

W dniu ślubu ginie zawsze to samo: obrączki, dowody świadków, koperty dla zespołu. W planie było jedno zadanie
„Przygotujcie obrączki, dokumenty i koperty”. Brakowało listy z osobą odpowiedzialną, którą świadek odhacza na
miejscu.

## Co zrobiono — Harmonogram dnia → „Co zabrać”

- Para układa listę: rzecz i kto bierze (np. „Obrączki · świadek”). Może usunąć pozycję.
- **„Wczytaj typową listę”:** 10 typowych pozycji (obrączki, dowody, dokumenty z USC/parafii, buty na zmianę,
  zestaw ratunkowy, ładowarka, wydruki, winietki, prezenty dla rodziców, przekąska) oraz **koperty z płatności
  zaplanowanych na dzień ślubu** („Koperta: Zespół (dopłata)”), **bez kwot**, bo koordynator nie widzi budżetu.
  Ponowne wczytanie nie dubluje pozycji.
- **Odhaczanie:** para i koordynator dnia (uprawnienie `DAY_RUN`). Koordynator nie edytuje listy. Postęp
  „3 z 11” w nagłówku.

## API

`GET /weddings/{id}/day-checklist` (`DAY_READ`), `POST` (para), `POST …/typical`, `PATCH …/{item}` (If-Match),
`DELETE …/{item}`, `PUT …/{item}/done` (`DAY_RUN`). Lista jest w eksporcie wesela.

## Weryfikacja

- Backend: `tests/api/test_day_checklist.py` (typowa lista, koperty bez kwot, brak duplikatów, If-Match,
  koordynator odhacza, ale nie edytuje), trasy w `test_idor.py`.
- Frontend: `dayChecklist.test.ts`. E2E „Dzień: lista »Co zabrać«…” zielony na 8 profilach.
- Pełny przebieg: backend **965 passed**, vitest **121**, E2E dev **354 passed** bez błędów.
- Baza dev: kopia przed migracją `backups/wedding-20261022-064644-przed-co-zabrac.dump`.
