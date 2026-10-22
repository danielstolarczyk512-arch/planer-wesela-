/**
 * Wydruki: czyste strony A4 bez nawigacji (przeglądarka: „Drukuj” → „Zapisz jako PDF”).
 * Bez bibliotek PDF — arkusz stylów druku w print.css.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Field";
import { PremiumBadge } from "../../components/Premium";
import { Card, Notice, Skeleton } from "../../components/Surface";
import { formatDate, formatTime, formatMoney } from "../../lib/format";
import { accentStyle } from "../rsvp/themes";
import { AGE_GROUPS, DIETS, fullName, svgDataUri } from "./EditGuestSheet";
import { useGuestInfo } from "./GuestInfoSheet";
import { defaultPositions, ITEM_LABEL, tableSize } from "./RoomLayout";
import { isOpen, monthLabel, subtasksOf, topLevel } from "./tasks";
import {
  useBudgetCategories,
  useBudgetItems,
  useEvents,
  useHouseholds,
  usePayments,
  useSeatingPlan,
  useSummary,
  useTasks,
  useWedding,
  useWeddingId,
  type Guest,
  type Household,
} from "./data";
import { useVendors } from "./vendors";
import "./print.css";

const KINDS = {
  stoly: "Plan stołów dla sali",
  winietki: "Winietki",
  sala: "Plan sali",
  goscie: "Lista gości",
  budzet: "Budżet",
  zadania: "Lista zadań",
  qr: "Karty z kodem QR",
  objazd: "Objazd z zaproszeniami",
  kursy: "Listy pasażerów",
  zyczenia: "Księga życzeń",
  podsumowanie: "Jak idą przygotowania",
} as const;
type Kind = keyof typeof KINDS;

const DIET = Object.fromEntries(DIETS.map((d) => [d.id, d.label]));
const AGE = Object.fromEntries(AGE_GROUPS.map((a) => [a.id, a.label]));

export function PrintView() {
  const id = useWeddingId();
  const { kind = "" } = useParams();
  const navigate = useNavigate();
  const wedding = useWedding(id);
  if (!(kind in KINDS)) {
    return (
      <main className="page">
        <Notice tone="error">Nie ma takiego wydruku.</Notice>
      </main>
    );
  }
  const k = kind as Kind;
  const w = wedding.data;
  return (
    <main className="page print-page" aria-labelledby="print-h">
      <div className="print-toolbar no-print">
        <Button variant="text" onPress={() => navigate(-1)}>
          ← Wróć
        </Button>
        <Button icon={<Printer aria-hidden size={20} />} onPress={() => window.print()}>
          Drukuj lub zapisz PDF
        </Button>
        <p className="text-secondary">W oknie drukowania wybierzcie drukarkę albo „Zapisz jako PDF”.</p>
      </div>
      <header className="print-head">
        <p className="overline">{w?.name}</p>
        <h1 id="print-h">{KINDS[k]}</h1>
        {w?.wedding_date && <p className="text-secondary">{formatDate(w.wedding_date)}</p>}
      </header>
      {k === "stoly" && <TablesPrint weddingId={id} />}
      {k === "winietki" && <PlaceCards weddingId={id} />}
      {k === "sala" && <RoomPrint weddingId={id} />}
      {k === "goscie" && <GuestsPrint weddingId={id} />}
      {k === "budzet" && <BudgetPrint weddingId={id} />}
      {k === "zadania" && <TasksPrint weddingId={id} />}
      {k === "qr" && <QrPrint weddingId={id} weddingName={w?.name ?? ""} />}
      {k === "objazd" && <DeliveryPrint weddingId={id} />}
      {k === "kursy" && <RunsPrint weddingId={id} />}
      {k === "zyczenia" && <WishesPrint weddingId={id} />}
      {k === "podsumowanie" && <SummaryPrint weddingId={id} />}
    </main>
  );
}

function Loading({ pending, error }: { pending: boolean; error: unknown }) {
  if (pending) return <Skeleton lines={6} />;
  if (error)
    return (
      <Notice tone="error" live>
        {userMessage(error)}
      </Notice>
    );
  return null;
}

function guestIndex(households: Household[] | undefined): Map<string, Guest> {
  const map = new Map<string, Guest>();
  for (const h of households ?? []) for (const g of h.guests) map.set(g.id, g);
  return map;
}

function dietText(g: Guest | undefined): string {
  if (!g || g.dietary_preference === "standard") return "";
  return g.dietary_note ? `${DIET[g.dietary_preference]}: ${g.dietary_note}` : (DIET[g.dietary_preference] ?? "");
}

/** Plan stołów dla sali: kto przy którym stole, diety, dzieci i posiłki dla obsługi. */
function TablesPrint({ weddingId }: { weddingId: string }) {
  const plan = useSeatingPlan(weddingId);
  const households = useHouseholds(weddingId);
  const vendors = useVendors(weddingId);
  if (!plan.data || !households.data) return <Loading pending={plan.isPending || households.isPending} error={plan.error ?? households.error} />;
  const guests = guestIndex(households.data);
  const seated = plan.data.tables.flatMap((t) => t.guests.map((s) => guests.get(s.guest_id)));
  const count = (pred: (g: Guest) => boolean) => seated.filter((g): g is Guest => !!g && pred(g)).length;
  const diets = DIETS.filter((d) => d.id !== "standard").map((d) => ({ label: d.label, n: count((g) => g.dietary_preference === d.id) }));
  const crew = (vendors.data ?? []).filter((v) => v.status !== "rejected").reduce((sum, v) => sum + (v.crew_meals ?? 0), 0);
  return (
    <>
      <Notice tone="info">Wydruk zawiera informacje o dietach i alergiach — przekażcie go tylko obsłudze sali.</Notice>
      <table className="print-table print-summary">
        <tbody>
          <tr>
            <th scope="row">Dorośli i nastolatki</th>
            <td>{count((g) => g.age_group === "adult" || g.age_group === "teen")}</td>
          </tr>
          <tr>
            <th scope="row">Dzieci (4–12)</th>
            <td>{count((g) => g.age_group === "child")}</td>
          </tr>
          <tr>
            <th scope="row">Maluchy (0–3)</th>
            <td>{count((g) => g.age_group === "infant")}</td>
          </tr>
          {diets
            .filter((d) => d.n > 0)
            .map((d) => (
              <tr key={d.label}>
                <th scope="row">Dieta: {d.label.toLowerCase()}</th>
                <td>{d.n}</td>
              </tr>
            ))}
          {crew > 0 && (
            <tr>
              <th scope="row">Posiłki dla obsługi (muzycy, fotograf)</th>
              <td>{crew}</td>
            </tr>
          )}
        </tbody>
      </table>
      {plan.data.tables.map((t) => (
        <section key={t.id} className="print-block">
          <h2>
            {t.name} <span className="text-secondary">· {t.guests.length} os.</span>
          </h2>
          <table className="print-table">
            <thead>
              <tr>
                <th scope="col">Miejsce</th>
                <th scope="col">Gość</th>
                <th scope="col">Dieta / uwagi</th>
              </tr>
            </thead>
            <tbody>
              {[...t.guests]
                .sort((a, b) => (a.seat_number ?? 999) - (b.seat_number ?? 999))
                .map((s) => {
                  const g = guests.get(s.guest_id);
                  return (
                    <tr key={s.guest_id}>
                      <td>{s.seat_number ?? ""}</td>
                      <td>
                        {s.name}
                        {s.age_group !== "adult" && s.age_group !== "teen" && ` (${AGE[s.age_group]?.toLowerCase()})`}
                      </td>
                      <td>{dietText(g)}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </section>
      ))}
      {plan.data.unassigned.length > 0 && (
        <p className="no-print text-secondary">Bez miejsca: {plan.data.unassigned.length} os. — nie ma ich na wydruku.</p>
      )}
    </>
  );
}

/** Winietki do wycięcia: imię i nazwisko oraz stół. */
/** Kolor przewodni wesela (akcent ze strony dla gości) na winietkach i kartach QR. */
function useAccent(weddingId: string) {
  const accent = useGuestInfo(weddingId).data?.accent;
  return accent ? { className: " print-accented", style: accentStyle(accent) } : { className: "", style: undefined };
}

function PlaceCards({ weddingId }: { weddingId: string }) {
  const plan = useSeatingPlan(weddingId);
  const accent = useAccent(weddingId);
  if (!plan.data) return <Loading pending={plan.isPending} error={plan.error} />;
  const cards = plan.data.tables.flatMap((t) => t.guests.map((g) => ({ ...g, table: t.name })));
  if (cards.length === 0) return <Notice tone="info">Najpierw posadźcie gości przy stołach.</Notice>;
  return (
    <div className={`place-cards${accent.className}`} style={accent.style}>
      {cards.map((c) => (
        <div key={c.guest_id} className="place-card">
          <span className="place-card__name">{c.name}</span>
          <span className="place-card__table">
            {c.table}
            {c.seat_number != null ? `, miejsce ${c.seat_number}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

const ATTENDANCE: Record<string, string> = { attending: "Będzie", declined: "Nie będzie", maybe: "Nie wie", pending: "Brak odpowiedzi" };

function GuestsPrint({ weddingId }: { weddingId: string }) {
  const households = useHouseholds(weddingId);
  const events = useEvents(weddingId);
  if (!households.data) return <Loading pending={households.isPending} error={households.error} />;
  const reception = events.data?.find((e) => e.kind === "reception");
  return (
    <table className="print-table">
      <thead>
        <tr>
          <th scope="col">Zaproszenie</th>
          <th scope="col">Gość</th>
          <th scope="col">Przyjęcie</th>
          <th scope="col">Dieta</th>
          <th scope="col">Nocleg / transport</th>
        </tr>
      </thead>
      <tbody>
        {households.data.flatMap((h) =>
          h.guests.map((g, i) => (
            <tr key={g.id}>
              <td>{i === 0 ? h.name : ""}</td>
              <td>{fullName(g)}</td>
              <td>{reception ? ATTENDANCE[g.attendance[reception.id] ?? "pending"] : ""}</td>
              <td>{dietText(g)}</td>
              <td>{[g.needs_accommodation && "nocleg", g.needs_transport && "transport"].filter(Boolean).join(", ")}</td>
            </tr>
          )),
        )}
      </tbody>
    </table>
  );
}

function BudgetPrint({ weddingId }: { weddingId: string }) {
  const categories = useBudgetCategories(weddingId);
  const items = useBudgetItems(weddingId);
  const payments = usePayments(weddingId);
  if (!categories.data || !items.data) return <Loading pending={categories.isPending || items.isPending} error={categories.error ?? items.error} />;
  const upcoming = (payments.data ?? []).filter((p) => p.status === "scheduled");
  return (
    <>
      {categories.data.map((c) => {
        const own = items.data.filter((i) => i.category_id === c.id);
        if (own.length === 0) return null;
        return (
          <section key={c.id} className="print-block">
            <h2>{c.name}</h2>
            <table className="print-table">
              <thead>
                <tr>
                  <th scope="col" className="print-col-main">
                    Wydatek
                  </th>
                  <th scope="col" className="num">
                    Kwota
                  </th>
                  <th scope="col" className="num">
                    Wpłacono
                  </th>
                </tr>
              </thead>
              <tbody>
                {own.map((i) => (
                  <tr key={i.id}>
                    <td>{i.name}</td>
                    <td className="num">{i.estimated ? formatMoney(i.estimated) : "—"}</td>
                    <td className="num">{formatMoney(i.paid)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        );
      })}
      {upcoming.length > 0 && (
        <section className="print-block">
          <h2>Płatności do zrobienia</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th scope="col">Termin</th>
                <th scope="col" className="print-col-main">
                  Za co
                </th>
                <th scope="col" className="num">
                  Kwota
                </th>
              </tr>
            </thead>
            <tbody>
              {upcoming.map((p) => (
                <tr key={p.id}>
                  <td>{p.due_date ? formatDate(p.due_date) : "bez terminu"}</td>
                  <td>{p.item_name}</td>
                  <td className="num">{formatMoney(p.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}

function TasksPrint({ weddingId }: { weddingId: string }) {
  const tasks = useTasks(weddingId);
  if (!tasks.data) return <Loading pending={tasks.isPending} error={tasks.error} />;
  const open = topLevel(tasks.data).filter(isOpen);
  const groups = new Map<string, typeof open>();
  for (const t of open) groups.set(monthLabel(t.due_date), [...(groups.get(monthLabel(t.due_date)) ?? []), t]);
  return (
    <>
      {[...groups.entries()].map(([label, list]) => (
        <section key={label} className="print-block">
          <h2>{label}</h2>
          <ul className="print-checklist">
            {list.map((t) => (
              <li key={t.id}>
                <span aria-hidden="true">☐</span> {t.title}
                {subtasksOf(tasks.data, t.id).filter(isOpen).length > 0 && (
                  <ul className="print-checklist">
                    {subtasksOf(tasks.data, t.id)
                      .filter(isOpen)
                      .map((s) => (
                        <li key={s.id}>
                          <span aria-hidden="true">☐</span> {s.title}
                        </li>
                      ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

type QrCard = components["schemas"]["RsvpQrCard"];

/**
 * Karty z kodem QR (4 na A4). Token znamy tylko przy tworzeniu linku, więc karty powstają razem
 * z nowymi linkami: z arkusza zaproszenia (jedna karta) albo hurtowo dla wybranych rodzin.
 */
function QrPrint({ weddingId, weddingName }: { weddingId: string; weddingName: string }) {
  const location = useLocation();
  const given = (location.state as { cards?: QrCard[] } | null)?.cards;
  const [cards, setCards] = useState<QrCard[] | null>(given ?? null);
  const [withLink, setWithLink] = useState(false);
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const accent = useAccent(weddingId);
  const path = { path: { wedding_id: weddingId } };
  const preview = useQuery({
    queryKey: ["wedding", weddingId, "rsvp-qr", withLink],
    queryFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/rsvp-qr", { params: path, body: { dry_run: true, include_with_link: withLink } })),
    enabled: !cards,
  });
  const chosen = (preview.data?.cards ?? []).filter((c) => !skipped.has(c.household_id));
  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/rsvp-qr", {
          params: path,
          body: { dry_run: false, include_with_link: withLink, household_ids: chosen.map((c) => c.household_id) },
        }),
      ),
    onSuccess: (r) => setCards(r.cards),
  });

  if (cards) {
    return (
      <>
        <p className="text-secondary no-print">
          Karty mają nowe linki — {cards.length === 1 ? "poprzedni link tej rodziny" : "poprzednie linki tych rodzin"} przestały działać. Wydrukujcie je teraz: kodów nie da się
          pokazać ponownie.
        </p>
        <div className={`qr-cards${accent.className}`} style={accent.style}>
          {cards.map((c) => (
            <article key={c.household_id} className="qr-card">
              <p className="overline">{weddingName}</p>
              <p className="qr-card__name">{c.name}</p>
              {c.qr_svg && <img className="qr-card__code" src={svgDataUri(c.qr_svg)} alt={`Kod QR dla: ${c.name}`} />}
              <p>
                Zeskanujcie, aby potwierdzić obecność{c.rsvp_deadline ? ` do ${formatDate(c.rsvp_deadline)}` : ""}.
              </p>
              {c.url && <p className="qr-card__url">{c.url}</p>}
            </article>
          ))}
        </div>
      </>
    );
  }

  return (
    <Card className="form-stack no-print">
      <p>
        Kod QR na zaproszeniu prowadzi do formularza potwierdzenia tej rodziny <PremiumBadge />. Dla każdej wybranej rodziny utworzymy nowy link.
      </p>
      <Checkbox isSelected={withLink} onChange={setWithLink}>
        Także rodziny, które mają już link (stary przestanie działać)
      </Checkbox>
      {preview.isPending && <Skeleton lines={4} />}
      {preview.isError && <Notice tone="error">{userMessage(preview.error)}</Notice>}
      {preview.data && (
        <>
          {preview.data.with_link_skipped > 0 && (
            <p className="text-secondary">Pominięte, bo mają aktywny link: {preview.data.with_link_skipped}.</p>
          )}
          {preview.data.cards.length === 0 ? (
            <p className="text-secondary">Brak rodzin do przygotowania kart.</p>
          ) : (
            <fieldset className="plain-fieldset form-stack">
              <legend className="wp-field__label">Rodziny</legend>
              {preview.data.cards.map((c) => (
                <Checkbox
                  key={c.household_id}
                  isSelected={!skipped.has(c.household_id)}
                  onChange={(v) =>
                    setSkipped((s) => {
                      const next = new Set(s);
                      if (v) next.delete(c.household_id);
                      else next.add(c.household_id);
                      return next;
                    })
                  }
                >
                  {c.name}
                  {c.has_active_link ? " (ma link)" : ""}
                </Checkbox>
              ))}
            </fieldset>
          )}
          {create.isError && (
            <Notice tone="error" live>
              {userMessage(create.error)}
            </Notice>
          )}
          <Button isDisabled={chosen.length === 0} pending={create.isPending} onPress={() => create.mutate()}>
            {`Utwórz linki i przygotuj karty (${chosen.length})`}
          </Button>
        </>
      )}
    </Card>
  );
}

/** Plan sali dla obsługi: stoły z nazwami i liczbą osób, elementy stałe, legenda pod spodem. */
function RoomPrint({ weddingId }: { weddingId: string }) {
  const plan = useSeatingPlan(weddingId);
  if (!plan.data) return <Loading pending={plan.isPending} error={plan.error} />;
  const { room, tables } = plan.data;
  const items = room.items ?? [];
  const defaults = defaultPositions(tables, room);
  return (
    <>
      <svg className="room-plan room-plan--print" viewBox={`0 0 ${room.width_m} ${room.length_m}`} role="img" aria-label={`Plan sali ${room.width_m} na ${room.length_m} m`}>
        <rect className="room-plan__floor" x={0} y={0} width={room.width_m} height={room.length_m} />
        {items.map((i, n) => (
          <g key={`${i.kind}-${n}`} className={`room-plan__item room-plan__item--${i.kind}`}>
            <rect x={i.x - i.w / 2} y={i.y - i.h / 2} width={i.w} height={i.h} rx={0.2} />
            <text x={i.x} y={i.y} className="room-plan__label">
              {i.label || ITEM_LABEL[i.kind]}
            </text>
          </g>
        ))}
        {tables.map((t) => {
          const p = t.pos_x != null && t.pos_y != null ? { x: t.pos_x, y: t.pos_y, rotation: t.rotation } : defaults.get(t.id)!;
          const { w, h } = tableSize(t);
          return (
            <g key={t.id} className={`room-plan__table${t.kind === "head" ? " is-head" : ""}`} transform={`translate(${p.x} ${p.y}) rotate(${p.rotation})`}>
              {t.shape === "round" ? <circle r={w / 2} /> : <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={0.1} />}
              <text className="room-plan__label" transform={`rotate(${-p.rotation})`}>
                {t.name}
              </text>
            </g>
          );
        })}
      </svg>
      <table className="print-table print-summary">
        <thead>
          <tr>
            <th scope="col">Stół</th>
            <th scope="col" className="num">
              Osób
            </th>
          </tr>
        </thead>
        <tbody>
          {tables.map((t) => (
            <tr key={t.id}>
              <td>{t.name}</td>
              <td className="num">
                {t.capacity - t.free_seats} / {t.capacity}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

/** Objazd z zaproszeniami na papier: miejscowości, zaproszenia, kto wręcza i rubryka do odhaczenia. */
/** Jedna strona dla rodziców i sponsorów: termin, miejsca, goście, budżet, wkład, najbliższe kroki. */
function SummaryPrint({ weddingId }: { weddingId: string }) {
  const params = { params: { path: { wedding_id: weddingId } } };
  const summary = useSummary(weddingId);
  const events = useEvents(weddingId);
  const funders = useQuery({
    queryKey: ["wedding", weddingId, "funders"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/funders", { ...params, signal })),
  });
  const forecast = useQuery({
    queryKey: ["wedding", weddingId, "attendance-forecast", "0.85", "0.5"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/attendance-forecast", { ...params, signal })),
  });
  if (!summary.data) return <Loading pending={summary.isPending} error={summary.error} />;
  const s = summary.data;
  const f = funders.data;
  const percent = s.tasks.total ? Math.round((s.tasks.done / s.tasks.total) * 100) : 0;
  return (
    <div className="print-summary">
      <section>
        <h2>Termin i miejsca</h2>
        <p>
          {s.wedding.wedding_date ? formatDate(s.wedding.wedding_date) : (s.wedding.planned_month ?? "data do ustalenia")}
          {s.wedding.days_to_wedding != null && s.wedding.days_to_wedding >= 0 && ` — za ${s.wedding.days_to_wedding} dni`}
        </p>
        <ul>
          {(events.data ?? []).map((e) => (
            <li key={e.id}>
              <strong>{e.name}</strong>
              {e.starts_at && `, ${formatTime(e.starts_at)}`}
              {e.address && ` — ${e.address}`}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2>Goście</h2>
        <p>
          Zaproszonych: {s.guests.invited}, potwierdziło: {s.guests.confirmed}, czeka na odpowiedź: {s.guests.pending_answers}
          {forecast.data && s.guests.invited > 0 && `. Prognoza: ok. ${forecast.data.forecast.expected} osób`}.
        </p>
      </section>
      <section>
        <h2>Budżet</h2>
        <p>
          Szacowany koszt: {formatMoney(s.budget.estimated_total)}, zapłacone: {formatMoney(s.budget.paid_total)}, zostało: {formatMoney(s.budget.remaining_to_pay)}
          {s.budget.total_budget && ` (budżet: ${formatMoney(s.budget.total_budget)})`}.
        </p>
        {f && f.funders.length > 0 && (
          <ul>
            {f.funders.map((x) => (
              <li key={x.id}>
                {x.name}: wpłacone {formatMoney(x.covered)}
                {x.pledged_amount && ` z zadeklarowanych ${formatMoney(x.pledged_amount)}`}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2>Przygotowania</h2>
        <p>
          Zrobione {s.tasks.done} z {s.tasks.total} zadań ({percent}%)
          {s.tasks.overdue > 0 && `, po terminie: ${s.tasks.overdue}`}.
        </p>
        {s.tasks.due_next_14_days.length > 0 && (
          <>
            <h3>W najbliższych dwóch tygodniach</h3>
            <ul>
              {s.tasks.due_next_14_days.map((t) => (
                <li key={t.id}>
                  {t.title}
                  {t.due_date && ` — do ${formatDate(t.due_date)}`}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}

function WishesPrint({ weddingId }: { weddingId: string }) {
  const data = useQuery({
    queryKey: ["wedding", weddingId, "wishes"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/wishes", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  if (!data.data) return <Loading pending={data.isPending} error={data.error} />;
  const rows = data.data.filter((w) => !w.hidden);
  if (rows.length === 0) return <p>Brak życzeń do wydruku.</p>;
  return (
    <ul className="print-wishes">
      {rows.map((w) => (
        <li key={w.id}>
          <p className="prewrap">{w.text}</p>
          <p className="text-secondary">— {w.author}</p>
        </li>
      ))}
    </ul>
  );
}

function DeliveryPrint({ weddingId }: { weddingId: string }) {
  const data = useQuery({
    queryKey: ["wedding", weddingId, "households", "delivery"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/invitation-delivery", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  if (!data.data) return <Loading pending={data.isPending} error={data.error} />;
  const groups = data.data.groups.filter((g) => g.remaining > 0);
  if (groups.length === 0) return <p>Wszystkie zaproszenia osobiste są wręczone.</p>;
  return (
    <>
      {groups.map((g) => (
        <section key={g.place ?? "bez"} className="print-group">
          <h2>{g.place ?? "Bez miejscowości"}</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th scope="col">Zaproszenie</th>
                <th scope="col">Osób</th>
                <th scope="col">Kto wręcza</th>
                <th scope="col">Plan</th>
                <th scope="col">Wręczone</th>
              </tr>
            </thead>
            <tbody>
              {g.households
                .filter((h) => h.invitation_status !== "delivered")
                .map((h) => (
                  <tr key={h.id}>
                    <td>{h.name}</td>
                    <td className="num">{h.guests}</td>
                    <td>{h.delivery_by ?? ""}</td>
                    <td>{h.delivery_planned_on ? formatDate(h.delivery_planned_on) : ""}</td>
                    <td aria-label="Do odhaczenia">☐</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      ))}
    </>
  );
}

/** Listy pasażerów kursów (dla pary lub świadka przy autokarze): godzina, trasa, osoby do odhaczenia. */
function RunsPrint({ weddingId }: { weddingId: string }) {
  const data = useQuery({
    queryKey: ["wedding", weddingId, "households", "logistics"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/logistics", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  if (!data.data) return <Loading pending={data.isPending} error={data.error} />;
  if (data.data.runs.length === 0) return <p>Nie ma jeszcze kursów.</p>;
  return (
    <>
      {data.data.runs.map((r) => (
        <section key={r.id} className="print-group">
          <h2>
            {r.departs_at ? `${formatDate(r.departs_at.slice(0, 10))}, ${formatTime(r.departs_at)} · ` : ""}
            {r.name}
          </h2>
          <p>
            {[r.from_place, r.to_place].filter(Boolean).join(" → ")}
            {` · ${r.taken}/${r.capacity} miejsc`}
          </p>
          {r.passengers.length === 0 ? (
            <p>Brak pasażerów.</p>
          ) : (
            <table className="print-table">
              <thead>
                <tr>
                  <th scope="col">Osoba</th>
                  <th scope="col">Wsiadł(a)</th>
                </tr>
              </thead>
              <tbody>
                {r.passengers.map((p) => (
                  <tr key={p.guest_id}>
                    <td>{p.name}</td>
                    <td aria-label="Do odhaczenia">☐</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ))}
    </>
  );
}
