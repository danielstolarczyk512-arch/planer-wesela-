"""Zapisuje specyfikację OpenAPI do docs/openapi.json (do przeglądu zmian w API)."""

import json
from pathlib import Path

from app.main import create_app

out = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
out.write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"Zapisano {out}")
