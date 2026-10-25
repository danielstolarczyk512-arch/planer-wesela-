/** Dobór usługodawców: katalog, preferencje, kandydaci, czat z asystentem i zapytania do firm. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import type { Tone } from "../../components/Surface";

export type Match = components["schemas"]["MatchOut"];
export type CatalogVendor = components["schemas"]["CatalogVendorOut"];
export type CatalogPackage = components["schemas"]["PackageOut"];
export type Preferences = components["schemas"]["PreferencesOut"];
export type Candidate = components["schemas"]["CandidateOut"];
export type Message = components["schemas"]["MessageOut"];
export type Discovery = components["schemas"]["DiscoveryOut"];
export type Inquiry = components["schemas"]["InquiryOut"];

export const aKeys = {
  prefs: (id: string, category: string) => ["wedding", id, "prefs", category] as const,
  search: (id: string, category: string, version: number) => ["wedding", id, "search", category, version] as const,
  candidates: (id: string) => ["wedding", id, "candidates"] as const,
  conversations: (id: string) => ["wedding", id, "conversations"] as const,
  messages: (id: string, conversationId: string) => ["wedding", id, "conversations", conversationId] as const,
  discovery: (id: string) => ["wedding", id, "discovery"] as const,
  inquiries: (id: string) => ["wedding", id, "inquiries"] as const,
};

const p = (weddingId: string) => ({ path: { wedding_id: weddingId } });

export function usePreferences(id: string, category: string) {
  return useQuery({
    queryKey: aKeys.prefs(id, category),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/vendor-preferences/{category}", {
          params: { path: { wedding_id: id, category } },
          signal,
        }),
      ),
  });
}

/** Dobór z katalogu wg zapisanych preferencji (kod, nie model — działa bez AI). */
export function useSearch(id: string, category: string, version: number) {
  return useQuery({
    queryKey: aKeys.search(id, category, version),
    queryFn: ({ signal }) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/vendor-search", {
          params: p(id),
          body: { category: category as never, limit: 8 },
          signal,
        }),
      ),
  });
}

export function useCandidates(id: string, state: "saved" | "rejected" = "saved") {
  return useQuery({
    queryKey: [...aKeys.candidates(id), state],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/candidates", { params: { ...p(id), query: { state } }, signal })),
  });
}

export function useConversations(id: string) {
  return useQuery({
    queryKey: aKeys.conversations(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/concierge/conversations", { params: p(id), signal })),
  });
}

/** Wiadomości rozmowy; dopóki odpowiedź jest „w toku”, dopytujemy co 2 s (odświeżenie nie gubi zadania). */
export function useMessages(id: string, conversationId: string | null) {
  return useQuery({
    queryKey: aKeys.messages(id, conversationId ?? "none"),
    enabled: conversationId !== null,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/concierge/conversations/{conversation_id}/messages", {
          params: { path: { wedding_id: id, conversation_id: conversationId ?? "" } },
          signal,
        }),
      ),
    refetchInterval: (query) => (query.state.data?.some((m) => m.state === "pending") ? 2000 : false),
  });
}

export function useDiscovery(id: string) {
  return useQuery({
    queryKey: aKeys.discovery(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/discovery-requests", { params: p(id), signal })),
    refetchInterval: (query) => (query.state.data?.some((r) => r.state === "queued" || r.state === "running") ? 3000 : false),
  });
}

export function useInquiries(id: string) {
  return useQuery({
    queryKey: aKeys.inquiries(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/inquiries", { params: p(id), signal })),
    refetchInterval: (query) =>
      query.state.data?.some((i) => i.delivery?.state === "queued" || i.delivery?.state === "sending") ? 2000 : false,
  });
}

export function useSaveCandidate(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { catalog_vendor_id: string; note?: string }) =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/candidates", { params: p(id), body: vars })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: aKeys.candidates(id) }),
  });
}

/** Polskie nazwy stanów zapytania — zawsze z ikoną i tekstem (nigdy sam kolor). */
export const INQUIRY_STATUS: Record<string, { label: string; tone: Tone }> = {
  draft: { label: "Szkic — czeka na Waszą zgodę", tone: "neutral" },
  draft_revised: { label: "Nowa wersja czeka na zgodę", tone: "neutral" },
  queued: { label: "W kolejce do wysłania", tone: "info" },
  sending: { label: "Wysyłanie", tone: "info" },
  sent: { label: "Wysłano do serwera pocztowego", tone: "success" },
  failed: { label: "Błąd wysyłki", tone: "error" },
  uncertain: { label: "Wynik wysyłki niepewny", tone: "warning" },
  answered: { label: "Odpowiedź otrzymana", tone: "success" },
};

export const FRESHNESS: Record<string, { label: string; tone: Tone }> = {
  fresh: { label: "Dane aktualne", tone: "success" },
  stale: { label: "Dane mogą być nieaktualne", tone: "warning" },
  unknown: { label: "Brak danych o aktualności", tone: "neutral" },
};

export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric" });
}
