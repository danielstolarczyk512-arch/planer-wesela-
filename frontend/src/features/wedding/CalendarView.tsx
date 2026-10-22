/** Kalendarz: zadania, płatności i wydarzenia miesiąca w jednym miejscu + kalendarz w telefonie (ICS). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CalendarHeart, ChevronLeft, ChevronRight, Copy, ListChecks, PartyPopper, Wallet } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton } from "react-aria-components";
import { Link, useSearchParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { PremiumBadge } from "../../components/Premium";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { todayInWarsaw } from "../../lib/format";
import { EditTaskSheet } from "./EditTaskSheet";
import { PLAN_SECTIONS, SectionNav } from "./SectionNav";
import { keys, useTasks, useWeddingId, type Task } from "./data";

type Entry = components["schemas"]["CalendarEntry"];

const MONTH = new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });
const DAY = new Intl.DateTimeFormat("pl-PL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });

const pad = (n: number) => String(n).padStart(2, "0");

/** "2026-11" → zakres dat miesiąca i sąsiednie miesiące. */
export function monthRange(month: string): { start: string; end: string; prev: string; next: string } {
  const [y = 2026, m = 1] = month.split("-").map(Number);
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const prev = m === 1 ? `${y - 1}-12` : `${y}-${pad(m - 1)}`;
  const next = m === 12 ? `${y + 1}-01` : `${y}-${pad(m + 1)}`;
  return { start: `${month}-01`, end: `${month}-${pad(last)}`, prev, next };
}

const utc = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1, 12));
};
const capitalize = (s: string) => s.charAt(0).toLocaleUpperCase("pl-PL") + s.slice(1);

const ICON = { task: ListChecks, payment: Wallet, event: CalendarHeart, wedding: PartyPopper, reminder: Bell } as const;
const KIND_LABEL = { task: "Zadanie", payment: "Płatność", event: "Wydarzenie", wedding: "Ślub", reminder: "Przypomnienie" } as const;

