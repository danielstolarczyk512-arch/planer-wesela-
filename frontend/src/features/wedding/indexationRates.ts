import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import { keys } from "./data";

/** „10%” z „0.10” (stopy waloryzacji; zapisane założenia zwraca API razem z wyliczeniem). */
export const percent = (rate: string) => `${Math.round(Number(rate) * 100)}%`;

/** Wyliczenie wg założeń zapisanych na weselu (wspólne z ekranem Dziś). */
export function useIndexation(weddingId: string) {
  return useQuery({
    queryKey: [...keys.budget(weddingId), "indexation"],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/budget/indexation", { params: { path: { wedding_id: weddingId } }, signal })),
    placeholderData: (previous) => previous,
  });
}
