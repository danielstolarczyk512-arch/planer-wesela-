import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { useMe } from "../../api/me";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip, type Tone } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { useVendorCategories } from "../wedding/vendors";

type Source = components["schemas"]["app__modules__discovery__router__SourceOut"];

const SOURCE_STATE: Record<string, { label: string; tone: Tone }> = {
  active: { label: "Aktywne", tone: "success" },
  paused: { label: "Wstrzymane", tone: "neutral" },
  blocked: { label: "Zablokowane przez stronę", tone: "warning" },
  gone: { label: "Strona zniknęła", tone: "warning" },
  failed: { label: "Błąd — zatrzymane", tone: "error" },
};

const adminKeys = {
  status: ["admin", "discovery", "status"] as const,
  sources: ["admin", "discovery", "sources"] as const,
  review: ["admin", "catalog", "review"] as const,
  vendors: ["admin", "catalog", "vendors"] as const,
};

function when(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function StatusBlock() {
  const qc = useQueryClient();
  const toast = useToast();
  const status = useQuery({
    queryKey: adminKeys.status,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/admin/discovery/status", { signal })),
    refetchInterval: 15_000,
  });
  const [limit, setLimit] = useState("");
  const toggle = useMutation({
    mutationFn: (pause: boolean) =>
      unwrap(pause ? api.POST("/api/v1/admin/discovery/pause") : api.POST("/api/v1/admin/discovery/resume")),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adminKeys.status }),
  });
  const setLimitMut = useMutation({
    mutationFn: () => unwrap(api.PUT("/api/v1/admin/discovery/limits", { body: { daily_fetch_limit: Number(limit) } })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminKeys.status });
      toast("Zapisano limit.");
    },
  });
  if (status.isPending) return <Skeleton lines={4} />;
  if (status.isError) return <Notice tone="error" live>{userMessage(status.error)}</Notice>;
  const s = status.data as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const caps = s.capabilities as { search_new_sources: { configured: boolean; reason: string } };
  const stale = (iso?: string | null) => !iso || status.dataUpdatedAt - new Date(iso).getTime() > 5 * 60_000;
  return (
    <Card>
      <h2>Stan badacza</h2>
      <p>
        <StatusChip tone={s.paused ? "warning" : "success"}>{s.paused ? "Wstrzymany" : "Działa"}</StatusChip>{" "}
        <StatusChip tone={stale(s.worker_heartbeat_at) ? "error" : "success"}>
          Worker: {when(s.worker_heartbeat_at)}
        </StatusChip>{" "}
        <StatusChip tone={stale(s.scheduler_heartbeat_at) ? "error" : "success"}>
          Harmonogram: {when(s.scheduler_heartbeat_at)}
        </StatusChip>
      </p>
      <ul className="match__list">
        <li>Ostatni sukces: {when(s.last_success_at)}</li>
        <li>
          Pobrania w ostatniej dobie: {s.fetches_last_24h} / {s.daily_fetch_limit}
        </li>
        <li>
          Kolejka: {s.queued_jobs} · martwe zadania: {s.dead_jobs} · najstarsze zadanie: {when(s.oldest_queued_job_at)}
        </li>
        <li>Najbardziej spóźnione źródło: {when(s.oldest_overdue_source_at)}</li>
        <li>Otwarte wpisy do weryfikacji: {s.catalog.open_reviews}</li>
      </ul>
      <Notice tone={caps.search_new_sources.configured ? "success" : "info"} title="Wyszukiwanie nowych firm">
        {caps.search_new_sources.reason}
      </Notice>
      <div className="match__actions">
        <Button variant="secondary" pending={toggle.isPending} onPress={() => toggle.mutate(!s.paused)}>
          {s.paused ? "Wznów badacza" : "Wstrzymaj badacza"}
        </Button>
      </div>
      <AmountField label="Dzienny limit pobrań" value={limit} onChange={(v) => setLimit(v ?? "")} />
      <Button variant="text" pending={setLimitMut.isPending} isDisabled={!limit} onPress={() => setLimitMut.mutate()}>
        Zapisz limit
      </Button>
    </Card>
  );
}

