/** Zapytania do API wspólne dla widoków wesela (klucze React Query w jednym miejscu). */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";

export type Wedding = components["schemas"]["WeddingOut"];
export type Task = components["schemas"]["TaskOut"];
export type Member = components["schemas"]["MemberOut"];
export type Summary = components["schemas"]["WeddingSummary"];
export type Payment = components["schemas"]["PaymentOut"];
export type BudgetOverview = components["schemas"]["BudgetOverview"];
// Nazwa z prefiksem modułu: harmonogram też ma schemat ItemOut.
export type BudgetItem = components["schemas"]["app__modules__budget__schemas__ItemOut"];
export type BudgetCategory = components["schemas"]["CategoryOut"];
export type Household = components["schemas"]["HouseholdOut"];
export type Guest = components["schemas"]["GuestOut"];
export type WeddingEvent = components["schemas"]["EventOut"];
export type GuestStats = components["schemas"]["GuestStats"];
export type ScheduleItem = components["schemas"]["app__modules__schedule__schemas__ItemOut"];
export type ScheduleConflict = components["schemas"]["ConflictOut"];
export type SeatingPlan = components["schemas"]["PlanOut"];
export type SeatingTable = components["schemas"]["TablePlan"];
export type SeatingRule = components["schemas"]["RuleOut"];

export const keys = {
  wedding: (id: string) => ["wedding", id] as const,
  summary: (id: string) => ["wedding", id, "summary"] as const,
  tasks: (id: string) => ["wedding", id, "tasks"] as const,
  members: (id: string) => ["wedding", id, "members"] as const,
  payments: (id: string) => ["wedding", id, "payments"] as const,
  budget: (id: string) => ["wedding", id, "budget"] as const,
  items: (id: string) => ["wedding", id, "budget-items"] as const,
  categories: (id: string) => ["wedding", id, "budget-categories"] as const,
  households: (id: string) => ["wedding", id, "households"] as const,
  events: (id: string) => ["wedding", id, "events"] as const,
  guestStats: (id: string) => ["wedding", id, "guest-stats"] as const,
  forecast: (id: string) => ["wedding", id, "attendance-forecast"] as const,
  funders: (id: string) => ["wedding", id, "funders"] as const,
  reserve: (id: string) => ["wedding", id, "reserve"] as const,
  schedule: (id: string) => ["wedding", id, "schedule"] as const,
  scheduleConflicts: (id: string) => ["wedding", id, "schedule", "conflicts"] as const,
  seating: (id: string) => ["wedding", id, "seating"] as const,
  seatingRules: (id: string) => ["wedding", id, "seating", "rules"] as const,
};

export function useWeddingId(): string {
  const { weddingId } = useParams();
  if (!weddingId) throw new Error("Brak identyfikatora wesela w adresie");
  return weddingId;
}

const p = (weddingId: string) => ({ path: { wedding_id: weddingId } });

export function useWedding(id: string) {
  return useQuery({
    queryKey: keys.wedding(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}", { params: p(id), signal })),
  });
}

export const ROLE_LABEL: Record<string, string> = {
  owner: "Właściciel",
  coorganizer: "Współorganizator",
  viewer: "Tylko podgląd",
  coordinator: "Koordynator dnia",
  sponsor: "Sponsor (tylko swój wkład)",
};

/** Edycja planu: właściciel i współorganizator (podgląd i koordynator dnia tylko czytają). */
export function useCanWrite(id: string): boolean {
  const wedding = useWedding(id);
  const role = wedding.data?.my_role;
  return role === "owner" || role === "coorganizer";
}

/** Prowadzenie dnia ślubu (przesuwanie programu): także koordynator dnia. */
export function useCanRunDay(id: string): boolean {
  const role = useWedding(id).data?.my_role;
  return role === "owner" || role === "coorganizer" || role === "coordinator";
}

export function useSummary(id: string) {
  return useQuery({
    queryKey: keys.summary(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/summary", { params: p(id), signal })),
  });
}

/** Wszystkie zadania (API stronicuje po 200): pobieramy kolejne strony do końca. */
export function useTasks(id: string) {
  return useQuery({
    queryKey: keys.tasks(id),
    queryFn: async ({ signal }) => {
      const all: Task[] = [];
      let cursor: string | undefined;
      do {
        const page = await unwrap(
          api.GET("/api/v1/weddings/{wedding_id}/tasks", {
            params: { ...p(id), query: { limit: 200, ...(cursor ? { cursor } : {}) } },
            signal,
          }),
        );
        all.push(...page.items);
        cursor = page.next_cursor ?? undefined;
      } while (cursor);
      return all;
    },
  });
}

export function useMembers(id: string) {
  return useQuery({
    queryKey: keys.members(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/members", { params: p(id), signal })),
    staleTime: 5 * 60_000,
  });
}

export function usePayments(id: string) {
  return useQuery({
    queryKey: keys.payments(id),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/payments/schedule", { params: p(id), signal })),
  });
}

export function useBudgetOverview(id: string) {
  return useQuery({
    queryKey: keys.budget(id),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/budget/overview", { params: p(id), signal })),
  });
}

export function useBudgetItems(id: string) {
  return useQuery({
    queryKey: keys.items(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/budget/items", { params: p(id), signal })),
  });
}

export function useBudgetCategories(id: string) {
  return useQuery({
    queryKey: keys.categories(id),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/budget/categories", { params: p(id), signal })),
    staleTime: 5 * 60_000,
  });
}

export function useHouseholds(id: string) {
  return useQuery({
    queryKey: keys.households(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/households", { params: p(id), signal })),
  });
}

export function useEvents(id: string) {
  return useQuery({
    queryKey: keys.events(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/events", { params: p(id), signal })),
    staleTime: 5 * 60_000,
  });
}

export function useGuestStats(id: string) {
  return useQuery({
    queryKey: keys.guestStats(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/guests/stats", { params: p(id), signal })),
  });
}

/** Imię członka do wyświetlenia (nazwa albo część e-maila przed @). */
export function memberName(members: Member[] | undefined, userId: string | null | undefined): string | null {
  if (!userId) return null;
  const m = members?.find((x) => x.user_id === userId);
  if (!m) return null;
  return m.display_name?.trim() || m.email.split("@")[0] || null;
}

export function useSchedule(id: string) {
  return useQuery({
    queryKey: keys.schedule(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/schedule", { params: p(id), signal })),
  });
}

export function useScheduleConflicts(id: string) {
  return useQuery({
    queryKey: keys.scheduleConflicts(id),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/schedule/conflicts", { params: p(id), signal })),
  });
}

export function useSeatingPlan(id: string) {
  return useQuery({
    queryKey: keys.seating(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/seating", { params: p(id), signal })),
  });
}

export function useSeatingRules(id: string) {
  return useQuery({
    queryKey: keys.seatingRules(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/seating/rules", { params: p(id), signal })),
  });
}

export const helpersKey = (id: string) => ["wedding", id, "helpers"] as const;

/** Pomocnicy bez konta (zadania na linku). */
export function useHelpers(id: string) {
  return useQuery({
    queryKey: helpersKey(id),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/helpers", { params: p(id), signal })),
  });
}
