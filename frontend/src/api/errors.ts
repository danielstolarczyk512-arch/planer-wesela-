/** Błędy API w formacie RFC 9457 (application/problem+json) i komunikaty dla użytkownika. */

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly fieldErrors: FieldError[];
  /** Sekundy z nagłówka Retry-After (429). */
  readonly retryAfter: number | null;

  constructor(init: {
    status: number;
    code: string;
    detail: string;
    fieldErrors?: FieldError[];
    retryAfter?: number | null;
  }) {
    super(init.detail);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.detail = init.detail;
    this.fieldErrors = init.fieldErrors ?? [];
    this.retryAfter = init.retryAfter ?? null;
  }
}

/** Brak połączenia albo serwer nieosiągalny: formularz zostaje, nic nie udaje sukcesu. */
export class NetworkError extends Error {
  constructor() {
    super("Brak połączenia z serwerem.");
    this.name = "NetworkError";
  }
}

interface Problem {
  title?: string;
  detail?: string;
  code?: string;
  errors?: { loc?: (string | number)[]; field?: string; msg?: string; message?: string }[];
}

/**
 * Błąd z odpowiedzi. `parsed` — treść już odczytana przez openapi-fetch (body jest wtedy zużyte,
 * a `clone()` rzuciłby wyjątek i zgubilibyśmy kod błędu).
 */
export async function toApiError(response: Response, parsed?: unknown): Promise<ApiError> {
  let body: Problem = {};
  if (parsed !== undefined) {
    if (parsed && typeof parsed === "object") body = parsed as Problem;
  } else if (!response.bodyUsed) {
    try {
      body = (await response.clone().json()) as Problem;
    } catch {
      // treść nie jest JSON-em (np. proxy): komunikat ogólny
    }
  }
  const retry = Number(response.headers.get("retry-after"));
  return new ApiError({
    status: response.status,
    code: body.code ?? `http.${response.status}`,
    detail: body.detail ?? body.title ?? "Coś poszło nie tak. Spróbuj ponownie.",
    fieldErrors: (body.errors ?? []).map((e) => ({
      field: e.field ?? String(e.loc?.[e.loc.length - 1] ?? ""),
      message: e.message ?? e.msg ?? "Nieprawidłowa wartość",
    })),
    retryAfter: Number.isFinite(retry) && retry > 0 ? retry : null,
  });
}

/** Komunikat dla użytkownika (GUI-SPEC v1.1, sekcja 6). Dla 4xx zwykle tekst z API. */
export function userMessage(error: unknown): string {
  if (error instanceof NetworkError) return "Brak połączenia. Nic nie zapisano — spróbuj ponownie.";
  if (!(error instanceof ApiError)) return "Coś poszło nie tak. Spróbuj ponownie.";
  switch (error.status) {
    case 409:
      if (error.code === "conflict.version_mismatch")
        return "Ktoś zmienił te dane w międzyczasie. Odśwież, aby zobaczyć aktualną wersję.";
      return error.detail;
    case 403:
      return error.code === "account.locked" ? "Konto jest zablokowane." : "Masz dostęp tylko do podglądu.";
    case 404:
      return "Nie znaleziono.";
    case 429:
      return error.retryAfter
        ? `Za dużo prób. Spróbuj za ${error.retryAfter} s.`
        : "Za dużo prób. Spróbuj za chwilę.";
    default:
      return error.status >= 500 ? "Serwer chwilowo nie odpowiada. Spróbuj ponownie." : error.detail;
  }
}
