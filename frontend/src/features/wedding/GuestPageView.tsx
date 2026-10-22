/** Strona gościa w jednym miejscu: co widzą goście, informacje, komunikat, stół, prezenty i życzenia. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextAreaField } from "../../components/Field";
import { ConfirmDialog } from "../../components/Overlay";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { GUEST_SECTIONS, PrintLink, SectionNav } from "./SectionNav";
import { useCanWrite, useWeddingId } from "./data";
import { GiftsSection } from "./GiftsSection";
import { GuestInfoSheet } from "./GuestInfoSheet";

export function GuestPageView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", id, "guest-page"];
  const path = { params: { path: { wedding_id: id } } };
  const settings = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/guest-page", { ...path, signal })) });
  const [error, setError] = useState<string | null>(null);
  const [infoOpen, setInfoOpen] = useState(false);
  const save = useMutation({
    mutationFn: (body: { show_tables?: boolean; wishes_enabled?: boolean; gifts_enabled?: boolean }) => unwrap(api.PUT("/api/v1/weddings/{wedding_id}/guest-page", { ...path, body })),
    onSuccess: (s) => {
      queryClient.setQueryData(key, s);
      toast("Zapisano");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const s = settings.data;

  return (
    <main className="page enter-tab" aria-labelledby="gpage-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div>
        <h1 id="gpage-h">Strona gościa</h1>
        <p className="text-secondary">
          Każde zaproszenie ma swoją stronę z linku RSVP (lub kodu QR). Tu ustawiacie, co na niej widać — w jednym miejscu.
        </p>
      </div>
      {settings.isPending && <Skeleton lines={4} />}
      {settings.isError && (
        <Notice tone="error" live>
          {userMessage(settings.error)}
        </Notice>
      )}
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {s && (
        <>
          <VisibilityCard weddingId={id} settings={s} canWrite={canWrite} onEditInfo={() => setInfoOpen(true)} />
          <AnnouncementCard key={s.announcement_at ?? "brak"} weddingId={id} settings={s} canWrite={canWrite} queryKey={key} />
          <section className="form-stack" aria-labelledby="tables-h">
            <h2 id="tables-h">Gdzie siedzimy</h2>
            <Card className="form-stack">
              <Checkbox isSelected={s.show_tables} isDisabled={!canWrite || save.isPending} onChange={(v) => save.mutate({ show_tables: v })}>
                Pokaż gościom ich stół i miejsca
              </Checkbox>
              <p className="text-secondary">
                Każde zaproszenie widzi tylko swój stół (bez nazwisk innych gości). Włączcie, gdy plan stołów jest gotowy.
              </p>
            </Card>
          </section>
          <GiftsSection weddingId={id} enabled={s.gifts_enabled} canWrite={canWrite} onToggle={(v) => save.mutate({ gifts_enabled: v })} pending={save.isPending} />
          <WishesSection weddingId={id} enabled={s.wishes_enabled} canWrite={canWrite} onToggle={(v) => save.mutate({ wishes_enabled: v })} pending={save.isPending} />
        </>
      )}
      <GuestInfoSheet
        weddingId={id}
        isOpen={infoOpen}
        onClose={() => {
          setInfoOpen(false);
          void queryClient.invalidateQueries({ queryKey: key });
        }}
      />
    </main>
  );
}

/** „22 października 14:05” (czas polski). */
export function sentAt(iso: string): string {
  return new Date(iso).toLocaleString("pl-PL", { timeZone: "Europe/Warsaw", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
}

type Settings = components["schemas"]["GuestPageSettings"];

/** Części strony gościa: co jest włączone i gdzie to zmienić. */
export function visibilityRows(s: Settings): { label: string; on: boolean; state: string }[] {
  return [
    { label: "Informacje (dojazd, nocleg, dress code…)", on: s.info_published, state: s.info_published ? "widoczne" : "szkic" },
    { label: "Komunikat od pary", on: !!s.announcement, state: s.announcement ? "widoczny" : "brak" },
    { label: "Menu z alergenami", on: s.show_menu, state: s.show_menu ? "widoczne" : "ukryte" },
    { label: "Kursy autokaru do wyboru", on: s.runs_shown > 0, state: s.runs_shown > 0 ? `${s.runs_shown} w RSVP` : "brak" },
    { label: "Propozycje utworów", on: s.song_requests, state: s.song_requests ? "włączone" : "wyłączone" },
    { label: "Gdzie siedzimy", on: s.show_tables, state: s.show_tables ? "widoczne" : "ukryte" },
    { label: "Lista prezentów", on: s.gifts_enabled, state: s.gifts_enabled ? "włączona" : "wyłączona" },
    { label: "Księga życzeń", on: s.wishes_enabled, state: s.wishes_enabled ? "włączona" : "wyłączona" },
  ];
}

const ELSEWHERE: Record<string, { to: string; label: string }> = {
  "Menu z alergenami": { to: "menu", label: "Menu" },
  "Kursy autokaru do wyboru": { to: "logistyka", label: "Transport i noclegi" },
  "Propozycje utworów": { to: "muzyka", label: "Muzyka" },
};

function VisibilityCard({ weddingId, settings: s, canWrite, onEditInfo }: { weddingId: string; settings: Settings; canWrite: boolean; onEditInfo: () => void }) {
  return (
    <section className="form-stack" aria-labelledby="visible-h">
      <div className="section-head section-head--wrap">
        <h2 id="visible-h">Co widzą goście</h2>
        <Link to={`/w/${weddingId}/podglad-goscia`} viewTransition className="wp-button wp-button--text">
          Zobacz jak gość
        </Link>
      </div>
      <Card>
        <ul className="row-list">
          {visibilityRows(s).map((r) => (
            <li key={r.label} className="row">
              <span className="row__body">
                <span className="row__title">{r.label}</span>
                {ELSEWHERE[r.label] && (
                  <Link to={`/w/${weddingId}/${ELSEWHERE[r.label]!.to}`} className="text-secondary">
                    ustawiacie w: {ELSEWHERE[r.label]!.label}
                  </Link>
                )}
              </span>
              <StatusChip tone={r.on ? "success" : "neutral"}>{r.state}</StatusChip>
            </li>
          ))}
        </ul>
        {canWrite && (
          <Button variant="secondary" onPress={onEditInfo}>
            Edytuj informacje i wygląd strony
          </Button>
        )}
      </Card>
    </section>
  );
}

function AnnouncementCard({ weddingId, settings: s, canWrite, queryKey }: { weddingId: string; settings: Settings; canWrite: boolean; queryKey: unknown[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState(s.announcement ?? "");
  const [confirm, setConfirm] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const path = { params: { path: { wedding_id: weddingId } } };
  const save = useMutation({
    mutationFn: (value: string | null) => unwrap(api.PUT("/api/v1/weddings/{wedding_id}/guest-page/announcement", { ...path, body: { text: value } })),
    onSuccess: (fresh) => {
      queryClient.setQueryData(queryKey, fresh);
      toast(fresh.announcement ? "Komunikat widoczny dla gości" : "Usunięto komunikat");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const email = useMutation({
    mutationFn: (dryRun: boolean) => unwrap(api.POST("/api/v1/weddings/{wedding_id}/guest-page/announcement/email", { ...path, body: { dry_run: dryRun } })),
    onSuccess: async (r) => {
      if (r.dry_run) {
        setConfirm(r.recipients);
        return;
      }
      setConfirm(null);
      await queryClient.invalidateQueries({ queryKey });
      toast(`Wysłano do ${r.recipients} rodzin`);
    },
    onError: (e) => {
      setConfirm(null);
      setError(userMessage(e));
    },
  });
  const dirty = text.trim() !== (s.announcement ?? "");
  return (
    <section className="form-stack" aria-labelledby="ann-h">
      <h2 id="ann-h">Komunikat dla gości</h2>
      <Card className="form-stack">
        <p className="text-secondary">
          Np. zmiana godziny ceremonii albo sali. Pokażemy go na górze strony gościa. E-mail wyślemy do rodzin z adresem — bez nowego
          linku, więc kody QR z zaproszeń dalej działają.
        </p>
        {canWrite ? (
          <Form
            className="form-stack"
            aria-label="Komunikat dla gości"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate(text.trim() || null);
            }}
          >
            <TextAreaField label="Treść komunikatu" value={text} onChange={setText} maxLength={500} rows={3} />
            <div className="wp-sheet__actions">
              <Button type="submit" variant="secondary" pending={save.isPending} isDisabled={!dirty}>
                {text.trim() ? "Pokaż gościom" : "Usuń komunikat"}
              </Button>
              {s.announcement && !dirty && !s.announcement_emailed_at && s.households_with_email > 0 && (
                <Button variant="text" pending={email.isPending} onPress={() => email.mutate(true)}>
                  Wyślij e-mailem
                </Button>
              )}
            </div>
          </Form>
        ) : (
          <p>{s.announcement ?? "Brak komunikatu."}</p>
        )}
        {s.announcement_emailed_at && <p className="text-secondary">Wysłano e-mailem: {sentAt(s.announcement_emailed_at)}.</p>}
        {s.announcement && s.households_with_email === 0 && <p className="text-secondary">Żadna rodzina nie ma adresu e-mail — komunikat zobaczą na stronie.</p>}
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
      </Card>
      <ConfirmDialog title="Wysłać komunikat e-mailem?" isOpen={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        <p>
          Wyślemy komunikat do {confirm} z {s.households} rodzin (tych z adresem e-mail). Ten sam komunikat można wysłać tylko raz.
        </p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setConfirm(null)}>
            Anuluj
          </Button>
          <Button pending={email.isPending} onPress={() => email.mutate(false)}>
            Wyślij
          </Button>
        </div>
      </ConfirmDialog>
    </section>
  );
}

function WishesSection({ weddingId, enabled, canWrite, onToggle, pending }: { weddingId: string; enabled: boolean; canWrite: boolean; onToggle: (v: boolean) => void; pending: boolean }) {
  const queryClient = useQueryClient();
  const key = ["wedding", weddingId, "wishes"];
  const wishes = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/wishes", { params: { path: { wedding_id: weddingId } }, signal })),
  });
  const hide = useMutation({
    mutationFn: ({ wish, hidden }: { wish: string; hidden: boolean }) =>
      unwrap(api.PUT("/api/v1/weddings/{wedding_id}/wishes/{wish_id}/hidden", { params: { path: { wedding_id: weddingId, wish_id: wish } }, body: { hidden } })),
    onSuccess: (rows) => queryClient.setQueryData(key, rows),
  });
  const remove = useMutation({
    mutationFn: (wish: string) => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/wishes/{wish_id}", { params: { path: { wedding_id: weddingId, wish_id: wish } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const [deleting, setDeleting] = useState<string | null>(null);
  const rows = wishes.data ?? [];
  return (
    <section className="form-stack" aria-labelledby="wishes-h">
      <div className="section-head section-head--wrap">
        <h2 id="wishes-h">Księga życzeń{rows.length > 0 && <span className="text-secondary num"> · {rows.length}</span>}</h2>
        {rows.length > 0 && <PrintLink kind="zyczenia">Drukuj życzenia</PrintLink>}
      </div>
      <Card className="form-stack">
        <Checkbox isSelected={enabled} isDisabled={!canWrite || pending} onChange={onToggle}>
          Goście mogą zostawić życzenia na swojej stronie (do 5 wpisów na zaproszenie)
        </Checkbox>
      </Card>
      {rows.length === 0 ? (
        enabled && <EmptyState title="Jeszcze bez życzeń">Gdy goście coś napiszą, zobaczycie to tutaj.</EmptyState>
      ) : (
        <Card>
          <ul className="row-list">
            {rows.map((w) => (
              <li key={w.id} className="row">
                <span className="row__body">
                  <span className={w.hidden ? "done-title" : "row__title"}>{w.text}</span>
                  <span className="text-secondary">
                    {w.author}
                    {w.household_name && w.household_name !== w.author && ` · ${w.household_name}`}
                    {w.hidden && " · ukryte (nie trafi do wydruku)"}
                  </span>
                </span>
                {canWrite && (
                  <span className="row-actions">
                    <AriaButton className="wp-icon-button" aria-label={w.hidden ? `Pokaż wpis: ${w.author}` : `Ukryj wpis: ${w.author}`} onPress={() => hide.mutate({ wish: w.id, hidden: !w.hidden })}>
                      {w.hidden ? <Eye aria-hidden size={20} /> : <EyeOff aria-hidden size={20} />}
                    </AriaButton>
                    <AriaButton className="wp-icon-button" aria-label={`Usuń wpis: ${w.author}`} onPress={() => setDeleting(w.id)}>
                      <Trash2 aria-hidden size={20} />
                    </AriaButton>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <ConfirmDialog title="Usunąć wpis?" isOpen={deleting !== null} onOpenChange={(o) => !o && setDeleting(null)}>
        <p>Wpis zniknie na stałe. Jeśli chcecie go tylko schować, użyjcie „Ukryj”.</p>
        <div className="wp-sheet__actions">
          <Button variant="secondary" onPress={() => setDeleting(null)}>
            Zostaw
          </Button>
          <Button
            variant="danger"
            pending={remove.isPending}
            onPress={() => {
              if (deleting) remove.mutate(deleting);
              setDeleting(null);
            }}
          >
            Usuń
          </Button>
        </div>
      </ConfirmDialog>
    </section>
  );
}
