/** Kurs i pokój przy gościu (z modułu Transport i noclegi): czy ma przydział i jaki. */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { keys } from "./data";

export function GuestLogistics({ weddingId, guestId }: { weddingId: string; guestId: string }) {
  const data = useQuery({
    queryKey: [...keys.households(weddingId), "logistics"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/logistics", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const o = data.data;
  if (!o || (o.runs.length === 0 && o.rooms.length === 0)) return null;
  const runs = o.runs.filter((r) => r.passengers.some((p) => p.guest_id === guestId)).map((r) => r.name);
  const room = o.rooms.find((r) => r.occupants.some((p) => p.guest_id === guestId));
  return (
    <p className="text-secondary">
      {runs.length ? `Kurs: ${runs.join(", ")}.` : "Bez kursu."} {room ? `Pokój: ${room.place}, ${room.name}.` : "Bez pokoju."}{" "}
      <Link to={`/w/${weddingId}/logistyka`}>Transport i noclegi</Link>
    </p>
  );
}
