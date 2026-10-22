import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Form } from "react-aria-components";

import { api, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, PasswordField, TextField } from "../../components/Field";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import "../auth/auth.css";

type Setup = components["schemas"]["MfaSetupOut"];
type Step = { kind: "idle" } | { kind: "password" } | { kind: "scan"; setup: Setup } | { kind: "codes"; codes: string[] };

/** „ABCD EFGH …” — sekret w grupach po 4 znaki do ręcznego przepisania. */
export function groupSecret(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

function codeMessage(e: unknown): string {
  if (e instanceof ApiError && (e.code === "mfa.invalid_code" || e.code === "auth.invalid_credentials")) {
    return e.code === "mfa.invalid_code" ? "Kod się nie zgadza. Wpisz aktualny kod z aplikacji." : "Nieprawidłowe hasło.";
  }
  return userMessage(e);
}

function downloadCodes(codes: string[]) {
  const text = `Nasz dzień — kody zapasowe (każdy działa jeden raz)\r\n\r\n${codes.join("\r\n")}\r\n`;
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "nasz-dzien-kody-zapasowe.txt";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function MfaSection({ enabled, codesLeft }: { enabled: boolean; codesLeft: number | null }) {
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [manage, setManage] = useState<"disable" | "codes" | null>(null);

  return (
    <section aria-labelledby="mfa-h" className="form-stack">
      <h2 id="mfa-h">Weryfikacja dwuetapowa</h2>
      <Card className="form-stack">
        <div className="section-head">
          <span className="row__body">
            <span className="row__title">Kod z telefonu przy logowaniu</span>
            <span className="text-secondary">
              {enabled
                ? codesLeft !== null && `Kody zapasowe: ${codesLeft} z 10`
                : "Chroni konto, nawet gdy ktoś pozna hasło. Potrzebna aplikacja, np. Google Authenticator, Microsoft Authenticator, Aegis."}
            </span>
          </span>
          {enabled ? <StatusChip tone="success">Włączona</StatusChip> : <StatusChip tone="neutral">Wyłączona</StatusChip>}
        </div>
        {enabled && codesLeft !== null && codesLeft <= 3 && (
          <Notice tone="warning">Zostało mało kodów zapasowych. Wygeneruj nowe, zanim się skończą.</Notice>
        )}

        {!enabled && step.kind === "idle" && (
          <Button variant="secondary" icon={<ShieldCheck aria-hidden size={20} />} onPress={() => setStep({ kind: "password" })}>
            Włącz weryfikację dwuetapową
          </Button>
        )}
        {!enabled && step.kind === "password" && <SetupPassword onCancel={() => setStep({ kind: "idle" })} onReady={(setup) => setStep({ kind: "scan", setup })} />}
        {!enabled && step.kind === "scan" && (
          <SetupScan setup={step.setup} onCancel={() => setStep({ kind: "idle" })} onEnabled={(codes) => setStep({ kind: "codes", codes })} />
        )}
        {step.kind === "codes" && <RecoveryCodes codes={step.codes} onDone={() => setStep({ kind: "idle" })} />}

        {enabled && step.kind === "idle" && !manage && (
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setManage("codes")}>
              Nowe kody zapasowe
            </Button>
            <Button variant="text" onPress={() => setManage("disable")}>
              Wyłącz
            </Button>
          </div>
        )}
        {enabled && manage && (
          <ConfirmWithCode
            mode={manage}
            onCancel={() => setManage(null)}
            onCodes={(codes) => {
              setManage(null);
              setStep({ kind: "codes", codes });
            }}
            onDisabled={() => setManage(null)}
          />
        )}
      </Card>
    </section>
  );
}

function SetupPassword({ onCancel, onReady }: { onCancel: () => void; onReady: (s: Setup) => void }) {
  const [password, setPassword] = useState("");
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/mfa/setup", { body: { password } })),
    onSuccess: onReady,
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (password) start.mutate();
      }}
    >
      <PasswordField
        label="Hasło (dla bezpieczeństwa)"
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
        error={start.isError ? codeMessage(start.error) : null}
        isRequired
      />
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={onCancel}>
          Anuluj
        </Button>
        <Button type="submit" pending={start.isPending}>
          Dalej
        </Button>
      </div>
    </Form>
  );
}

