import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Form } from "react-aria-components";
import { Link, Navigate, useSearchParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Checkbox, PasswordField, TextField } from "../../components/Field";
import { Notice } from "../../components/Surface";
import "./auth.css";

/** Rama stron konta: znak, karta, linki pomocnicze. */
export function AuthLayout({ title, lead, children, footer }: { title: string; lead?: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <main className="auth-page" aria-labelledby="auth-h">
      <div className="auth-card">
        <p className="auth-brand" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="auth-brand__icon">
            <circle cx="9" cy="12" r="5" />
            <circle cx="15" cy="12" r="5" />
          </svg>
          Nasz dzień
        </p>
        <h1 id="auth-h">{title}</h1>
        {lead && <p className="text-secondary">{lead}</p>}
        {children}
        {footer && <nav className="auth-links" aria-label="Konto">{footer}</nav>}
      </div>
    </main>
  );
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Komunikat dla pola hasła z błędu API (zxcvbn i reguły serwera). */
function passwordError(e: unknown, field: string): string | null {
  if (e instanceof ApiError) {
    const f = e.fieldErrors.filter((x) => x.field === field).map((x) => x.message);
    if (f.length) return f.join(" ");
  }
  return null;
}

/* --------------------------------------------------------------------------- rejestracja */

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [terms, setTerms] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; terms?: string }>({});
  const register = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/auth/register", {
          body: { email: email.trim(), password, display_name: name.trim() || null, accept_terms: true, accept_privacy: true },
        }),
      ),
    onError: (e) => {
      const pw = passwordError(e, "password");
      if (pw) setErrors({ password: pw });
    },
  });

  if (register.isSuccess) {
    return (
      <AuthLayout title="Sprawdź skrzynkę" footer={<Link to="/logowanie">Przejdź do logowania</Link>}>
        <Notice tone="success" live>
          Wysłaliśmy link na adres {email.trim()}. Kliknij go, aby potwierdzić konto. Wiadomość może trafić do spamu.
        </Notice>
        <p className="text-secondary">Możesz już się zalogować — potwierdzenie adresu dokończysz później.</p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Załóż konto"
      lead="Planujcie wesele razem: oferty, budżet, goście i plan dnia."
      footer={
        <>
          Masz już konto? <Link to="/logowanie">Zaloguj się</Link>
        </>
      }
    >
      {register.isError && !errors.password && (
        <Notice tone="error" live>
          {userMessage(register.error)}
        </Notice>
      )}
      <Form
        className="auth-form"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          if (!EMAIL.test(email.trim())) next.email = "Wpisz adres e-mail, np. ania@example.com.";
          if (password.length < 10) next.password = "Hasło musi mieć co najmniej 10 znaków.";
          if (!terms) next.terms = "Aby założyć konto, zaakceptuj regulamin i politykę prywatności.";
          setErrors(next);
          if (next.email || next.password || next.terms) return;
          register.mutate();
        }}
      >
        <TextField
          label="E-mail"
          type="email"
          inputMode="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
          error={errors.email}
          isRequired
        />
        <PasswordField
          label="Hasło"
          description="Co najmniej 10 znaków. Najlepiej kilka niepowiązanych słów, np. „kawa-rower-tulipan”."
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          isRequired
        />
        <TextField label="Imię (opcjonalnie)" autoComplete="given-name" value={name} onChange={setName} />
        <p className="text-secondary">
          Przeczytaj{" "}
          <Link to="/regulamin" target="_blank">
            regulamin
          </Link>{" "}
          i{" "}
          <Link to="/prywatnosc" target="_blank">
            politykę prywatności
          </Link>{" "}
          (otwierają się w nowej karcie).
        </p>
        <Checkbox isSelected={terms} onChange={setTerms} isInvalid={!!errors.terms}>
          Akceptuję regulamin i politykę prywatności
        </Checkbox>
        {errors.terms && (
          <p className="wp-field__error" role="alert">
            {errors.terms}
          </p>
        )}
        <Button type="submit" block pending={register.isPending}>
          Załóż konto
        </Button>
      </Form>
    </AuthLayout>
  );
}

