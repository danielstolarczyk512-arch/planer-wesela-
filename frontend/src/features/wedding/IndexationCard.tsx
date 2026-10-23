/** Strażnik waloryzacji: ile może kosztować wesele, jeśli umowy pozwalają podnieść ceny. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Segmented } from "../../components/Segmented";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { formatDate, formatMoney } from "../../lib/format";
import { keys } from "./data";
import { EXPECTED_RATE, WORST_RATE } from "./indexationRates";

type Item = components["schemas"]["IndexationItem"];

export const EXPECTED_RATES = ["0.03", "0.05", "0.07"] as const;
export const WORST_RATES = ["0.08", "0.10", "0.15"] as const;
const percent = (rate: string) => `${Math.round(Number(rate) * 100)}%`;

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

export function IndexationCard({ weddingId }: { weddingId: string }) {
  const [expected, setExpected] = useState<string>(EXPECTED_RATE);
  const [worst, setWorst] = useState<string>(WORST_RATE);
  const data = useQuery({
    queryKey: [...keys.budget(weddingId), "indexation", expected, worst],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/budget/indexation", {
          params: { path: { wedding_id: weddingId }, query: { expected_rate: Number(expected), worst_rate: Number(worst) } },
          signal,
        }),
      ),
    placeholderData: (previous) => previous,
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
        <Segmented
          label="Prognoza: inflacja rocznie"
          value={expected}
          options={EXPECTED_RATES.map((r) => ({ value: r, label: percent(r) }))}
          onChange={setExpected}
        />
        <Segmented
          label="Najgorszy przypadek: inflacja rocznie"
          value={worst}
          options={WORST_RATES.map((r) => ({ value: r, label: percent(r) }))}
          onChange={setWorst}
        />
      </details>
    </section>
  );
}
