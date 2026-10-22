/** „Wymaga uwagi” na ekranie Dziś: ostrzeżenia z frekwencji, dokumentów, cen, transportu itd. */
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Card, StatusChip } from "../../components/Surface";

type Item = components["schemas"]["AttentionItem"];

const LABEL: Record<Item["severity"], string> = { error: "Pilne", warning: "Uwaga", info: "Do zrobienia" };

export function AttentionCard({ weddingId }: { weddingId: string }) {
  const data = useQuery({
    queryKey: ["wedding", weddingId, "attention"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/attention", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  // Brak ostrzeżeń albo błąd odczytu: karta się nie pokazuje (reszta pulpitu działa dalej).
  if (!data.data?.length) return null;
  return (
    <section className="form-stack" aria-labelledby="attention-h">
      <h2 id="attention-h">Wymaga uwagi</h2>
      <Card>
        <ul className="row-list">
          {data.data.map((i) => (
            <li key={`${i.code}-${i.message}`}>
              <Link to={`/w/${weddingId}/${i.link}`} viewTransition className="row link-card attention-row">
                <StatusChip tone={i.severity === "error" ? "error" : i.severity === "warning" ? "warning" : "info"}>{LABEL[i.severity]}</StatusChip>
                <span className="row__body">{i.message}</span>
                <ChevronRight aria-hidden size={20} />
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}
