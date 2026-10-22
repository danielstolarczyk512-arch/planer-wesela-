/** Plan wydatków po miesiącach (ile odkładać) i koszt jednego gościa (średni i każda kolejna osoba). */
import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Card, Notice } from "../../components/Surface";
import { formatMoney } from "../../lib/format";
import { keys } from "./data";

type Cashflow = components["schemas"]["Cashflow"];

/** „styczeń 2028” z daty „2028-01-01”. */
export function monthLabel(iso: string): string {
  const [y, m] = iso.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, 15)).toLocaleDateString("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });
}

/** Szerokość paska miesiąca względem najwyższego miesiąca (0–100%). */
export function barWidth(value: number, max: number): number {
  return max > 0 ? Math.round((value / max) * 100) : 0;
}

export function CashflowCard({ weddingId }: { weddingId: string }) {
  const data = useQuery({
    queryKey: [...keys.budget(weddingId), "cashflow"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/budget/cashflow", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const o = data.data;
  if (!o) return null;
  const max = Math.max(0, ...o.months.map((m) => Number(m.total.amount)));
  const hasAny = max > 0 || Number(o.not_scheduled.amount) > 0;
  if (!hasAny) return null;
  return (
    <section id="plan-wydatkow" className="form-stack" aria-labelledby="cashflow-h">
      <h2 id="cashflow-h">Plan wydatków</h2>
      <Card className="form-stack">
        {o.saving_per_month && (
          <p>
            Odkładajcie ok. <strong className="num">{formatMoney(o.saving_per_month)}</strong> miesięcznie przez {o.saving_months} mies. — tyle
            zostało Wam do zapłacenia (<span className="num">{formatMoney(o.couple_need)}</span>)
            {Number(o.pledged_open.amount) > 0 && <> po odjęciu deklaracji sponsorów ({formatMoney(o.pledged_open)})</>}.
          </p>
        )}
        {Number(o.overdue.amount) > 0 && <Notice tone="warning">Po terminie: {formatMoney(o.overdue)} — sprawdźcie płatności.</Notice>}
        <MonthsTable months={o.months} max={max} peak={o.peak_month} />
        {Number(o.not_scheduled.amount) > 0 && (
          <p className="text-secondary">
            Bez zaplanowanych płatności: <span className="num">{formatMoney(o.not_scheduled)}</span> — dopiszcie raty i dopłaty przy wydatkach, żeby
            plan był pełny.
          </p>
        )}
        {Number(o.undated.amount) > 0 && <p className="text-secondary">Płatności bez terminu: {formatMoney(o.undated)}.</p>}
      </Card>
    </section>
  );
}

function MonthsTable({ months, max, peak }: { months: Cashflow["months"]; max: number; peak: string | null | undefined }) {
  const shown = months.filter((m) => Number(m.total.amount) > 0);
  if (shown.length === 0) return null;
  return (
    <table className="cashflow">
      <caption className="visually-hidden">Płatności w kolejnych miesiącach</caption>
      <thead>
        <tr>
          <th scope="col">Miesiąc</th>
          <th scope="col">Wy</th>
          <th scope="col">Sponsorzy</th>
        </tr>
      </thead>
      <tbody>
        {shown.map((m) => (
          <tr key={m.month} className={m.month === peak ? "is-peak" : undefined}>
            <th scope="row">
              {monthLabel(m.month)}
              <span className="cashflow__bar" style={{ width: `${barWidth(Number(m.total.amount), max)}%` }} aria-hidden="true" />
            </th>
            <td className="num">{formatMoney(m.couple)}</td>
            <td className="num">{Number(m.sponsors.amount) > 0 ? formatMoney(m.sponsors) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function GuestCostCard({ weddingId }: { weddingId: string }) {
  const data = useQuery({
    queryKey: [...keys.budget(weddingId), "guest-cost"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/budget/guest-cost", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const o = data.data;
  if (!o || (!o.average && Number(o.per_adult.amount) === 0)) return null;
  return (
    <section className="form-stack" aria-labelledby="guest-cost-h">
      <h2 id="guest-cost-h">Ile kosztuje gość</h2>
      <Card className="form-stack">
        <div className="stat-grid">
          {o.average && (
            <div className="stat">
              <span className="text-secondary">Średnio na osobę</span>
              <span className="stat__value num">{formatMoney(o.average)}</span>
            </div>
          )}
          <div className="stat">
            <span className="text-secondary">Każda kolejna dorosła osoba</span>
            <span className="stat__value num">+{formatMoney(o.per_adult)}</span>
          </div>
          <div className="stat">
            <span className="text-secondary">Każde kolejne dziecko</span>
            <span className="stat__value num">+{formatMoney(o.per_child)}</span>
          </div>
        </div>
        <p className="text-secondary">
          {o.sources.length > 0
            ? `Liczone z cen za osobę: ${o.sources.map((s) => s.name).join(", ")}. Poniżej minimum sali kolejna osoba może nic nie kosztować.`
            : "Dodajcie ceny za osobę (oferta sali, wydatek „za osobę”), żeby policzyć koszt kolejnej osoby."}
        </p>
      </Card>
    </section>
  );
}
