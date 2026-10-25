import { LogOut, Search, Settings } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useMatch, useNavigate } from "react-router";

import { logout, restoreSession, useSessionStatus } from "../../api/auth";
import { Button } from "../../components/Button";
import { OfflineDay } from "../../components/OfflineDay";
import { Notice, Skeleton } from "../../components/Surface";
import { listWeddingCopies } from "../../lib/dayCopy";
import { todayInWarsaw } from "../../lib/format";
import "./shell.css";

// Strona tytułowa tylko dla niezalogowanych — osobny fragment kodu (budżet JS).
const LandingPage = lazy(async () => ({ default: (await import("../home/LandingPage")).LandingPage }));

/** Trasy wymagające zalogowania. Podczas przywracania sesji z ciasteczka: szkielet. */
export function RequireAuth() {
  const status = useSessionStatus();
  const location = useLocation();
  if (status === "unknown") {
    return (
      <main className="page" aria-busy="true">
        <Skeleton lines={4} label="Przywracanie sesji" />
      </main>
    );
  }
  if (status === "offline") return <OfflineScreen />;
  if (status === "signed-out") {
    // Powrót z zachowaniem parametrów (np. token zaproszenia z e-maila).
    const target = location.pathname + location.search;
    // Adres główny bez logowania pokazuje stronę tytułową (przewijany nagłówek) zamiast formularza.
    if (target === "/") {
      return (
        <Suspense fallback={<main className="page" aria-busy="true" />}>
          <LandingPage />
        </Suspense>
      );
    }
    const back = target === "/" ? "" : `?powrot=${encodeURIComponent(target)}`;
    return <Navigate to={`/logowanie${back}`} replace />;
  }
  return <Outlet />;
}

/** Start bez sieci: zamiast wylogowania — informacja i ponowienie (także samo, gdy sieć wróci). */
function OfflineScreen() {
  const [pending, setPending] = useState(false);
  // Program dnia zapisany wcześniej na tym urządzeniu (tryb na żywo → „Zapisz program…”).
  const [copies] = useState(() => listWeddingCopies(todayInWarsaw()));
  const retry = async () => {
    setPending(true);
    await restoreSession();
    setPending(false);
  };
  useEffect(() => {
    const onOnline = () => void restoreSession();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);
  return (
    <main className="page" aria-labelledby="offline-h">
      <h1 id="offline-h">Brak połączenia</h1>
      <Notice tone="warning" live>
        Nie możemy połączyć się z serwerem. Dane wesela pokażemy, gdy wróci internet — nic nie zostało utracone.
      </Notice>
      <Button pending={pending} onPress={() => void retry()}>
        Spróbuj ponownie
      </Button>
      {copies.map((c) => (
        <OfflineDay key={c.saved_at} copy={c} />
      ))}
    </main>
  );
}

export function AppShell() {
  const navigate = useNavigate();
  const wedding = useMatch("/w/:weddingId/*");
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (!wedding?.params.weddingId) return;
    const search = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && !e.altKey) {
        e.preventDefault();
        navigate(`/w/${wedding.params.weddingId}/szukaj`);
      }
    };
    window.addEventListener("keydown", search);
    return () => window.removeEventListener("keydown", search);
  }, [navigate, wedding?.params.weddingId]);

  return (
    <>
      <a href="#tresc" className="skip-link">
        Przejdź do treści
      </a>
      <header className="shell-header">
        <Link to="/" className="shell-brand">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          Nasz dzień
        </Link>
        <nav aria-label="Konto" className="shell-actions">
          {wedding && (
            <Link to={`/w/${wedding.params.weddingId}/szukaj`} className="shell-icon-link" aria-label="Szukaj w weselu" title="Szukaj (Ctrl+K / ⌘K)" aria-keyshortcuts="Control+k Meta+k">
              <Search aria-hidden size={22} strokeWidth={1.75} />
            </Link>
          )}
          <Link to="/ustawienia" className="shell-icon-link" aria-label="Ustawienia">
            <Settings aria-hidden size={22} strokeWidth={1.75} />
          </Link>
          <Button
            variant="text"
            aria-label="Wyloguj"
            pending={leaving}
            icon={<LogOut aria-hidden size={20} strokeWidth={1.75} />}
            onPress={async () => {
              setLeaving(true);
              await logout();
              navigate("/logowanie", { replace: true });
            }}
          >
            <span className="shell-hide-narrow">Wyloguj</span>
          </Button>
        </nav>
      </header>
      <div id="tresc" tabIndex={-1} className="shell-content">
        <Outlet />
      </div>
    </>
  );
}
