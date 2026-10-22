import { parseDate, type CalendarDate } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Form } from "react-aria-components";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Notice } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import type { components } from "../../api/schema";
import { helpersKey, keys, memberName, useHelpers, useMembers, useTasks, type Task } from "./data";
import { subtasksOf, TaskRow, useToggleTask } from "./tasks";
import { useVendors } from "./vendors";

type TaskPatch = components["schemas"]["TaskUpdate"];
import { TaskComments } from "./TaskComments";
import { ifMatch, saveErrorMessage } from "./mutations";

const NOBODY = "__nobody__";
const NO_VENDOR = "__no_vendor__";

/** Edycja zadania: tytuł, termin, osoba; pominięcie; usunięcie z potwierdzeniem. */
const NO_HELPER = "bez-pomocnika";

export function EditTaskSheet({ weddingId, task: picked, onClose }: { weddingId: string; task: Task | null; onClose: () => void }) {
  // Świeża wersja z listy (np. po dodaniu zależności), a nie kopia z chwili otwarcia.
  const tasks = useTasks(weddingId);
  const task = picked ? (tasks.data?.find((t) => t.id === picked.id) ?? picked) : null;
  return (
    <Sheet title="Zadanie" isOpen={!!task} onOpenChange={(o) => !o && onClose()}>
      {task && <EditTaskForm key={`${task.id}-${task.version}`} weddingId={weddingId} task={task} onClose={onClose} />}
    </Sheet>
  );
}

