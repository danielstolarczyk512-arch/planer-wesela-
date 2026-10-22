import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authFetch, unwrap } from "./client";
import { ApiError, NetworkError, toApiError, userMessage } from "./errors";
import { refreshAccessToken, session } from "./session";

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

describe("authFetch i sesja", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    session.signIn("stary-token");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    session.signOut();
  });

  it("dokleja Bearer z pamięci", async () => {
    fetchMock.mockResolvedValueOnce(json(200, {}));
    await authFetch(new Request("http://localhost/api/v1/me"));
    const req = fetchMock.mock.calls[0]![0] as Request;
    expect(req.headers.get("Authorization")).toBe("Bearer stary-token");
  });

  it("przy 401 odświeża token z ciasteczka i ponawia żądanie", async () => {
    fetchMock
      .mockResolvedValueOnce(json(401, { code: "auth.invalid_token" }))
      .mockResolvedValueOnce(json(200, { access_token: "nowy-token" }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    const r = await authFetch(new Request("http://localhost/api/v1/me"));
    expect(r.status).toBe(200);
    const [, refreshUrl, refreshInit] = [null, fetchMock.mock.calls[1]![0], fetchMock.mock.calls[1]![1]];
    expect(refreshUrl).toBe("/api/v1/auth/refresh");
    expect(refreshInit.headers["X-Client"]).toBe("web");
    expect((fetchMock.mock.calls[2]![0] as Request).headers.get("Authorization")).toBe("Bearer nowy-token");
    expect(session.token).toBe("nowy-token");
  });

  it("wiele równoczesnych odświeżeń = jedno żądanie", async () => {
    let resolve!: (r: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => (resolve = r)));
    const a = refreshAccessToken();
    const b = refreshAccessToken();
    resolve(json(200, { access_token: "t" }));
    expect(await a).toBe(true);
    expect(await b).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("nieudane odświeżenie wylogowuje", async () => {
    fetchMock.mockResolvedValueOnce(json(401, {})).mockResolvedValueOnce(json(401, {}));
    const r = await authFetch(new Request("http://localhost/api/v1/me"));
    expect(r.status).toBe(401);
    expect(session.status).toBe("signed-out");
  });

  it("żądania /auth/* dostają X-Client: web i nie są ponawiane", async () => {
    fetchMock.mockResolvedValueOnce(json(401, {}));
    await authFetch(new Request("http://localhost/api/v1/auth/login", { method: "POST", body: "{}" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect((fetchMock.mock.calls[0]![0] as Request).headers.get("X-Client")).toBe("web");
  });

  it("brak sieci przy odświeżeniu zalogowanej sesji: bez wylogowania", async () => {
    session.signIn("stary");
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    expect(await refreshAccessToken()).toBe(false);
    expect(session.status).toBe("signed-in");
  });

  it("brak sieci po wylogowaniu: stan się nie zmienia (ekran „offline” tylko przy starcie)", async () => {
    session.signOut();
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    expect(await refreshAccessToken()).toBe(false);
    expect(session.status).toBe("signed-out");
  });

  it("brak sieci → NetworkError (formularz nie udaje sukcesu)", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(authFetch(new Request("http://localhost/api/v1/me"))).rejects.toBeInstanceOf(NetworkError);
  });
});

describe("błędy API", () => {
  it("czyta problem+json, pola i Retry-After", async () => {
    const e = await toApiError(
      json(
        429,
        { code: "rate_limited", detail: "Spróbuj później.", errors: [{ loc: ["body", "email"], msg: "zły" }] },
        { "retry-after": "42" },
      ),
    );
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("rate_limited");
    expect(e.retryAfter).toBe(42);
    expect(e.fieldErrors).toEqual([{ field: "email", message: "zły" }]);
    expect(userMessage(e)).toBe("Za dużo prób. Spróbuj za 42 s.");
  });

  it("unwrap zachowuje kod błędu, gdy openapi-fetch już odczytał treść", async () => {
    const response = json(401, { code: "mfa.invalid_code", detail: "Nieprawidłowy kod." });
    const error = JSON.parse(await response.text()) as unknown;
    const e = await unwrap(Promise.resolve({ error, response })).catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect((e as ApiError).code).toBe("mfa.invalid_code");
    expect((e as ApiError).detail).toBe("Nieprawidłowy kod.");
  });

  it("konflikt wersji i brak sieci mają zrozumiałe komunikaty", () => {
    expect(userMessage(new ApiError({ status: 409, code: "conflict.version_mismatch", detail: "x" }))).toMatch(
      /zmienił/,
    );
    expect(userMessage(new NetworkError())).toMatch(/Nic nie zapisano/);
    expect(userMessage(new ApiError({ status: 500, code: "x", detail: "Traceback…" }))).not.toMatch(/Traceback/);
  });
});
