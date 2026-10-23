import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { I18nProvider, RouterProvider as AriaRouterProvider } from "react-aria-components";
import { createBrowserRouter, Navigate, Outlet, RouterProvider, useHref, useNavigate } from "react-router";

import { restoreSession } from "../api/auth";
import { ApiError } from "../api/errors";
import { bindQueryCacheToSession } from "../api/sessionCache";
import { Skeleton } from "../components/Surface";
import { ToastProvider } from "../components/Toast";
import { LoginPage } from "../features/auth/LoginPage";
import { AppShell, RequireAuth } from "../features/shell/AppShell";

// Ekrany po zalogowaniu i galeria ładowane osobno: strona logowania (pierwsze wejście)
// nie pobiera kodu list, pól daty itp. (budżet JS z GUI-SPEC v1.1, sekcja 9).
const lazyPage = (load: () => Promise<{ Component: React.ComponentType }>) => ({ lazy: load });

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 4xx nie ponawiamy (to nie chwilowy problem); sieć i 5xx: do 2 razy.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      staleTime: 30_000,
      refetchOnWindowFocus: true,
    },
  },
});
bindQueryCacheToSession(queryClient);

/** Linki React Aria korzystają z routera aplikacji (bez przeładowania strony). */
function Root() {
  const navigate = useNavigate();
  return (
    <AriaRouterProvider navigate={navigate} useHref={useHref}>
      <Outlet />
    </AriaRouterProvider>
  );
}

/** Pierwsze wejście na leniwą trasę (np. link RSVP): szkielet, zanim dojdzie kod ekranu. */
function BootFallback() {
  return (
    <main className="page">
      <Skeleton lines={5} />
    </main>
  );
}

const account = (name: "RegisterPage" | "VerifyEmailPage" | "ForgotPasswordPage" | "ResetPasswordPage") =>
  lazyPage(async () => ({ Component: (await import("../features/auth/AccountPages"))[name] }));
const legal = (name: "TermsPage" | "PrivacyPage") =>
  lazyPage(async () => ({ Component: (await import("../features/auth/LegalPages"))[name] }));

/** Ścieżki z e-maili API (angielskie) → polskie adresy aplikacji, z zachowaniem ?token=. */
function KeepQuery({ to }: { to: string }) {
  return <Navigate to={{ pathname: to, search: location.search }} replace />;
}

// Strony konta i dokumenty prawne: dostępne bez logowania.
const accountRoutes = [
  { path: "/rejestracja", ...account("RegisterPage") },
  { path: "/potwierdz-email", ...account("VerifyEmailPage") },
  { path: "/zapomniane-haslo", ...account("ForgotPasswordPage") },
  { path: "/nowe-haslo", ...account("ResetPasswordPage") },
  { path: "/regulamin", ...legal("TermsPage") },
  { path: "/prywatnosc", ...legal("PrivacyPage") },
  { path: "/verify-email", element: <KeepQuery to="/potwierdz-email" /> },
  { path: "/forgot-password", element: <KeepQuery to="/zapomniane-haslo" /> },
  { path: "/reset-password", element: <KeepQuery to="/nowe-haslo" /> },
  { path: "/settings", element: <KeepQuery to="/ustawienia" /> },
];