function EditTaskForm({ weddingId, task, onClose }: { weddingId: string; task: Task; onClose: () => void }) {
  const members = useMembers(weddingId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = useState(task.title);
  const [due, setDue] = useState<CalendarDate | null>(task.due_date ? parseDate(task.due_date) : null);
  const [assignee, setAssignee] = useState<string>(task.assignee_user_id ?? NOBODY);
  const [vendor, setVendor] = useState<string>(task.vendor_id ?? NO_VENDOR);
  const [helper, setHelper] = useState<string>(task.helper_id ?? NO_HELPER);
  const helpers = useHelpers(weddingId);
  const vendors = useVendors(weddingId);
  // Najpierw usługodawcy z kategorii, której dotyczy zadanie (np. sala przy „Zarezerwujcie salę”).
  const vendorOptions = [...(vendors.data ?? [])].sort(
    (a, b) => Number(b.category === task.vendor_category) - Number(a.category === task.vendor_category) || a.name.localeCompare(b.name, "pl"),
  );
  const [titleError, setTitleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.tasks(weddingId) }),
      queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) }),
    ]);
  };

  const save = useMutation({
    // Najpierw zmiany z If-Match, potem pomocnik (osobny zapis, który też zmienia zadanie).
    mutationFn: async ({ body, helperId }: { body: Partial<TaskPatch>; helperId?: string | null }) => {
      const params = { params: { path: { wedding_id: weddingId, task_id: task.id } } };
      if (Object.keys(body).length > 0) {
        await unwrap(api.PATCH("/api/v1/weddings/{wedding_id}/tasks/{task_id}", { ...params, body: { clear_due: false, ...body }, headers: ifMatch(task.version) }));
      }
      if (helperId !== undefined) {
        await unwrap(api.PUT("/api/v1/weddings/{wedding_id}/tasks/{task_id}/helper", { ...params, body: { helper_id: helperId } }));
        await queryClient.invalidateQueries({ queryKey: helpersKey(weddingId) });
      }
    },
    onSuccess: async () => {
      await refresh();
      onClose();
      toast("Zapisano zadanie");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [keys.tasks(weddingId)])),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/tasks/{task_id}", {
          params: { path: { wedding_id: weddingId, task_id: task.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirmDelete(false);
      await refresh();
      onClose();
      toast(`Usunięto zadanie „${task.title}”`);
    },
    onError: (e) => {
      setConfirmDelete(false);
      setError(`Nie usunięto. ${userMessage(e)}`);
    },
  });

  const changes = (): Partial<TaskPatch> => {
    const body: Partial<TaskPatch> = {};
    if (title.trim() !== task.title) body.title = title.trim();
    const dueStr = due ? due.toString() : null;
    if (dueStr !== (task.due_date ?? null)) {
      if (dueStr) body.due_date = dueStr;
      else body.clear_due = true;
    }
    const who = assignee === NOBODY ? null : assignee;
    if (who !== (task.assignee_user_id ?? null)) body.assignee_user_id = who;
    const vendorId = vendor === NO_VENDOR ? null : vendor;
    if (vendorId !== (task.vendor_id ?? null)) body.vendor_id = vendorId;
    return body;
  };

  return (
    <>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim()) {
            setTitleError("Wpisz, co trzeba zrobić.");
            return;
          }
          setTitleError(null);
          const body = changes();
          const helperId = helper === NO_HELPER ? null : helper;
          const helperChanged = helperId !== (task.helper_id ?? null);
          if (Object.keys(body).length === 0 && !helperChanged) return onClose();
          save.mutate({ body, helperId: helperChanged ? helperId : undefined });
        }}
      >
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <TextField label="Co trzeba zrobić?" value={title} onChange={setTitle} error={titleError} isRequired />
        {task.tip && (
          <Notice tone="info" title="Wskazówka">
            {task.tip}
          </Notice>
        )}
        <DateField
          label="Termin"
          description={task.due_mode === "relative" ? "Termin liczony od daty ślubu; po zmianie ręcznej nie przesunie się z datą." : undefined}
          value={due}
          onChange={setDue}
        />
        {due && (
          <Button variant="text" onPress={() => setDue(null)}>
            Usuń termin
          </Button>
        )}
        <Select
          label="Kto się zajmie?"
          options={[
            { id: NOBODY, label: "Nikt konkretny" },
            ...(members.data ?? []).map((m) => ({ id: m.user_id, label: memberName(members.data, m.user_id) ?? m.email })),
          ]}
          value={assignee}
          onChange={setAssignee}
        />
        {(helpers.data?.length ?? 0) > 0 && (
          <Select
            label="Pomocnik bez konta"
            description="Zobaczy to zadanie na swoim linku i odhaczy, gdy zrobi."
            options={[{ id: NO_HELPER, label: "Bez pomocnika" }, ...(helpers.data ?? []).map((h) => ({ id: h.id, label: h.name }))]}
            value={helper}
            onChange={setHelper}
          />
        )}
        {vendorOptions.length > 0 ? (
          <Select
            label="Usługodawca"
            description="Zadanie pokaże się też na karcie usługodawcy."
            options={[{ id: NO_VENDOR, label: "Nie dotyczy usługodawcy" }, ...vendorOptions.map((v) => ({ id: v.id, label: `${v.name} · ${v.category_label}` }))]}
            value={vendor}
            onChange={setVendor}
          />
        ) : (
          task.vendor_category && (
            <Link className="wp-button wp-button--text" to={`/w/${weddingId}/uslugodawcy?nowy=${task.vendor_category}`}>
              Dodaj usługodawcę do tego zadania
            </Link>
          )
        )}
        <Button type="submit" block pending={save.isPending}>
          Zapisz
        </Button>
        {task.status !== "skipped" && task.status !== "done" && (
          <Button variant="secondary" block onPress={() => save.mutate({ body: { status: "skipped" } })}>
            Nie dotyczy nas (pomiń)
          </Button>
        )}
        {task.status === "skipped" && (
          <Button variant="secondary" block onPress={() => save.mutate({ body: { status: "todo" } })}>
            Przywróć zadanie
          </Button>
        )}
        <Button variant="text" onPress={() => setConfirmDelete(true)}>
          Usuń zadanie
        </Button>
      </Form>
      <Subtasks weddingId={weddingId} task={task} />
      <Dependencies weddingId={weddingId} task={task} />
      <TaskComments weddingId={weddingId} taskId={task.id} />
      <ConfirmDialog title="Usunąć zadanie?" isOpen={confirmDelete} onOpenChange={setConfirmDelete}>
        <p>„{task.title}” zniknie z planu. Zamiast usuwać, możesz je pominąć — wtedy da się je przywrócić.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirmDelete(false)}>
            Anuluj
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </>
  );
}

