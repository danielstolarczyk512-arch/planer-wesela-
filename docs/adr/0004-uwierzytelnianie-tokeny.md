# ADR-0004: Własne uwierzytelnianie z rotowanymi refresh tokenami

- Status: zaakceptowany, Data: 2026-10-19

## Decyzja
- Hasła: Argon2id (`argon2-cffi`, MIT), polityka: min. 10 znaków + sprawdzenie na liście popularnych haseł (lokalnie, bez wysyłki).
- Access token: JWT (EdDSA lub HS256 z sekretem z env), 15 min, zawiera tylko `sub`, `sid`, `exp`.
- Refresh token: losowy (256 bit), w bazie tylko hash SHA-256, 30 dni, **rotacja przy każdym użyciu**, wykrycie ponownego użycia unieważnia rodzinę sesji.
- Weryfikacja e-mail i reset hasła: jednorazowe tokeny z hashem w bazie, ważne 24 h / 1 h.
- Limity: logowanie 5 prób/15 min na konto + limit per IP.
- MFA (TOTP, `pyotp`, MIT) — **wdrożone 2026-10-20**: sekret szyfrowany AES-GCM (kontekst użytkownika, rotacja klucza obejmuje sekrety), okno ±30 s z blokadą ponownego użycia kodu, limit 5 błędnych kodów / 15 min na konto, 10 jednorazowych kodów zapasowych (w bazie SHA-256), logowanie dwuetapowe: hasło → token wyzwania (JWT typ `mfa`, 5 min, jednorazowy) → `POST /auth/login/mfa`. Kod QR jako SVG z `segno` (BSD-3). Włączenie i wyłączenie wymagają hasła, wyłączenie także kodu; e-mail z powiadomieniem przy każdej zmianie.

## Odrzucone
Keycloak/Authentik (osobna usługa i koszt utrzymania przy jednym kliencie), Auth0/Firebase/Clerk (vendor lock-in, dane w USA, koszt przy wzroście). Do rewizji, gdy dojdzie SSO/social login.
