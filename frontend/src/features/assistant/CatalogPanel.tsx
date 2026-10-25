import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { useCanWrite } from "../wedding/data";
import { ifMatch, saveErrorMessage } from "../wedding/mutations";
import { useVendorCategories } from "../wedding/vendors";
import { MatchCard } from "./MatchCard";
import { aKeys, formatDay, useCandidates, useDiscovery, usePreferences, useSaveCandidate, useSearch, type Preferences } from "./assistant";

const split = (text: string) =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

function PreferencesForm({ id, category }: { id: string; category: string }) {
  const prefs = usePreferences(id, category);
  if (prefs.isPending) return <Skeleton lines={3} />;
  if (!prefs.data) return null;
  // Klucz z wersją: po zapisie albo zmianie kategorii formularz startuje od aktualnych danych.
  return <PreferencesFields key={`${category}-${prefs.data.version}`} id={id} category={category} prefs={prefs.data} />;
}

function PreferencesFields({ id, category, prefs }: { id: string; category: string; prefs: Preferences }) {
  const canWrite = useCanWrite(id);
  const qc = useQueryClient();
  const toast = useToast();
  const [scope, setScope] = useState(prefs.scope_terms.join(", "));
  const [style, setStyle] = useState(prefs.style_tags.join(", "));
  const [budget, setBudget] = useState(prefs.budget_max ? String(Number(prefs.budget_max)) : "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/vendor-preferences/{category}", {
          params: { path: { wedding_id: id, category } },
          headers: prefs.version > 0 ? ifMatch(prefs.version) : undefined,
          body: { scope_terms: split(scope), style_tags: split(style), budget_max: budget ? budget : null },
        }),
      ),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: aKeys.prefs(id, category) });
      void qc.invalidateQueries({ queryKey: ["wedding", id, "search", category] });
      toast("Zapisano preferencje.");
    },
    onError: (e) => setError(saveErrorMessage(e, qc, [aKeys.prefs(id, category)])),
  });

  return (
    <Card>
      <form
        className="form-stack"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <h2>Czego szukacie</h2>
        <TextField
          label="Co ma obejmować usługa"
          description="Po przecinku, np. przygotowania, oczepiny. Szukamy tych słów w cennikach firm."
          value={scope}
          onChange={setScope}
          isDisabled={!canWrite}
        />
        <TextField
          label="Styl"
          description="Po przecinku, np. reportaż. Porównujemy tylko z opisami potwierdzonymi w katalogu."
          value={style}
          onChange={setStyle}
          isDisabled={!canWrite}
        />
        <AmountField label="Budżet na tę usługę (zł)" description="Służy tylko do doboru; nie jest wysyłany do firm." value={budget} onChange={(v) => setBudget(v ?? "")} />
        {error && <Notice tone="error" live>{error}</Notice>}
        {canWrite && (
          <Button type="submit" variant="secondary" pending={save.isPending}>
            Zapisz preferencje
          </Button>
        )}
      </form>
    </Card>
  );
}

export function CatalogPanel({ id }: { id: string }) {
  const categories = useVendorCategories();
  const canWrite = useCanWrite(id);
  const [category, setCategory] = useState("photographer");
  const prefs = usePreferences(id, category);
  const search = useSearch(id, category, prefs.data?.version ?? 0);
  const candidates = useCandidates(id);
  const save = useSaveCandidate(id);
  const discovery = useDiscovery(id);
  const qc = useQueryClient();
  const toast = useToast();
  const savedIds = new Set((candidates.data ?? []).map((c) => c.catalog_vendor_id));
  const key = useState(newIdempotencyKey)[0];

  const research = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/discovery-requests", {
          params: { path: { wedding_id: id } },
          body: { category: category as never },
          headers: { "Idempotency-Key": `${key}-${Date.now()}` },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: aKeys.discovery(id) });
      toast("Zlecono odświeżenie znanych źródeł.");
    },
  });
  const latest = (discovery.data ?? []).find((r) => r.category === category);

  return (
    <div className="form-stack">
      <Select
        label="Kategoria"
        options={(categories.data ?? []).map((c) => ({ id: c.slug, label: c.label }))}
        value={category}
        onChange={setCategory}
      />
      <PreferencesForm id={id} category={category} />

      <h2>Dopasowane firmy</h2>
      {search.isPending && <Skeleton lines={4} />}
      {search.isError && (
        <Notice tone="error" live>
          {userMessage(search.error)}
        </Notice>
      )}
      {search.data && search.data.items.length === 0 && (
        <EmptyState title="Brak firm w tej kategorii">
          Katalog jest budowany z adresów stron firm, które dodaje administrator. Nie wymyślamy firm — gdy będzie ich więcej, pojawią się tutaj.
        </EmptyState>
      )}
      {search.data?.items.map((m) => (
        <MatchCard
          key={m.catalog_vendor_id}
          match={m}
          actions={
            canWrite &&
            (savedIds.has(m.catalog_vendor_id) ? (
              <StatusChip tone="success">Na liście kandydatów</StatusChip>
            ) : (
              <Button variant="secondary" pending={save.isPending} onPress={() => save.mutate({ catalog_vendor_id: m.catalog_vendor_id })}>
                Zapisz na liście
              </Button>
            ))
          }
        />
      ))}

      <Card>
        <h2>Dodatkowy research</h2>
        <p className="text-secondary">
          Poprosimy badacza o odświeżenie znanych stron firm z tej kategorii. Badacz nie przeszukuje całego internetu — aktualizuje
          tylko strony, które dodał administrator. Do badacza trafia wyłącznie kategoria i region (bez budżetu i danych osobowych).
        </p>
        {latest && (
          <Notice tone={latest.state === "done" ? "success" : "info"} live>
            {latest.state === "done"
              ? String((latest.result as { message?: string }).message ?? "Gotowe.")
              : "Badacz pracuje nad zleceniem…"}{" "}
            <span className="text-secondary">({formatDay(latest.created_at)})</span>
          </Notice>
        )}
        {canWrite && (
          <Button variant="secondary" pending={research.isPending} onPress={() => research.mutate()}>
            Poproś o odświeżenie źródeł
          </Button>
        )}
        {research.isError && <Notice tone="error" live>{userMessage(research.error)}</Notice>}
      </Card>
    </div>
  );
}