function SourcesBlock() {
  const qc = useQueryClient();
  const toast = useToast();
  const categories = useVendorCategories();
  const sources = useQuery({
    queryKey: adminKeys.sources,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/admin/discovery/sources", { signal })),
  });
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState("photographer");
  const [region, setRegion] = useState("");
  const [basis, setBasis] = useState("");
  const [error, setError] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: adminKeys.sources });
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/admin/discovery/sources", {
          body: { url, category, region_hint: region || null, access_basis: basis || null, refresh_interval_days: 14 },
        }),
      ),
    onSuccess: () => {
      setUrl("");
      setError(null);
      refresh();
      toast("Dodano źródło. Pierwsze pobranie zaplanuje harmonogram.");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const patch = useMutation({
    mutationFn: (v: { id: string; state: "active" | "paused" }) =>
      unwrap(api.PATCH("/api/v1/admin/discovery/sources/{source_id}", { params: { path: { source_id: v.id } }, body: { state: v.state } })),
    onSuccess: refresh,
  });
  const fetchNow = useMutation({
    mutationFn: (sid: string) => unwrap(api.POST("/api/v1/admin/discovery/sources/{source_id}/fetch-now", { params: { path: { source_id: sid } } })),
    onSuccess: () => toast("Odświeżenie w kolejce."),
    onError: (e) => toast(userMessage(e)),
  });
  return (
    <Card>
      <h2>Źródła (strony firm)</h2>
      <p className="text-secondary">
        Badacz pobiera wyłącznie strony, które tu dodasz, i uznaje 401/403, CAPTCHA oraz robots.txt za zakaz. Dodawaj strony, do których masz prawo
        (strona firmy, zgoda firmy) — nie katalogi konkurencji ani portale z zakazem automatycznego pobierania.
      </p>
      <form
        className="form-stack"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate();
        }}
      >
        <TextField label="Adres strony (https://…)" value={url} onChange={setUrl} isRequired />
        <Select label="Kategoria" options={(categories.data ?? []).map((c) => ({ id: c.slug, label: c.label }))} value={category} onChange={setCategory} />
        <TextField label="Region (opcjonalnie)" value={region} onChange={setRegion} />
        <TextField label="Podstawa dostępu" description="Dlaczego wolno pobrać tę stronę, np. „strona firmy, publiczny cennik”." value={basis} onChange={setBasis} />
        {error && <Notice tone="error" live>{error}</Notice>}
        <Button type="submit" pending={add.isPending} isDisabled={!url}>
          Dodaj źródło
        </Button>
      </form>
      {sources.isPending && <Skeleton lines={3} />}
      {sources.data?.length === 0 && <EmptyState title="Brak źródeł">Dodaj pierwszą stronę firmy, żeby zbudować katalog.</EmptyState>}
      <ul className="row-list">
        {(sources.data ?? []).map((s: Source) => {
          const st = SOURCE_STATE[s.state] ?? SOURCE_STATE.paused!;
          return (
            <li key={s.id} className="row inq">
              <span className="row__body">
                <span className="row__title">{s.url}</span>
                <span className="text-secondary">
                  {s.category} · ostatni sukces: {when(s.last_success_at)} · następne: {when(s.next_check_at)}
                  {s.state_reason ? ` · ${s.state_reason}` : ""}
                </span>
              </span>
              <StatusChip tone={st.tone}>{st.label}</StatusChip>
              {s.state === "active" ? (
                <>
                  <Button variant="text" onPress={() => fetchNow.mutate(s.id)}>Odśwież teraz</Button>
                  <Button variant="text" onPress={() => patch.mutate({ id: s.id, state: "paused" })}>Wstrzymaj</Button>
                </>
              ) : (
                <Button variant="text" onPress={() => patch.mutate({ id: s.id, state: "active" })}>Wznów</Button>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function ReviewBlock() {
  const qc = useQueryClient();
  const review = useQuery({
    queryKey: adminKeys.review,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/admin/catalog/review", { signal })),
  });
  const resolve = useMutation({
    mutationFn: (v: { id: string; confirm?: string }) =>
      unwrap(
        api.POST("/api/v1/admin/catalog/review/{review_id}/resolve", {
          params: { path: { review_id: v.id } },
          body: { resolution: v.confirm ? "Wybrano cenę potwierdzoną przez administratora." : "Sprawdzone ręcznie.", confirm_package_id: v.confirm ?? null },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adminKeys.review }),
  });
  return (
    <Card>
      <h2>Do weryfikacji</h2>
      {review.data?.length === 0 && <p className="text-secondary">Nic nie czeka na weryfikację.</p>}
      <ul className="row-list">
        {(review.data ?? []).map((r) => {
          const prices = (r.details as { prices?: { from: string | null; to: string | null; source_id: string }[]; package_ids?: string[] }) ?? {};
          return (
            <li key={r.id} className="row inq">
              <span className="row__body">
                <span className="row__title">{r.summary}</span>
                <span className="text-secondary">{r.kind}</span>
                {r.kind === "conflict" &&
                  prices.package_ids?.map((pid, i) => (
                    <Button key={pid} variant="text" onPress={() => resolve.mutate({ id: r.id, confirm: pid })}>
                      Uznaj cenę {prices.prices?.[i]?.from ?? "?"} zł
                    </Button>
                  ))}
              </span>
              <Button variant="secondary" onPress={() => resolve.mutate({ id: r.id })}>
                Oznacz jako sprawdzone
              </Button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function VendorsBlock() {
  const qc = useQueryClient();
  const vendors = useQuery({
    queryKey: adminKeys.vendors,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/admin/catalog/vendors", { signal })),
  });
  const setStatus = useMutation({
    mutationFn: (v: { id: string; status: "published" | "hidden" | "draft" | "needs_review" }) =>
      unwrap(api.PUT("/api/v1/admin/catalog/vendors/{vendor_id}/status", { params: { path: { vendor_id: v.id } }, body: { status: v.status } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adminKeys.vendors }),
  });
  return (
    <Card>
      <h2>Firmy w katalogu</h2>
      <ul className="row-list">
        {(vendors.data ?? []).map((v) => (
          <li key={v.id} className="row inq">
            <span className="row__body">
              <span className="row__title">{v.name}</span>
              <span className="text-secondary">{[v.category, v.city, v.merged_into_id ? "scalona" : null].filter(Boolean).join(" · ")}</span>
            </span>
            <StatusChip tone={v.publication_status === "published" ? "success" : "neutral"}>{v.publication_status}</StatusChip>
            {v.publication_status === "published" ? (
              <Button variant="text" onPress={() => setStatus.mutate({ id: v.id, status: "hidden" })}>Ukryj</Button>
            ) : (
              <Button variant="text" onPress={() => setStatus.mutate({ id: v.id, status: "published" })}>Opublikuj</Button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Panel badacza katalogu — tylko dla administratora (inni dostają 404 z API). */
export function CatalogAdminView() {
  const me = useMe();
  if (me.isPending) return <Skeleton lines={3} />;
  if (me.data?.global_role !== "admin")
    return (
      <main className="page">
        <EmptyState title="Brak dostępu">Ta strona jest dostępna tylko dla administratora.</EmptyState>
      </main>
    );
  return (
    <main className="page enter-tab form-stack" aria-labelledby="admin-h">
      <h1 id="admin-h">Katalog firm: badacz</h1>
      <StatusBlock />
      <SourcesBlock />
      <ReviewBlock />
      <VendorsBlock />
    </main>
  );
}
