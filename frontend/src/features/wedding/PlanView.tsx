import type { CalendarDate } from "@internationalized/date";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Form } from "react-aria-components";
import { useSearchParams } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { DateField } from "../../components/DateField";
import { TextField } from "../../components/Field";
import { Sheet } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Card, EmptyState, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { daysUntil, plural } from "../../lib/format";
import { EditTaskSheet } from "./EditTaskSheet";
import { CatchUpNotice, TemplateSyncNotice } from "./PlanAssist";
import { PLAN_SECTIONS, PrintLink, SectionNav } from "./SectionNav";
import { isOpen, monthLabel, subtaskProgress, TaskRow, topLevel, useToggleTask } from "./tasks";
import { keys, memberName, useCanWrite, useMembers, useTasks, useWeddingId, type Task } from "./data";

type Segment = "teraz" | "pozniej" | "zrobione";

const SEGMENTS: { value: Segment; label: string }[] = [
  { value: "teraz", label: "Teraz" },
  { value: "pozniej", label: "Później" },
  { value: "zrobione", label: "Zrobione" },
];

/** Teraz: po terminie albo w ciągu 30 dni. Później: dalsze i bez terminu. */
export function segmentOf(t: Task, now = new Date()): Segment {
  if (!isOpen(t)) return "zrobione";
  if (t.is_overdue) return "teraz";
  if (t.due_date && daysUntil(t.due_date, now) <= 30) return "teraz";
  return "pozniej";
}

export function PlanView() {
  const id = useWeddingId();
  const tasks = useTasks(id);
  const members = useMembers(id);
  const canWrite = useCanWrite(id);
  const { toggle, error } = useToggleTask(id);
  const [params, setParams] = useSearchParams();
  const segment = (params.get("widok") as Segment) || "teraz";
  const person = params.get("osoba") ?? "";
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  // Link z wyszukiwarki (?zadanie=…): to zadanie otwiera się w oknie edycji.
  const linked = params.get("zadanie");
  const linkedTask = linked ? (tasks.data?.find((t) => t.id === linked) ?? null) : null;
  // Zadanie odhaczone w tym widoku zostaje widoczne (nie znika spod palca).
  const [touched, setTouched] = useState<Set<string>>(new Set());

  const setParam = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );

  const everything = useMemo(() => tasks.data ?? [], [tasks.data]);
  const all = useMemo(() => topLevel(everything), [everything]);
  const overdue = all.filter((t) => isOpen(t) && t.is_overdue).length;
  const done = all.filter((t) => t.status === "done").length;
  const active = all.filter((t) => t.status !== "skipped").length;

  const visible = useMemo(
    () =>
      all.filter(
        (t) =>
          (segmentOf(t) === segment || (touched.has(t.id) && segment !== "zrobione")) &&
          (!person || t.assignee_user_id === person),
      ),
    [all, segment, person, touched],
  );
  const groups = useMemo(() => {
    const map = new Map<string, Task[]>();
    for (const t of visible) {
      const label = monthLabel(t.due_date);
      map.set(label, [...(map.get(label) ?? []), t]);
    }
    return [...map.entries()];
  }, [visible]);

  const onToggle = (task: Task, value: boolean) => {
    setTouched((s) => new Set(s).add(task.id));
    toggle(task, value);
  };

  return (
    <main className="page enter-tab" aria-labelledby="plan-h">
      <SectionNav label="Plan" sections={PLAN_SECTIONS} />
      <div className="view-head">
        <div>
          <p className="overline view-head__overline">Przygotowania</p>
          <h1 id="plan-h">Plan przygotowań</h1>
          <p className="text-secondary">Jedno zadanie po drugim.</p>
          <PrintLink kind="zadania">Drukuj listę zadań</PrintLink>
        </div>
        {canWrite && (
          <Button variant="secondary" icon={<Plus aria-hidden size={20} />} onPress={() => setAdding(true)}>
            Dodaj zadanie
          </Button>
        )}
      </div>

      {tasks.isPending && <Skeleton lines={6} />}
      {tasks.isError && (
        <Notice tone="error" title="Nie udało się wczytać zadań." live>
          {userMessage(tasks.error)}
        </Notice>
      )}

      {tasks.data && (
        <>
          <div className="meter" role="group" aria-label="Postęp">
            <div className="section-head">
              <span className="text-secondary">Wasze postępy</span>
              <span className="num">
                <strong>{done}</strong> z {active}{" "}
                {plural(active, { one: "zadania gotowe", few: "zadań gotowe", many: "zadań gotowe", other: "zadań gotowe" })}
              </span>
            </div>
            <div
              className="meter__track"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={active}
              aria-valuenow={done}
              aria-label="Ukończone zadania"
            >
              <div className="meter__fill" style={{ width: `${active ? (done / active) * 100 : 0}%` }} />
            </div>
          </div>

          {canWrite && <TemplateSyncNotice weddingId={id} canWrite={canWrite} />}
          {canWrite && <CatchUpNotice weddingId={id} overdue={overdue} />}

          <Segmented label="Widok" value={segment} options={SEGMENTS} onChange={(v) => setParam("widok", v === "teraz" ? "" : v)} />

          {(members.data?.length ?? 0) > 1 && (
            <Segmented
              label="Osoba"
              variant="chips"
              value={person || "all"}
              options={[
                { value: "all", label: "Wszyscy" },
                ...(members.data ?? []).map((m) => ({ value: m.user_id, label: memberName(members.data, m.user_id) ?? "?" })),
              ]}
              onChange={(v) => setParam("osoba", v === "all" ? "" : v)}
            />
          )}

          {error && (
            <Notice tone="error" live>
              {error}
            </Notice>
          )}

          {groups.length === 0 ? (
            <EmptyState title={segment === "zrobione" ? "Jeszcze nic nie odhaczyliście" : "Nic tu teraz nie czeka"}>
              {segment === "teraz" ? "Zadania na kolejne miesiące są w zakładce „Później”." : undefined}
            </EmptyState>
          ) : (
            groups.map(([label, list]) => (
              <section key={label} aria-label={label} className="form-stack">
                <div className="section-head">
                  <h2>{label}</h2>
                  <span className="text-secondary num">
                    {plural(list.length, { one: "# zadanie", few: "# zadania", many: "# zadań", other: "# zadania" })}
                  </span>
                </div>
                <Card>
                  <ul className="row-list">
                    {list.map((t) => (
                      <li key={t.id}>
                        <TaskRow
                          task={t}
                          members={members.data}
                          canWrite={canWrite}
                          onToggle={onToggle}
                          onEdit={setEditing}
                          blockedBy={all.find((d) => t.depends_on.includes(d.id) && isOpen(d))?.title}
                          subtasks={subtaskProgress(everything, t.id)}
                          showOrigin
                        />
                      </li>
                    ))}
                  </ul>
                </Card>
              </section>
            ))
          )}
          {!canWrite && <p className="text-secondary">Masz dostęp tylko do podglądu planu.</p>}
        </>
      )}
      <NewTaskSheet weddingId={id} isOpen={adding} onOpenChange={setAdding} />
      <EditTaskSheet
        weddingId={id}
        task={editing ?? linkedTask}
        onClose={() => {
          setEditing(null);
          if (linked) setParam("zadanie", "");
        }}
      />
    </main>
  );
}

