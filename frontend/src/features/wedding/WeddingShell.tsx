import { CalendarCheck, Clock, Ellipsis, HandCoins, House, Users, Wallet, type LucideIcon } from "lucide-react";
import { useEffect } from "react";
import { Link, Navigate, Outlet, ScrollRestoration, useLocation } from "react-router";

import { userMessage } from "../../api/errors";
import { Notice, Skeleton } from "../../components/Surface";
import { rememberWedding } from "./lastWedding";
import { useWedding, useWeddingId } from "./data";
import "./wedding.css";

interface Tab {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Podstrony działu, na których zakładka też jest aktywna. */
  also?: string[];
}

export const TABS: Tab[] = [
  { to: "", label: "Dziś", icon: House, also: ["szukaj"] },
  { to: "plan", label: "Plan", icon: CalendarCheck, also: ["kalendarz", "formalnosci", "pomocnicy"] },
  { to: "budzet", label: "Budżet", icon: Wallet, also: ["uslugodawcy", "oferty", "sponsorzy"] },
  { to: "goscie", label: "Goście", icon: Users, also: ["stoly", "podglad-goscia", "frekwencja", "zaproszenia", "logistyka", "menu", "strona-goscia"] },
  { to: "dzien", label: "Dzień", icon: Clock, also: ["fryzura-i-makijaz", "zdjecia", "muzyka"] },
  { to: "wiecej", label: "Więcej", icon: Ellipsis, also: ["ustawienia", "dokumenty", "druk", "po-weselu"] },
];

/** Sponsor (np. rodzice): tylko własny wkład i ustawienia konta. */
const SPONSOR_TAB: Tab = { to: "wklad", label: "Nasz wkład", icon: HandCoins };

/** Role z ograniczonym widokiem: dozwolone zakładki i strona startowa. */
const RESTRICTED: Record<string, { tabs: Set<string>; home: string }> = {
  coordinator: { tabs: new Set(["dzien", "wiecej"]), home: "dzien" },
  sponsor: { tabs: new Set(["wklad", "wiecej"]), home: "wklad" },
};

/** Która zakładka jest aktywna dla ścieżki w weselu (np. „uslugodawcy/123” → Budżet). */
export function activeTab(rest: string): string {
  const first = rest.split("/")[0] ?? "";
  return [...TABS, SPONSOR_TAB].find((t) => t.to === first || t.also?.includes(first))?.to ?? "";
}

/**
 * Powłoka wesela: 6 zakładek (telefon: na dole, od 768 px: z boku). Pasek nawigacji
 * nie bierze udziału w przejściu (stała nazwa view-transition), treść przenika się.
 * Każda zakładka ma własny adres: działają linki bezpośrednie i przycisk Wstecz.
 */
export function WeddingShell() {
  const weddingId = useWeddingId();
  const wedding = useWedding(weddingId);
  const location = useLocation();
  const base = `/w/${weddingId}`;
  const current = activeTab(location.pathname.slice(base.length).replace(/^\//, ""));
  // Koordynator dnia: tylko program dnia; sponsor: tylko swój wkład (bez budżetu, gości i planu).
  const restricted = RESTRICTED[wedding.data?.my_role ?? ""];
  const tabs = restricted ? [SPONSOR_TAB, ...TABS].filter((t) => restricted.tabs.has(t.to)) : TABS;

  useEffect(() => {
    if (wedding.data) rememberWedding(wedding.data.id);
  }, [wedding.data]);

  return (
    <div className="wshell">
      <nav className="wshell__nav" aria-label="Główne">
        {tabs.map(({ to, label, icon: Icon }) => {
          const href = `${base}${to ? `/${to}` : ""}`;
          return (
            <Link
              key={label}
              to={href}
              viewTransition
              className="wshell__tab"
              aria-current={current === to ? "page" : undefined}
              onClick={(e) => {
                // Ponowne dotknięcie aktywnej zakładki: przewinięcie na górę (bez utraty danych).
                if (location.pathname === href) {
                  e.preventDefault();
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }
              }}
            >
              <span className="wshell__icon" aria-hidden="true">
                <Icon size={24} strokeWidth={1.75} />
              </span>
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="wshell__main">
        {wedding.isPending && (
          <main className="page">
            <Skeleton lines={5} />
          </main>
        )}
        {wedding.isError && (
          <main className="page">
            <Notice tone="error" title="Nie udało się otworzyć wesela." live>
              {userMessage(wedding.error)}
            </Notice>
          </main>
        )}
        {wedding.data && (restricted && !restricted.tabs.has(current) ? <Navigate to={`${base}/${restricted.home}`} replace /> : <Outlet />)}
      </div>
      <ScrollRestoration />
    </div>
  );
}
