# ADR-0001: Modularny monolit w Pythonie/FastAPI

- Status: zaakceptowany (Etap 1), Data: 2026-10-19

## Kontekst
Jeden deweloper + Claude Code, wczesny produkt, niepewny zakres. Potrzebne szybkie zmiany modelu i niski koszt utrzymania.

## Decyzja
Jedna aplikacja FastAPI (Python 3.12, Pydantic v2, SQLAlchemy 2.x, Alembic) z modułami domenowymi (`app/modules/*`). Moduły komunikują się tylko przez publiczne serwisy. Jeden obraz Dockera, dwa procesy: `api` i `worker`.

## Konsekwencje
+ jedno wdrożenie, jedna baza, proste transakcje, łatwe testy.
+ możliwość wydzielenia modułu później (np. `documents` + `ai`), bo granice są jawne.
− dyscyplina granic modułów musi być pilnowana (test importów, np. `import-linter`, MIT).

## Odrzucone
Mikroserwisy (koszt operacyjny), Django (cięższe ORM/admin niepotrzebne przy API-first), Node/TypeScript (zespół i biblioteki do dokumentów/AI są lepsze w Pythonie).
