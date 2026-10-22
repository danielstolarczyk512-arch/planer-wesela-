/** Gotowe wiadomości do usługodawcy: wybór sytuacji, tekst z danymi wesela, kopiowanie i e-mail. */
import { Copy, Mail } from "lucide-react";
import { useState } from "react";

import { Button } from "../../components/Button";
import { TextAreaField } from "../../components/Field";
import { Select } from "../../components/Select";
import { Card } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";
import { MESSAGE_KINDS, messageSubject, messageText, type MessageContext, type MessageKind } from "../../lib/vendorMessages";
import type { Wedding } from "./data";

const CEREMONY: Record<string, string> = { concordat: "kościelny", civil: "cywilny", religious_other: "wyznaniowy", humanist: "humanistyczny" };

/** Dane wesela do wiadomości (data dokładna albo miesiąc, liczba gości, rodzaj ślubu). */
export function contextOf(w: Wedding, vendor: { name: string; category: string; city?: string | null }): MessageContext {
  const month = w.planned_month
    ? new Date(`${w.planned_month.slice(0, 7)}-15T12:00:00Z`).toLocaleDateString("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" })
    : null;
  return {
    vendorName: vendor.name,
    category: vendor.category,
    weddingDate: w.wedding_date ? formatDate(w.wedding_date) : month,
    city: w.city ?? vendor.city ?? null,
    guests: w.guest_count_planned ?? null,
    ceremony: CEREMONY[w.ceremony_type] ?? null,
    signature: w.name,
  };
}

export function VendorMessages({ wedding, vendor }: { wedding: Wedding; vendor: { name: string; category: string; city?: string | null; email?: string | null; status: string } }) {
  const toast = useToast();
  const [kind, setKind] = useState<MessageKind>(vendor.status === "booked" ? "contract" : "inquiry");
  const ctx = contextOf(wedding, vendor);
  const generated = messageText(kind, ctx);
  const [edited, setEdited] = useState<{ kind: MessageKind; text: string } | null>(null);
  const text = edited?.kind === kind ? edited.text : generated;
  const mailto = vendor.email ? `mailto:${vendor.email}?subject=${encodeURIComponent(messageSubject(kind, ctx))}&body=${encodeURIComponent(text)}` : null;

  return (
    <section className="form-stack" aria-labelledby="vmsg-h">
      <h2 id="vmsg-h">Napisz do usługodawcy</h2>
      <Card className="form-stack">
        <p className="text-secondary">Gotowy tekst z danymi Waszego wesela — popraw, skopiuj i wyślij e-mailem lub w komunikatorze. Aplikacja nic nie wysyła sama.</p>
        <Select label="Sytuacja" options={MESSAGE_KINDS.map((k) => ({ id: k.id, label: k.label }))} value={kind} onChange={(v) => setKind(v as MessageKind)} />
        <TextAreaField label="Treść wiadomości" value={text} onChange={(v) => setEdited({ kind, text: v })} rows={9} />
        <div className="wp-sheet__actions">
          <Button
            variant="secondary"
            icon={<Copy aria-hidden size={18} />}
            onPress={async () => {
              try {
                await navigator.clipboard.writeText(text);
                toast("Skopiowano wiadomość");
              } catch {
                toast("Nie udało się skopiować — zaznaczcie tekst ręcznie");
              }
            }}
          >
            Kopiuj
          </Button>
          {mailto && (
            <a className="wp-button wp-button--text" href={mailto}>
              <Mail aria-hidden size={18} /> Otwórz w poczcie
            </a>
          )}
        </div>
      </Card>
    </section>
  );
}
