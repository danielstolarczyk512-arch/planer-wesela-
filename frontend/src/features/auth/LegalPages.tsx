import type { ReactNode } from "react";
import { Link } from "react-router";

import { Notice } from "../../components/Surface";
import "./auth.css";
import "./legal.css";

// WERSJA ROBOCZA (terms_version / privacy_version = „2026-10-draft” w API). Treść opisuje faktyczne
// działanie aplikacji, ale przed uruchomieniem komercyjnym wymaga weryfikacji prawnika i uzupełnienia
// danych firmy. Zmiana treści = nowa wersja w konfiguracji API (zgody są wersjonowane).

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="legal" aria-labelledby="legal-h">
      <p>
        <Link to="/">Nasz dzień</Link>
      </p>
      <h1 id="legal-h">{title}</h1>
      <Notice tone="warning" title="Wersja robocza">
        Ten dokument jest projektem przed weryfikacją prawną. Fragmenty w nawiasach kwadratowych zostaną uzupełnione przed
        uruchomieniem usługi.
      </Notice>
      {children}
    </main>
  );
}

export function PrivacyPage() {
  return (
    <LegalLayout title="Polityka prywatności">
      <p className="text-secondary">Wersja: 2026-10-draft</p>

      <h2>1. Administrator</h2>
      <p>
        Administratorem danych konta jest [nazwa firmy, adres, NIP, e-mail do spraw danych osobowych]. W sprawach danych
        osobowych możesz pisać na [adres e-mail].
      </p>
      <p>
        Dane gości, usługodawców i dokumenty wpisujecie Wy, organizując własne wesele. [Do rozstrzygnięcia przez prawnika:
        rola platformy wobec tych danych — podmiot przetwarzający na zlecenie pary czy odrębny administrator.]
      </p>

      <h2>2. Jakie dane i po co</h2>
      <ul>
        <li>
          <strong>Konto:</strong> e-mail, imię (opcjonalnie), skrót hasła (samego hasła nie przechowujemy) — aby świadczyć
          usługę (art. 6 ust. 1 lit. b RODO).
        </li>
        <li>
          <strong>Dane wesela:</strong> plan, budżet, harmonogram, usługodawcy, oferty, dokumenty — jw., w zakresie, w jakim je
          wpiszecie lub wgracie.
        </li>
        <li>
          <strong>Goście:</strong> imiona i nazwiska, odpowiedzi, dieta, potrzeba noclegu lub transportu. Uwagi dietetyczne mogą
          dotyczyć zdrowia — gość podaje je tylko po wyrażeniu zgody (art. 9 ust. 2 lit. a RODO); przechowujemy je
          zaszyfrowane.
        </li>
        <li>
          <strong>Bezpieczeństwo:</strong> skrócony adres IP, dziennik zdarzeń (logowania, zmiany danych) — aby chronić konta przed
          nadużyciami (prawnie uzasadniony interes, art. 6 ust. 1 lit. f RODO).
        </li>
      </ul>

      <h2>3. Sztuczna inteligencja</h2>
      <p>
        Odczyt ofert z dokumentów wykonuje model językowy uruchomiony na naszym serwerze. Dokumenty nie są przekazywane
        zewnętrznym dostawcom AI bez Twojej wyraźnej zgody. Wynik to propozycja do sprawdzenia — nie jest poradą prawną ani
        finansową.
      </p>

      <h2>4. Odbiorcy</h2>
      <p>
        Dane przetwarzają w naszym imieniu: [dostawca serwerów / hostingu, kraj], [dostawca wysyłki e-maili, kraj]. Nie sprzedajemy
        danych i nie używamy ich do reklam.
      </p>

      <h2>5. Jak długo</h2>
      <ul>
        <li>Konto i dane wesela — do usunięcia konta; po zleceniu usunięcia masz 30 dni na rozmyślenie się, potem dane są trwale anonimizowane.</li>
        <li>Dane gości — anonimizujemy automatycznie 90 dni po ostatnim dniu wesela (zostają liczby, znikają imiona i uwagi).</li>
        <li>Dziennik bezpieczeństwa — 24 miesiące.</li>
        <li>Kopie zapasowe — [okres przechowywania kopii].</li>
      </ul>

      <h2>6. Twoje prawa</h2>
      <p>
        Masz prawo dostępu do danych, ich sprostowania, usunięcia, ograniczenia przetwarzania, przeniesienia (eksport w ustawieniach
        konta, format JSON), sprzeciwu oraz cofnięcia zgody w dowolnym momencie (bez wpływu na wcześniejsze przetwarzanie). Możesz
        złożyć skargę do Prezesa Urzędu Ochrony Danych Osobowych (ul. Stawki 2, 00-193 Warszawa).
      </p>

      <h2>7. Pliki cookie</h2>
      <p>
        Używamy jednego niezbędnego ciasteczka sesji (utrzymanie zalogowania). Nie używamy ciasteczek analitycznych ani
        reklamowych.
      </p>
      <p>
        Na Twoje żądanie (przycisk „Zapisz program na tym telefonie”) zapisujemy w pamięci przeglądarki kopię programu dnia
        ślubu: tytuły, godziny, miejsca, plan B, przygotowania i nazwy usługodawców — bez danych gości i kwot. Strona programu
        dla usługodawcy zapisuje taką kopię po otwarciu. Kopia służy tylko do pokazania programu bez internetu, wygasa dzień po
        ślubie i jest usuwana przy wylogowaniu; możesz ją też usunąć przyciskiem w trybie dnia ślubu.
        Przesunięcia programu zrobione bez internetu czekają w pamięci przeglądarki, aż wróci połączenie, i również
        znikają przy wylogowaniu.
      </p>
    </LegalLayout>
  );
}

