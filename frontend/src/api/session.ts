/**
 * Sesja klienta webowego (GUI-SPEC v1.1, sekcja 8):
 * - access token wyłącznie w pamięci (nie w localStorage: ryzyko XSS),
 * - refresh token w ciasteczku HttpOnly ustawianym przez API (X-Client: web),
 * - przy wielu równoczesnych 401 tylko jedno odświeżenie (single flight).
 */

type Listener = () => void;

let accessToken: string | null = null;
/** „offline”: przy starcie nie było sieci — nie wiemy, czy sesja jest ważna (nie wylogowujemy). */
let status: "unknown" | "signed-in" | "signed-out" | "offline" = "unknown";
const listeners = new Set<Listener>();
let refreshing: Promise<boolean> | null = null;

export const WEB_CLIENT_HEADER = { "X-Client": "web" } as const;

function emit() {
  listeners.forEach((l) => l());
}

/** Identyfikator użytkownika (`sub`) z access tokena — tylko do rozpoznania zmiany konta. */
function subjectOf(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = (token.split(".")[1] ?? "").replaceAll("-", "+").replaceAll("_", "/");
    const sub = (JSON.parse(atob(payload)) as { sub?: unknown }).sub;
    return typeof sub === "string" ? sub : null;
  } catch {
    return null;
  }
}

export const session = {
  get token() {
    return accessToken;
  },
  get subject() {
    return subjectOf(accessToken);
  },
  get status() {
    return status;
  },
  subscribe(listener: Listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  signIn(token: string) {
    accessToken = token;
    status = "signed-in";
    emit();
  },
  signOut() {
    accessToken = null;
    status = "signed-out";
    emit();
  },
};

/** Odświeża access token z ciasteczka. Równoległe wywołania czekają na to samo żądanie. */
export function refreshAccessToken(fetchImpl: typeof fetch = fetch): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const r = await fetchImpl("/api/v1/auth/refresh", {
        method: "POST",
        headers: { ...WEB_CLIENT_HEADER },
        credentials: "same-origin",
      });
      if (!r.ok) {
        session.signOut();
        return false;
      }
      const body = (await r.json()) as { access_token: string };
      session.signIn(body.access_token);
      return true;
    } catch {
      // brak sieci: nie wylogowujemy, tylko zgłaszamy porażkę (ponowimy później)
      if (session.status === "unknown" || session.status === "offline") {
        status = "offline";
        emit();
      }
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}
