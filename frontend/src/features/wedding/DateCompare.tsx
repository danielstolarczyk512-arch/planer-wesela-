/** Pomocnik wyboru daty: kilka terminów obok siebie (święta, Adwent/Post, sezon, zachód słońca). */
import { parseDate, type CalendarDate } from "@internationalized/date";
import { useQuery } from "@tanstack/react-query";
import { Plus, Sunset } from "lucide-react";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components, paths } from "../../api/schema";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { Select } from "../../components/Select";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { formatDate } from "../../lib/format";
import type { Wedding } from "./data";

type Check = components["schemas"]["DateCheck"];
type Ceremony = NonNullable<NonNullable<paths["/api/v1/date-check"]["get"]["parameters"]["query"]>["ceremony_type"]>;

const MAX_DATES = 4;
const SEASON: Record<Check["season"], string> = { high: "Szczyt sezonu", mid: "Średni sezon", low: "Poza sezonem" };

/** "21:12:00" → "21:12". */
export function hhmm(t: string | null | undefined): string | null {
  return t ? t.slice(0, 5) : null;
}

/** Same daty do zapytania: bez pustych i bez powtórzeń, w kolejności wpisania. */
export function chosenDates(values: (CalendarDate | null)[]): string[] {
  return [...new Set(values.filter((v): v is CalendarDate => v !== null).map((v) => v.toString()))];
}

export function DateCompare({ wedding: w }: { wedding: Wedding }) {
  const [values, setValues] = useState<(CalendarDate | null)[]>([w.wedding_date ? parseDate(w.wedding_date) : null, null]);
  const [city, setCity] = useState<string | null>(w.city ?? null);
  const picked = chosenDates(values);
  const check = useQuery({
    queryKey: ["date-check", picked, city, w.ceremony_type],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/date-check", {
          params: { query: { date: picked, city: city ?? undefined, ceremony_type: w.ceremony_type as Ceremony } },
          signal,
        }),
      ),
    enabled: picked.length > 0,
    placeholderData: (previous) => previous,
  });
  const data = check.data;

  return (
    <section id="porownaj-daty" aria-labelledby="compare-h" className="form-stack">
      <h2 id="compare-h">Porównajcie daty</h2>
      <Card className="form-stack">
        <p className="text-secondary">
          Wpiszcie kilka terminów — pokażemy dzień tygodnia, święta i długie weekendy, sezon, Adwent i Wielki Post (przy ślubie
          w kościele) oraz godzinę zachodu słońca do zdjęć w plenerze.
        </p>
        <div className="stat-grid">
          {values.map((v, i) => (
            <DateField
              key={i}
              label={`Termin ${i + 1}`}
              value={v}
              onChange={(d) => setValues((all) => all.map((x, j) => (j === i ? d : x)))}
            />
          ))}
        </div>
        {values.length < MAX_DATES && (
          <Button variant="secondary" onPress={() => setValues((all) => [...all, null])}>
            <Plus aria-hidden size={18} /> Dodaj termin
          </Button>
        )}
        {data && (
          <Select
            label="Zachód słońca liczymy dla"
            options={data.cities.map((c) => ({ id: c, label: c }))}
            value={city && data.cities.includes(city) ? city : data.city}
            onChange={setCity}
          />
        )}
        {check.isError && (
          <Notice tone="error" live>
            {userMessage(check.error)}
          </Notice>
        )}
      </Card>
      {data &&
        picked.length > 0 &&
        data.dates.map((d) => (
          <Card key={d.date} className="form-stack" aria-label={`Termin ${formatDate(d.date)}`}>
            <h3 className="card-title">
              {d.weekday}, {formatDate(d.date)}
            </h3>
            <ul className="chip-list" aria-label="Najważniejsze">
              <li>
                <StatusChip tone={d.season === "high" ? "warning" : "neutral"}>{SEASON[d.season]}</StatusChip>
              </li>
              {d.holiday && (
                <li>
                  <StatusChip tone="warning">{d.holiday}</StatusChip>
                </li>
              )}
              {d.holidays_near.length > 0 && (
                <li>
                  <StatusChip tone="info">Blisko święta</StatusChip>
                </li>
              )}
              {d.church_season && (
                <li>
                  <StatusChip tone="warning">{d.church_season}</StatusChip>
                </li>
              )}
            </ul>
            {d.sunset && (
              <p className="row-inline">
                <Sunset aria-hidden size={18} />
                <span className="num">
                  Zachód słońca {hhmm(d.sunset)}
                  {d.golden_hour_from && ` · zdjęcia w plenerze najlepiej od ${hhmm(d.golden_hour_from)}`}
                </span>
              </p>
            )}
            {d.notes.length > 0 && (
              <ul className="notes-list">
                {d.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      <p className="text-secondary">To podpowiedzi do rozmowy, nie ocena terminu. Zasady w okresach kościelnych ustala parafia.</p>
    </section>
  );
}
