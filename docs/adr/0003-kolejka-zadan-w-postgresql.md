# ADR-0003: Kolejka zadań w tabeli PostgreSQL

- Status: zaakceptowany, Data: 2026-10-19

## Decyzja
Tabela `jobs` (typ, payload JSONB, status, próby, `run_after`, `locked_until`, `last_error`). Worker pobiera zadania przez `SELECT … FOR UPDATE SKIP LOCKED`, ponawia z backoffem, po N próbach ustawia status `dead`. Zadania okresowe (przypomnienia, retencja) planuje sam worker (prosty scheduler w pętli, zapis ostatniego uruchomienia w bazie).

## Konsekwencje
+ transakcyjność: zadanie powstaje w tej samej transakcji co dane (brak utraty zadań).
+ zero nowych usług.
− własny kod (~200 linii) i testy. Alternatywa gotowa: `procrastinate` (MIT), do rozważenia przy implementacji.

## Odrzucone
Celery + Redis/RabbitMQ, RQ, Dramatiq (wymagają brokera).
