# Raport: weryfikacja dwuetapowa (MFA, TOTP)

Data: 2026-10-20. Zakres: logowanie w dwóch krokach z kodem z aplikacji uwierzytelniającej
(Google Authenticator, Microsoft Authenticator, Aegis itp.) oraz kody zapasowe.

## Co jest gotowe

- **Backend** (`app/modules/identity/mfa.py`): sekret 160 bitów (pyotp, MIT), zaszyfrowany AES-GCM
  i objęty rotacją klucza (`scripts/rotate_encryption_key.py`); kod QR jako SVG (segno, BSD) generowany
  lokalnie — sekret nie trafia do żadnej zewnętrznej usługi. Kod TOTP działa tylko raz, limit 5 błędnych
  prób na 15 min na konto. 10 kodów zapasowych (przechowywane jako skróty, każdy jednorazowy).
- **Endpointy:** `POST /auth/login` zwraca wyzwanie (`mfa_required`, `mfa_token`) zamiast tokenów,
  `POST /auth/login/mfa` kończy logowanie; `/me/mfa/setup`, `/enable`, `/disable`, `/recovery-codes`
  (setup — hasło, enable — kod z aplikacji, disable i nowe kody — hasło i kod). `MeOut.mfa_enabled`. Migracja `49365b4f862b`.
- **GUI:** w ustawieniach konta sekcja „Weryfikacja dwuetapowa” (`settings/MfaSection.tsx`): hasło →
  kod QR i klucz do ręcznego wpisania → kod z aplikacji → 10 kodów zapasowych do zapisania (z potwierdzeniem
  „Zapisałem/am kody”). Wyłączenie i nowe kody zapasowe. Przy logowaniu drugi krok (`MfaStep`
  w `LoginPage.tsx`): 6 cyfr albo „Nie mam telefonu — użyj kodu zapasowego”; po wygaśnięciu wyzwania powrót do hasła.
- **Testy:** `tests/api/test_mfa.py` (10), E2E w `frontend/e2e/account.spec.ts` (włączenie, błędny kod,
  poprawny kod z następnego okna 30 s, stan „Włączona”), axe na każdym kroku.

## Naprawiony błąd: utracony kod błędu API w całym GUI

Objaw: po błędnym kodzie GUI pokazywało „Coś poszło nie tak” zamiast „Nieprawidłowy kod”.
Przyczyna: `openapi-fetch` 0.17 sam odczytuje treść odpowiedzi błędu, a `toApiError` próbował potem
`response.clone()` na zużytej treści — wyjątek był połykany, więc **każdy** `ApiError` z `unwrap`
miał kod `http.<status>` i komunikat ogólny. Logowanie hasłem tego nie ujawniało, bo rozpoznaje błąd
po statusie 401. Poprawka: `unwrap` przekazuje do `toApiError` treść już odczytaną przez openapi-fetch
(`src/api/client.ts`, `src/api/errors.ts`), test regresyjny w `src/api/client.test.ts`.
Skutek uboczny na plus: od teraz działają też komunikaty zależne od kodu w innych miejscach
(np. konflikt wersji `conflict.version_mismatch`, „Konto jest zablokowane”, błędy pól z API).

## Weryfikacja

ruff, mypy, pytest (622 passed, 5 skipped), tsc, eslint, vitest (68), Playwright pełne (225 passed;
1 niestabilny: „Budżet: podsumowanie…” na 390-dark — chwilowy poziomy scroll 21 px, przy powtórzeniu
6/6 zielonych; do obserwacji).

## Ograniczenia

- Brak WebAuthn/passkeys (możliwe w kolejnej wersji).
- Odzyskanie konta bez telefonu i bez kodów zapasowych — tylko przez obsługę (procedura do opisania
  przed startem komercyjnym).
