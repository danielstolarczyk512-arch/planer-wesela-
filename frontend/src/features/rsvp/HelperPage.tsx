/** Strona pomocnika (link bez logowania): tylko jego zadania, odhaczane jednym dotknięciem. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import { Checkbox } from "../../components/Field";
import { Card, Notice, Skeleton } from "../../components/Surface";
import { formatDate } from "../../lib/format";
import "../auth/auth.css";
import "./rsvp.css";

export function HelperPage() {
  const { token = "" } = useParams();
  const queryClient = useQueryClient();
  const key = ["helper", token];
  const view = useQuery({
    queryKey: key,
    queryFn: () => unwrap(api.GET("/api/v1/helper/{token}", { params: { path: { token } } })),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const done = useMutation({
    mutationFn: ({ task, value }: { task: string; value: boolean }) =>
      unwrap(api.PUT("/api/v1/helper/{token}/tasks/{task_id}/done", { params: { path: { token, task_id: task } }, body: { done: value } })),
    onSuccess: (fresh) => queryClient.setQueryData(key, fresh),
  });
  const d = view.data;
  const open = d?.tasks.filter((t) => !t.done).length ?? 0;

  return (
    <main className="auth-page rsvp-page" aria-labelledby="helper-h">
      <div className="auth-card rsvp-card">
        <p className="auth-brand" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="auth-brand__icon">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          Nasz dzień
        </p>
        {view.isPending && (
          <>
            <h1 id="helper-h">Zadania</h1>
            <Skeleton lines={4} />
          </>
        )}
        {view.isError && (
          <>
            <h1 id="helper-h">Link nie działa</h1>
            <Notice tone="error" live>
              {view.error instanceof ApiError && view.error.status === 404
                ? "Link jest nieprawidłowy albo para utworzyła nowy. Poproście parę o aktualny link."
                : userMessage(view.error)}
            </Notice>
          </>
        )}
        {d && (
          <>
            <div>
              <p className="overline">{d.wedding_name}</p>
              <h1 id="helper-h">{d.helper_name}</h1>
              <p className="text-secondary">
                {d.tasks.length === 0
                  ? "Para nie przypisała Ci jeszcze zadań."
                  : open === 0
                    ? "Wszystko zrobione — dziękujemy!"
                    : `Do zrobienia: ${open}. Odhacz zadanie, gdy będzie gotowe — para od razu to zobaczy.`}
                {d.wedding_date && ` Ślub: ${formatDate(d.wedding_date)}.`}
              </p>
            </div>
            {done.isError && (
              <Notice tone="error" live>
                {userMessage(done.error)}
              </Notice>
            )}
            {d.tasks.length > 0 && (
              <Card>
                <ul className="row-list">
                  {d.tasks.map((t) => (
                    <li key={t.id} className="row">
                      <Checkbox isSelected={t.done} isDisabled={done.isPending} onChange={(value) => done.mutate({ task: t.id, value })}>
                        <span className="row__body">
                          <span className={t.done ? "done-title" : "row__title"}>{t.title}</span>
                          {t.description && <span className="text-secondary prewrap">{t.description}</span>}
                          {t.due_date && <span className="text-secondary num">termin: {formatDate(t.due_date)}</span>}
                        </span>
                      </Checkbox>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            <p className="text-secondary rsvp-privacy">Ten link widzisz tylko Ty — nie przekazuj go dalej. Nie zawiera budżetu ani listy gości.</p>
          </>
        )}
      </div>
    </main>
  );
}
