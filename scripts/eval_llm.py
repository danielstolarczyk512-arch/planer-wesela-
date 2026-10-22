"""Porównanie modeli lokalnych na korpusie ofert. Wynik: docs/ai-ewaluacja.md.

Użycie: task ai:eval -- qwen2.5:7b-instruct SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M
"""

import base64
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

# Ewaluacja nie dotyka danych: klucze jednorazowe, losowane przy każdym uruchomieniu.
os.environ.setdefault("WP_JWT_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("WP_DATA_ENCRYPTION_KEY", base64.b64encode(secrets.token_bytes(32)).decode())

from tests.ai_regression.evaluate import evaluate

OUT = Path(__file__).resolve().parent.parent / "docs" / "ai-ewaluacja.md"


def main(models: list[str]) -> None:
    lines = [
        "# Ewaluacja lokalnych modeli: odczyt ofert (OfferExtractor)",
        "",
        f"Data: {datetime.now().astimezone():%Y-%m-%d %H:%M}. Sprzęt: laptop (Ryzen 7 5800H, "
        "28 GB RAM, RTX 3050 Ti 4 GB). Korpus: 10 PDF + 6 DOCX (fikcyjne oferty).",
        "",
        "Fakt „trafiony” = poprawna wartość **i** pozytywna weryfikacja cytatu "
        "(liczba występuje w dosłownym fragmencie dokumentu). Czasy są orientacyjne: zależą "
        "od obciążenia laptopa i tego, czy model jest już załadowany do pamięci.",
        "",
        "| Model | Licencja | Trafione fakty | Skuteczność | Pozycje niezweryfikowane | "
        "Śr. czas / dokument | Błędy | Prompt injection |",
        "|---|---|---|---|---|---|---|---|",
    ]
    details: list[str] = []
    for model in models:
        print(f"== {model}")
        results, s = evaluate(model)
        print(s)
        license_ = "Apache-2.0"
        lines.append(
            f"| `{model}` | {license_} | {s['facts_hit']}/{s['facts_total']} | "
            f"{s['recall']:.0%} | {s['unverified_items']}/{s['items_total']} | "
            f"{s['avg_seconds']} s | {s['errors']} | {s['injection']} |"
        )
        details += [
            "",
            f"## {model}",
            "",
            "| Dokument | Fakty (trafione) | Czas |",
            "|---|---|---|",
        ]
        for r in results:
            facts = ", ".join(f"{k}: {'tak' if v else 'NIE'}" for k, v in r.facts.items())
            details.append(f"| {r.name} | {r.error or facts} | {r.seconds:.0f} s |")
    OUT.write_text("\n".join(lines + details) + "\n", encoding="utf-8")
    print(f"Zapisano {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["qwen2.5:7b-instruct"])