function SetupScan({ setup, onCancel, onEnabled }: { setup: Setup; onCancel: () => void; onEnabled: (codes: string[]) => void }) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const enable = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/mfa/enable", { body: { code: code.replace(/\s/g, "") } })),
    onSuccess: async (r) => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      onEnabled(r.recovery_codes);
    },
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (code.trim()) enable.mutate();
      }}
    >
      <ol className="mfa-steps">
        <li>Otwórz aplikację uwierzytelniającą i dodaj konto (zeskanuj kod QR).</li>
        <li>Wpisz 6-cyfrowy kod, który pokaże aplikacja.</li>
      </ol>
      {/* SVG z naszego serwera jako obraz (bez wstawiania HTML na stronę). */}
      <img
        className="mfa-qr"
        src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
        alt="Kod QR do zeskanowania w aplikacji uwierzytelniającej"
        width={200}
        height={200}
      />
      <p className="text-secondary">
        Nie możesz zeskanować? Wpisz w aplikacji klucz: <code className="mfa-secret">{groupSecret(setup.secret)}</code>
      </p>
      <TextField
        label="Kod z aplikacji"
        inputMode="numeric"
        autoComplete="one-time-code"
        value={code}
        onChange={setCode}
        error={enable.isError ? codeMessage(enable.error) : null}
        isRequired
      />
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={onCancel}>
          Anuluj
        </Button>
        <Button type="submit" pending={enable.isPending}>
          Włącz
        </Button>
      </div>
    </Form>
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const toast = useToast();
  const [saved, setSaved] = useState(false);
  return (
    <div className="form-stack">
      <Notice tone="success" title="Weryfikacja dwuetapowa działa" live>
        Zapisz kody zapasowe w bezpiecznym miejscu. Pozwolą się zalogować, gdy zgubisz telefon. Pokazujemy je tylko teraz.
      </Notice>
      <ul className="mfa-codes num" aria-label="Kody zapasowe">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={() => downloadCodes(codes)}>
          Pobierz jako plik
        </Button>
        <Button
          variant="secondary"
          onPress={() =>
            void navigator.clipboard
              .writeText(codes.join("\n"))
              .then(() => toast("Skopiowano kody"))
              .catch(() => toast("Nie udało się skopiować — zapisz kody ręcznie"))
          }
        >
          Kopiuj
        </Button>
      </div>
      <Checkbox isSelected={saved} onChange={setSaved}>
        Zapisałem/am kody w bezpiecznym miejscu
      </Checkbox>
      <Button isDisabled={!saved} onPress={onDone}>
        Gotowe
      </Button>
    </div>
  );
}

function ConfirmWithCode({
  mode,
  onCancel,
  onCodes,
  onDisabled,
}: {
  mode: "disable" | "codes";
  onCancel: () => void;
  onCodes: (codes: string[]) => void;
  onDisabled: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const run = useMutation({
    mutationFn: async () => {
      const body = { password, code: code.trim() };
      if (mode === "disable") {
        await unwrap(api.POST("/api/v1/me/mfa/disable", { body }));
        return null;
      }
      return (await unwrap(api.POST("/api/v1/me/mfa/recovery-codes", { body }))).recovery_codes;
    },
    onSuccess: async (codes) => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      if (codes) onCodes(codes);
      else {
        toast("Wyłączono weryfikację dwuetapową");
        onDisabled();
      }
    },
  });
  return (
    <Form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (password && code.trim()) run.mutate();
      }}
    >
      <p className="text-secondary">
        {mode === "disable"
          ? "Po wyłączeniu do logowania wystarczy samo hasło."
          : "Dotychczasowe kody zapasowe przestaną działać."}
      </p>
      {run.isError && (
        <Notice tone="error" live>
          {codeMessage(run.error)}
        </Notice>
      )}
      <PasswordField label="Hasło" autoComplete="current-password" value={password} onChange={setPassword} isRequired />
      <TextField
        label={mode === "disable" ? "Kod z aplikacji lub zapasowy" : "Kod z aplikacji"}
        inputMode={mode === "disable" ? "text" : "numeric"}
        autoComplete="one-time-code"
        value={code}
        onChange={setCode}
        isRequired
      />
      <div className="wp-sheet__actions">
        <Button variant="secondary" onPress={onCancel}>
          Anuluj
        </Button>
        <Button type="submit" variant={mode === "disable" ? "danger" : "primary"} pending={run.isPending}>
          {mode === "disable" ? "Wyłącz" : "Wygeneruj nowe kody"}
        </Button>
      </div>
    </Form>
  );
}