export function CalendarView() {
  const id = useWeddingId();
  const [params, setParams] = useSearchParams();
  const month = /^\d{4}-\d{2}$/.test(params.get("miesiac") ?? "") ? (params.get("miesiac") as string) : todayInWarsaw().slice(0, 7);
  const range = monthRange(month);
  const tasks = useTasks(id);
  const [editing, setEditing] = useState<Task | null>(null);
  const calendar = useQuery({
    queryKey: [...keys.tasks(id), "calendar", month],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/weddings/{wedding_id}/calendar", {
          params: { path: { wedding_id: id }, query: { start: range.start, end: range.end } },
          signal,
        }),
      ),
  });

  const days = new Map<string, Entry[]>();
  for (const e of calendar.data ?? []) days.set(e.date, [...(days.get(e.date) ?? []), e]);
  const go = (m: string) => setParams({ miesiac: m }, { replace: true });

  return (
    <main className="page enter-tab" aria-labelledby="calendar-h">
      <SectionNav label="Plan" sections={PLAN_SECTIONS} />
      <div>
        <h1 id="calendar-h">Kalendarz</h1>
        <p className="text-secondary">Zadania, płatności, wydarzenia i przypomnienia — dzień po dniu.</p>
      </div>

      <div className="month-nav">
        <AriaButton className="wp-icon-button" aria-label={`Poprzedni miesiąc: ${MONTH.format(utc(`${range.prev}-01`))}`} onPress={() => go(range.prev)}>
          <ChevronLeft aria-hidden size={22} />
        </AriaButton>
        <h2 aria-live="polite">{capitalize(MONTH.format(utc(range.start)))}</h2>
        <AriaButton className="wp-icon-button" aria-label={`Następny miesiąc: ${MONTH.format(utc(`${range.next}-01`))}`} onPress={() => go(range.next)}>
          <ChevronRight aria-hidden size={22} />
        </AriaButton>
      </div>

      {calendar.isPending && <Skeleton lines={5} />}
      {calendar.isError && (
        <Notice tone="error" live>
          {userMessage(calendar.error)}
        </Notice>
      )}
      {calendar.data && days.size === 0 && <EmptyState title="W tym miesiącu nic nie zaplanowano">Przejdźcie do kolejnego miesiąca strzałką.</EmptyState>}
      {[...days.entries()].map(([day, entries]) => (
        <section key={day} className="form-stack" aria-label={DAY.format(utc(day))}>
          <h3 className={day === todayInWarsaw() ? "calendar-day calendar-day--today" : "calendar-day"}>
            {capitalize(DAY.format(utc(day)))}
            {day === todayInWarsaw() && " · dziś"}
          </h3>
          <Card>
            <ul className="row-list">
              {entries.map((e) => {
                const Icon = ICON[e.kind];
                const task = e.kind === "task" ? tasks.data?.find((t) => t.id === e.ref_id) : undefined;
                const body = (
                  <>
                    <Icon aria-hidden size={20} strokeWidth={1.75} />
                    <span className="row__body">
                      <span className={`row__title${e.done ? " done-title" : ""}`}>
                        {e.time && <span className="num">{e.time} </span>}
                        {e.title}
                      </span>
                      <span className="text-secondary">{KIND_LABEL[e.kind]}</span>
                    </span>
                    {e.overdue && <StatusChip tone="warning">Po terminie</StatusChip>}
                    {e.done && <StatusChip tone="success">{e.kind === "payment" ? "Zapłacone" : "Zrobione"}</StatusChip>}
                  </>
                );
                return (
                  <li key={`${e.kind}-${e.ref_id}`}>
                    {task ? (
                      <AriaButton className="row row-edit calendar-entry" onPress={() => setEditing(task)}>
                        {body}
                      </AriaButton>
                    ) : e.kind === "payment" ? (
                      <Link to={`/w/${id}/budzet#platnosci`} className="row link-card">
                        {body}
                      </Link>
                    ) : e.kind === "reminder" && e.link ? (
                      <Link to={`/w/${id}/${e.link}`} className="row link-card">
                        {body}
                      </Link>
                    ) : (
                      <div className="row">{body}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        </section>
      ))}

      <CalendarFeed weddingId={id} />
      <EditTaskSheet weddingId={id} task={editing} onClose={() => setEditing(null)} />
    </main>
  );
}

/** Prywatny adres kalendarza do subskrypcji w Google, Apple lub Outlooku. */
function CalendarFeed({ weddingId }: { weddingId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [token, setToken] = useState<string | null>(null);
  const path = { path: { wedding_id: weddingId } };
  const statusKey = ["wedding", weddingId, "calendar-feed"];
  const status = useQuery({
    queryKey: statusKey,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/calendar-feed", { params: path, signal })),
  });
  const create = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/calendar-feed", { params: path })),
    onSuccess: (r) => {
      setToken(r.token);
      queryClient.setQueryData(statusKey, { active: true, created_at: new Date().toISOString(), last_used_at: null });
    },
  });
  const revoke = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/calendar-feed", { params: path })),
    onSuccess: () => {
      setToken(null);
      queryClient.setQueryData(statusKey, { active: false, created_at: null, last_used_at: null });
      toast("Adres kalendarza wyłączony");
    },
  });
  const url = token ? `${window.location.origin}/api/v1/calendar/${token}.ics` : null;
  const active = status.data?.active;

  return (
    <section className="form-stack" aria-labelledby="feed-h">
      <h2 id="feed-h">
        Kalendarz w telefonie <PremiumBadge />
      </h2>
      <Card className="form-stack">
        <p className="text-secondary">
          Terminy zadań i płatności (bez kwot) pojawią się w Waszym kalendarzu Google, Apple lub Outlook i będą się same aktualizować. Każda
          osoba z dostępem do wesela ma własny adres.
        </p>
        {(create.isError || revoke.isError) && (
          <Notice tone="error" live>
            {userMessage(create.error ?? revoke.error)}
          </Notice>
        )}
        {url ? (
          <>
            <Notice tone="info" title="Wasz prywatny adres">
              <p className="feed-url">{url}</p>
              <p>Adres widać tylko teraz. Nie wysyłajcie go innym osobom — każdy, kto go zna, zobaczy Wasze terminy.</p>
            </Notice>
            <div className="wp-sheet__actions">
              <Button
                variant="secondary"
                icon={<Copy aria-hidden size={18} />}
                onPress={async () => {
                  try {
                    await navigator.clipboard.writeText(url);
                    toast("Skopiowano adres");
                  } catch {
                    toast("Nie udało się skopiować — zaznaczcie adres ręcznie");
                  }
                }}
              >
                Kopiuj adres
              </Button>
              <a className="wp-button wp-button--secondary" href={url.replace(/^https?:/, "webcal:")}>
                Otwórz w kalendarzu
              </a>
            </div>
            <p className="text-secondary">
              Google: Kalendarz → Inne kalendarze → „Z adresu URL”. iPhone: Ustawienia → Kalendarz → Konta → Dodaj konto → Inne →
              „Dodaj subskrybowany kalendarz”.
            </p>
          </>
        ) : active ? (
          <p>
            Adres jest włączony{status.data?.last_used_at ? " i używany przez kalendarz" : ""}. Jeśli go zgubiliście, utwórzcie nowy — stary
            przestanie działać.
          </p>
        ) : null}
        <div className="wp-sheet__actions">
          <Button variant={active ? "secondary" : "primary"} pending={create.isPending} onPress={() => create.mutate()}>
            {active ? "Utwórz nowy adres" : "Włącz kalendarz w telefonie"}
          </Button>
          {active && (
            <Button variant="text" pending={revoke.isPending} onPress={() => revoke.mutate()}>
              Wyłącz adres
            </Button>
          )}
        </div>
      </Card>
    </section>
  );
}
