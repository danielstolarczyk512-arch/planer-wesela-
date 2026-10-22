/** Wręczanie zaproszeń osobiście: objazdy po miejscowościach, kto wręcza, odhaczanie „wręczone”. */
import type { CalendarDate } from "@internationalized/date";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { Checkbox, TextField } from "../../components/Field";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, plural } from "../../lib/format";
import { GUEST_SECTIONS, PrintLink, SectionNav } from "./SectionNav";
import { keys, useCanWrite, useWeddingId } from "./data";

type Overview = components["schemas"]["DeliveryOverview"];
type Group = Overview["groups"][number];

const VISITS = { one: "# wizyta", few: "# wizyty", many: "# wizyt", other: "# wizyty" };
const WEEKENDS = { one: "# weekend", few: "# weekendy", many: "# weekendów", other: "# weekendu" };
const INVITES = { one: "# zaproszenie", few: "# zaproszenia", many: "# zaproszeń", other: "# zaproszenia" };

/** Z czego składa się liczba do drukarni (rodziny, zapas, lista rezerwowa). */
export function printBreakdown(p: Overview["print_order"]): string {
  const parts = [`${plural(p.printed, INVITES)} dla rodzin`, `${p.spare} zapasu`];
  if (p.reserve) parts.push(`${p.reserve} dla listy rezerwowej`);
  return parts.join(" + ");
}