function NewTaskSheet({ weddingId, isOpen, onOpenChange }: { weddingId: string; isOpen: boolean; onOpenChange: (o: boolean) => void }) {
  const [title, setTitle] = useState("");
  const [due, setDue] = useState<CalendarDate | null>(null);
  const [titleError, setTitleError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey());
  const queryClient = useQueryClient();
  const toast = useToast();
  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/tasks", {
          params: { path: { wedding_id: weddingId } },
          body: { title: title.trim(), due_date: due ? due.toString() : null, category: "inne", priority: 2 },
          headers: { "Idempotency-Key": key.current },
        }),
      ),
    onSuccess: async (t) => {
      key.current = newIdempotencyKey();
      setTitle("");
      setDue(null);
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: keys.tasks(weddingId) });
      void queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) });
      toast(`Dodano zadanie „${t.title}”`);
    },
  });
  return (
    <Sheet title="Nowe zadanie" isOpen={isOpen} onOpenChange={onOpenChange} isDirty={(title.trim() !== "" || due !== null) && !create.isPending}>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim()) {
            setTitleError("Wpisz, co trzeba zrobić.");
            document.getElementById("task-title")?.focus();
            return;
          }
          setTitleError(null);
          create.mutate();
        }}
      >
        {create.isError && (
          <Notice tone="error" title="Nie zapisano." live>
            {userMessage(create.error)}
          </Notice>
        )}
        <TextField id="task-title" label="Co trzeba zrobić?" value={title} onChange={setTitle} error={titleError} isRequired autoFocus />
        <DateField label="Termin (opcjonalnie)" value={due} onChange={setDue} />
        <Button type="submit" block pending={create.isPending}>
          Dodaj zadanie
        </Button>
      </Form>
    </Sheet>
  );
}
