/** Wspólne pomocnicze dla zapisów: wersja rekordu (If-Match) i obsługa konfliktu. */
import type { QueryClient, QueryKey } from "@tanstack/react-query";

import { ApiError, userMessage } from "../../api/errors";

/** Nagłówek If-Match: zapis tylko, jeśli nikt nie zmienił rekordu w międzyczasie. */
export function ifMatch(version: number) {
  return { "If-Match": `"${version}"` };
}

/**
 * Komunikat po nieudanym zapisie. Przy konflikcie wersji odświeża dane, żeby użytkownik
 * zobaczył aktualny stan (bez cichego nadpisania cudzej zmiany).
 */
export function saveErrorMessage(error: unknown, queryClient: QueryClient, refresh: QueryKey[]): string {
  if (error instanceof ApiError && error.code === "conflict.version_mismatch") {
    refresh.forEach((queryKey) => void queryClient.invalidateQueries({ queryKey }));
    return "Ktoś zmienił te dane w międzyczasie. Wczytaliśmy aktualną wersję — sprawdź i zapisz ponownie.";
  }
  return `Nie zapisano. ${userMessage(error)}`;
}
