"""Regresja jakości na prawdziwym modelu. Uruchomienie: task test:llm (wymaga działającego Ollama).

Domyślnie pomijane (wolne, zależne od sprzętu). Próg jakości dla modelu z ustawień.
"""

import os

import pytest

from app.core.config import get_settings
from tests.ai_regression.evaluate import evaluate

pytestmark = pytest.mark.skipif(
    os.environ.get("WP_TEST_OLLAMA") != "1",
    reason="Ustaw WP_TEST_OLLAMA=1 (wymaga Ollama z modelem)",
)

MIN_RECALL = 0.8


def test_offer_extraction_quality_on_corpus():
    settings = get_settings()
    model = os.environ.get("WP_TEST_OLLAMA_MODEL", settings.ollama_model)
    results, summary = evaluate(model, settings.ollama_url)
    print(summary)
    assert summary["errors"] == 0, [r.error for r in results if r.error]
    assert summary["recall"] >= MIN_RECALL, summary
    assert "przeszło weryfikację" not in summary["injection"], summary["injection"]
