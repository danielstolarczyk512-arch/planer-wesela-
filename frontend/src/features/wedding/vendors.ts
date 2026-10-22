/** Usługodawcy i oferty: zapytania, klucze i polskie etykiety. */
import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import type { Tone } from "../../components/Surface";

export type Vendor = components["schemas"]["VendorOut"];
export type VendorStatus = Vendor["status"];
export type Offer = components["schemas"]["OfferOut"];
export type OfferComponent = components["schemas"]["ComponentOut"];
export type OfferTerm = components["schemas"]["TermOut"];
export type ComponentKind = components["schemas"]["ComponentIn"]["kind"];

export const vendorKeys = {
  all: (id: string) => ["wedding", id, "vendors"] as const,
  one: (id: string, vendorId: string) => ["wedding", id, "vendors", vendorId] as const,
  categories: ["vendor-categories"] as const,
  offers: (id: string) => ["wedding", id, "offers"] as const,
  offer: (id: string, offerId: string) => ["wedding", id, "offers", offerId] as const,
};

const p = (weddingId: string) => ({ path: { wedding_id: weddingId } });

export function useVendorCategories() {
  return useQuery({
    queryKey: vendorKeys.categories,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/vendor-categories", { signal })),
    staleTime: Infinity,
  });
}

export function useVendors(id: string) {
  return useQuery({
    queryKey: vendorKeys.all(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/vendors", { params: p(id), signal })),
  });
}

export function useVendor(id: string, vendorId: string) {
  return useQuery({
    queryKey: vendorKeys.one(id, vendorId),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}", {
          params: { path: { wedding_id: id, vendor_id: vendorId } },
          signal,
        }),
      ),
  });
}

export function useOffers(id: string) {
  return useQuery({
    queryKey: vendorKeys.offers(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/offers", { params: p(id), signal })),
  });
}

export function useOffer(id: string, offerId: string) {
  return useQuery({
    queryKey: vendorKeys.offer(id, offerId),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/offers/{offer_id}", {
          params: { path: { wedding_id: id, offer_id: offerId } },
          signal,
        }),
      ),
  });
}

export const VENDOR_STATUS: Record<VendorStatus, { label: string; tone: Tone }> = {
  considering: { label: "Rozważamy", tone: "neutral" },
  contacted: { label: "W kontakcie", tone: "info" },
  offer_received: { label: "Mamy ofertę", tone: "info" },
  booked: { label: "Zarezerwowany", tone: "success" },
  rejected: { label: "Odpada", tone: "neutral" },
};

export const OFFER_STATUS: Record<Offer["status"], { label: string; tone: Tone }> = {
  draft: { label: "Szkic", tone: "neutral" },
  needs_review: { label: "Do sprawdzenia", tone: "warning" },
  approved: { label: "Sprawdzona", tone: "info" },
  selected: { label: "Wybrana", tone: "success" },
  rejected: { label: "Odrzucona", tone: "neutral" },
};

export const COMPONENT_KINDS: { id: ComponentKind; label: string; unit: string }[] = [
  { id: "per_guest", label: "Za osobę dorosłą", unit: "za osobę" },
  { id: "per_child", label: "Za dziecko", unit: "za dziecko" },
  { id: "per_crew", label: "Za posiłek dla obsługi (muzycy, fotograf)", unit: "za osobę obsługi" },
  { id: "fixed", label: "Kwota stała", unit: "" },
  { id: "per_hour", label: "Za godzinę", unit: "za godzinę" },
  { id: "per_unit", label: "Za sztukę", unit: "za sztukę" },
  { id: "percent", label: "Procent (np. serwis)", unit: "%" },
];

export const TERM_LABEL: Record<OfferTerm["term_type"], string> = {
  deposit: "Zadatek / zaliczka",
  payment_schedule: "Harmonogram płatności",
  cancellation: "Rezygnacja",
  menu: "Menu",
  drinks: "Napoje",
  corkage: "Korkowe",
  overtime: "Nadgodziny",
  other: "Inne",
};

export const CONFIDENCE: Record<OfferComponent["confidence"], { label: string; tone: Tone } | null> = {
  high: null,
  medium: { label: "Sprawdź", tone: "info" },
  low: { label: "Niepewne", tone: "warning" },
  unverified: { label: "Niezweryfikowane", tone: "warning" },
};
