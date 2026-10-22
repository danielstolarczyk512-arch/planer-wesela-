"""Dostawcy modeli językowych za jednym interfejsem (ADR-0005).

- `OllamaProvider`: lokalny model (domyślny). Dane nie opuszczają serwera.
- `FakeProvider`: deterministyczny dubler do testów (bez sieci, bez modelu).
Dostawca zewnętrzny (np. Claude API) zostanie dodany po umowie powierzenia (DPA). Interfejs
i ścieżka zgody użytkownika są już gotowe (`external=True`, test na `fake_external`).
"""

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import get_settings


class ProviderError(Exception):
    """Błąd dostawcy (niedostępny, przekroczony czas, niepoprawny JSON)."""


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    tokens_in: int | None
    tokens_out: int | None
    duration_ms: int


class LLMProvider(Protocol):
    name: str
    model: str
    external: bool  # True = dane trafiają poza naszą infrastrukturę (wymaga zgody i DPA)
    model_license: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResult: ...


class OllamaProvider:
    name = "ollama"
    external = False

    def __init__(self, url: str, model: str, timeout: int) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.model_license = _MODEL_LICENSES.get(model.split(":")[0], "nieznana: sprawdź")

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,  # wymuszenie struktury JSON (structured outputs)
            "stream": False,
            "options": {"temperature": 0, "seed": 42, "num_ctx": 8192},
        }
        started = time.perf_counter()
        try:
            response = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError("Model nie odpowiedział w wyznaczonym czasie.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Lokalny model (Ollama) jest niedostępny: {type(exc).__name__}"
            ) from exc
        payload = response.json()
        content = payload.get("message", {}).get("content", "")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError("Model zwrócił niepoprawny JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderError("Model zwrócił JSON w nieoczekiwanym formacie.")
        return LLMResult(
            data=data,
            tokens_in=payload.get("prompt_eval_count"),
            tokens_out=payload.get("eval_count"),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


# Licencje modeli dopuszczonych do użytku komercyjnego (sprawdzone na kartach modeli).
_MODEL_LICENSES = {
    "qwen2.5": "Apache-2.0",
    "SpeakLeash/bielik-11b-v2.3-instruct": "Apache-2.0",
}


class FakeProvider:
    """Dubler testowy. Domyślnie prosta heurystyka regex; testy mogą podać własną odpowiedź."""

    name = "fake"
    model = "fake-rules-1"
    model_license = "n/d (kod projektu)"
    external = False
    responder: Callable[[str], dict[str, Any]] | None = None
    calls = 0

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        type(self).calls += 1
        data = self.responder(user) if self.responder else _heuristic(user)
        return LLMResult(data=data, tokens_in=len(user) // 4, tokens_out=50, duration_ms=1)


class FakeExternalProvider(FakeProvider):
    """Dubler „zewnętrznego” dostawcy: testuje ścieżkę zgody i redakcji PII."""

    name = "fake_external"
    external = True
    last_user_message = ""

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        type(self).last_user_message = user
        return super().complete_json(system, user, schema)


def _heuristic(text: str) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    terms: list[dict[str, Any]] = []
    for m in re.finditer(r"^.*?(\d[\d ]*)\s*zł za osobę.*$", text, re.MULTILINE):
        line = m.group(0).strip()
        kind_label = "Poprawiny" if "oprawin" in line else "Menu"
        components.append(
            {
                "label": kind_label,
                "kind": "per_guest",
                "amount": int(m.group(1).replace(" ", "")),
                "quote": line,
                "event_kind": "after_party" if kind_label == "Poprawiny" else None,
            }
        )
    for m in re.finditer(r"^.*Zadatek:?\s*(\d[\d ]*)\s*zł.*$", text, re.MULTILINE):
        terms.append(
            {
                "term_type": "deposit",
                "amount": int(m.group(1).replace(" ", "")),
                "quote": m.group(0).strip(),
            }
        )
    minimum = re.search(r"Minimalna liczba gości:\s*(\d+)", text)
    return {
        "title": "Oferta",
        "min_guests": int(minimum.group(1)) if minimum else None,
        "components": components,
        "terms": terms,
    }


def get_provider() -> LLMProvider:
    s = get_settings()
    if s.ai_provider == "fake":
        return FakeProvider()
    if s.ai_provider == "fake_external":
        return FakeExternalProvider()
    return OllamaProvider(s.ollama_url, s.ollama_model, s.ai_timeout_seconds)
