/** Kursy na ekranie Dzień: godziny, trasy i liczby osób (także dla koordynatora; bez nazwisk). */
import { useQuery } from "@tanstack/react-query";
import { Bus } from "lucide-react";

import { api, unwrap } from "../../api/client";
import { Card, StatusChip } from "../../components/Surface";
import { formatTime, plural } from "../../lib/format";

const PEOPLE = { one: "# osoba", few: "# osoby", many: "# osób", other: "# osoby" };

export function DayTransport({ weddingId }: { weddingId: string }) {
  const runs = useQuery({
    queryKey: ["wedding", weddingId, "day-transport"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/day-transport", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  if (!runs.data?.length) return null;
  return (
    <section className="form-stack" aria-labelledby="day-transport-h">
      <h2 id="day-transport-h">Kursy</h2>
      <Card>
        <ul className="row-list">
          {runs.data.map((r) => (
            <li key={r.id} className="row">
              <Bus aria-hidden size={20} strokeWidth={1.75} />
              <span className="row__body">
                <span className="row__title">
                  {r.departs_at && <span className="num">{formatTime(r.departs_at)} </span>}
                  {r.name}
                </span>
                {(r.from_place || r.to_place) && <span className="text-secondary">{[r.from_place, r.to_place].filter(Boolean).join(" → ")}</span>}
              </span>
              <StatusChip tone={r.passengers > r.capacity ? "error" : "neutral"}>
                {plural(r.passengers, PEOPLE)} / {r.capacity}
              </StatusChip>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}
