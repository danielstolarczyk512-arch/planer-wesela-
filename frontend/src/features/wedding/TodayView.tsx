import { ChevronRight, Clock, HeartHandshake, ListChecks, PartyPopper, Users, Wallet, type LucideIcon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button as AriaButton } from "react-aria-components";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Card, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { daysUntil, formatDate, formatMoney, plural, todayInWarsaw } from "../../lib/format";
import { EditTaskSheet } from "./EditTaskSheet";
import { percent, useIndexation } from "./indexationRates";
import { CatchUpNotice } from "./PlanAssist";
import { isOpen, TaskRow, topLevel, useToggleTask } from "./tasks";
import { AttentionCard } from "./AttentionCard";
import { useVendors } from "./vendors";
import {
  keys,
  useCanWrite,
  useMembers,
  usePayments,
  useSummary,
  useTasks,
  useWedding,
  useWeddingId,
  type Payment,
  type Summary,
  type Task,
} from "./data";

const KIND: Record<string, string> = {
  deposit_zadatek: "zadatek",
  advance_zaliczka: "zaliczka",
  installment: "rata",
  final: "dopłata",
  other: "płatność",
};

const MONTH = new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });

/** Wygląd odliczania (B3) — wybór zapamiętany na urządzeniu. */
export type CountdownStyle = "days" | "weeks" | "months";
const STYLES: CountdownStyle[] = ["days", "weeks", "months"];
const STYLE_KEY = "wp.countdown";
const SWITCH_LABEL: Record<CountdownStyle, string> = {
  days: "Pokaż w dniach",
  weeks: "Pokaż w tygodniach",
  months: "Pokaż w miesiącach",
};

function savedStyle(): CountdownStyle {
  try {
    const v = localStorage.getItem(STYLE_KEY);
    if (v === "weeks" || v === "months") return v;
  } catch {
    // tryb prywatny: domyślnie dni
  }
  return "days";
}

const DAYS_TAIL = { one: "# dzień", few: "# dni", many: "# dni", other: "# dnia" };

/** Pełne miesiące kalendarzowe i pozostałe dni od dziś (czas polski) do daty ślubu. */
export function monthsAndDays(weddingDate: string, now: Date = new Date()): { months: number; days: number } {
  const [ty, tm, td] = todayInWarsaw(now).split("-").map(Number) as [number, number, number];
  const [wy, wm, wd] = weddingDate.split("-").map(Number) as [number, number, number];
  let months = (wy - ty) * 12 + (wm - tm);
  if (wd < td) months -= 1;
  months = Math.max(0, months);
  // Ten sam dzień miesiąca po `months` miesiącach (31 stycznia + 1 → ostatni dzień lutego).
  const last = new Date(Date.UTC(ty, tm - 1 + months + 1, 0)).getUTCDate();
  const anchor = Date.UTC(ty, tm - 1 + months, Math.min(td, last));
  const days = Math.round((Date.UTC(wy, wm - 1, wd) - anchor) / 86_400_000);
  return { months, days };
}

/** Odliczanie wg GUI-SPEC v1.1, sekcja 2.4 (+ wygląd w tygodniach lub miesiącach). */
export function countdown(
  w: Summary["wedding"],
  style: CountdownStyle = "days",
  now: Date = new Date(),
): { value: string; caption: string; overline: string } {
  if (w.wedding_date && w.days_to_wedding !== null) {
    const d = w.days_to_wedding;
    const overline = formatDate(w.wedding_date);
    if (d === 0) return { value: "Dziś", caption: "Wasz dzień", overline };
    if (d < 0) return { value: "Po", caption: "ślubie — gratulujemy!", overline };
    if (style === "weeks" && d >= 7) {
      const weeks = Math.floor(d / 7);
      const rest = d % 7;
      const unit = plural(weeks, { one: "tydzień", few: "tygodnie", many: "tygodni", other: "tygodnia" });
      return { value: String(weeks), caption: rest ? `${unit} i ${plural(rest, DAYS_TAIL)} do ślubu` : `${unit} do ślubu`, overline };
    }
    if (style === "months") {
      const { months, days } = monthsAndDays(w.wedding_date, now);
      if (months > 0) {
        const unit = plural(months, { one: "miesiąc", few: "miesiące", many: "miesięcy", other: "miesiąca" });
        return { value: String(months), caption: days ? `${unit} i ${plural(days, DAYS_TAIL)} do ślubu` : `${unit} do ślubu`, overline };
      }
    }
    return {
      value: String(d),
      caption: plural(d, { one: "dzień do ślubu", few: "dni do ślubu", many: "dni do ślubu", other: "dnia do ślubu" }),
      overline,
    };
  }
  if (w.planned_month) {
    const [y, m] = w.planned_month.split("-").map(Number);
    const month = MONTH.format(new Date(Date.UTC(y ?? 2000, (m ?? 1) - 1, 15)));
    const months = w.days_to_wedding !== null ? Math.max(0, Math.round(w.days_to_wedding / 30.44)) : null;
    return {
      value: months !== null ? `ok. ${months}` : "—",
      caption: months !== null ? plural(months, { one: "miesiąc do ślubu", few: "miesiące do ślubu", many: "miesięcy do ślubu", other: "miesiąca do ślubu" }) : "",
      overline: month,
    };
  }
  return { value: "—", caption: "Ustalcie datę lub miesiąc ślubu", overline: "Data do ustalenia" };
}

