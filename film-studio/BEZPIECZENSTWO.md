# Ochrona przed kosztami i utratą danych — V4

1. **Tylko Sogni Unlimited.** Wychodzące żądania `studio/sogni.py` wymuszają `billing_mode: subscription`, listy modeli oraz kontrolę aktywności `GET /v1/subscriptions/status`. Zlecenie, które nie mieści się w abonamencie, powinno zostać przez Sogni odrzucone, zamiast obciążać Spark. Zasady z dokumentacji Sogni obowiązujące na dzień 2026-10-28.
2. **Rozdział wycena / zgoda.** Workflow używa `confirm_cost: false` do wyceny, a wykonanie wymaga osobnego potwierdzenia limitu `max_estimated_capacity_units` w UI.
3. **Zero automatycznego fallbacku na tokens / Spark.** Nie ma automatycznej zmiany na vendorowe modele premium. Nie korzystamy z dodatkowych płatnych API.
4. **Przechowywanie klucza.** Tylko `SOGNI_API_KEY` w środowisku uruchomieniowym. Nie umieszczaj kluczy w projekcie, logach, ZIP, plikach `.env`, ani w repozytorium. Wcześniej ujawniony klucz należy wymienić.
5. **Praca z telefonem.** Serwer LAN działa na HTTP w prywatnej sieci. Nie przekazuj go publicznie; do internetu potrzebna jest bramka HTTPS, uwierzytelnienie i właściwa konfiguracja.
6. **Jakość.** Analiza wideo przez FFprobe identyfikuje parametry techniczne, nie wykrywa automatycznie wszystkich błędów twarzy, mimiki, tekstu ani licencji. Ręczna akceptacja jest obowiązkowa w trybie V4.
7. **Ekrany aplikacji.** UI w nagraniu musi być autentyczne i potwierdzone. Deklaracja użytkownika nie jest automatycznym dowodem pochodzenia wideo.
8. **Nieobecna integracja:** testy API wykonano symulacyjnie; realny stan i dostępność modeli na Twoim koncie nadal wymagają sprawdzenia online.
