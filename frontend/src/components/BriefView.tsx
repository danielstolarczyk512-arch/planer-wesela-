/** Informacje dla usługodawcy: podgląd w aplikacji (tylko odczyt) i na stronie jego linku. */
import type { components } from "../api/schema";
import type { BriefLabels } from "../lib/vendorBrief";
import { StatusChip } from "./Surface";
import "./BriefView.css";

/** Podgląd informacji (rola tylko do odczytu i strona usługodawcy). */
export function BriefView({ brief, labels }: { brief: components["schemas"]["BriefIn"]; labels: BriefLabels }) {
  return (
    <div className="form-stack brief-view">
      {!!brief.must?.length && (
        <div>
          <h3>{labels.must}</h3>
          <ul>
            {brief.must.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {!!brief.avoid?.length && (
        <div>
          <h3>{labels.avoid}</h3>
          <ul>
            {brief.avoid.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {!!brief.people?.length && (
        <div>
          <h3>{labels.people}</h3>
          <ul>
            {brief.people.map((p, i) => (
              <li key={i}>
                <strong>{p.name}</strong> — {p.role}
              </li>
            ))}
          </ul>
        </div>
      )}
      {brief.notes && <p>{brief.notes}</p>}
      {brief.contact && (
        <p>
          <StatusChip tone="info">Kontakt w dniu ślubu</StatusChip> {brief.contact}
        </p>
      )}
    </div>
  );
}
