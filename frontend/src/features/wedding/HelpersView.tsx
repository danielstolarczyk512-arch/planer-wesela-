/** Pomocnicy bez konta: bliscy dostają link tylko ze swoimi zadaniami i odhaczają je sami. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";
import { Link } from "react-router";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { ConfirmDialog } from "../../components/Overlay";
import { Card, EmptyState, Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { plural } from "../../lib/format";
import { PLAN_SECTIONS, SectionNav } from "./SectionNav";
import { helpersKey, keys, useCanWrite, useHelpers, useWeddingId } from "./data";

const TASKS = { one: "# zadanie", few: "# zadania", many: "# zadań", other: "# zadania" };

/** „2 zadania do zrobienia · 1 zrobione”. */
export function helperProgress(open: number, done: number): string {
  if (!open && !done) return "bez zadań — przypiszcie je w zadaniu („Pomocnik bez konta”)";
  return [open && `${plural(open, TASKS)} do zrobienia`, done && `${done} zrobione`].filter(Boolean).join(" · ");
}

export function HelpersView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const helpers = useHelpers(id);
  const [name, setName] = useState("");
  const [link, setLink] = useState<{ helper: string; url: string } | null>(null);
  const [deleting, setDeleting] = useState<{ id: string; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const idem = useRef(newIdempotencyKey());
  const refresh = () => queryClient.invalidateQueries({ queryKey: helpersKey(id) });

  const create = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/weddings/{wedding_id}/helpers", { params: { path: { wedding_id: id } }, body: { name: name.trim() }, headers: { "Idempotency-Key": idem.current } })),
    onSuccess: async (r) => {
      idem.current = newIdempotencyKey();
      setLink({ helper: r.helper_id, url: r.url });
      setName("");
      setError(null);
      await refresh();
    },
    onError: (e) => setError(`Nie dodano. ${userMessage(e)}`),
  });
  const renew = useMutation({
    mutationFn: (helper: string) => unwrap(api.POST("/api/v1/weddings/{wedding_id}/helpers/{helper_id}/link", { params: { path: { wedding_id: id, helper_id: helper } } })),
    onSuccess: async (r) => {
      setLink({ helper: r.helper_id, url: r.url });
      await refresh();
    },
    onError: (e) => setError(userMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (helper: string) => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/helpers/{helper_id}", { params: { path: { wedding_id: id, helper_id: helper } } })),
    onSuccess: async () => {
      setDeleting(null);
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: keys.tasks(id) })]);
      toast("Usunięto pomocnika — jego zadania zostały na liście");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast("Skopiowano link");
    } catch {
      toast("Nie udało się skopiować — zaznaczcie link ręcznie");
    }
  };
  const rows = helpers.data ?? [];

  return (
    <main className="page enter-tab" aria-labelledby="helpers-h">
      <SectionNav label="Plan" sections={PLAN_SECTIONS} />
      <div>
        <h1 id="helpers-h">Pomocnicy</h1>
        <p className="text-secondary">
          Nie bierzcie wszystkiego na siebie. Tata, świadkowa czy brat dostaną link tylko ze swoimi zadaniami — bez zakładania konta, bez
          budżetu i listy gości. Zadania przypiszecie w Planie (pole „Pomocnik bez konta”).
        </p>
      </div>
      {helpers.isPending && <Skeleton lines={3} />}
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {link && (
        <Notice tone="success" title="Link dla pomocnika" live>
          <span className="form-stack">
            <span className="link-text">{link.url}</span>
            <span>Pokazujemy go tylko teraz — wyślijcie go SMS-em lub w komunikatorze. Nowy link unieważni ten.</span>
            <Button variant="secondary" icon={<Copy aria-hidden size={18} />} onPress={() => copy(link.url)}>
              Kopiuj link
            </Button>
          </span>
        </Notice>
      )}
      {helpers.data && rows.length === 0 && (
        <EmptyState title="Brak pomocników">{canWrite ? "Dodajcie pierwszą osobę, np. „Tata — kierowcy”." : "Para nie dodała pomocników."}</EmptyState>
      )}
      {rows.length > 0 && (
        <Card>
          <ul className="row-list photo-groups">
            {rows.map((h) => (
              <li key={h.id} className="row">
                <span className="row__body">
                  <span className="row__title">{h.name}</span>
                  <span className="text-secondary">{helperProgress(h.open_tasks, h.done_tasks)}</span>
                  <span className="text-secondary">{h.last_used_at ? "otworzył(a) link" : "jeszcze nie otworzył(a) linku"}</span>
                </span>
                {canWrite && (
                  <span className="row-actions">
                    <Button variant="text" pending={renew.isPending && renew.variables === h.id} onPress={() => renew.mutate(h.id)}>
                      Nowy link
                    </Button>
                    <AriaButton className="wp-icon-button" aria-label={`Usuń: ${h.name}`} onPress={() => setDeleting({ id: h.id, name: h.name })}>
                      <Trash2 aria-hidden size={20} />
                    </AriaButton>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
      {canWrite && (
        <Form
          className="delivery-plan checklist__add"
          aria-label="Nowy pomocnik"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <TextField label="Kto pomaga" value={name} onChange={setName} maxLength={80} autoComplete="off" placeholder="np. Tata — kierowcy" />
          <Button type="submit" variant="secondary" pending={create.isPending} isDisabled={!name.trim()}>
            Dodaj i utwórz link
          </Button>
        </Form>
      )}
      <p className="text-secondary">
        <Link to={`/w/${id}/plan`}>Przejdź do zadań</Link>, żeby przypisać je pomocnikom.
      </p>
      <ConfirmDialog title="Usunąć pomocnika?" isOpen={deleting !== null} onOpenChange={(o) => !o && setDeleting(null)}>
        <p>{deleting?.name} straci dostęp do linku. Zadania zostaną na Waszej liście, bez przypisania.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setDeleting(null)}>
            Zostaw
          </Button>
          <Button variant="danger" pending={remove.isPending} onPress={() => deleting && remove.mutate(deleting.id)}>
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </main>
  );
}
