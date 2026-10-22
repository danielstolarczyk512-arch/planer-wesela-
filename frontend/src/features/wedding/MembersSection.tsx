import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Form } from "react-aria-components";

import { useMe } from "../../api/me";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Field";
import { ConfirmDialog } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, Notice, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { formatDate } from "../../lib/format";
import { keys, memberName, ROLE_LABEL, useMembers, type Member, type Wedding } from "./data";
import { useFunders } from "./FundersView";

const ROLE = ROLE_LABEL;

const INVITE_ROLES = [
  { id: "coorganizer", label: "Współorganizator (partner, świadkowa)" },
  { id: "viewer", label: "Tylko podgląd (np. rodzice)" },
  { id: "coordinator", label: "Koordynator dnia (tylko program dnia i kontakty)" },
  { id: "sponsor", label: "Sponsor (np. rodzice: widzi tylko swój wkład)" },
];

/** Członkowie wesela i zaproszenia (zarządza właściciel). Pozostali widzą listę i mogą odejść. */
export function MembersSection({ wedding: w }: { wedding: Wedding }) {
  const members = useMembers(w.id);
  const me = useMe();
  const isOwner = w.my_role === "owner";
  const queryClient = useQueryClient();
  const toast = useToast();
  const [removing, setRemoving] = useState<Member | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invitations = useQuery({
    queryKey: ["wedding", w.id, "invitations"],
    enabled: isOwner,
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/weddings/{wedding_id}/invitations", { params: { path: { wedding_id: w.id } }, signal })),
  });
  const pending = (invitations.data ?? []).filter((i) => !i.accepted_at && !i.revoked_at && new Date(i.expires_at) > new Date());

  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      unwrap(
        api.PATCH("/api/v1/weddings/{wedding_id}/members/{user_id}", {
          params: { path: { wedding_id: w.id, user_id: userId } },
          body: { role: role as "owner" },
        }),
      ),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: keys.members(w.id) });
      toast("Zmieniono rolę");
    },
    onError: (e) => setError(`Nie zmieniono roli. ${userMessage(e)}`),
  });

  const remove = useMutation({
    mutationFn: (m: Member) =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/members/{user_id}", {
          params: { path: { wedding_id: w.id, user_id: m.user_id } },
        }),
      ),
    onSuccess: async (_, m) => {
      setRemoving(null);
      if (m.user_id === me.data?.id) {
        window.location.assign("/?wybierz=1");
        return;
      }
      await queryClient.invalidateQueries({ queryKey: keys.members(w.id) });
      toast("Usunięto z wesela");
    },
    onError: (e) => setError(`Nie usunięto. ${userMessage(e)}`),
  });

  const revoke = useMutation({
    mutationFn: (invitationId: string) =>
      unwrap(
        api.DELETE("/api/v1/weddings/{wedding_id}/invitations/{invitation_id}", {
          params: { path: { wedding_id: w.id, invitation_id: invitationId } },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["wedding", w.id, "invitations"] });
      toast("Wycofano zaproszenie");
    },
    onError: (e) => setError(`Nie wycofano. ${userMessage(e)}`),
  });

  return (
    <section aria-labelledby="members-h" className="form-stack">
      <h2 id="members-h">Osoby z dostępem</h2>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <Card>
        <ul className="row-list">
          {(members.data ?? []).map((m) => {
            const self = m.user_id === me.data?.id;
            return (
              <li key={m.user_id} className="row member-row">
                <div className="row__body">
                  <span className="row__title">
                    {memberName(members.data, m.user_id)}
                    {self && " (Ty)"}
                  </span>
                  <span className="text-secondary">{m.email}</span>
                </div>
                {isOwner && !self ? (
                  <div className="member-row__actions">
                    <Select
                      label={`Rola: ${memberName(members.data, m.user_id)}`}
                      // Rolę sponsora nadaje się przy zaproszeniu (trzeba wskazać, czyj wkład widzi).
                      options={Object.entries(ROLE)
                        .filter(([id]) => id !== "sponsor" || m.role === "sponsor")
                        .map(([id, label]) => ({ id, label }))}
                      value={m.role}
                      onChange={(role) => changeRole.mutate({ userId: m.user_id, role })}
                    />
                    <Button variant="text" onPress={() => setRemoving(m)}>
                      Usuń dostęp
                    </Button>
                  </div>
                ) : (
                  <StatusChip tone="info">{ROLE[m.role] ?? m.role}</StatusChip>
                )}
                {self && !isOwner && (
                  <Button variant="text" onPress={() => setRemoving(m)}>
                    Opuść wesele
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      {isOwner && (
        <>
          {pending.length > 0 && (
            <Card>
              <h3 className="card-title">Zaproszenia czekające na przyjęcie</h3>
              <ul className="row-list">
                {pending.map((i) => (
                  <li key={i.id} className="row">
                    <div className="row__body">
                      <span className="row__title">{i.email}</span>
                      <span className="text-secondary">
                        {ROLE[i.role] ?? i.role} · ważne do {formatDate(i.expires_at.slice(0, 10))}
                      </span>
                    </div>
                    <Button variant="text" pending={revoke.isPending && revoke.variables === i.id} onPress={() => revoke.mutate(i.id)}>
                      Wycofaj
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <InviteForm weddingId={w.id} />
        </>
      )}

      <ConfirmDialog
        title={removing?.user_id === me.data?.id ? "Opuścić wesele?" : "Usunąć dostęp?"}
        isOpen={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
      >
        {removing && (
          <>
            <p>
              {removing.user_id === me.data?.id
                ? "Stracisz dostęp do planu, budżetu i gości tego wesela. Wrócisz tylko po nowym zaproszeniu."
                : `${memberName(members.data, removing.user_id)} straci dostęp do tego wesela. Dane wesela zostają.`}
            </p>
            <div className="wp-sheet__actions">
              <Button variant="secondary" onPress={() => setRemoving(null)}>
                Anuluj
              </Button>
              <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate(removing)}>
                {removing.user_id === me.data?.id ? "Opuść wesele" : "Usuń dostęp"}
              </Button>
            </div>
          </>
        )}
      </ConfirmDialog>
    </section>
  );
}

function InviteForm({ weddingId }: { weddingId: string }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("coorganizer");
  const [funder, setFunder] = useState<string | null>(null);
  const funders = useFunders(weddingId, role === "sponsor");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [key, setKey] = useState(newIdempotencyKey);
  const queryClient = useQueryClient();
  const toast = useToast();
  const invite = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/weddings/{wedding_id}/invitations", {
          params: { path: { wedding_id: weddingId } },
          body: { email: email.trim(), role: role as "coorganizer", funder_id: role === "sponsor" ? funder : null },
          headers: { "Idempotency-Key": key },
        }),
      ),
    onSuccess: async (i) => {
      setEmail("");
      setKey(newIdempotencyKey());
      await queryClient.invalidateQueries({ queryKey: ["wedding", weddingId, "invitations"] });
      toast(`Wysłaliśmy zaproszenie na ${i.email}`);
    },
  });
  return (
    <Card>
      <Form
        className="form-stack"
        validationBehavior="aria"
        onSubmit={(e) => {
          e.preventDefault();
          if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
            setEmailError("Wpisz adres e-mail, np. partner@example.com.");
            return;
          }
          setEmailError(null);
          invite.mutate();
        }}
      >
        <h3 className="card-title">Zaproś partnera lub pomocnika</h3>
        <p className="text-secondary">
          Wyślemy e-mail z linkiem ważnym 14 dni. Osoba musi założyć konto na ten sam adres.
        </p>
        {invite.isError && (
          <Notice tone="error" live>
            Nie wysłano. {userMessage(invite.error)}
          </Notice>
        )}
        <TextField label="E-mail" type="email" inputMode="email" value={email} onChange={setEmail} error={emailError} isRequired />
        <Select label="Rola" options={INVITE_ROLES} value={role} onChange={setRole} />
        {role === "sponsor" &&
          (funders.data && funders.data.funders.length === 0 ? (
            <Notice tone="info">
              Najpierw dodajcie sponsora w Budżet → <Link to={`/w/${weddingId}/sponsorzy`}>Kto płaci</Link>.
            </Notice>
          ) : (
            <Select
              label="Czyj wkład zobaczy"
              options={(funders.data?.funders ?? []).map((f) => ({ id: f.id, label: f.name }))}
              value={funder}
              onChange={setFunder}
              isRequired
            />
          ))}
        <Button type="submit" pending={invite.isPending}>
          Wyślij zaproszenie
        </Button>
      </Form>
    </Card>
  );
}
