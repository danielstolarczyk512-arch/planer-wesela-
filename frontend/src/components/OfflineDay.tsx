/** Program dnia z kopii na urządzeniu (bez sieci): „teraz / za chwilę” i pełna lista, tylko do odczytu. */
import { useEffect, useState, useSyncExternalStore } from "react";

import type { DayCopy } from "../lib/dayCopy";
import { formatDate, formatTime } from "../lib/format";
import { Card, Notice } from "./Surface";
import "./OfflineDay.css";

function subscribe(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

/** Czy przeglądarka ma sieć (navigator.onLine + zdarzenia online/offline). */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
}

export function OfflineDay({ copy, headingLevel = 2 }: { copy: DayCopy; headingLevel?: 1 | 2 }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const t = (iso: string) => new Date(iso).getTime();
  const current = copy.items.filter((i) => t(i.starts_at) <= now && now < Math.max(t(i.ends_at), t(i.starts_at) + 60_000));
  const next = copy.items.find((i) => t(i.starts_at) > now);
  const Heading = headingLevel === 1 ? "h1" : "h2";
  return (
    <section className="form-stack offline-day" aria-labelledby="offline-day-h">
      <Heading id="offline-day-h">{copy.name}</Heading>
      <Notice tone="warning" live>
        Bez połączenia — program z godz. {formatTime(copy.saved_at)}
        {copy.saved_at.slice(0, 10) !== new Date(now).toISOString().slice(0, 10) ? ` (${formatDate(copy.saved_at.slice(0, 10))})` : ""}.
        Zmiany zrobione później zobaczycie, gdy wróci internet.
      </Notice>
      <Card className="form-stack">
        {current.map((i) => (
          <div key={i.id} className="live__item">
            <p className="overline">Teraz · do {formatTime(i.ends_at)}</p>
            <p className="live__title">{i.title}</p>
            {i.location && <p className="text-secondary">{i.location}</p>}
            {i.plan_b && <p className="plan-b">Plan B: {i.plan_b}</p>}
          </div>
        ))}
        {next && (
          <div className="live__item">
            <p className="overline">Za chwilę · {formatTime(next.starts_at)}</p>
            <p className="live__title">{next.title}</p>
            {next.preparations && <p className="text-secondary">Przygotować: {next.preparations}</p>}
          </div>
        )}
        {current.length === 0 && !next && <p className="text-secondary">Program z kopii się zakończył.</p>}
      </Card>
      <Card>
        <ol className="day-list">
          {copy.items.map((i) => (
            <li key={i.id} className="day-item">
              <span className="day-item__time num">{formatTime(i.starts_at)}</span>
              <div className="day-item__body">
                <p className="day-item__title">{i.title}</p>
                {(i.location || i.vendor_name) && <p className="text-secondary">{[i.location, i.vendor_name].filter(Boolean).join(" · ")}</p>}
                {i.preparations && <p>Przygotować: {i.preparations}</p>}
                {i.plan_b && <p>Plan B: {i.plan_b}</p>}
              </div>
            </li>
          ))}
        </ol>
      </Card>
    </section>
  );
}
