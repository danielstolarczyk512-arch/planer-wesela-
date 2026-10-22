import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button as AriaButton, Checkbox as AriaCheckbox } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { daysUntil, formatDate, todayInWarsaw } from "../../lib/format";
import { keys, memberName, type Member, type Task } from "./data";
import "../../components/Field.css";

const MONTH = new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });

/** „Listopad 2026” albo „Bez terminu” (nagłówki grup zadań). */
export function monthLabel(due: string | null | undefined): string {
  if (!due) return "Bez terminu";
  const [y, m] = due.split("-").map(Number);
  const s = MONTH.format(new Date(Date.UTC(y ?? 2000, (m ?? 1) - 1, 15)));
  return s.charAt(0).toLocaleUpperCase("pl-PL") + s.slice(1);
}

export const OPEN = new Set(["todo", "in_progress"]);

export function isOpen(t: Task): boolean {
  return OPEN.has(t.status);
}

/** „Do 10 czerwca” / „Termin minął 3 dni temu” / „Bez terminu”. */
export function dueLabel(t: Task, now = new Date()): string {
  if (!t.due_date) return "Bez terminu";
  const days = daysUntil(t.due_date, now);
  // Bieżący rok pomijamy („Do 10 czerwca”), inny podajemy („Do 10 czerwca 2028”).
  const sameYear = t.due_date.slice(0, 4) === todayInWarsaw(now).slice(0, 4);
  const full = formatDate(t.due_date);
  const date = sameYear ? full.replace(/ \d{4}$/, "") : full;
  if (isOpen(t) && days < 0) return `Termin minął: ${date}`;
  return `Do ${date}`;
}

/**
 * Ukończenie / przywrócenie zadania. Zmiana widoczna od razu (optymistycznie), po błędzie
 * wraca z komunikatem. Po ukończeniu: powiadomienie z „Cofnij” (≥ 6 s).
 */
export function useToggleTask(weddingId: string) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: ({ task, done }: { task: Task; done: boolean }) =>
      unwrap(
        api.POST(done ? "/api/v1/weddings/{wedding_id}/tasks/{task_id}/complete" : "/api/v1/weddings/{wedding_id}/tasks/{task_id}/reopen", {
          params: { path: { wedding_id: weddingId, task_id: task.id } },
        }),
      ),
    onMutate: async ({ task, done }) => {
      setError(null);
      await queryClient.cancelQueries({ queryKey: keys.tasks(weddingId) });
      const previous = queryClient.getQueryData<Task[]>(keys.tasks(weddingId));
      queryClient.setQueryData<Task[]>(keys.tasks(weddingId), (list) =>
        list?.map((t) => (t.id === task.id ? { ...t, status: done ? "done" : "todo" } : t)),
      );
      return { previous };
    },
    onError: (e, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(keys.tasks(weddingId), ctx.previous);
      setError(`Nie zapisano zmiany zadania. ${userMessage(e)}`);
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<Task[]>(keys.tasks(weddingId), (list) =>
        list?.map((t) => (t.id === saved.id ? saved : t)),
      );
      void queryClient.invalidateQueries({ queryKey: keys.summary(weddingId) });
    },
  });

  function toggle(task: Task, done: boolean) {
    mutation.mutate(
      { task, done },
      {
        onSuccess: () => {
          if (done) toast(`„${task.title}” — zrobione`, () => mutation.mutate({ task: { ...task, status: "done" }, done: false }));
        },
      },
    );
  }

  return { toggle, error, pendingId: mutation.isPending ? mutation.variables?.task.id : undefined };
}

interface TaskRowProps {
  task: Task;
  members: Member[] | undefined;
  canWrite: boolean;
  onToggle: (task: Task, done: boolean) => void;
  showOrigin?: boolean;
  onEdit?: (task: Task) => void;
  /** Tytuł niezrobionego zadania, na które to czeka. */
  blockedBy?: string;
  /** Postęp podzadań (np. lista dokumentów). */
  subtasks?: { done: number; total: number };
  /** Pozycja listy w zadaniu nadrzędnym: termin jest ten sam, więc go nie powtarzamy. */
  hideDue?: boolean;
}

/** Podzadania (np. pozycje listy dokumentów) pokazujemy w zadaniu nadrzędnym, nie na liście. */
export function topLevel(tasks: Task[]): Task[] {
  return tasks.filter((t) => !t.parent_task_id);
}

export function subtasksOf(tasks: Task[], parentId: string): Task[] {
  return tasks.filter((t) => t.parent_task_id === parentId);
}

export function subtaskProgress(tasks: Task[], parentId: string): { done: number; total: number } | undefined {
  const subs = subtasksOf(tasks, parentId).filter((t) => t.status !== "skipped");
  return subs.length ? { done: subs.filter((t) => t.status === "done").length, total: subs.length } : undefined;
}

export function TaskRow({ task, members, canWrite, onToggle, showOrigin, onEdit, blockedBy, subtasks, hideDue }: TaskRowProps) {
  const done = task.status === "done";
  const overdue = isOpen(task) && task.is_overdue;
  const who = memberName(members, task.assignee_user_id);
  const meta = hideDue ? null : (
    <span className="text-secondary num">
      {dueLabel(task)}
      {who && ` · ${who}`}
      {subtasks && ` · ${subtasks.done} z ${subtasks.total} gotowe`}
      {showOrigin && task.source === "template" && " · z planu przygotowań"}
      {blockedBy && isOpen(task) && ` · czeka na „${blockedBy}”`}
    </span>
  );
  return (
    <div className="row">
      <AriaCheckbox
        className="wp-checkbox"
        isSelected={done}
        isDisabled={!canWrite}
        onChange={(v) => onToggle(task, v)}
        aria-label={`${task.title}: ${done ? "zrobione" : "do zrobienia"}`}
      >
        <span className="wp-checkbox__box" aria-hidden="true">
          <svg viewBox="0 0 18 18">
            <polyline points="4 9.5 7.5 13 14 5.5" />
          </svg>
        </span>
      </AriaCheckbox>
      {onEdit && canWrite ? (
        // Dotknięcie treści zadania otwiera edycję (nazwa przycisku = widoczny tytuł).
        <AriaButton className="row-edit" onPress={() => onEdit(task)}>
          <span className={`row__title${done ? " done-title" : ""}`}>{task.title}</span>
          {meta}
        </AriaButton>
      ) : (
        <div className="row__body">
          <span className={`row__title${done ? " done-title" : ""}`}>{task.title}</span>
          {meta}
        </div>
      )}
      {overdue && <StatusChip tone="warning">Po terminie</StatusChip>}
      {task.status === "skipped" && <StatusChip tone="neutral">Pominięte</StatusChip>}
    </div>
  );
}