export function TermsPage() {
  return (
    <LegalLayout title="Regulamin">
      <p className="text-secondary">Wersja: 2026-10-draft</p>

      <h2>1. Usługodawca</h2>
      <p>Usługę „Nasz dzień” świadczy [nazwa firmy, adres, NIP, REGON, e-mail kontaktowy].</p>

      <h2>2. Czym jest usługa</h2>
      <p>
        Aplikacja pomaga zaplanować wesele: plan zadań, budżet i płatności, lista gości z odpowiedziami, plan stołów, harmonogram
        dnia, zbieranie i porównywanie ofert usługodawców. Nie jesteśmy stroną umów z usługodawcami i nie pośredniczymy w
        płatnościach.
      </p>

      <h2>3. Konto</h2>
      <ul>
        <li>Konto zakładasz, podając e-mail i hasło oraz akceptując regulamin i politykę prywatności.</li>
        <li>Możesz zaprosić do wesela inne osoby (np. partnera); odpowiadasz za to, komu dajesz dostęp.</li>
        <li>Konto możesz usunąć w ustawieniach w każdej chwili.</li>
        <li>Cena: [usługa bezpłatna / cennik — do uzupełnienia].</li>
      </ul>

      <h2>4. Twoje treści</h2>
      <p>
        Odpowiadasz za dane, które wpisujesz lub wgrywasz (w tym dane gości i dokumenty), oraz za to, że masz prawo je
        przetwarzać. Nie wgrywaj treści bezprawnych.
      </p>

      <h2>5. Wyliczenia i podpowiedzi</h2>
      <p>
        Porównania ofert, wyliczenia budżetu, automatyczne usadzenie gości i odczyt dokumentów przez AI to narzędzia pomocnicze.
        Mogą zawierać błędy — przed decyzją sprawdź je z dokumentami. Wiążąca jest treść umowy z usługodawcą. Nie udzielamy porad
        prawnych ani finansowych.
      </p>

      <h2>6. Reklamacje</h2>
      <p>
        Reklamacje zgłoś na [adres e-mail]; odpowiemy w ciągu 14 dni. Konsument może skorzystać z pozasądowych sposobów
        rozwiązywania sporów (np. rzecznik konsumentów).
      </p>

      <h2>7. Zmiany i prawo właściwe</h2>
      <p>
        O zmianach regulaminu poinformujemy z wyprzedzeniem [okres]. Stosuje się prawo polskie; przepisy chroniące konsumentów
        mają pierwszeństwo przed postanowieniami regulaminu.
      </p>
    </LegalLayout>
  );
}
