import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Field";
import { Card, EmptyState, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { useCanWrite } from "../wedding/data";
import { aKeys, formatDay, useCandidates, type Candidate } from "./assistant";

export function CandidatesPanel({ id }: { id: string }) {
  const candidates = useCandidates(id);
  const canWrite = useCanWrite(id);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => void qc.invalidateQueries({ queryKey: aKeys.candidates(id) });
  const reject = useMutation({
    mutationFn: (c: Candidate) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/candidates/{candidate_id}", {
          params: { path: { wedding_id: id, candidate_id: c.id } },
          body: { state: "rejected" },
        }),
      ),
    onSuccess: () => {
      refresh();
      toast("Firma nie będzie już proponowana.");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const toVendor = useMutation({
    mutationFn: (c: Candidate) =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/candidates/{candidate_id}/to-vendor", { params: { path: { wedding_id: id, candidate_id: c.id } } })),
    onSuccess: () => {
      refresh();
      void qc.invalidateQueries({ queryKey: ["wedding", id, "vendors"] });
      toast("Dodano do Waszych usługodawców.");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const draft = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/inquiries", {
          params: { path: { wedding_id: id } },
          body: { recipients: picked.map((catalog_vendor_id) => ({ catalog_vendor_id })), extra_questions: [] },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: aKeys.inquiries(id) });
      void navigate(`/w/${id}/dobor?zakladka=zapytania`);
    },
    onError: (e) => setError(userMessage(e)),
  });

  if (candidates.isPending) return <Skeleton lines={4} />;
  const list = candidates.data ?? [];
  if (list.length === 0)
    return (
      <EmptyState title="Lista kandydatów jest pusta">
        Zapisujcie firmy z katalogu albo z rozmowy z asystentem. Stąd przygotujecie zapytania o termin i cenę.
      </EmptyState>
    );
  const toggle = (catalogId: string, on: boolean) =>
    setPicked((p) => (on ? [...p, catalogId].slice(0, 5) : p.filter((x) => x !== catalogId)));

  return (
    <div className="form-stack">
      {error && <Notice tone="error" live>{error}</Notice>}
      <Card>
        <ul className="row-list">
          {list.map((c) => (
            <li key={c.id} className="row cand">
              {canWrite && (
                <Checkbox isSelected={picked.includes(c.catalog_vendor_id)} onChange={(on) => toggle(c.catalog_vendor_id, on)}>
                  <span className="visually-hidden">Wybierz {c.name} do zapytania</span>
                </Checkbox>
              )}
              <span className="row__body">
                <span className="row__title">{c.name}</span>
                <span className="text-secondary">
                  {[c.city, `zapisano ${formatDay(c.created_at)}`].filter(Boolean).join(" · ")}
                </span>
                {Array.isArray(c.reasoning.missing) ? (
                  <span className="text-secondary">Do ustalenia: {(c.reasoning.missing as string[]).slice(0, 3).join("; ")}</span>
                ) : null}
              </span>
              {canWrite && (
                <span className="cand__actions">
                  {c.vendor_id ? (
                    <Link to={`/w/${id}/uslugodawcy/${c.vendor_id}`} className="wp-button wp-button--text">
                      W usługodawcach
                    </Link>
                  ) : (
                    <Button variant="text" pending={toVendor.isPending} onPress={() => toVendor.mutate(c)}>
                      Dodaj do moich usługodawców
                    </Button>
                  )}
                  <Button variant="text" pending={reject.isPending} onPress={() => reject.mutate(c)}>
                    Odrzuć
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      </Card>
      {canWrite && (
        <Button
          isDisabled={picked.length === 0}
          pending={draft.isPending}
          onPress={() => draft.mutate()}
        >
          {`Przygotuj zapytania (${picked.length})`}
        </Button>
      )}
      <p className="text-secondary">
        Szkic zapytania możecie przejrzeć i poprawić. Nic nie zostanie wysłane, dopóki go nie zatwierdzicie.
      </p>
    </div>
  );
}
