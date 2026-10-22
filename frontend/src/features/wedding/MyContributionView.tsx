/** Widok sponsora (np. rodziców): tylko własny wkład — obiecane, zapłacone, przekazane i do zapłaty. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { AmountField, TextField } from "../../components/Field";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatMoney } from "../../lib/format";
import { FunderDetailList, coveredPercent, settleText } from "./FundersView";
import { useWedding, useWeddingId } from "./data";

export function MyContributionView() {
  const id = useWeddingId();
  const wedding = useWedding(id);
  const mine = useQuery({
    queryKey: ["wedding", id, "my-contribution"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/my-contribution", { params: { path: { wedding_id: id } }, signal })),
    retry: false,
  });
  const notAssigned = mine.error instanceof ApiError && mine.error.code === "funder.not_assigned";
  const f = mine.data?.funder;
  const settle = f ? settleText(f) : null;
  const pct = f ? coveredPercent(f) : null;
  return (
    <main className="page enter-tab" aria-labelledby="mine-h">
      <div>
        <h1 id="mine-h">Nasz wkład</h1>
        <p className="text-secondary">{wedding.data?.name}: to, co para zapisała jako Wasz udział w kosztach wesela.</p>
      </div>
      {mine.isPending && <Skeleton lines={4} />}
      {notAssigned && <EmptyState title="Para nie przypisała jeszcze Waszego wkładu">Gdy to zrobi, zobaczycie tu obiecaną kwotę i płatności.</EmptyState>}
      {mine.isError && !notAssigned && (
        <Notice tone="error" live>
          {userMessage(mine.error)}
        </Notice>
      )}
      {mine.data && f && settle && (
        <>
          <Card className="form-stack">
            <div className="section-head section-head--wrap">
              <h2>{f.name}</h2>
              <StatusChip tone={settle.tone}>{settle.text}</StatusChip>
            </div>
            <dl className="funder-numbers">
              <div>
                <dt>Obiecane</dt>
                <dd className="num">{f.pledged_amount ? formatMoney(f.pledged_amount) : "—"}</dd>
              </div>
              <div>
                <dt>Zapłacone firmom</dt>
                <dd className="num">{formatMoney(f.paid_direct)}</dd>
              </div>
              <div>
                <dt>Przekazane parze</dt>
                <dd className="num">{formatMoney(f.given)}</dd>
              </div>
              <div>
                <dt>Do zapłaty</dt>
                <dd className="num">{formatMoney(f.scheduled_direct)}</dd>
              </div>
            </dl>
            {pct !== null && (
              <div className="funder-progress">
                <progress max={100} value={pct} aria-label={`Dotarło ${pct}% obiecanej kwoty`} />
                <span className="text-secondary num">{pct}% obiecanej kwoty już dotarło</span>
              </div>
            )}
          </Card>
          {Number(f.reported.amount) > 0 && (
            <Notice tone="info">Zgłoszone przelewy czekają na potwierdzenie pary: {formatMoney(f.reported)}.</Notice>
          )}
          <ReportTransfer weddingId={id} />
          <Card>
            <FunderDetailList detail={mine.data} weddingId={null} />
          </Card>
          <p className="text-secondary">Widzicie tylko swój wkład. Budżet wesela, goście i umowy są widoczne tylko dla pary.</p>
        </>
      )}
    </main>
  );
}

/** Sponsor zgłasza przelew dla pary; kwota liczy się po potwierdzeniu przez parę. */
function ReportTransfer({ weddingId }: { weddingId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [amount, setAmount] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());
  const report = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/my-contribution/reports", {
          params: { path: { wedding_id: weddingId } },
          body: { amount: { amount: amount!, currency: "PLN" }, note: note.trim() || null },
          headers: { "Idempotency-Key": key.current },
        }),
      ),
    onSuccess: (data) => {
      key.current = newIdempotencyKey();
      queryClient.setQueryData(["wedding", weddingId, "my-contribution"], data);
      setAmount(null);
      setNote("");
      setError(null);
      toast("Zgłoszono przelew — para potwierdzi go po otrzymaniu");
    },
    onError: (e) => setError(`Nie zgłoszono. ${userMessage(e)}`),
  });
  return (
    <Card>
      <Form
        className="form-stack"
        aria-label="Zgłoś przelew"
        onSubmit={(e) => {
          e.preventDefault();
          if (!amount || Number(amount) <= 0) {
            setError("Wpisz kwotę większą od zera.");
            return;
          }
          report.mutate();
        }}
      >
        <h2>Zgłoś przelew dla pary</h2>
        <p className="text-secondary">Para zobaczy zgłoszenie i potwierdzi je, gdy pieniądze dotrą.</p>
        <AmountField label="Kwota przelewu" value={amount} onChange={setAmount} />
        <TextField label="Notatka (opcjonalnie)" description="Np. z którego konta, tytuł przelewu." value={note} onChange={setNote} />
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <div className="wp-sheet__actions">
          <Button type="submit" variant="secondary" pending={report.isPending}>
            Zgłoś przelew
          </Button>
        </div>
      </Form>
    </Card>
  );
}
