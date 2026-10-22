import createClient from "openapi-fetch";

import { ApiError, NetworkError, toApiError } from "./errors";
import type { paths } from "./schema";
import { WEB_CLIENT_HEADER, refreshAccessToken, session } from "./session";

const AUTH_PATH = "/api/v1/auth/";

/**
 * fetch z sesją: dokleja Bearer, przy 401 jednokrotnie odświeża token (ciasteczko)
 * i ponawia żądanie. Brak sieci → NetworkError (formularze nie udają sukcesu).
 */
export async function authFetch(input: Request): Promise<Response> {
  const isAuth = new URL(input.url, location.origin).pathname.startsWith(AUTH_PATH);
  const retryCopy = input.clone();
  const send = (req: Request) => {
    if (isAuth) Object.entries(WEB_CLIENT_HEADER).forEach(([k, v]) => req.headers.set(k, v));
    if (session.token && !req.headers.has("Authorization")) {
      req.headers.set("Authorization", `Bearer ${session.token}`);
    }
    return fetch(req, { credentials: "same-origin" }).catch(() => {
      throw new NetworkError();
    });
  };
  const response = await send(input);
  if (response.status !== 401 || isAuth) return response;
  const refreshed = await refreshAccessToken();
  if (!refreshed) return response;
  retryCopy.headers.delete("Authorization");
  return send(retryCopy);
}

// API zawsze pod tym samym originem co aplikacja (ciasteczko SameSite=Strict).
export const api = createClient<paths>({ baseUrl: globalThis.location?.origin ?? "", fetch: authFetch });

/** Rozpakowuje wynik openapi-fetch: dane albo ApiError (z kodem, polami, Retry-After). */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || !response.ok) throw await toApiError(response, error);
  return data as T;
}

export { ApiError };

/**
 * Klucz idempotencji dla jednej próby zapisu formularza: ten sam przy ponowieniu po błędzie
 * sieci (serwer zwróci zapisany wynik zamiast tworzyć duplikat), nowy po sukcesie.
 */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