/** Pozycje do odhaczenia w zadaniu (np. lista dokumentów do ślubu). */
function Subtasks({ weddingId, task }: { weddingId: string; task: Task }) {
  const tasks = useTasks(weddingId);
  const members = useMembers(weddingId);
  const { toggle, error } = useToggleTask(weddingId);
  const subs = subtasksOf(tasks.data ?? [], task.id);
  if (subs.length === 0) return null;
  return (
    <section className="form-stack item-payments" aria-labelledby={`subs-${task.id}`}>
      <h3 id={`subs-${task.id}`}>Do odhaczenia</h3>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <ul className="row-list">
        {subs.map((t) => (
          <li key={t.id}>
            <TaskRow task={t} members={members.data} canWrite onToggle={toggle} hideDue />
            {t.tip && <p className="text-secondary subtask-tip">{t.tip}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** „Najpierw trzeba zrobić”: zadania, od których to zależy (serwer pilnuje braku cykli). */
function Dependencies({ weddingId, task }: { weddingId: string; task: Task }) {
  const tasks = useTasks(weddingId);
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  // Po dodaniu/usunięciu znika kontrolka z fokusem — przenosimy go na nagłówek sekcji, inaczej
  // fokus trafia na <body>, poza dialog (Escape przestaje zamykać arkusz, czytnik gubi miejsce).
  const heading = useRef<HTMLHeadingElement>(null);
  const all = tasks.data ?? [];
  const deps = all.filter((t) => task.depends_on.includes(t.id));
  const candidates = all.filter((t) => t.id !== task.id && !task.depends_on.includes(t.id) && t.status !== "skipped");
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.tasks(weddingId) });

  const link = useMutation({
    mutationFn: ({ dependsOn, add }: { dependsOn: string; add: boolean }) => {
      const params = { path: { wedding_id: weddingId, task_id: task.id, depends_on_id: dependsOn } };
      return add
        ? unwrap(api.PUT("/api/v1/weddings/{wedding_id}/tasks/{task_id}/dependencies/{depends_on_id}", { params }))
        : unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/tasks/{task_id}/dependencies/{depends_on_id}", { params }));
    },
    onSuccess: async () => {
      setError(null);
      setAdding(false);
      requestAnimationFrame(() => heading.current?.focus());
      await refresh();
    },
    onError: (e) => setError(userMessage(e)),
  });

  return (
    <section className="form-stack item-payments" aria-labelledby={`deps-${task.id}`}>
      <h3 id={`deps-${task.id}`} ref={heading} tabIndex={-1}>
        Najpierw trzeba zrobić
      </h3>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {deps.length === 0 ? (
        <p className="text-secondary">To zadanie nie czeka na inne. Np. „Wysłać zaproszenia” czeka na „Ustalić listę gości”.</p>
      ) : (
        <ul className="row-list">
          {deps.map((d) => (
            <li key={d.id} className="row">
              <span className="row__body">
                <span className={`row__title${d.status === "done" ? " done-title" : ""}`}>{d.title}</span>
                <span className="text-secondary">{d.status === "done" ? "zrobione" : "jeszcze nie zrobione"}</span>
              </span>
              <Button
                variant="text"
                pending={link.isPending && link.variables?.dependsOn === d.id}
                onPress={() => link.mutate({ dependsOn: d.id, add: false })}
                aria-label={`Usuń zależność od: ${d.title}`}
              >
                Usuń
              </Button>
            </li>
          ))}
        </ul>
      )}
      {adding ? (
        <Select
          label="Które zadanie musi być wcześniej?"
          options={candidates.map((t) => ({ id: t.id, label: t.title }))}
          value={null}
          placeholder="Wybierz zadanie"
          onChange={(v) => link.mutate({ dependsOn: v, add: true })}
        />
      ) : (
        candidates.length > 0 && (
          <Button variant="text" onPress={() => setAdding(true)}>
            Dodaj zadanie, które musi być wcześniej
          </Button>
        )
      )}
    </section>
  );
}
