/** Link z programem dnia dla usługodawcy (Premium): bez logowania, tylko do odczytu, odwoływalny. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Field";
import { PremiumBadge } from "../../components/Premium";
import { Card, Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";

/** Sala i catering dostają dodatkowo liczby dla kuchni (a za zgodą — imiona i diety przy stołach). */
const CATERING = ["venue", "catering"];

export function DayLinkSection({
  weddingId,
  vendorId,
  vendorCategory,
  canWrite,
}: {
  weddingId: string;
  vendorId: string;
  vendorCategory: string;
  canWrite: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [token, setToken] = useState<string | null>(null);
  const catering = CATERING.includes(vendorCategory);
  const [share, setShare] = useState(false);
  const params = { path: { wedding_id: weddingId, vendor_id: vendorId } };
  const statusKey = ["wedding", weddingId, "vendors", vendorId, "day-link"];
  const status = useQuery({
    queryKey: statusKey,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/day-link", { params, signal })),
  });
  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/day-link", {
          params,
          body: { share_catering: catering && share },
        }),
      ),
    onSuccess: (r) => {
      setToken(r.token);
      queryClient.setQueryData(statusKey, { active: true, share_catering: catering && share, created_at: new Date().toISOString(), last_used_at: null });
    },
  });
  const revoke = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/vendors/{vendor_id}/day-link", { params })),
    onSuccess: () => {
      setToken(null);
      queryClient.setQueryData(statusKey, { active: false, share_catering: false, created_at: null, last_used_at: null });
      toast("Link wyłączony");
    },
  });
  const url = token ? `${window.location.origin}/dzien/${token}` : null;
  const s = status.data;

  return (
    <section className="form-stack" aria-labelledby={`daylink-${vendorId}`}>
      <h2 id={`daylink-${vendorId}`}>
        Program dnia dla usługodawcy <PremiumBadge />
      </h2>
      <Card className="form-stack">
        <p className="text-secondary">
          Link bez logowania: godziny całego programu, a przy punktach tego usługodawcy — przygotowania i plan B. Bez danych gości i kwot.
          Gdy przesuniecie program, usługodawca zobaczy nowe godziny.
        </p>
        {catering && (
          <p className="text-secondary">
            Sala i catering widzą też liczby dla kuchni: potwierdzonych dorosłych i dzieci, diety, posiłki dla obsługi i liczbę osób przy
            każdym stole — aktualne po każdej odpowiedzi gości.
          </p>
        )}
        {(create.isError || revoke.isError) && (
          <Notice tone="error" live>
            {userMessage(create.error ?? revoke.error)}
          </Notice>
        )}
        {url && (
          <Notice tone="info" title="Link dla usługodawcy">
            <p className="feed-url">{url}</p>
            <p>Link widać tylko teraz — skopiujcie go i wyślijcie usługodawcy.</p>
          </Notice>
        )}
        {!url && s?.active && (
          <p>
            Link jest włączony{s.created_at ? ` od ${formatDate(s.created_at.slice(0, 10))}` : ""}
            {s.last_used_at ? " i był otwierany." : "."}
            {catering && (s.share_catering ? " Udostępnia imiona, diety i uwagi przy stołach." : " Pokazuje same liczby, bez imion.")}
          </p>
        )}
        {canWrite && catering && (
          <Checkbox isSelected={share} onChange={setShare}>
            Udostępnić sali listę diet i plan stołów (imiona, diety i uwagi dla kuchni)?
          </Checkbox>
        )}
        {canWrite && catering && share && (
          <Notice tone="warning">
            Uwagi dietetyczne mogą dotyczyć zdrowia (np. alergie). Udostępnijcie je tylko sali, która przygotowuje posiłki — link działa
            bez logowania, więc wysyłajcie go jednej osobie. Zgoda dotyczy nowego linku; możecie go w każdej chwili wyłączyć.
          </Notice>
        )}
        {canWrite && (
          <div className="wp-sheet__actions">
            {url && (
              <Button
                variant="secondary"
                icon={<Copy aria-hidden size={18} />}
                onPress={async () => {
                  try {
                    await navigator.clipboard.writeText(url);
                    toast("Skopiowano link");
                  } catch {
                    toast("Nie udało się skopiować — zaznaczcie link ręcznie");
                  }
                }}
              >
                Kopiuj link
              </Button>
            )}
            <Button variant={s?.active ? "secondary" : "primary"} pending={create.isPending} onPress={() => create.mutate()}>
              {s?.active ? "Utwórz nowy link" : "Utwórz link"}
            </Button>
            {s?.active && (
              <Button variant="text" pending={revoke.isPending} onPress={() => revoke.mutate()}>
                Wyłącz link
              </Button>
            )}
          </div>
        )}
      </Card>
    </section>
  );
}
