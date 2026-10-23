import type { QueryClient } from "@tanstack/react-query";

import { session } from "./session";

/**
 * Cache zapytań należy do jednego konta. Przy wylogowaniu (także wygaśnięciu sesji) i przy
 * zmianie użytkownika anulujemy trwające odczyty i czyścimy cache — na wspólnym urządzeniu
 * kolejne konto nie zobaczy danych poprzedniego (audyt 2026-10-23, S2).
 * Odświeżenie tokena tego samego konta niczego nie czyści.
 */
export function bindQueryCacheToSession(queryClient: QueryClient): () => void {
  let owner: string | null = session.status === "signed-in" ? session.subject : null;
  return session.subscribe(() => {
    if (session.status !== "signed-in" && session.status !== "signed-out") return;
    const current = session.status === "signed-in" ? session.subject : null;
    if (owner !== null && current !== owner) {
      void queryClient.cancelQueries();
      queryClient.clear();
    }
    owner = current;
  });
}
