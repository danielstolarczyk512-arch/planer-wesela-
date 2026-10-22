import { useMutation } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";

import { useMe } from "../../api/me";
import { api, unwrap } from "../../api/client";
import { ApiError, userMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import { Card, Notice } from "../../components/Surface";

/** Link z e-maila zaproszenia: /invitations/accept?token=… (wymaga zalogowania na adres z zaproszenia). */
export function AcceptInvitationPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const me = useMe();
  const accept = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/invitations/accept", { body: { token } })),
    onSuccess: (w) => navigate(`/w/${w.id}`, { replace: true }),
  });
  const notFound = accept.error instanceof ApiError && accept.error.status === 404;

  return (
    <main className="page enter-detail" aria-labelledby="inv-accept-h">
      <h1 id="inv-accept-h">Zaproszenie do wesela</h1>
      <Card className="form-stack">
        {!token ? (
          <Notice tone="error">Link jest niepełny. Otwórz go ponownie z wiadomości e-mail.</Notice>
        ) : (
          <>
            <p>
              Dołączysz do planowania wesela jako <strong>{me.data?.email}</strong>.
            </p>
            {accept.isError && (
              <Notice tone="error" live>
                {notFound
                  ? "Zaproszenie wygasło, zostało wycofane albo jest dla innego adresu e-mail. Poproś o nowe."
                  : userMessage(accept.error)}
              </Notice>
            )}
            <Button pending={accept.isPending} onPress={() => accept.mutate()}>
              Dołącz do wesela
            </Button>
          </>
        )}
      </Card>
    </main>
  );
}
