# Ewaluacja lokalnych modeli: odczyt ofert (OfferExtractor)

Data: 2026-10-19 18:44. Sprzęt: laptop (Ryzen 7 5800H, 28 GB RAM, RTX 3050 Ti 4 GB). Korpus: 10 PDF + 6 DOCX (fikcyjne oferty).

Fakt „trafiony” = poprawna wartość **i** pozytywna weryfikacja cytatu (liczba występuje w dosłownym fragmencie dokumentu). Czasy są orientacyjne: zależą od obciążenia laptopa i tego, czy model jest już załadowany do pamięci.

| Model | Licencja | Trafione fakty | Skuteczność | Pozycje niezweryfikowane | Śr. czas / dokument | Błędy | Prompt injection |
|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | Apache-2.0 | 44/52 | 85% | 0/104 | 143.4 s | 0 | model wykonał polecenie, walidacja zatrzymała (pozycja niezweryfikowana, ostrzeżenie: 1 fragm.) |
| `SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M` | Apache-2.0 | 43/52 | 83% | 15/134 | 105.9 s | 0 | model wykonał polecenie, walidacja zatrzymała (pozycja niezweryfikowana, ostrzeżenie: 1 fragm.) |

## qwen2.5:7b-instruct

| Dokument | Fakty (trafione) | Czas |
|---|---|---|
| pdf-Dworek Pod Lipami | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 270 s |
| pdf-Sala Bankietowa Złoty Róg | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 153 s |
| pdf-Pałac Różany Ogród | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 49 s |
| pdf-Karczma Pod Jeleniem | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 46 s |
| pdf-Hotel Nad Jeziorem | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 220 s |
| pdf-Stodoła Wiśniowy Sad | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 280 s |
| pdf-Zajazd Łąkowy Zakątek | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 245 s |
| pdf-Folwark Żurawie Gniazdo | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 42 s |
| pdf-Restauracja Śródmiejska | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 41 s |
| pdf-Oranżeria Biała Róża | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 75 s |
| docx-Zespół Weselny Krakowiacy | cena pakietu: tak, zadatek/zaliczka: NIE | 246 s |
| docx-DJ Mateusz Muzyka | cena pakietu: tak, zadatek/zaliczka: NIE | 141 s |
| docx-Fotograf Ślubny Ania Kadr | cena pakietu: tak, zadatek/zaliczka: NIE | 256 s |
| docx-Studio Filmowe Żółty Kadr | cena pakietu: tak, zadatek/zaliczka: NIE | 181 s |
| docx-Kwiaciarnia Łąka i Róża | cena pakietu: tak, zadatek/zaliczka: tak | 24 s |
| docx-Słodki Stół Bezowa Chmurka | cena pakietu: tak, zadatek/zaliczka: NIE | 26 s |

## SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M

| Dokument | Fakty (trafione) | Czas |
|---|---|---|
| pdf-Dworek Pod Lipami | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 156 s |
| pdf-Sala Bankietowa Złoty Róg | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 120 s |
| pdf-Pałac Różany Ogród | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 159 s |
| pdf-Karczma Pod Jeleniem | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 117 s |
| pdf-Hotel Nad Jeziorem | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 118 s |
| pdf-Stodoła Wiśniowy Sad | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 118 s |
| pdf-Zajazd Łąkowy Zakątek | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 120 s |
| pdf-Folwark Żurawie Gniazdo | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 118 s |
| pdf-Restauracja Śródmiejska | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: tak | 132 s |
| pdf-Oranżeria Biała Róża | cena za osobę: tak, poprawiny: tak, minimum gości: tak, zadatek/zaliczka: NIE | 120 s |
| docx-Zespół Weselny Krakowiacy | cena pakietu: tak, zadatek/zaliczka: tak | 72 s |
| docx-DJ Mateusz Muzyka | cena pakietu: tak, zadatek/zaliczka: tak | 52 s |
| docx-Fotograf Ślubny Ania Kadr | cena pakietu: tak, zadatek/zaliczka: tak | 56 s |
| docx-Studio Filmowe Żółty Kadr | cena pakietu: tak, zadatek/zaliczka: tak | 56 s |
| docx-Kwiaciarnia Łąka i Róża | cena pakietu: tak, zadatek/zaliczka: tak | 96 s |
| docx-Słodki Stół Bezowa Chmurka | cena pakietu: tak, zadatek/zaliczka: NIE | 87 s |
