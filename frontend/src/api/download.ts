import { authFetch } from "./client";
import { toApiError } from "./errors";

/**
 * Pobranie pliku wymagającego sesji (nagłówek Authorization): fetch → Blob → link do zapisu.
 * Zwykły link <a href> nie wyśle tokenu, a token nie trafia do adresu URL.
 */
export async function downloadAuthorized(path: string, filename: string): Promise<void> {
  const response = await authFetch(new Request(`${location.origin}${path}`));
  if (!response.ok) throw await toApiError(response);
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
