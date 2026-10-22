import { useEffect, useRef, useState } from "react";
import { Form } from "react-aria-components";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";

import { login, loginMfa, useSessionStatus } from "../../api/auth";
import { ApiError, userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { PasswordField, TextField } from "../../components/Field";
import { Notice } from "../../components/Surface";
import "./auth.css";

type Errors = Partial<Record<"email" | "password", string>>;

/** Walidacja przed wysłaniem (pełną sprawdza serwer). Bez biblioteki: dwa proste warunki. */
export function validateLogin(email: string, password: string): Errors {
  const errors: Errors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "Wpisz adres e-mail, np. anna@example.com.";
  if (!password) errors.password = "Wpisz hasło.";
  return errors;
}

/** Bezpieczny powrót: tylko ścieżka w obrębie aplikacji (bez otwartego przekierowania). */
export function safeReturnPath(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

export function LoginPage() {
  const status = useSessionStatus();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const returnTo = safeReturnPath(params.get("powrot"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [waitSeconds, setWaitSeconds] = useState(0);
  const errorRef = useRef<HTMLDivElement>(null);
  const [mfaToken, setMfaToken] = useState<string | null>(null);

  // Limit prób (429): przycisk nieaktywny z odliczaniem z nagłówka Retry-After.
  useEffect(() => {
    if (waitSeconds <= 0) return;
    const t = window.setTimeout(() => setWaitSeconds((s) => s - 1), 1000);
    return () => window.clearTimeout(t);
  }, [waitSeconds]);

  if (status === "signed-in") return <Navigate to={returnTo} replace />;
  if (mfaToken) {
    return (
      <MfaStep
        mfaToken={mfaToken}
        onDone={() => navigate(returnTo, { replace: true })}
        onRestart={(message) => {
          setMfaToken(null);
          setFormError(message);
        }}
      />
    );
  }

  async function submit() {
    const trimmed = email.trim();
    const next = validateLogin(trimmed, password);
    if (next.email || next.password) {
      setErrors(next);
      setFormError(null);
      // Fokus na pierwszym błędnym polu.
      document.getElementById(next.email ? "login-email" : "login-password")?.focus();
      return;
    }
    setErrors({});
    setFormError(null);
    setPending(true);
    try {
      const challenge = await login(trimmed, password);
      if (challenge) {
        // Weryfikacja dwuetapowa: hasło poprawne, teraz kod z aplikacji.
        setPassword("");
        setMfaToken(challenge.mfaToken);
        return;
      }
      navigate(returnTo, { replace: true });
    } catch (e) {
      setPassword("");
      if (e instanceof ApiError && e.status === 401) {
        // Ten sam komunikat dla złego e-maila i hasła (bez ujawniania, czy konto istnieje).
        setFormError("Nieprawidłowy e-mail lub hasło.");
      } else {
        setFormError(userMessage(e));
        if (e instanceof ApiError && e.status === 429) setWaitSeconds(e.retryAfter ?? 60);
      }
      requestAnimationFrame(() => errorRef.current?.querySelector<HTMLElement>(".wp-notice")?.focus());
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <p className="auth-brand" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="auth-brand__icon">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          Nasz dzień
        </p>
        <h1>Zaloguj się</h1>
        <p className="text-secondary">Wasze wesele: oferty, budżet, goście i plan w jednym miejscu.</p>
        <div ref={errorRef}>
          {formError && (
            <Notice tone="error" live>
              {formError}
              {waitSeconds > 0 && <span className="num"> Pozostało {waitSeconds} s.</span>}
            </Notice>
          )}
        </div>
        <Form
          className="auth-form"
          validationBehavior="aria"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <TextField
            id="login-email"
            label="E-mail"
            type="email"
            name="email"
            autoComplete="username"
            inputMode="email"
            value={email}
            onChange={setEmail}
            error={errors.email}
            isRequired
          />
          <PasswordField
            id="login-password"
            label="Hasło"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
            error={errors.password}
            isRequired
          />
          <Button type="submit" block pending={pending} isDisabled={waitSeconds > 0}>
            Zaloguj się
          </Button>
        </Form>
        <nav className="auth-links" aria-label="Konto">
          <Link to="/zapomniane-haslo">Nie pamiętasz hasła?</Link>
          <span>
            Nie masz konta? <Link to="/rejestracja">Załóż konto</Link>
          </span>
        </nav>
      </div>
    </main>
  );
}

/** Drugi krok logowania: kod z aplikacji uwierzytelniającej albo kod zapasowy. */
function MfaStep({ mfaToken, onDone, onRestart }: { mfaToken: string; onDone: () => void; onRestart: (message: string) => void }) {
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    const value = code.trim();
    if (!recovery && !/^\d{6}$/.test(value.replace(/\s/g, ""))) {
      setError("Wpisz 6 cyfr z aplikacji.");
      return;
    }
    if (recovery && value.replace(/[\s-]/g, "").length < 10) {
      setError("Wpisz kod zapasowy, np. abcde-fghjk.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await loginMfa(mfaToken, value);
      onDone();
    } catch (e) {
      setCode("");
      if (e instanceof ApiError && e.code === "mfa.challenge_expired") {
        onRestart("Minęło za dużo czasu. Zaloguj się ponownie.");
        return;
      }
      setError(e instanceof ApiError && e.code === "mfa.invalid_code" ? "Nieprawidłowy kod. Spróbuj ponownie." : userMessage(e));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <p className="auth-brand" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="auth-brand__icon">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          Nasz dzień
        </p>
        <h1>Weryfikacja dwuetapowa</h1>
        <p className="text-secondary">
          {recovery
            ? "Wpisz jeden z kodów zapasowych zapisanych przy włączaniu weryfikacji. Każdy działa tylko raz."
            : "Otwórz aplikację uwierzytelniającą w telefonie i wpisz 6-cyfrowy kod dla „Nasz dzień”."}
        </p>
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <Form
          className="auth-form"
          validationBehavior="aria"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <TextField
            key={recovery ? "recovery" : "totp"}
            label={recovery ? "Kod zapasowy" : "Kod z aplikacji"}
            autoComplete="one-time-code"
            inputMode={recovery ? "text" : "numeric"}
            value={code}
            onChange={setCode}
            isRequired
            autoFocus
          />
          <Button type="submit" block pending={pending}>
            Potwierdź
          </Button>
        </Form>
        <nav className="auth-links" aria-label="Inne możliwości">
          <Button
            variant="text"
            onPress={() => {
              setRecovery((r) => !r);
              setCode("");
              setError(null);
            }}
          >
            {recovery ? "Mam dostęp do aplikacji" : "Nie mam telefonu — użyj kodu zapasowego"}
          </Button>
        </nav>
      </div>
    </main>
  );
}
