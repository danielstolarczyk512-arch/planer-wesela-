/** Wyszukiwarka w weselu: zadania, goście, usługodawcy i wydatki — z każdego ekranu (lupa w nagłówku). */
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Button as AriaButton, Input, Label, SearchField } from "react-aria-components";
import { Link, useSearchParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Card, EmptyState, Notice, Skeleton } from "../../components/Surface";
import { useWeddingId } from "./data";

type Hit = components["schemas"]["WeddingSearchHit"];

const GROUPS: { kind: Hit["kind"]; label: string }[] = [
  { kind: "task", label: "Zadania" },
  { kind: "guest", label: "Goście" },
  { kind: "vendor", label: "Usługodawcy" },
  { kind: "expense", label: "Wydatki" },
];

/** Dokąd prowadzi wynik: zadanie otwiera się w Planie, gość na liście z filtrem, firma na swojej karcie. */
export function hitLink(weddingId: string, h: Hit): string {
  const base = `/w/${weddingId}`;
  switch (h.kind) {
    case "task":
      return `${base}/plan?zadanie=${h.id}`;
    case "guest":
      return `${base}/goscie?q=${encodeURIComponent(h.subtitle)}`;
    case "vendor":
      return `${base}/uslugodawcy/${h.id}`;
    default:
      return `${base}/budzet`;
  }
}

/** Opóźnienie zapytania podczas pisania. */
function useDebounced(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export function SearchView() {
  const id = useWeddingId();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const q = useDebounced(query.trim(), 250);
  const result = useQuery({
    queryKey: ["wedding", id, "search", q],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/search", { params: { path: { wedding_id: id }, query: { q } }, signal })),
    enabled: q.length >= 2,
  });
  useEffect(() => {
    setParams(q ? { q } : {}, { replace: true });
  }, [q, setParams]);
  const waiting = q !== query.trim();
  const hits = !waiting && q.length >= 2 ? (result.data?.results ?? []) : [];

  return (
    <main className="page enter-tab" aria-labelledby="search-h">
      <h1 id="search-h">Szukaj</h1>
      <SearchField className="wp-field" value={query} onChange={setQuery} autoFocus>
        <Label className="wp-field__label">Zadania, goście, usługodawcy, wydatki</Label>
        <div className="search-control">
          <Input className="wp-field__input" placeholder="np. kwiaty, Kowalscy, zespół" />
          {query && <AriaButton className="search-clear" aria-label="Wyczyść wyszukiwanie">Wyczyść</AriaButton>}
        </div>
      </SearchField>
      {query.trim().length < 2 && <p className="text-secondary">Wpiszcie co najmniej 2 znaki, aby wyszukać w całym weselu.</p>}
      {!waiting && q.length >= 2 && result.isError && (
        <Notice tone="error" live>
          {userMessage(result.error)}
        </Notice>
      )}
      {query.trim().length >= 2 && (waiting || result.isPending) && <Skeleton lines={3} />}
      {!waiting && q.length >= 2 && result.data && hits.length === 0 && <EmptyState title="Nic nie znaleźliśmy">Spróbujcie krótszego fragmentu nazwy.</EmptyState>}
      <p className="visually-hidden" aria-live="polite">
        {!waiting && q.length >= 2 && result.data ? `Wyniki: ${hits.length}` : ""}
      </p>
      {GROUPS.map((g) => {
        const list = hits.filter((h) => h.kind === g.kind);
        if (list.length === 0) return null;
        return (
          <section key={g.kind} className="form-stack" aria-labelledby={`search-${g.kind}`}>
            <h2 id={`search-${g.kind}`}>{g.label}</h2>
            <Card>
              <ul className="row-list">
                {list.map((h) => (
                  <li key={`${h.kind}-${h.id}-${h.title}`}>
                    <Link to={hitLink(id, h)} className="row link-card">
                      <span className="row__body">
                        <span className="row__title">{h.title}</span>
                        <span className="text-secondary">{h.subtitle}</span>
                      </span>
                      <ChevronRight aria-hidden size={20} />
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        );
      })}
    </main>
  );
}