/** Najbliższa płatność do zrobienia: najpierw zaległe, potem wg terminu. */
export function nextPayment(payments: Payment[] | undefined): Payment | null {
  const open = (payments ?? []).filter((p) => p.status === "scheduled");
  open.sort((a, b) => Number(b.is_overdue) - Number(a.is_overdue) || (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999"));
  return open[0] ?? null;
}

/** Powitanie zależne od pory dnia (czas polski). */
export function greeting(now: Date = new Date()): string {
  const hour = Number(new Intl.DateTimeFormat("pl-PL", { hour: "numeric", hourCycle: "h23", timeZone: "Europe/Warsaw" }).format(now));
  return hour >= 5 && hour < 18 ? "Dzień dobry" : "Dobry wieczór";
}

/** Udział 0…1 (ułamek pierścienia); brak mianownika = brak danych. */
export function share(part: number, whole: number): number | null {
  if (!(whole > 0)) return null;
  return Math.min(1, Math.max(0, part / whole));
}

/** Pierścień postępu: dekoracja obok liczb (liczby są w tekście karty). */
function Ring({ value }: { value: number | null }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <span className="ring" aria-hidden="true">
      <svg viewBox="0 0 64 64" width="64" height="64">
        <circle className="ring__track" cx="32" cy="32" r={r} />
        {value !== null && value > 0 && (
          <circle className="ring__value" cx="32" cy="32" r={r} strokeDasharray={`${c * value} ${c}`} transform="rotate(-90 32 32)" />
        )}
      </svg>
      <span className="ring__label num">{value === null ? "—" : `${Math.round(value * 100)}%`}</span>
    </span>
  );
}

function StatCard({
  icon: Icon,
  title,
  tone,
  value,
  children,
  to,
  linkLabel,
}: {
  icon: LucideIcon;
  title: string;
  tone: string;
  value: number | null;
  children: React.ReactNode;
  to: string;
  linkLabel: string;
}) {
  return (
    <Card className={`today-stat today-stat--${tone}`}>
      <h2 className="today-stat__title">
        <span className="today-stat__icon" aria-hidden="true">
          <Icon size={18} strokeWidth={1.75} />
        </span>
        {title}
      </h2>
      <div className="today-stat__body">
        <Ring value={value} />
        <div className="today-stat__numbers">{children}</div>
      </div>
      <Link to={to} viewTransition className="today-stat__link">
        {linkLabel}
        <ChevronRight aria-hidden size={16} />
      </Link>
    </Card>
  );
}

export function TodayView() {
  const id = useWeddingId();
  const wedding = useWedding(id);
  const summary = useSummary(id);
  const tasks = useTasks(id);
  const members = useMembers(id);
  const payments = usePayments(id);
  const vendors = useVendors(id);
  const canWrite = useCanWrite(id);
  const { toggle, error } = useToggleTask(id);
  const [editing, setEditing] = useState<Task | null>(null);
  const [style, setStyle] = useState<CountdownStyle>(savedStyle);

  if (summary.isPending) {
    return (
      <main className="page">
        <Skeleton lines={6} />
      </main>
    );
  }
  if (summary.isError) {
    return (
      <main className="page">
        <Notice tone="error" title="Nie udało się wczytać pulpitu." live>
          <p>{userMessage(summary.error)}</p>
          <Button variant="text" onPress={() => void summary.refetch()}>
            Spróbuj ponownie
          </Button>
        </Notice>
      </main>
    );
  }

  const s = summary.data;
  const c = countdown(s.wedding, style);
  // Przełącznik wyglądu ma sens tylko przy znanej dacie i co najmniej tygodniu do ślubu.
  const canSwitch = Boolean(s.wedding.wedding_date) && (s.wedding.days_to_wedding ?? 0) >= 7;
  const nextStyle = STYLES[(STYLES.indexOf(style) + 1) % STYLES.length] ?? "days";
  const switchStyle = () => {
    setStyle(nextStyle);
    try {
      if (nextStyle === "days") localStorage.removeItem(STYLE_KEY);
      else localStorage.setItem(STYLE_KEY, nextStyle);
    } catch {
      // brak zapisu w trybie prywatnym: wybór działa do zamknięcia karty
    }
  };
  // Najbliższe 3 otwarte zadania (wg terminu; zadania bez terminu na końcu).
  const next = topLevel(tasks.data ?? []).filter(isOpen).slice(0, 3);
  const pay = nextPayment(payments.data);
  const openCount = s.tasks.open;

  return (
    <main className="page enter-tab" aria-labelledby="today-h">
      <header className="today-head">
        <p className="overline">{greeting()}</p>
        <h1 id="today-h">{wedding.data?.name}</h1>
        <p className="text-secondary">Wszystko, co ważne, w jednym miejscu.</p>
      </header>

      <section className="hero today-hero" aria-label="Odliczanie do ślubu">
        {/* Zdjęcie tylko w motywie Romantycznym (dekoracja, bez treści). */}
        <picture className="today-hero__photo" aria-hidden="true">
          <source media="(max-width: 767px)" srcSet="/media/zdjecia/stol-z-rozami-800.webp" />
          <img src="/media/zdjecia/stol-z-rozami.webp" alt="" width={1325} height={515} decoding="async" />
        </picture>
        <p className="overline hero__overline">{c.overline}</p>
        <p className="hero__count" aria-live="polite">
          <span className="hero__value num">{c.value}</span>
          <span>{c.caption}</span>
        </p>
        {/* Prawdziwy stan zamiast stałego hasła (spec 2.2). */}
        <p>
          {s.tasks.overdue > 0
            ? plural(s.tasks.overdue, { one: "# zadanie po terminie", few: "# zadania po terminie", many: "# zadań po terminie", other: "# zadania po terminie" })
            : openCount === 0
              ? "Wszystkie zadania zrobione."
              : plural(openCount, { one: "Zostało # zadanie", few: "Zostały # zadania", many: "Zostało # zadań", other: "Zostało # zadania" })}
        </p>
        {canSwitch && (
          <AriaButton className="hero__switch" onPress={switchStyle}>
            {SWITCH_LABEL[nextStyle]}
          </AriaButton>
        )}
      </section>

      {s.wedding.days_to_wedding === 0 && (
        // W dniu ślubu najważniejszy jest program dnia i lista „Co zabrać”.
        <Link to={`/w/${id}/dzien`} viewTransition className="wp-card link-card wedding-day-card">
          <PartyPopper aria-hidden size={24} strokeWidth={1.75} />
          <span className="row__body">
            <strong>Dziś Wasz dzień!</strong>
            <span className="text-secondary">Program dnia na żywo, kursy i lista „Co zabrać”.</span>
          </span>
          <ChevronRight aria-hidden size={20} />
        </Link>
      )}
      <div className="today-stats">
        <StatCard
          icon={ListChecks}
          title="Zadania"
          tone="tasks"
          value={share(s.tasks.done, s.tasks.total)}
          to={`/w/${id}/plan`}
          linkLabel="Zobacz zadania"
        >
          <span className="today-stat__value num">
            {s.tasks.done} z {s.tasks.total}
          </span>
          <span className="text-secondary">{plural(s.tasks.total, { one: "zadania wykonano", few: "zadań wykonano", many: "zadań wykonano", other: "zadania wykonano" })}</span>
        </StatCard>
        <StatCard
          icon={Wallet}
          title="Budżet"
          tone="budget"
          value={share(Number(s.budget.estimated_total.amount), Number(s.budget.total_budget?.amount ?? 0))}
          to={`/w/${id}/budzet`}
          linkLabel="Zobacz budżet"
        >
          <span className="text-secondary">Przewidywany koszt</span>
          <span className="today-stat__value num">{formatMoney(s.budget.estimated_total)}</span>
          {s.budget.total_budget && Number(s.budget.total_budget.amount) > 0 && (
            <span className="text-secondary num">z {formatMoney(s.budget.total_budget)} budżetu</span>
          )}
          {s.budget.over_budget && <StatusChip tone="error">Ponad budżet</StatusChip>}
          <IndexationHint weddingId={id} />
        </StatCard>
        <StatCard
          icon={Users}
          title="Goście"
          tone="guests"
          value={share(s.guests.confirmed, s.guests.invited)}
          to={`/w/${id}/goscie`}
          linkLabel="Zarządzaj gośćmi"
        >
          <span className="text-secondary">Potwierdzeni goście</span>
          <span className="today-stat__value num">
            {s.guests.confirmed} z {s.guests.invited}
          </span>
          <span className="text-secondary">
            {plural(s.guests.invited, { one: "zaproszonej osoby", few: "zaproszonych", many: "zaproszonych", other: "zaproszonych" })}
          </span>
          <ForecastHint weddingId={id} invited={s.guests.invited} />
        </StatCard>
        <VendorsStat weddingId={id} vendors={vendors.data} />
      </div>

      {canWrite && <CatchUpNotice weddingId={id} overdue={s.tasks.overdue} />}

      <AttentionCard weddingId={id} />

      <section aria-labelledby="steps-h" className="form-stack">
        <div className="section-head">
          <h2 id="steps-h">Najbliższe kroki</h2>
          <Link to={`/w/${id}/plan`} viewTransition className="wp-button wp-button--text">
            Cały plan
          </Link>
        </div>
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <Card>
          {tasks.isPending ? (
            <Skeleton lines={3} />
          ) : next.length === 0 ? (
            <p className="text-secondary">Brak otwartych zadań. Nowe dodacie w zakładce Plan.</p>
          ) : (
            <ul className="row-list">
              {next.map((t) => (
                <li key={t.id}>
                  <TaskRow task={t} members={members.data} canWrite={canWrite} onToggle={toggle} onEdit={setEditing} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {pay && (
        // Bez aria-label: nazwą linku jest widoczny tekst (WCAG 2.5.3, sterowanie głosem).
        <Link to={`/w/${id}/budzet#platnosci`} viewTransition className="wp-card link-card">
          <Clock aria-hidden size={24} strokeWidth={1.75} />
          <span className="row__body">
            <span className="text-secondary">
              Najbliższa płatność · {KIND[pay.kind] ?? "płatność"}
              {pay.due_date && ` · ${formatDate(pay.due_date)}`}
            </span>
            <strong className="num">
              {pay.item_name} · {formatMoney(pay.amount)}
            </strong>
          </span>
          {pay.is_overdue ? (
            <StatusChip tone="error">Po terminie</StatusChip>
          ) : (
            pay.due_date && (
              <StatusChip tone="warning">
                {plural(daysUntil(pay.due_date), { one: "jutro", few: "za # dni", many: "za # dni", other: "za # dnia" }).replace("za 0 dni", "dziś")}
              </StatusChip>
            )
          )}
          <ChevronRight aria-hidden size={20} />
        </Link>
      )}
      <EditTaskSheet weddingId={id} task={editing} onClose={() => setEditing(null)} />
    </main>
  );
}

/** Usługodawcy: zarezerwowani spośród branych pod uwagę (bez odrzuconych). */
function VendorsStat({ weddingId, vendors }: { weddingId: string; vendors: { status: string }[] | undefined }) {
  const active = (vendors ?? []).filter((v) => v.status !== "rejected");
  const booked = active.filter((v) => v.status === "booked").length;
  return (
    <StatCard
      icon={HeartHandshake}
      title="Usługodawcy"
      tone="vendors"
      value={vendors ? share(booked, active.length) : null}
      to={`/w/${weddingId}/uslugodawcy`}
      linkLabel="Zobacz usługodawców"
    >
      <span className="today-stat__value num">{vendors ? `${booked} z ${active.length}` : "—"}</span>
      <span className="text-secondary">zarezerwowanych</span>
    </StatCard>
  );
}

/** Koszt z podwyżkami cen z umów (najgorszy wariant); założenia zapisane na weselu, jak w Budżecie. */
function IndexationHint({ weddingId }: { weddingId: string }) {
  const o = useIndexation(weddingId).data;
  if (!o || o.items.length === 0 || Number(o.worst_total.amount) <= Number(o.today_total.amount)) return null;
  return (
    <Link to={`/w/${weddingId}/budzet#podwyzki`} className="text-secondary num">
      z podwyżkami cen do {formatMoney(o.worst_total)} (przy inflacji {percent(String(o.worst_rate))} rocznie, jak w Budżecie)
    </Link>
  );
}

/** Prognoza frekwencji w kafelku gości (link do ekranu Frekwencja). */
function ForecastHint({ weddingId, invited }: { weddingId: string; invited: number }) {
  const forecast = useQuery({
    queryKey: [...keys.forecast(weddingId), "0.85", "0.5"],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/attendance-forecast", { params: { path: { wedding_id: weddingId } }, signal })),
    enabled: invited > 0,
  });
  if (!forecast.data) return null;
  return (
    <Link to={`/w/${weddingId}/frekwencja`} className="text-secondary num">
      prognoza ok. {forecast.data.forecast.expected}
    </Link>
  );
}
