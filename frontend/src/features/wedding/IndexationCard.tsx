/** Strażnik waloryzacji: ile może kosztować wesele, jeśli umowy pozwalają podnieść ceny. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Segmented } from "../../components/Segmented";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, formatMoney } from "../../lib/format";
import { keys } from "./data";
import { percent, useIndexation } from "./indexationRates";

type Item = components["schemas"]["IndexationItem"];

export const EXPECTED_RATES = ["0.03", "0.05", "0.07"] as const;
export const WORST_RATES = ["0.08", "0.10", "0.15"] as const;

/** Opcje wyboru stopy; zapisana wartość spoza listy (np. ustawiona inną drogą) też jest widoczna. */
export function rateOptions(rates: readonly string[], saved: number): { value: string; label: string }[] {
  const all = rates.some((r) => Number(r) === saved) ? [...rates] : [...rates, String(saved)].sort((a, b) => Number(a) - Number(b));
  return all.map((r) => ({ value: r, label: percent(r) }));
}

const selected = (rates: readonly string[], saved: number) => rates.find((r) => Number(r) === saved) ?? String(saved);

const KIND: Record<string, string> = {
  cpi: "wg inflacji GUS",
  price_list: "wg cennika z roku wesela",
  cap: "z limitem",
};

/** Opis klauzuli pozycji, np. „z limitem 5%”. */
export function clauseText(i: Pick<Item, "indexation" | "indexation_cap_percent">): string {
  const base = KIND[i.indexation] ?? "cena stała";
  return i.indexation === "cap" && i.indexation_cap_percent != null ? `${base} ${Number(i.indexation_cap_percent)}%` : base;
}

export function IndexationCard({ weddingId, canWrite }: { weddingId: string; canWrite: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [saveError, setSaveError] = useState<string | null>(null);
  const data = useIndexation(weddingId);
  const save = useMutation({
    mutationFn: (body: { expected_rate: number; worst_rate: number }) =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/budget/indexation/assumptions", { params: { path: { wedding_id: weddingId } }, body }),
      ),
    onSuccess: async () => {
      setSaveError(null);
      await queryClient.invalidateQueries({ queryKey: [...keys.budget(weddingId), "indexation"] });
      toast("Zapisano założenia — tak liczą Budżet i Dziś");
    },
    onError: (e) => setSaveError(`Nie zapisano założeń. ${userMessage(e)}`),
  });
  const o = data.data;
  if (data.isError)
    return (
      <Notice tone="error" live>
        {userMessage(data.error)}
      </Notice>
    );
  if (!o) return null;
  if (o.items.length === 0) {
    return (
      <p className="text-secondary">
        Umowa pozwala podnieść cenę (np. wg inflacji)? Zaznaczcie to przy wydatku w polu „Podwyżka ceny w umowie” — pokażemy, ile może
        kosztować wesele w dniu ślubu.
      </p>
    );
  }
  return (
    <section id="podwyzki" className="form-stack" aria-labelledby="indexation-h">
      <h2 id="indexation-h">Podwyżki cen w umowach</h2>
      {o.reviews_soon.map((r) => (
        <Notice key={r.item_id} tone="warning">
          {r.name}: termin aneksu lub potwierdzenia ceny {r.price_review_on ? formatDate(r.price_review_on) : ""}.
        </Notice>
      ))}
      <div className="stat-grid">
        <Card className="stat">
          <span className="text-secondary">Dziś</span>
          <span className="stat__value">{formatMoney(o.today_total)}</span>
        </Card>
        <Card className="stat">
          <span className="text-secondary">Z prognozowaną podwyżką</span>
          <span className="stat__value">{formatMoney(o.expected_total)}</span>
        </Card>
        <Card className="stat">
          <span className="text-secondary">W najgorszym razie</span>
          <span className="stat__value">{formatMoney(o.worst_total)}</span>
        </Card>
      </div>
      <Card>
        <ul className="row-list">
          {o.items.map((i) => (
            <li key={i.item_id} className="row">
              <span className="row__body">
                <span className="row__title">{i.name}</span>
                <span className="text-secondary">
                  {clauseText(i)} · do zapłaty {formatMoney(i.remaining)}
                  {i.years != null ? ` · ${Number(i.years).toLocaleString("pl-PL")} lat do ślubu` : ""}
                </span>
              </span>
              <StatusChip tone={Number(i.worst_increase.amount) > 0 ? "warning" : "neutral"}>
                +{formatMoney(i.expected_increase)} … +{formatMoney(i.worst_increase)}
              </StatusChip>
            </li>
          ))}
        </ul>
      </Card>
      <details className="form-stack">
        <summary>Założenia</summary>
        <p className="text-secondary">
          Podwyżka obejmuje tylko niezapłaconą część. Inflacja to Wasze założenie, nie dane GUS — sprawdźcie aktualny wskaźnik i zapis
          w umowie.{o.approximate ? " Data ślubu przybliżona (planowany miesiąc)." : ""}
        </p>
        {saveError && (
          <Notice tone="error" live>
            {saveError}
          </Notice>
        )}
        {canWrite ? (
          <>
            <Segmented
              label="Prognoza: inflacja rocznie"
              value={selected(EXPECTED_RATES, o.expected_rate)}
              options={rateOptions(EXPECTED_RATES, o.expected_rate)}
              onChange={(v) => save.mutate({ expected_rate: Number(v), worst_rate: o.worst_rate })}
            />
            <Segmented
              label="Najgorszy przypadek: inflacja rocznie"
              value={selected(WORST_RATES, o.worst_rate)}
              options={rateOptions(WORST_RATES, o.worst_rate)}
              onChange={(v) => save.mutate({ expected_rate: o.expected_rate, worst_rate: Number(v) })}
            />
            <p className="text-secondary">Wybór zapisuje się na weselu — widzą go wszyscy organizatorzy.</p>
          </>
        ) : (
          <p className="text-secondary">
            Prognoza: inflacja {percent(String(o.expected_rate))} rocznie, najgorszy przypadek: {percent(String(o.worst_rate))} rocznie.
          </p>
        )}
      </details>
    </section>
  );
}