/* --------------------------------------------------------------- potwierdzenie e-maila */

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const started = useRef(false);
  const verify = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/verify-email", { body: { token } })),
  });
  useEffect(() => {
    // Token jest jednorazowy: wysyłamy go tylko raz (StrictMode uruchamia efekt dwa razy).
    if (!started.current && token.length >= 20) {
      started.current = true;
      verify.mutate();
    }
  }, [token, verify]);

  if (token.length < 20 || verify.isError) {
    return (
      <AuthLayout title="Link nie działa" footer={<Link to="/logowanie">Przejdź do logowania</Link>}>
        <Notice tone="error" live>
          Link jest nieprawidłowy, wygasł albo został już użyty. Po zalogowaniu wyślesz nowy z ustawień konta.
        </Notice>
      </AuthLayout>
    );
  }
  if (verify.isSuccess) {
    return (
      <AuthLayout title="Adres potwierdzony" footer={<Link to="/">Przejdź do aplikacji</Link>}>
        <Notice tone="success" live>
          Dziękujemy! Twoje konto jest aktywne.
        </Notice>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Potwierdzamy adres…">
      <p className="text-secondary" aria-live="polite">
        Chwileczkę.
      </p>
    </AuthLayout>
  );
}

/* ------------------------------------------------------------------------- reset hasła */

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/password/forgot", { body: { email: email.trim() } })),
  });

  if (send.isSuccess) {
    return (
      <AuthLayout title="Sprawdź skrzynkę" footer={<Link to="/logowanie">Wróć do logowania</Link>}>
        <Notice tone="success" live>
          Jeśli konto o adresie {email.trim()} istnieje, wysłaliśmy link do ustawienia nowego hasła. Link jest ważny przez
          ograniczony czas.
        </Notice>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout
      title="Nie pamiętasz hasła?"
      lead="Podaj adres e-mail konta — wyślemy link do ustawienia nowego hasła."
      footer={<Link to="/logowanie">Wróć do logowania</Link>}
    >
      {send.isError && (
        <Notice tone="error" live>
          {userMessage(send.error)}
        </Notice>
      )}
      <Form
        className="auth-form"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (!EMAIL.test(email.trim())) {
            setError("Wpisz adres e-mail, np. ania@example.com.");
            return;
          }
          setError(null);
          send.mutate();
        }}
      >
        <TextField
          label="E-mail"
          type="email"
          inputMode="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
          error={error}
          isRequired
        />
        <Button type="submit" block pending={send.isPending}>
          Wyślij link
        </Button>
      </Form>
    </AuthLayout>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [errors, setErrors] = useState<{ password?: string; repeat?: string }>({});
  const reset = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/password/reset", { body: { token, new_password: password } })),
    onError: (e) => {
      const pw = passwordError(e, "new_password");
      if (pw) setErrors({ password: pw });
    },
  });

  if (token.length < 20) return <Navigate to="/zapomniane-haslo" replace />;
  if (reset.isSuccess) {
    return (
      <AuthLayout title="Hasło zmienione" footer={<Link to="/logowanie">Zaloguj się</Link>}>
        <Notice tone="success" live>
          Nowe hasło działa. Ze względów bezpieczeństwa wylogowaliśmy wszystkie urządzenia.
        </Notice>
      </AuthLayout>
    );
  }
  const tokenError = reset.isError && !errors.password;
  return (
    <AuthLayout title="Ustaw nowe hasło" footer={<Link to="/logowanie">Wróć do logowania</Link>}>
      {tokenError && (
        <Notice tone="error" live>
          {reset.error instanceof ApiError && reset.error.status === 422
            ? "Link wygasł albo został już użyty. "
            : `${userMessage(reset.error)} `}
          <Link to="/zapomniane-haslo">Wyślij nowy link</Link>
        </Notice>
      )}
      <Form
        className="auth-form"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          const next: typeof errors = {};
          if (password.length < 10) next.password = "Hasło musi mieć co najmniej 10 znaków.";
          if (repeat !== password) next.repeat = "Hasła się różnią.";
          setErrors(next);
          if (next.password || next.repeat) return;
          reset.mutate();
        }}
      >
        <PasswordField
          label="Nowe hasło"
          description="Co najmniej 10 znaków. Najlepiej kilka niepowiązanych słów."
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          isRequired
        />
        <PasswordField
          label="Powtórz hasło"
          autoComplete="new-password"
          value={repeat}
          onChange={setRepeat}
          error={errors.repeat}
          isRequired
        />
        <Button type="submit" block pending={reset.isPending}>
          Ustaw hasło
        </Button>
      </Form>
    </AuthLayout>
  );
}
