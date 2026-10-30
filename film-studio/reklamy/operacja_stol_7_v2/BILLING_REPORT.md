# BILLING REPORT — OPERACJA STÓŁ 7 V2

Zasady: tylko abonament Sogni Unlimited, `billing_mode="subscription"`, `token_type=auto`, bez Premium Spark, bez zewnętrznych płatnych API, bez omijania fair-use. Wycena (`confirm_cost=false`) przed każdym startem, potem start z limitem jednostek. Klucz API nie jest w archiwum.

## Rzeczywiste zadania (rejestr: `ledger_full.json`, identyfikatory workflow w `SOGNI_GENERATIONS/state.json`)
| Rodzaj | Liczba | Narzędzie / model | Tryb rozliczenia (z odpowiedzi API) |
|---|---:|---|---|
| Klatki startowe (kandydaci) | 35 | edit_image / FLUX.3 Klein | subscription |
| IA2V (mowa → ruch ust) | 3 (v02, v04, v07) | sound_to_video / H3 IA2V turbo | subscription |
| I2V | 3 (v06, v06m, v08; 5,2 s każdy, użyte ok. 1 s) | animate_photo / H3 I2V turbo | subscription |
| Muzyka 20 s | 1 | generate_music / ACE-Step turbo | subscription |
Suma jednostek wg wycen: ok. 68,6.

## Konto przed i po
- Przed: dzienne fair-use 0% (reset 29.10 o 18:07 czasu lokalnego), sparkSpent 0, paidSparkSpent 0, saldo Spark 25.
- Po: dzienne fair-use **5,07%**, `limited=false`, **sparkSpent 0, paidSparkSpent 0, saldo Spark 25, saldo SOGNI 0**. Kontrola `assert_free` po każdej partii nie wykryła wzrostu kosztów.
- API nie zwraca pola `paymentModel`; dowodem jest `billingMode: subscription` w workflow i brak ruchu na saldach.

## Incydenty
- Pierwsze uruchomienie partii klipów zatrzymałem na prośbę właściciela w trakcie jednego zadania IA2V (v02) — to zadanie dokończyłem odpytaniem tego samego workflow (bez ponownego wysyłania).
- Dwa zadania I2V (v06, v06m) zakończyły się błędem walidacji lokalnie (min. 5,17 s) przed wysłaniem — nie kosztowały; brak połączenia przy v08 — ponowione raz.
- Odrzucone klatki (kobieta o złej twarzy) kosztowały jednostki abonamentu, ale nie płatne tokeny.
- Bez użycia: Camera 360, Premium Spark, płatne modele.