/** Link do mapy z samą nazwą miejscowości (otwiera OpenStreetMap; nic nie wysyłamy sami). */
export function mapLink(place: string): string {
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(place)}`;
}

/** Tempo: ile wizyt na weekend, żeby zdążyć przed terminem. */
export function pace(remaining: number, weekends: number | null | undefined): string | null {
  if (!remaining || weekends == null) return null;
  if (weekends <= 0) return "Termin minął albo wypada przed najbliższym weekendem.";
  return `Zostało ${plural(remaining, VISITS)} i ${plural(weekends, WEEKENDS)} — ok. ${Math.ceil(remaining / weekends)} na weekend.`;
}

export function InvitationsView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const queryKey = [...keys.households(id), "delivery"];
  const data = useQuery({
    queryKey,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/invitation-delivery", { params: { path: { wedding_id: id } }, signal })),
  });
  const o = data.data;
  const remaining = o ? o.in_person_total - o.in_person_delivered : 0;
  const tempo = o ? pace(remaining, o.weekends_left) : null;

  return (
    <main className="page enter-tab" aria-labelledby="inv-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div>
        <h1 id="inv-h">Zaproszenia</h1>
        <p className="text-secondary">Kogo odwiedzić z zaproszeniem — objazdy po miejscowościach, kto wręcza i co już za Wami.</p>
      </div>
      {o && o.in_person_total > o.in_person_delivered && <PrintLink kind="objazd">Wydrukuj listę na objazd</PrintLink>}
      {data.isPending && <Skeleton lines={4} />}
      {data.isError && (
        <Notice tone="error" live>
          {userMessage(data.error)}
        </Notice>
      )}
      {o && (
        <>
          <div className="stat-grid">
            <Card className="stat">
              <span className="text-secondary">Wręczone osobiście</span>
              <span className="stat__value num">
                {o.in_person_delivered} z {o.in_person_total}
              </span>
            </Card>
            <Card className="stat">
              <span className="text-secondary">Termin</span>
              <span className="stat__value">{o.deadline ? formatDate(o.deadline) : "—"}</span>
            </Card>
            {o.print_order.total > 0 && (
              <Card className="stat">
                <span className="text-secondary">Do zamówienia w drukarni</span>
                <span className="stat__value num">{o.print_order.total}</span>
                <span className="text-secondary">{printBreakdown(o.print_order)}</span>
              </Card>
            )}
          </div>
          {tempo && <Notice tone={o.weekends_left ? "info" : "warning"}>{tempo}</Notice>}
          {(o.by_method.none ?? 0) > 0 && (
            <p className="text-secondary">
              Bez ustalonego sposobu wręczenia: {o.by_method.none}. Ustawicie go w zaproszeniu na liście gości („Jak wręczamy zaproszenie”).
            </p>
          )}
          {o.groups.length === 0 ? (
            <EmptyState title="Brak zaproszeń wręczanych osobiście">
              Na liście gości otwórzcie zaproszenie i wybierzcie „Osobiście” oraz miejscowość — tu pojawi się plan objazdów.
            </EmptyState>
          ) : (
            o.groups.map((g, i) => <GroupCard key={g.place ?? "bez"} index={i} group={g} weddingId={id} canWrite={canWrite} queryKey={queryKey} />)
          )}
        </>
      )}
    </main>
  );
}

function GroupCard({
  index,
  group: g,
  weddingId,
  canWrite,
  queryKey,
}: {
  index: number;
  group: Group;
  weddingId: string;
  canWrite: boolean;
  queryKey: unknown[];
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [day, setDay] = useState<CalendarDate | null>(null);
  const [by, setBy] = useState("");
  const title = g.place ?? "Bez miejscowości";
  const done = (data: Overview, message: string) => {
    queryClient.setQueryData(queryKey, data);
    void queryClient.invalidateQueries({ queryKey: keys.households(weddingId), exact: true });
    setSelected(new Set());
    toast(message);
  };
  const plan = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/invitation-delivery/plan", {
          params: { path: { wedding_id: weddingId } },
          body: { household_ids: [...selected], ...(day ? { planned_on: day.toString() } : {}), ...(by.trim() ? { delivery_by: by.trim() } : {}) },
        }),
      ),
    onSuccess: (data) => done(data, "Zaplanowano objazd"),
  });
  const deliver = useMutation({
    mutationFn: (ids: string[]) =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/invitation-delivery/delivered", {
          params: { path: { wedding_id: weddingId } },
          body: { household_ids: ids },
        }),
      ),
    onSuccess: (data) => done(data, "Zaznaczono jako wręczone"),
  });
  const toggle = (id: string, on: boolean) =>
    setSelected((s) => {
      const next = new Set(s);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  return (
    <Card className="form-stack" aria-labelledby={`place-${index}`}>
      <div className="section-head section-head--wrap">
        <h2 id={`place-${index}`}>{title}</h2>
        <StatusChip tone={g.remaining ? "info" : "success"}>{g.remaining ? `Do wręczenia: ${g.remaining}` : "Wszystkie wręczone"}</StatusChip>
      </div>
      {g.planned_on.length > 0 && <p className="text-secondary">Objazd: {g.planned_on.map(formatDate).join(", ")}</p>}
      {g.place && (
        <a href={mapLink(g.place)} target="_blank" rel="noreferrer noopener" className="cdocs__source">
          <MapPin aria-hidden size={16} /> Pokaż na mapie
        </a>
      )}
      {(plan.isError || deliver.isError) && (
        <Notice tone="error" live>
          Nie zapisano. {userMessage(plan.error ?? deliver.error)}
        </Notice>
      )}
      <ul className="row-list">
        {g.households.map((h) => {
          const delivered = h.invitation_status === "delivered";
          const info = [
            `${h.guests} os.`,
            h.delivery_by && `wręcza: ${h.delivery_by}`,
            delivered && h.delivered_on ? `wręczone ${formatDate(h.delivered_on)}` : h.delivery_planned_on && `plan: ${formatDate(h.delivery_planned_on)}`,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <li key={h.id} className="row delivery-row">
              {canWrite && !delivered ? (
                <Checkbox isSelected={selected.has(h.id)} onChange={(on) => toggle(h.id, on)}>
                  <span className="row__body">
                    <span className="row__title">{h.name}</span>
                    <span className="text-secondary">{info}</span>
                  </span>
                </Checkbox>
              ) : (
                <span className="row__body">
                  <span className={`row__title${delivered ? " done-title" : ""}`}>{h.name}</span>
                  <span className="text-secondary">{info}</span>
                </span>
              )}
              {delivered ? (
                <StatusChip tone="success">Wręczone</StatusChip>
              ) : (
                canWrite && (
                  <Button variant="secondary" pending={deliver.isPending && deliver.variables?.includes(h.id)} onPress={() => deliver.mutate([h.id])}>
                    Wręczone
                  </Button>
                )
              )}
            </li>
          );
        })}
      </ul>
      {canWrite && g.remaining > 0 && (
        <details className="form-stack">
          <summary>Zaplanuj objazd ({selected.size ? `zaznaczone: ${selected.size}` : "zaznaczcie zaproszenia"})</summary>
          <div className="delivery-plan">
            <DateField label="Dzień objazdu" value={day} onChange={setDay} />
            <TextField label="Kto wręcza (opcjonalnie)" value={by} onChange={setBy} maxLength={80} autoComplete="off" />
          </div>
          <div className="wp-sheet__actions">
            <Button variant="secondary" isDisabled={selected.size === 0 || (!day && !by.trim())} pending={plan.isPending} onPress={() => plan.mutate()}>
              Zapisz plan
            </Button>
            <Button variant="text" isDisabled={selected.size === 0} pending={deliver.isPending} onPress={() => deliver.mutate([...selected])}>
              Zaznaczone wręczone
            </Button>
          </div>
        </details>
      )}
    </Card>
  );
}
