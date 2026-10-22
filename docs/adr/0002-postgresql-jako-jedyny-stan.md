# ADR-0002: PostgreSQL jako jedyne źródło stanu

- Status: zaakceptowany, Data: 2026-10-19

## Decyzja
PostgreSQL 17 przechowuje dane domenowe, kolejkę zadań, audyt i wyszukiwanie (FTS + `pg_trgm`). Brak Redis, brokera i silnika wyszukiwania w MVP.

## Uzasadnienie
Wolumen MVP (setki–tysiące wesel) jest o rzędy wielkości poniżej limitów PostgreSQL. Mniej usług oznacza mniej kosztów, kopii zapasowych i punktów awarii.

## Kryteria rewizji
Redis: >1 instancja `api` (wspólny rate limit) albo p95 opóźnienia kolejki > 30 s. pgvector: potwierdzony przypadek wyszukiwania semantycznego. Meilisearch/Typesense: publiczny katalog > 50 tys. rekordów z wymaganiami typo-tolerance, których `pg_trgm` nie spełnia.