const router = createBrowserRouter([
  {
    element: <Root />,
    HydrateFallback: BootFallback,
    children: [
      { path: "/logowanie", element: <LoginPage /> },
      ...accountRoutes,
      {
        // Odpowiedź gości z linku w zaproszeniu: bez logowania (ścieżka ustalona w API).
        path: "/rsvp/:token",
        ...lazyPage(async () => ({ Component: (await import("../features/rsvp/RsvpPage")).RsvpPage })),
      },
      {
        // Zadania pomocnika bez konta: link bez logowania (tylko jego zadania).
        path: "/pomocnik/:token",
        ...lazyPage(async () => ({ Component: (await import("../features/rsvp/HelperPage")).HelperPage })),
      },
      {
        // Program dnia dla usługodawcy: link bez logowania (tylko do odczytu).
        path: "/dzien/:token",
        ...lazyPage(async () => ({ Component: (await import("../features/rsvp/DayPage")).DayPage })),
      },
      ...(import.meta.env.DEV
        ? [
            {
              path: "/komponenty",
              ...lazyPage(async () => ({ Component: (await import("../features/gallery/GalleryPage")).GalleryPage })),
            },
          ]
        : []),
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppShell />,
            children: [
              {
                index: true,
                ...lazyPage(async () => ({ Component: (await import("../features/home/HomePage")).HomePage })),
              },
              {
                path: "/ustawienia",
                ...lazyPage(async () => ({
                  Component: (await import("../features/settings/SettingsPage")).SettingsPage,
                })),
              },
              {
                // Link z e-maila zaproszenia (ścieżka ustalona w API).
                path: "/invitations/accept",
                ...lazyPage(async () => ({
                  Component: (await import("../features/wedding/AcceptInvitationPage")).AcceptInvitationPage,
                })),
              },
              {
                // Wesele: 5 zakładek (Dziś, Plan, Budżet, Goście, Więcej), każda z własnym adresem.
                path: "/w/:weddingId",
                ...lazyPage(async () => ({
                  Component: (await import("../features/wedding/WeddingShell")).WeddingShell,
                })),
                children: [
                  {
                    index: true,
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/TodayView")).TodayView })),
                  },
                  {
                    path: "plan",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/PlanView")).PlanView })),
                  },
                  {
                    path: "podglad-goscia",
                    ...lazyPage(async () => ({ Component: (await import("../features/rsvp/GuestPreview")).GuestPreview })),
                  },
                  {
                    path: "druk/:kind",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/PrintView")).PrintView })),
                  },
                  {
                    path: "kalendarz",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/CalendarView")).CalendarView })),
                  },
                  {
                    path: "budzet",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/BudgetView")).BudgetView })),
                  },
                  {
                    path: "goscie",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/GuestsView")).GuestsView })),
                  },
                  {
                    path: "sponsorzy",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/FundersView")).FundersView })),
                  },
                  {
                    path: "wklad",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/MyContributionView")).MyContributionView })),
                  },
                  {
                    path: "formalnosci",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/CeremonyDocsView")).CeremonyDocsView })),
                  },
                  {
                    path: "zaproszenia",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/InvitationsView")).InvitationsView })),
                  },
                  {
                    path: "logistyka",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/LogisticsView")).LogisticsView })),
                  },
                  {
                    path: "po-weselu",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/AfterWeddingView")).AfterWeddingView })),
                  },
                  {
                    path: "frekwencja",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/AttendanceView")).AttendanceView })),
                  },
                  {
                    path: "ustawienia",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/SettingsView")).SettingsView,
                    })),
                  },
                  {
                    path: "uslugodawcy",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/VendorsView")).VendorsView,
                    })),
                  },
                  {
                    path: "uslugodawcy/:vendorId",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/VendorView")).VendorView,
                    })),
                  },
                  {
                    path: "oferty/porownanie",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/CompareView")).CompareView,
                    })),
                  },
                  {
                    path: "oferty/:offerId",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/OfferView")).OfferView,
                    })),
                  },
                  {
                    path: "dokumenty",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/Documents")).DocumentsView,
                    })),
                  },
                  {
                    path: "stoly",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/SeatingView")).SeatingView,
                    })),
                  },
                  {
                    path: "dzien",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/ScheduleView")).ScheduleView,
                    })),
                  },
                  {
                    path: "fryzura-i-makijaz",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/PrepView")).PrepView })),
                  },
                  {
                    path: "szukaj",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/SearchView")).SearchView })),
                  },
                  {
                    path: "pomocnicy",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/HelpersView")).HelpersView })),
                  },
                  {
                    path: "strona-goscia",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/GuestPageView")).GuestPageView })),
                  },
                  {
                    path: "menu",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/MenuView")).MenuView })),
                  },
                  {
                    path: "zdjecia",
                    ...lazyPage(async () => ({
                      Component: (await import("../features/wedding/PhotoGroupsView")).PhotoGroupsView,
                    })),
                  },
                  {
                    path: "muzyka",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/MusicView")).MusicView })),
                  },
                  {
                    path: "wiecej",
                    ...lazyPage(async () => ({ Component: (await import("../features/wedding/MoreView")).MoreView })),
                  },
                ],
              },
            ],
          },
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export function App() {
  useEffect(() => {
    // Przywrócenie sesji z ciasteczka HttpOnly (bez ponownego logowania).
    void restoreSession();
  }, []);
  return (
    <I18nProvider locale="pl-PL">
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>
    </I18nProvider>
  );
}
