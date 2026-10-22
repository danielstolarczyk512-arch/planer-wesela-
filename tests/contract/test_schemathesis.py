"""Testy kontraktowe: losowe (ale zgodne ze schematem) żądania do każdego endpointu.

Sprawdzamy, że API nigdy nie zwraca 5xx, a udane odpowiedzi zgadzają się ze schematem OpenAPI.
Uruchamiane jako część `task test`; liczba przykładów na operację jest mała, by testy były szybkie.
"""

from typing import Any

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error
from schemathesis.specs.openapi.checks import response_schema_conformance

from app.main import create_app

schema = schemathesis.openapi.from_asgi("/api/v1/openapi.json", create_app())


@pytest.fixture
def ctx(alice: dict[str, str], wedding: dict[str, Any]) -> dict[str, Any]:
    return {"headers": alice, "wedding_id": wedding["id"]}


@schema.parametrize()
@settings(max_examples=4, deadline=None, suppress_health_check=list(HealthCheck))
def test_api_contract(case: Any, ctx: dict[str, Any]) -> None:
    if case.path_parameters and "wedding_id" in case.path_parameters:
        case.path_parameters["wedding_id"] = ctx["wedding_id"]
    response = case.call(headers={**ctx["headers"], "If-Match": '"1"'})
    case.validate_response(response, checks=[not_a_server_error])
    if response.status_code < 300:
        case.validate_response(response, checks=[response_schema_conformance])
