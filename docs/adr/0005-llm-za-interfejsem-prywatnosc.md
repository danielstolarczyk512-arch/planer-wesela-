# ADR-0005: LLM za interfejsem, prywatność domyślnie

- Status: zaakceptowany i zrealizowany w Etapie 5 (dostawca lokalny), Data: 2026-10-19

## Decyzja
Interfejs `LLMProvider.extract(schema, document_text, prompt_version) -> Result`. Implementacje:
1. `FakeProvider`: deterministyczny, do testów i CI.
2. `OllamaProvider`: lokalny model (np. Bielik lub inny z licencją komercyjną, wybór po teście jakości na polskich ofertach).
3. `ExternalProvider`: np. Claude API. **Włączany tylko gdy:** podpisana umowa powierzenia (DPA), przetwarzanie w UE lub odpowiednie zabezpieczenia transferu, brak trenowania na danych, zgoda użytkownika w aplikacji, redakcja PII przed wysyłką.

Każde wywołanie zapisuje `ai_runs` (provider, model, prompt_version, input_hash, tokeny, koszt, czas, status). Wynik jest walidowany schematem, a każde pole musi mieć cytat z tekstu źródłowego. Wynik zawsze wymaga zatwierdzenia przez człowieka.

## Realizacja (Etap 5, 2026-10-19)

Decyzja właściciela: **start od lokalnego modelu przez Ollama**, z architekturą gotową na dostawcę zewnętrznego.

- Interfejs: `LLMProvider.complete_json(system, user, schema)` (`app/modules/ai/providers.py`), wymuszona struktura JSON (structured outputs Ollama), `temperature=0`, stały `seed`.
- `OllamaProvider` (domyślny) i dublery testowe `FakeProvider` oraz `FakeExternalProvider` (ten drugi sprawdza ścieżkę zgody i redakcji). **Dostawca zewnętrzny nie jest zaimplementowany:** `WP_AI_PROVIDER` nie przyjmie innej wartości, dopóki nie będzie DPA.
- Wybór modelu: porównanie Qwen2.5 7B i Bielik 11B v2.3 (oba Apache-2.0) na korpusie, wyniki w [ai-ewaluacja.md](../ai-ewaluacja.md). **Wybrany: `qwen2.5:7b-instruct`** (44/52 faktów, zero niezweryfikowanych cytatów; Bielik 43/52, 15 niezweryfikowanych). Zmiana modelu to tylko `WP_OLLAMA_MODEL`.
- Ewaluacja wykazała, że oba modele wykonują polecenia wstrzyknięte w treść dokumentu. Dlatego linie wyglądające na polecenia są wykrywane deterministycznie, a pozycje z nich cytowane nie są uznawane za zweryfikowane (`suspicious_instructions` w wyniku analizy).
- Kontrola wyniku jest deterministyczna i niezależna od modelu: cytat musi występować w dokumencie, kwota musi występować w cytacie, zadatek/zaliczka rozstrzygane słowem w cytacie, poprawiny regułą domenową. Wszystko, co nie przejdzie kontroli, ma status `unverified` i wymaga jawnego potwierdzenia.
- Model nie ma narzędzi ani dostępu do bazy: jedynym skutkiem analizy jest szkic oferty `needs_review`.
- Redakcja PII (PESEL z sumą kontrolną, rachunki, e-maile, telefony) uruchamiana dla dostawców `external=True`.
- `ai_runs`: dostawca, model, licencja modelu, wersja i odcisk promptu, hash wejścia, tokeny, czas, wynik surowy, statystyki walidacji, cache.

## Konsekwencje
+ zmiana dostawcy bez zmian w domenie, testy bez sieci.
− jakość lokalnych modeli dla polskich dokumentów jest niepewna. Wymagany zestaw testowy i porównanie przed wyborem.

## Odrzucone
LangChain/LlamaIndex (zbędna warstwa abstrakcji), wywołania LLM bezpośrednio z modułów domenowych.
