import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { session } from "../../api/session";
import { LoginPage, safeReturnPath } from "./LoginPage";

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

function renderLogin(path = "/logowanie") {
  const router = createMemoryRouter(
    [
      { path: "/logowanie", element: <LoginPage /> },
      { path: "/", element: <p>Strona główna</p> },
      { path: "/ustawienia", element: <p>Ustawienia</p> },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
}

describe("LoginPage", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    session.signOut();
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("puste pola: błędy przy polach i fokus na pierwszym", async () => {
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(screen.getByLabelText(/E-mail/)).toHaveFocus();
    expect(screen.getByLabelText(/E-mail/)).toHaveAccessibleDescription(/adres e-mail/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("zły login: ten sam komunikat dla e-maila i hasła, hasło wyczyszczone", async () => {
    fetchMock.mockResolvedValueOnce(json(401, { code: "auth.invalid_credentials", detail: "x" }));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/E-mail/), "anna@example.com");
    await userEvent.type(screen.getByLabelText(/^Hasło/), "zle-haslo-123");
    await userEvent.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Nieprawidłowy e-mail lub hasło.");
    expect(screen.getByLabelText(/^Hasło/)).toHaveValue("");
  });

  it("limit prób (429): przycisk zablokowany z odliczaniem", async () => {
    fetchMock.mockResolvedValueOnce(json(429, { code: "rate_limited", detail: "x" }, { "retry-after": "30" }));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/E-mail/), "anna@example.com");
    await userEvent.type(screen.getByLabelText(/^Hasło/), "haslo-123456");
    await userEvent.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Spróbuj za 30 s");
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeDisabled();
  });

  it("udane logowanie: token tylko w pamięci, powrót na wskazaną stronę", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { access_token: "abc", refresh_token: null, expires_in: 900 }));
    renderLogin("/logowanie?powrot=%2Fustawienia");
    await userEvent.type(screen.getByLabelText(/E-mail/), "anna@example.com");
    await userEvent.type(screen.getByLabelText(/^Hasło/), "Dobre-Haslo-2027");
    await userEvent.click(screen.getByRole("button", { name: "Zaloguj się" }));
    await waitFor(() => expect(screen.getByText("Ustawienia")).toBeInTheDocument());
    expect(session.token).toBe("abc");
    expect(localStorage.length).toBe(0);
  });

  it("powrót tylko w obrębie aplikacji (bez otwartego przekierowania)", () => {
    expect(safeReturnPath("/ustawienia")).toBe("/ustawienia");
    expect(safeReturnPath("//evil.example")).toBe("/");
    expect(safeReturnPath("https://evil.example")).toBe("/");
    expect(safeReturnPath(null)).toBe("/");
  });
});
