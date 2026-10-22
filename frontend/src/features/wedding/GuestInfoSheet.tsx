/** Strona dla gości (pod linkiem RSVP): dojazd, nocleg, transport, dress code, prezenty, kontakt. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { PremiumBadge } from "../../components/Premium";
import { Segmented } from "../../components/Segmented";
import { Sheet } from "../../components/Overlay";
import { Notice, Skeleton } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { ACCENTS, THEMES, accentStyle, type Accent, type GuestTheme } from "../rsvp/themes";
import "../rsvp/rsvp.css";
import { ifMatch, saveErrorMessage } from "./mutations";

type Info = components["schemas"]["GuestInfoOut"];
type Field = "welcome" | "directions" | "accommodation" | "transport" | "dress_code" | "gifts" | "contact";

export const FIELDS: { key: Field; label: string; hint: string }[] = [
  { key: "welcome", label: "Powitanie", hint: "Kilka słów od Was na początek." },
  { key: "directions", label: "Dojazd i parking", hint: "Np. parking za kościołem, wjazd od ul. Lipowej." },
  { key: "accommodation", label: "Nocleg", hint: "Gdzie nocować, do kiedy zgłosić potrzebę noclegu." },
  { key: "transport", label: "Transport", hint: "Np. bus z kościoła na salę o 16:30, powrót o 2:00." },
  { key: "dress_code", label: "Dress code", hint: "Np. elegancko, wygodne buty do ogrodu." },
  { key: "gifts", label: "Prezenty", hint: "Np. zamiast kwiatów — wino albo książka." },
  { key: "contact", label: "Kontakt w dniu ślubu", hint: "Np. świadkowa Kasia — przez nią pytania o organizację." },
];

const infoKey = (weddingId: string) => ["wedding", weddingId, "guest-info"] as const;

export function useGuestInfo(weddingId: string) {
  return useQuery({
    queryKey: infoKey(weddingId),
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/guest-info", { params: { path: { wedding_id: weddingId } }, signal })),
  });
}

export function GuestInfoSheet({ weddingId, isOpen, onClose }: { weddingId: string; isOpen: boolean; onClose: () => void }) {
  const info = useGuestInfo(weddingId);
  return (
    <Sheet title="Strona dla gości" isOpen={isOpen} onOpenChange={(o) => !o && onClose()}>
      {info.isPending && <Skeleton lines={6} />}
      {info.data && <GuestInfoForm key={info.data.version} weddingId={weddingId} info={info.data} onClose={onClose} />}
    </Sheet>
  );
}

function GuestInfoForm({ weddingId, info, onClose }: { weddingId: string; info: Info; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [values, setValues] = useState<Record<Field, string>>(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, info[f.key] ?? ""])) as Record<Field, string>,
  );
  const [published, setPublished] = useState(info.published);
  const [theme, setTheme] = useState<GuestTheme>(info.theme ?? "classic");
  const [accent, setAccent] = useState<Accent | "none">(info.accent ?? "none");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/v1/weddings/{wedding_id}/guest-info", {
          params: { path: { wedding_id: weddingId } },
          body: {
            ...Object.fromEntries(FIELDS.map((f) => [f.key, values[f.key].trim() || null])),
            published,
            theme,
            accent: accent === "none" ? null : accent,
          },
          headers: ifMatch(info.version),
        }),
      ),
    onSuccess: async (saved) => {
      queryClient.setQueryData(infoKey(weddingId), saved);
      onClose();
      toast(saved.published ? "Zapisano — goście zobaczą informacje w swoim linku" : "Zapisano (jeszcze niewidoczne dla gości)");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [infoKey(weddingId)])),
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <p className="text-secondary">
        Goście zobaczą te informacje razem z formularzem potwierdzenia obecności, pod swoim linkiem RSVP. Adresy wydarzeń i punkty
        programu oznaczone „Pokaż gościom” dodajemy automatycznie.
      </p>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {FIELDS.map((f) => (
        <TextField
          key={f.key}
          label={`${f.label} (opcjonalnie)`}
          description={f.hint}
          value={values[f.key]}
          onChange={(v) => setValues((all) => ({ ...all, [f.key]: v }))}
          maxLength={f.key === "contact" ? 500 : 2000}
        />
      ))}
      <fieldset className="plain-fieldset form-stack">
        <legend className="wp-field__label">
          Wygląd strony <PremiumBadge />
        </legend>
        <Segmented label="Motyw" value={theme} options={THEMES} onChange={setTheme} />
        <Segmented
          label="Kolor akcentu"
          variant="chips"
          value={accent}
          options={[
            { value: "none", label: "Domyślny" },
            ...ACCENTS.map((a) => ({
              value: a.id,
              label: (
                <span className="guest-themed" style={accentStyle(a.id)}>
                  <span className="accent-swatch" aria-hidden />
                  {a.label}
                </span>
              ),
            })),
          ]}
          onChange={setAccent}
        />
        <div className="guest-preview guest-themed" data-guest-theme={theme} style={accentStyle(accent === "none" ? null : accent)} aria-label="Podgląd wyglądu">
          <p className="overline">Zaproszenie</p>
          <h1>Ania i Tomek</h1>
          <p className="text-secondary">Tak zobaczą nagłówek strony goście z linkiem do potwierdzenia.</p>
        </div>
      </fieldset>
      <Checkbox isSelected={published} onChange={setPublished}>
        Pokaż gościom
      </Checkbox>
      <Link to={`/w/${weddingId}/podglad-goscia`} className="wp-button wp-button--text" onClick={onClose}>
        Zobacz jak gość (zapisany stan)
      </Link>
      <Button type="submit" block pending={save.isPending}>
        Zapisz
      </Button>
    </Form>
  );
}
