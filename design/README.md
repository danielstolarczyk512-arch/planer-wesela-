# Projekt GUI

| Katalog / plik | Zawartość |
|---|---|
| [gui-v1.0/](gui-v1.0/) | oryginalna paczka „Nasz dzień — GUI premium” v1.0 (referencje, 20 ekranów, specyfikacja, tokeny) — bez zmian |
| [tokens/tokens.json](tokens/tokens.json) | **tokeny v1.1** (W3C Design Tokens): poprawione kolory i nowe stany; jedno źródło prawdy |
| [tokens/motion.json](tokens/motion.json) | tokeny ruchu (bez zmian względem v1.0) |
| [podglad/](podglad/) | interaktywny podgląd systemu v1.1: oba motywy, stany, fokus, dialog, dolny panel, ograniczenie ruchu; fonty OFL lokalnie |

Specyfikacja v1.1 (analiza paczki i ulepszenia): [docs/gui/GUI-SPEC-v1.1.md](../docs/gui/GUI-SPEC-v1.1.md). Kontrast tokenów: [docs/gui/kontrast.md](../docs/gui/kontrast.md).

| Polecenie | Działanie |
|---|---|
| `task gui:contrast` | kontrola kontrastu par tokenów (błąd przy regresji) |
| `task gui:tokens` | tokeny → `podglad/tokens.css` |
| podgląd | `uv run python -m http.server 8090 --directory design/podglad`, potem http://localhost:8090 |
