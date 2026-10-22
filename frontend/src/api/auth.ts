import { useSyncExternalStore } from "react";

import { clearDayCopies } from "../lib/dayCopy";
import { clearQueues } from "../lib/dayQueue";
import { api, unwrap } from "./client";
import { refreshAccessToken, session } from "./session";

/**
 * Logowanie hasłem. Przy włączonej weryfikacji dwuetapowej zwraca token wyzwania
 * (sesja powstaje dopiero po kodzie — `loginMfa`); w przeciwnym razie `null` i sesja jest gotowa.
 */
export async function login(email: string, password: string): Promise<{ mfaToken: string } | null> {
  const result = await unwrap(api.POST("/api/v1/auth/login", { body: { email, password } }));
  if ("mfa_required" in result && result.mfa_required) return { mfaToken: result.mfa_token };
  session.signIn((result as { access_token: string }).access_token);
  return null;
}

/** Drugi krok: kod z aplikacji (6 cyfr) albo kod zapasowy. */
export async function loginMfa(mfaToken: string, code: string): Promise<void> {
  const tokens = await unwrap(api.POST("/api/v1/auth/login/mfa", { body: { mfa_token: mfaToken, code } }));
  session.signIn(tokens.access_token);
}

export async function logout(): Promise<void> {
  try {
    let r = await api.POST("/api/v1/auth/logout");
    // Wygasły access token: odświeżamy i ponawiamy, inaczej ciasteczko zostałoby ważne
    // i kolejne otwarcie aplikacji przywróciłoby sesję.
    if (r.response.status === 401 && (await refreshAccessToken())) {
      r = await api.POST("/api/v1/auth/logout");
    }
  } finally {
    // Nawet przy błędzie sieci czyścimy sesję w przeglądarce i kopie programu dnia.
    clearDayCopies();
    clearQueues();
    session.signOut();
  }
}

/** Przy starcie aplikacji: przywrócenie sesji z ciasteczka (bez ponownego logowania). */
export function restoreSession(): Promise<boolean> {
  return refreshAccessToken();
}

export function useSessionStatus() {
  return useSyncExternalStore(session.subscribe, () => session.status);
}
