# Nasz Dzień — Wujek Boguś, pakiet referencji V1

18 nowych grafik PNG + oryginalny wybrany koncept. Dwanaście grafik odpowiada polom podstawowej biblioteki postaci; sześć jest materiałem dodatkowym do konkretnych ujęć. Grafiki wygenerowano narzędziem imagegen na podstawie wybranego obrazu. Nie użyto Sogni ani nie zmieniono projektu użytkownika.

## Szybki start
1. Otwórz PODGLAD.html w przeglądarce po rozpakowaniu CAŁEGO ZIP-a.
2. W bibliotece postaci utwórz Bogusia z rolą WUJEK. Opisy są w 04_DOKUMENTACJA/persona_create.json.
3. Wgraj 12 obrazów z 01_REFERENCJE do pól o tych samych nazwach. Jeśli interfejs nie pokazuje wszystkich pól, dołączony lokalny importer korzysta z istniejącego API V8.5.
4. Jako główną referencję twarzy wybierz portrait.png. Podczas generowania klatki całej postaci używaj również front.png, o ile wybrany tryb dopuszcza kilka obrazów.
5. Przypisz Bogusia do roli WUJEK w obsadzie projektu. Nie zastępuj nim roli ON/Daniela. W każdym odpowiednim ujęciu wpisz WUJEK do listy characters.
6. Usuń kolidujące opisy Zygmunta z dawnych scenariuszy. Wybierz referencję do danego ujęcia, wygeneruj i obejrzyj pierwszą klatkę, dopiero potem animuj.

## Import lokalny
Uruchom kreator na swoim komputerze, następnie w folderze paczki:
`python import_local.py --base-url http://127.0.0.1:8765`

Skrypt tworzy tylko nową kartę postaci i przesyła do lokalnego kreatora 12 PNG. Nie przypisuje obsady, nie edytuje istniejących postaci, nie uruchamia generacji, nie wysyła plików do Sogni. Zapisuje import_state.json, by można było wznowić import bez tworzenia drugiej postaci. Nie usuwaj tego pliku podczas wznawiania. Po przejściu do innej instalacji aplikacji użyj świeżo rozpakowanej paczki.

## Istotne ograniczenia
To pakiet referencji, nie zaktualizowana wersja programu. Automatyczny selektor V6 nadal wymaga rozszerzenia o WUJEK. Podstawowa karta działa z tą rolą, ale przechowuje jeden aktywny zdalny adres obrazu na postać. Same lokalne pliki nie są automatycznie dostępne dla modelu w chmurze. Synchronizację wykonuje się osobno w kreatorze.

Każdy obraz jest osobną generacją: proporcje i detale mogą lekko się różnić. Portrait.png ma pierwszeństwo dla twarzy. Nie są to rzuty techniczne ani certyfikat spójności wideo. Dokładne uwagi i sposób kontroli znajdują się w dokumentacji.
