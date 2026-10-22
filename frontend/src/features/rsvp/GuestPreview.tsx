/**
 * „Zobacz jak gość”: strona z linku RSVP oczami gościa — prawdziwe wydarzenia, program „dla
 * gości”, informacje i wygląd, ale fikcyjna rodzina. Nic się nie wysyła.
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import { Notice, Skeleton } from "../../components/Surface";
import { useWeddingId } from "../wedding/data";
import "../auth/auth.css";
import "./rsvp.css";
import { RsvpForm } from "./RsvpPage";
import { accentStyle } from "./themes";

export function GuestPreview() {
  const id = useWeddingId();
  const view = useQuery({
    queryKey: ["wedding", id, "guest-preview"],
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/guest-info/preview", { params: { path: { wedding_id: id } }, signal })),
  });
  return (
    <div className="page form-stack">
      <Link to={`/w/${id}/goscie`} viewTransition className="wp-button wp-button--text back-link">
        ← Goście
      </Link>
      <Notice tone="info" title="Podgląd strony gościa">
        Tak zobaczy stronę rodzina z linkiem do potwierdzenia obecności (tu z przykładowymi imionami). Odpowiedzi w podglądzie się
        nie wysyłają.
        {view.data && view.data.preview_info_published === false && view.data.info && (
          <> Informacje dla gości są jeszcze nieopublikowane — goście ich nie widzą, dopóki nie zaznaczycie „Pokaż gościom”.</>
        )}
      </Notice>
      <main
        className="auth-page rsvp-page guest-themed guest-preview-page"
        aria-labelledby="rsvp-h"
        data-guest-theme={view.data?.theme.style ?? "classic"}
        style={accentStyle(view.data?.theme.accent)}
      >
        <div className="auth-card rsvp-card">
          {view.isPending && <Skeleton lines={6} />}
          {view.isError && (
            <Notice tone="error" live>
              {userMessage(view.error)}
            </Notice>
          )}
          {view.data && <RsvpForm token="" view={view.data} preview />}
        </div>
      </main>
    </div>
  );
}
