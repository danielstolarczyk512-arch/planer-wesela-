import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "./client";

/** Zalogowany użytkownik (id, e-mail, nazwa). */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/me", { signal })),
    staleTime: 5 * 60_000,
  });
}
