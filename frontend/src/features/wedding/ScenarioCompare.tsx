import { ChevronDown } from "lucide-react";
import { Button as AriaButton, Disclosure, DisclosurePanel, Heading } from "react-aria-components";

import type { components } from "../../api/schema";
import { TextField } from "../../components/Field";
import { Card, Notice } from "../../components/Surface";
import { formatDate, formatMoney, plural } from "../../lib/format";

type Money = components["schemas"]["Money-Output"];
type Out = components["schemas"]["ScenariosOut"];
type OfferScenarios = Out["results"][number];
type ScenarioQuote = OfferScenarios["scenarios"][number];

export interface ScenarioDraft {
  adults: string;
  children: string;
  afterParty: string;
}

export const EMPTY_SCENARIO: ScenarioDraft = { adults: "", children: "", afterParty: "" };
export const SCENARIO_LABELS = ["Plan", "Co jeśli"] as const;

const KIND: Record<string, string> = {
  deposit_zadatek: "Zadatek",
  advance_zaliczka: "Zaliczka",
  installment: "Rata",
  final: "Dopłata",
  other: "Płatność",
};

/** Różnica opisana słowami („+3 000 zł w dopłacie”) — nie samym kolorem. */
export function diffText(diff: Money, what = ""): string {
  const value = Number(diff.amount);
  const suffix = what ? ` ${what}` : "";
  if (value === 0) return `bez zmian${suffix}`;
  const abs = formatMoney({ ...diff, amount: diff.amount.replace(/^-/, "") });
  return `${value > 0 ? "+" : "−"}${abs}${suffix}`;
}

function people(s: ScenarioQuote): string {
  const a = plural(s.adults, { one: "# dorosły", few: "# dorosłych", many: "# dorosłych", other: "# dorosłego" });
  return s.children > 0 ? `${a}, ${plural(s.children, { one: "# dziecko", few: "# dzieci", many: "# dzieci", other: "# dziecka" })}` : a;
}

/** Pola jednego scenariusza (puste = liczba z listy gości). */
export function ScenarioFields({
  legend,
  value,
  onChange,
  error,
}: {
  legend: string;
  value: ScenarioDraft;
  onChange: (v: ScenarioDraft) => void;
  error: string | null;
}) {
  return (
    <fieldset className="plain-fieldset form-stack">
      <legend className="wp-field__label">{legend}</legend>
      <div className="stat-grid">
        <TextField label="Dorośli" inputMode="numeric" value={value.adults} onChange={(v) => onChange({ ...value, adults: v })} />
        <TextField label="Dzieci" inputMode="numeric" value={value.children} onChange={(v) => onChange({ ...value, children: v })} />
      </div>
      <TextField
        label="Goście poprawin (opcjonalnie)"
        inputMode="numeric"
        value={value.afterParty}
        onChange={(v) => onChange({ ...value, afterParty: v })}
        error={error}
      />
    </fieldset>
  );
}

/** Wynik: tabela oferta × scenariusz (≥ 768 px) albo karty (telefon), raty w szczegółach. */
export function ScenarioResults({ data }: { data: Out }) {
  const labels = data.results[0]?.scenarios.map((s) => s.label) ?? [];
  const [a, b] = labels;
  return (
    <section aria-labelledby="scenarios-h" className="form-stack" aria-live="polite">
      <h2 id="scenarios-h">
        {a} i {b}
      </h2>
      <div className="scenario-table-wrap">
        <table className="scenario-table">
          <caption className="visually-hidden">Koszt ofert w scenariuszach „{a}” i „{b}”</caption>
          <thead>
            <tr>
              <th scope="col">Oferta</th>
              <th scope="col" className="num">
                {a}
              </th>
              <th scope="col" className="num">
                {b}
              </th>
              <th scope="col" className="num">
                Różnica
              </th>
              <th scope="col" className="num">
                Dopłata ({b})
              </th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((r) => {
              const [sa, sb] = r.scenarios;
              if (!sa || !sb) return null;
              return (
                <tr key={r.offer_id}>
                  <th scope="row">
                    {r.vendor_name}
                    <span className="text-secondary"> · {r.title}</span>
                  </th>
                  <td className="num">{formatMoney(sa.total)}</td>
                  <td className="num">{formatMoney(sb.total)}</td>
                  <td className="num">{diffText(sb.difference_to_first)}</td>
                  <td className="num">
                    {formatMoney(sb.final_payment)}
                    <span className="text-secondary scenario-table__sub">{diffText(sb.final_difference_to_first)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {data.results.map((r) => (
        <Card key={r.offer_id} className="form-stack" aria-label={`${r.vendor_name}: ${r.title}`}>
          <span className="row__body scenario-card__head">
            <strong>{r.vendor_name}</strong>
            <span className="text-secondary">{r.title}</span>
          </span>
          <ul className="row-list scenario-card__rows">
            {r.scenarios.map((s, i) => (
              <li key={s.label} className="row offer-line">
                <span className="row__body">
                  <span className="row__title">{s.label}</span>
                  <span className="text-secondary">{people(s)}</span>
                </span>
                <span className="offer-line__end num">
                  {formatMoney(s.total)}
                  {i > 0 && <span className="text-secondary scenario-table__sub">{diffText(s.difference_to_first)}</span>}
                </span>
              </li>
            ))}
          </ul>
          <ScenarioNotes scenarios={r.scenarios} />
          <Disclosure className="quote__details">
            <Heading level={3} className="household__heading">
              <AriaButton slot="trigger" className="household__trigger">
                <span className="row__body">
                  <span>Raty i dopłata</span>
                  <span className="text-secondary">{diffText(r.scenarios[1]?.final_difference_to_first ?? { amount: "0", currency: "PLN" }, "w dopłacie")}</span>
                </span>
                <ChevronDown aria-hidden size={20} className="household__chevron" />
              </AriaButton>
            </Heading>
            <DisclosurePanel>
              <div className="form-stack">
                {r.scenarios.map((s) => (
                  <div key={s.label} className="form-stack">
                    <h4 className="scenario-plan__h">{s.label}</h4>
                    <ul className="row-list">
                      {s.payments.map((p, i) => (
                        <li key={`${p.kind}-${i}`} className="row offer-line">
                          <span className="row__body">
                            <span className="row__title">
                              {KIND[p.kind] ?? p.kind}
                              {p.computed && " (wyliczona)"}
                            </span>
                            <span className="text-secondary">{p.due_date ? formatDate(p.due_date) : "termin wg umowy"}</span>
                          </span>
                          <span className="offer-line__end num">{formatMoney(p.amount)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </DisclosurePanel>
          </Disclosure>
        </Card>
      ))}
      <p className="text-secondary">{data.disclaimer}</p>
    </section>
  );
}

function ScenarioNotes({ scenarios }: { scenarios: ScenarioQuote[] }) {
  const notes = [...new Set(scenarios.flatMap((s) => [...s.warnings, ...s.unknown.map((u) => `Brak ceny: ${u}`)]))];
  if (notes.length === 0) return null;
  return (
    <Notice tone="warning">
      <ul className="conflict-list">
        {notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </Notice>
  );
}
