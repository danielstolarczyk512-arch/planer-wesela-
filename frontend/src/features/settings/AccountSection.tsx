import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";
import { useNavigate } from "react-router";

import { logout } from "../../api/auth";
import { api, unwrap } from "../../api/client";
import { downloadAuthorized } from "../../api/download";
import { ApiError, userMessage } from "../../api/errors";
import { useMe } from "../../api/me";
import { Button } from "../../components/Button";
import { PasswordField, TextField } from "../../components/Field";
import { ConfirmDialog } from "../../components/Overlay";
import { Segmented } from "../../components/Segmented";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";
import { MfaSection } from "./MfaSection";

/** Nazwa urządzenia z nagłówka User-Agent (bez bibliotek): „Chrome · Windows”. */
export function deviceName(ua: string | null | undefined): string {
  if (!ua) return "Nieznane urządzenie";
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /Firefox\//.test(ua)
      ? "Firefox"
      : /Chrome\//.test(ua)
        ? "Chrome"
        : /Safari\//.test(ua)
          ? "Safari"
          : "Przeglądarka";
  const os = /iPhone|iPad/.test(ua)
    ? "iPhone / iPad"
    : /Android/.test(ua)
      ? "Android"
      : /Windows/.test(ua)
        ? "Windows"
        : /Mac OS X/.test(ua)
          ? "macOS"
          : /Linux/.test(ua)
            ? "Linux"
            : null;
  return os ? `${browser} · ${os}` : browser;
}

function passwordProblem(e: unknown, field: string): string | null {
  if (e instanceof ApiError) {
    const f = e.fieldErrors.filter((x) => x.field === field).map((x) => x.message);
    if (f.length) return f.join(" ");
  }
  return null;
}

export function AccountSection() {
  const me = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState<string | null>(null);
  const value = name ?? me.data?.display_name ?? "";

  const saveName = useMutation({
    mutationFn: () => unwrap(api.PATCH("/api/v1/me", { body: { display_name: value.trim() || null } })),
    onSuccess: async () => {
      setName(null);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast("Zapisano imię");
    },
  });

  const resend = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/verify-email/resend")),
    onSuccess: () => toast("Wysłaliśmy nowy kod i link potwierdzający"),
  });

  const [code, setCode] = useState("");
  const verifyCode = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/verify-email/code", { body: { code: code.trim() } })),
    onSuccess: async () => {
      setCode("");
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast("Adres e-mail potwierdzony");
    },
  });

  if (!me.data) return null;
  const m = me.data;

  return (
    <>
      <section aria-labelledby="account-h" className="form-stack">
        <h2 id="account-h">Konto</h2>
        <Card className="form-stack">
          <div className="section-head">
            <span className="row__body">
              <span className="text-secondary">E-mail</span>
              <strong>{m.email}</strong>
            </span>
            {m.email_verified ? (
              <StatusChip tone="success">Potwierdzony</StatusChip>
            ) : (
              <StatusChip tone="warning">Niepotwierdzony</StatusChip>
            )}
          </div>
          {!m.email_verified && (
            <>
              <Form
                className="form-stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  verifyCode.mutate();
                }}
              >
                <TextField
                  label="Kod z e-maila (6 cyfr)"
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(v) => setCode(v.replace(/\D/g, ""))}
                />
                {verifyCode.isError && (
                  <Notice tone="error" live>
                    {userMessage(verifyCode.error)}
                  </Notice>
                )}
                <Button type="submit" pending={verifyCode.isPending} isDisabled={code.length !== 6}>
                  Potwierdź kodem
                </Button>
              </Form>
              {resend.isError && (
                <Notice tone="error" live>
                  {userMessage(resend.error)}
                </Notice>
              )}
              <Button variant="secondary" pending={resend.isPending} isDisabled={resend.isSuccess} onPress={() => resend.mutate()}>
                {resend.isSuccess ? "Wysłano — sprawdź skrzynkę" : "Wyślij ponownie kod i link"}
              </Button>
            </>
          )}
          <Form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              saveName.mutate();
            }}
          >
            <TextField label="Imię widoczne dla współorganizatorów" autoComplete="given-name" value={value} onChange={setName} />
            {name !== null && (
              <Button type="submit" variant="secondary" pending={saveName.isPending}>
                Zapisz imię
              </Button>
            )}
          </Form>
        </Card>
      </section>
      <NotificationsSection />
      <PasswordSection />
      <MfaSection enabled={m.mfa_enabled ?? false} codesLeft={m.mfa_recovery_codes_left ?? null} />
      <SessionsSection />
      <DataSection deletionScheduledAt={m.deletion_scheduled_at ?? null} />
    </>
  );
}

