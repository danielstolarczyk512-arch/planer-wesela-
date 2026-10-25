import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { INQUIRY_STATUS, type Match } from "./assistant";
import { MatchCard } from "./MatchCard";

const match = (over: Partial<Match> = {}): Match => ({
  catalog_vendor_id: "11111111-1111-4111-8111-111111111111",
  vendor: {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Foto Ola",
    category: "photographer",
    city: "Kraków",
    service_area: null,
    website: null,
    phones: [],
    emails: [],
    social: [],
    packages: [
      {
        id: "22222222-2222-4222-8222-222222222222",
        kind: "package",
        name: "Reportaż ślubny",
        price_from: "3500.00",
        price_to: null,
        currency: "PLN",
        unit: "unspecified",
        price_label: "od 3 500 zł",
        season: null,
        season_known: false,
        evidence: "Reportaż ślubny od 3 500 zł",
        source_url: "https://foto-ola.example/cennik",
        observed_at: "2026-10-20T10:00:00Z",
        fresh: true,
        conflict: false,
        note: "",
      },
    ],
    surcharges: [],
    freshness: "fresh",
    last_observed_at: "2026-10-20T10:00:00Z",
    availability: "unconfirmed",
    price_status: "public_price",
    sources: [],
    tags: [],
    missing: [],
  },
  reasons: [
    { kind: "category", text: "Kategoria: photographer.", evidence: null, source_url: null },
    { kind: "scope", text: "W cenniku jest „przygotowania”.", evidence: "Reportaż z przygotowaniami od 3 500 zł", source_url: null },
  ],
  missing: ["sezon, którego dotyczy cennik", "dostępność terminu (niepotwierdzona)"],
  flags: [],
  region_fit: "match",
  budget_fit: "fits",
  ...over,
});

describe("MatchCard", () => {
  it("pokazuje uzasadnienie z cytatem, cenę ze źródłem i braki — bez etykiety „sprawdzony”", () => {
    render(<MatchCard match={match()} />);
    const card = screen.getByRole("article", { name: "Foto Ola" });
    expect(within(card).getByText("od 3 500 zł")).toBeInTheDocument();
    expect(within(card).getByText(/Reportaż z przygotowaniami od 3 500 zł/)).toBeInTheDocument();
    expect(within(card).getByText(/sezon nie podany/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /źródło/ })).toHaveAttribute("href", "https://foto-ola.example/cennik");
    expect(within(card).getByText("dostępność terminu (niepotwierdzona)")).toBeInTheDocument();
    expect(card.textContent?.toLowerCase()).not.toContain("sprawdzon");
    expect(card.textContent).not.toMatch(/\d+\s*\/\s*100/);
  });

  it("bez ceny: „zapytaj o wycenę”; konflikt źródeł i nieaktualność mają tekst, nie tylko kolor", () => {
    const base = match();
    const m = match({
      vendor: { ...base.vendor, packages: [{ ...base.vendor.packages[0]!, conflict: true }], freshness: "stale" },
      flags: ["dane mogą być nieaktualne"],
    });
    render(<MatchCard match={m} />);
    expect(screen.getByText("Źródła podają różne ceny")).toBeInTheDocument();
    expect(screen.getByText("Dane mogą być nieaktualne")).toBeInTheDocument();
    render(<MatchCard match={match({ vendor: { ...base.vendor, name: "Foto Pusta", packages: [] } })} />);
    expect(screen.getByText(/Brak ceny w katalogu — zapytaj o wycenę/)).toBeInTheDocument();
  });
});

describe("stany zapytań", () => {
  it("„wysłano” jest opisane jako przyjęcie przez serwer pocztowy, nie doręczenie", () => {
    expect(INQUIRY_STATUS.sent!.label).toBe("Wysłano do serwera pocztowego");
    expect(Object.keys(INQUIRY_STATUS)).toEqual(
      expect.arrayContaining(["draft", "queued", "sent", "failed", "uncertain", "answered"]),
    );
  });
});
