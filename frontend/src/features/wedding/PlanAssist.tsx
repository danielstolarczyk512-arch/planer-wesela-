/** Pomoc w planie: rozłożenie zaległych zadań i uzupełnienie planu z szablonu (z podglądem). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Sheet } from "../../components/Overlay";
import { Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate, plural } from "../../lib/format";
import { keys } from "./data";

const p = (weddingId: string) => ({ path: { wedding_id: weddingId } });

/** Od tylu zaległych zadań proponujemy rozłożenie (pojedyncze para ogarnie sama). */
export const CATCH_UP_THRESHOLD = 3;

export function CatchUpNotice({ weddingId, overdue }: { weddingId: string; overdue: number }) {
  const [open, setOpen] = useState(false);
  if (overdue < CATCH_UP_THRESHOLD) return null;
  return (
    <>
      <Notice tone="warning" title={`${plural(overdue, { one: "# zadanie", few: "# zadania", many: "# zadań", other: "# zadania" })} po terminie`}>
        <p>Zaczęliście później niż zakłada plan — to normalne. Możemy rozłożyć zaległości na najbliższe tygodnie, od najważniejszych.</p>
        <Button variant="secondary" onPress={() => setOpen(true)}>
          Pokaż nowe terminy
        </Button>
      </Notice>
      <Sheet title="Nadrobienie zaległości" isOpen={open} onOpenChange={setOpen}>
        {open && <CatchUpPreview weddingId={weddingId} onDone={() => setOpen(false)} />}
      </Sheet>
    </>
  );
}

function CatchUpPreview({ weddingId, onDone }: { weddingId: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const preview = useQuery({
    queryKey: [...keys.tasks(weddingId), "catch-up-preview"],
    queryFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/tasks/catch-up", { params: p(weddingId), body: { dry_run: true } })),
    gcTime: 0,
  });
  const apply = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/weddings/{wedding_id}/tasks/catch-up", { params: p(weddingId), body: { dry_run: false } })),
    onSuccess: async (r) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.tasks(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) }),
      ]);
      onDone();
      toast(`Nowe terminy: ${plural(r.changes.length, { one: "# zadanie", few: "# zadania", many: "# zadań", other: "# zadania" })}`);
    },
  });
  if (preview.isPending) return <p className="text-secondary">Liczymy nowe terminy…</p>;
  if (preview.isError)
    return (
      <Notice tone="error" live>
        {userMessage(preview.error)}
      </Notice>
    );
  const changes = preview.data.changes;
  return (
    <div className="form-stack">
      <p className="text-secondary">{preview.data.note}</p>
      {apply.isError && (
        <Notice tone="error" live>
          Nie zapisano. {userMessage(apply.error)}
        </Notice>
      )}
      <ul className="row-list">
        {changes.map((c) => (
          <li key={c.task_id} className="row">
            <span className="row__body">
              <span className="row__title">{c.title}</span>
              <span className="text-secondary num">
                {c.old_due_date ? `${formatDate(c.old_due_date)} → ` : ""}
                <strong>{formatDate(c.new_due_date)}</strong>
              </span>
            </span>
          </li>
        ))}
      </ul>
      <Button block pending={apply.isPending} isDisabled={changes.length === 0} onPress={() => apply.mutate()}>
        Zapisz nowe terminy
      </Button>
    </div>
  );
}

const DISMISS_KEY = (weddingId: string, version: string) => `wp:template-sync:${weddingId}:${version}`;

function dismissed(weddingId: string, version: string): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY(weddingId, version)) === "1";
  } catch {
    return false;
  }
}

/** „W planie są nowe zadania” — po zmianie typu ceremonii albo nowej wersji szablonu. */
export function TemplateSyncNotice({ weddingId, canWrite }: { weddingId: string; canWrite: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const preview = useQuery({
    queryKey: [...keys.tasks(weddingId), "template-sync"],
    queryFn: () =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/tasks/sync-template", { params: p(weddingId), body: { dry_run: true } })),
    enabled: canWrite,
    staleTime: 5 * 60_000,
  });
  const apply = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/tasks/sync-template", { params: p(weddingId), body: { dry_run: false } })),
    onSuccess: async (r) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.tasks(weddingId) }),
        queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) }),
      ]);
      setOpen(false);
      const added = r.to_add.filter((t) => !t.parent_code).length;
      toast(`Plan uzupełniony: ${plural(added, { one: "# nowe zadanie", few: "# nowe zadania", many: "# nowych zadań", other: "# nowego zadania" })}`);
    },
  });
  const data = preview.data;
  if (!data || hidden || dismissed(weddingId, data.template_version)) return null;
  const topLevel = data.to_add.filter((t) => !t.parent_code);
  if (topLevel.length === 0 && data.to_skip.length === 0) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY(weddingId, data.template_version), "1");
    } catch {
      /* brak dostępu do pamięci przeglądarki: ukrywamy tylko do odświeżenia */
    }
    setHidden(true);
  };

  return (
    <>
      <Notice tone="info" title="Plan przygotowań ma nowe zadania">
        <p>
          {topLevel.length > 0 &&
            `${plural(topLevel.length, { one: "# nowe zadanie pasuje", few: "# nowe zadania pasują", many: "# nowych zadań pasuje", other: "# nowego zadania pasuje" })} do Waszej ceremonii. `}
          {data.to_skip.length > 0 && `${plural(data.to_skip.length, { one: "# zadanie nie dotyczy", few: "# zadania nie dotyczą", many: "# zadań nie dotyczy", other: "# zadania nie dotyczy" })} już Waszej ceremonii.`}
        </p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setOpen(true)}>
            Zobacz zmiany
          </Button>
          <Button variant="text" onPress={dismiss}>
            Nie teraz
          </Button>
        </div>
      </Notice>
      <Sheet title="Uzupełnienie planu" isOpen={open} onOpenChange={setOpen}>
        <div className="form-stack">
          {apply.isError && (
            <Notice tone="error" live>
              Nie zapisano. {userMessage(apply.error)}
            </Notice>
          )}
          <Button block pending={apply.isPending} onPress={() => apply.mutate()}>
            Uzupełnij plan
          </Button>
          {topLevel.length > 0 && (
            <section className="form-stack" aria-labelledby="sync-add-h">
              <h3 id="sync-add-h">Dodamy</h3>
              <ul className="row-list">
                {topLevel.map((t) => {
                  const subs = data.to_add.filter((s) => s.parent_code === t.code).length;
                  return (
                    <li key={t.code} className="row">
                      <span className="row__body">
                        <span className="row__title">{t.title}</span>
                        {subs > 0 && <span className="text-secondary">{plural(subs, { one: "z # pozycją", few: "z # pozycjami", many: "z # pozycjami", other: "z # pozycji" })}</span>}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
          {data.to_skip.length > 0 && (
            <section className="form-stack" aria-labelledby="sync-skip-h">
              <h3 id="sync-skip-h">Oznaczymy jako „nie dotyczy”</h3>
              <p className="text-secondary">Nic nie usuwamy — pominięte zadanie da się przywrócić.</p>
              <ul className="row-list">
                {data.to_skip.map((t) => (
                  <li key={t.task_id} className="row">
                    <span className="row__body">
                      <span className="row__title">{t.title}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </Sheet>
    </>
  );
}