const DIGESTS: { value: "daily" | "weekly" | "off"; label: string }[] = [
  { value: "daily", label: "Codziennie" },
  { value: "weekly", label: "Co tydzień" },
  { value: "off", label: "Wyłączone" },
];

const CONSENT_LABEL: Record<string, string> = {
  terms: "Regulamin",
  privacy: "Polityka prywatności",
  marketing: "Informacje marketingowe",
  ai_external_processing: "Analiza AI u zewnętrznego dostawcy",
};

/** Podsumowania e-mail (zadania i płatności) oraz historia zgód. */
function NotificationsSection() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const settings = useQuery({
    queryKey: ["me", "notifications"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/me/notifications", { signal })),
  });
  const consents = useQuery({
    queryKey: ["me", "consents"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/me/consents", { signal })),
  });
  const save = useMutation({
    mutationFn: (digest: "daily" | "weekly" | "off") => unwrap(api.PUT("/api/v1/me/notifications", { body: { digest } })),
    onSuccess: async (r) => {
      queryClient.setQueryData(["me", "notifications"], r);
      toast(r.digest === "off" ? "Wyłączono podsumowania e-mail" : "Zapisano częstotliwość podsumowań");
    },
  });
  return (
    <section aria-labelledby="notify-h" className="form-stack">
      <h2 id="notify-h">Powiadomienia</h2>
      <Card className="form-stack">
        {settings.data && (
          <Segmented
            label="Podsumowanie e-mail (zadania i płatności)"
            value={save.variables ?? settings.data.digest}
            options={DIGESTS}
            onChange={(v) => save.mutate(v)}
          />
        )}
        {save.isError && (
          <Notice tone="error" live>
            {userMessage(save.error)}
          </Notice>
        )}
        <p className="text-secondary">Jedna wiadomość zamiast wielu: co jest do zrobienia i do zapłaty w najbliższym czasie.</p>
        {(consents.data?.length ?? 0) > 0 && (
          <>
            <h3>Zgody</h3>
            <ul className="row-list">
              {consents.data!.map((c) => (
                <li key={`${c.type}-${c.granted_at}`} className="row">
                  <span className="row__body">
                    <span className="row__title">{CONSENT_LABEL[c.type] ?? c.type}</span>
                    <span className="text-secondary">
                      {c.withdrawn_at
                        ? `wycofana ${formatDate(c.withdrawn_at.slice(0, 10))}`
                        : `udzielona ${formatDate(c.granted_at.slice(0, 10))}`}
                      {c.document_version ? ` · wersja ${c.document_version}` : ""}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </section>
  );
}

function PasswordSection() {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [errors, setErrors] = useState<{ current?: string; next?: string }>({});
  const change = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/password", { body: { current_password: current, new_password: next } })),
    onSuccess: () => {
      setOpen(false);
      setCurrent("");
      setNext("");
      toast("Hasło zmienione. Pozostałe urządzenia zostały wylogowane.");
    },
    onError: (e) => {
      const pw = passwordProblem(e, "new_password");
      if (pw) setErrors({ next: pw });
      else if (e instanceof ApiError && (e.status === 401 || e.status === 403 || e.code.includes("password")))
        setErrors({ current: "Obecne hasło jest nieprawidłowe." });
    },
  });
  return (
    <section aria-labelledby="password-h" className="form-stack">
      <h2 id="password-h">Hasło</h2>
      <Card className="form-stack">
        {!open ? (
          <Button variant="secondary" onPress={() => setOpen(true)}>
            Zmień hasło
          </Button>
        ) : (
          <Form
            className="form-stack"
            validationBehavior="aria"
            onSubmit={(e) => {
              e.preventDefault();
              const errs: typeof errors = {};
              if (!current) errs.current = "Wpisz obecne hasło.";
              if (next.length < 10) errs.next = "Hasło musi mieć co najmniej 10 znaków.";
              setErrors(errs);
              if (errs.current || errs.next) return;
              change.mutate();
            }}
          >
            {change.isError && !errors.current && !errors.next && (
              <Notice tone="error" live>
                {userMessage(change.error)}
              </Notice>
            )}
            <PasswordField label="Obecne hasło" autoComplete="current-password" value={current} onChange={setCurrent} error={errors.current} isRequired />
            <PasswordField
              label="Nowe hasło"
              description="Co najmniej 10 znaków. Najlepiej kilka niepowiązanych słów."
              autoComplete="new-password"
              value={next}
              onChange={setNext}
              error={errors.next}
              isRequired
            />
            <div className="wp-sheet__actions">
              <Button variant="secondary" onPress={() => setOpen(false)}>
                Anuluj
              </Button>
              <Button type="submit" pending={change.isPending}>
                Zmień hasło
              </Button>
            </div>
          </Form>
        )}
      </Card>
    </section>
  );
}

function SessionsSection() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const sessions = useQuery({
    queryKey: ["me", "sessions"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/me/sessions", { signal })),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/me/sessions/{session_id}", { params: { path: { session_id: id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me", "sessions"] });
      toast("Wylogowano urządzenie");
    },
  });
  return (
    <section aria-labelledby="sessions-h" className="form-stack">
      <h2 id="sessions-h">Zalogowane urządzenia</h2>
      <Card>
        <ul className="row-list">
          {(sessions.data ?? []).map((s) => (
            <li key={s.id} className="row">
              <span className="row__body">
                <span className="row__title">{deviceName(s.user_agent)}</span>
                <span className="text-secondary">od {formatDate(s.created_at.slice(0, 10))}</span>
              </span>
              {s.current ? (
                <StatusChip tone="info">To urządzenie</StatusChip>
              ) : (
                <Button
                  variant="text"
                  pending={revoke.isPending && revoke.variables === s.id}
                  onPress={() => revoke.mutate(s.id)}
                  aria-label={`Wyloguj: ${deviceName(s.user_agent)}, od ${formatDate(s.created_at.slice(0, 10))}`}
                >
                  Wyloguj
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function DataSection({ deletionScheduledAt }: { deletionScheduledAt: string | null }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const exportData = useMutation({
    mutationFn: () => downloadAuthorized("/api/v1/me/export", `moje-dane-${new Date().toISOString().slice(0, 10)}.json`),
  });

  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/me", { body: { password } })),
    onSuccess: async () => {
      setDeleting(false);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast("Zaplanowano usunięcie konta");
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 401 ? "Nieprawidłowe hasło." : userMessage(e)),
  });

  const cancel = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/cancel-deletion")),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast("Anulowano usunięcie konta");
    },
  });

  return (
    <section aria-labelledby="data-h" className="form-stack">
      <h2 id="data-h">Twoje dane</h2>
      <Card className="form-stack">
        <p className="text-secondary">Kopia wszystkich Twoich danych w pliku JSON (RODO: prawo dostępu i przenoszenia).</p>
        {exportData.isError && (
          <Notice tone="error" live>
            {userMessage(exportData.error)}
          </Notice>
        )}
        <Button variant="secondary" pending={exportData.isPending} onPress={() => exportData.mutate()}>
          Pobierz moje dane
        </Button>
        {deletionScheduledAt ? (
          <Notice tone="warning" title="Konto zostanie usunięte">
            Dane znikną trwale {formatDate(deletionScheduledAt.slice(0, 10))}. Do tego dnia możesz zmienić zdanie.
            <Button variant="secondary" pending={cancel.isPending} onPress={() => cancel.mutate()}>
              Nie usuwaj konta
            </Button>
          </Notice>
        ) : (
          <Button variant="text" onPress={() => setDeleting(true)}>
            Usuń konto
          </Button>
        )}
      </Card>
      <ConfirmDialog title="Usunąć konto?" isOpen={deleting} onOpenChange={setDeleting}>
        <p>
          Po 30 dniach trwale usuniemy konto. Wesela, w których jesteś jedyną osobą, znikną razem z nim; z pozostałych zostaniesz
          wypisany(-a). Do tego czasu możesz się zalogować i anulować usunięcie. Najpierw warto pobrać kopię danych.
        </p>
        <Form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            if (!password) {
              setError("Wpisz hasło, aby potwierdzić.");
              return;
            }
            remove.mutate();
          }}
        >
          <PasswordField label="Hasło" autoComplete="current-password" value={password} onChange={setPassword} error={error} isRequired />
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setDeleting(false)}>
              Anuluj
            </Button>
            <Button type="submit" variant="danger" pending={remove.isPending}>
              Usuń konto
            </Button>
          </div>
        </Form>
      </ConfirmDialog>
      <Button
        variant="text"
        onPress={async () => {
          await logout();
          navigate("/logowanie", { replace: true });
        }}
      >
        Wyloguj się
      </Button>
    </section>
  );
}
