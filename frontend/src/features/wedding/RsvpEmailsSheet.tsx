/** Linki RSVP e-mailem do rodzin bez odpowiedzi: podgląd, kto dostanie wiadomość, potem wysyłka. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, plural } from "../../lib/format";
import { keys } from "./data";

export function RsvpEmailsSheet({ weddingId, isOpen, onClose }: { weddingId: string; isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet title="Linki do potwierdzenia e-mailem" isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {isOpen && <RsvpEmailsForm weddingId={weddingId} onClose={onClose} />}
    </Sheet>
  );
}

function RsvpEmailsForm({ weddingId, onClose }: { weddingId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [includeWithLink, setIncludeWithLink] = useState(false);
  const path = { path: { wedding_id: weddingId } };
  const preview = useQuery({
    queryKey: ["wedding", weddingId, "rsvp-emails-preview", includeWithLink],
    queryFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/rsvp-emails", { params: path, body: { dry_run: true, include_with_link: includeWithLink } })),
    gcTime: 0,
  });
  const send = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/rsvp-emails", { params: path, body: { dry_run: false, include_with_link: includeWithLink } })),
    onSuccess: async (r) => {
      await queryClient.invalidateQueries({ queryKey: keys.households(weddingId) });
      onClose();
      toast(`Wysłano: ${plural(r.to_send.length, { one: "# wiadomość", few: "# wiadomości", many: "# wiadomości", other: "# wiadomości" })}`);
    },
  });
  if (preview.isPending) return <Skeleton lines={4} />;
  if (preview.isError)
    return (
      <Notice tone="error" live>
        {userMessage(preview.error)}
      </Notice>
    );
  const p = preview.data;
  return (
    <div className="form-stack">
      <p className="text-secondary">{p.note}</p>
      {send.isError && (
        <Notice tone="error" live>
          Nie wysłano. {userMessage(send.error)}
        </Notice>
      )}
      {p.to_send.length === 0 ? (
        <Notice tone="info">Nie ma do kogo wysłać — wszyscy z adresem e-mail odpowiedzieli albo mają już link.</Notice>
      ) : (
        <ul className="row-list">
          {p.to_send.map((t) => (
            <li key={t.household_id} className="row">
              <span className="row__body">
                <span className="row__title">{t.name}</span>
                <span className="text-secondary">
                  {t.email}
                  {t.last_emailed_at && ` · ostatnio ${formatDate(t.last_emailed_at.slice(0, 10))}`}
                  {t.has_active_link && " · stary link przestanie działać"}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {p.with_link_skipped > 0 && (
        <Checkbox isSelected={includeWithLink} onChange={setIncludeWithLink}>
          Wyślij też do {plural(p.with_link_skipped, { one: "# rodziny", few: "# rodzin", many: "# rodzin", other: "# rodziny" })}, które mają już link
          (dostaną nowy, a poprzedni przestanie działać)
        </Checkbox>
      )}
      {p.without_email > 0 && (
        <p className="text-secondary">
          {plural(p.without_email, { one: "# rodzina bez odpowiedzi nie ma", few: "# rodziny bez odpowiedzi nie mają", many: "# rodzin bez odpowiedzi nie ma", other: "# rodziny bez odpowiedzi nie ma" })}{" "}
          adresu e-mail — do nich warto zadzwonić.
        </p>
      )}
      <Button block isDisabled={p.to_send.length === 0} pending={send.isPending} onPress={() => send.mutate()}>
        Wyślij {p.to_send.length > 0 ? `(${p.to_send.length})` : ""}
      </Button>
    </div>
  );
}
