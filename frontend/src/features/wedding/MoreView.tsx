import { Printer, ChevronRight, FileText, Gift, LogOut, Palette, Rows3, Settings2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { logout } from "../../api/auth";
import { Button } from "../../components/Button";
import { Card } from "../../components/Surface";
import { forgetWedding } from "./lastWedding";
import { ROLE_LABEL, useWedding, useWeddingId } from "./data";


export function MoreView() {
  const id = useWeddingId();
  const wedding = useWedding(id);
  const navigate = useNavigate();
  const [leaving, setLeaving] = useState(false);
  // Koordynator dnia i sponsor nie widzą ustawień wesela ani dokumentów.
  const coordinator = wedding.data?.my_role === "coordinator" || wedding.data?.my_role === "sponsor";
  return (
    <main className="page enter-tab" aria-labelledby="more-h">
      <div>
        <h1 id="more-h">Więcej</h1>
        {wedding.data && (
          <p className="text-secondary">
            {wedding.data.name} · {ROLE_LABEL[wedding.data.my_role] ?? wedding.data.my_role}
          </p>
        )}
      </div>
      <Card>
        <ul className="row-list">
          {!coordinator && (
            <li>
              <Link to={`/w/${id}/ustawienia`} viewTransition className="row link-card">
                <Settings2 aria-hidden size={22} strokeWidth={1.75} />
                <span className="row__body">
                  <span className="row__title">Ustawienia wesela</span>
                  <span className="text-secondary">Nazwa, data, ceremonia, budżet, osoby z dostępem</span>
                </span>
                <ChevronRight aria-hidden size={20} />
              </Link>
            </li>
  
          )}
          {!coordinator && (
            <li>
              <Link to={`/w/${id}/druk/podsumowanie`} viewTransition className="row link-card">
                <Printer aria-hidden size={22} strokeWidth={1.75} />
                <span className="row__body">
                  <span className="row__title">Podsumowanie dla rodziców</span>
                  <span className="text-secondary">Jedna strona: termin, goście, budżet, wkład sponsorów, najbliższe kroki — do druku lub PDF</span>
                </span>
                <ChevronRight aria-hidden size={20} />
              </Link>
            </li>
          )}
          {!coordinator && (
            <li>
              <Link to={`/w/${id}/po-weselu`} viewTransition className="row link-card">
                <Gift aria-hidden size={22} strokeWidth={1.75} />
                <span className="row__body">
                  <span className="row__title">Po weselu</span>
                  <span className="text-secondary">Dopłaty, zdjęcia i film, zmiana nazwiska, podziękowania</span>
                </span>
                <ChevronRight aria-hidden size={20} />
              </Link>
            </li>
          )}
          {!coordinator && (
            <li>
              <Link to={`/w/${id}/dokumenty`} viewTransition className="row link-card">
                <FileText aria-hidden size={22} strokeWidth={1.75} />
                <span className="row__body">
                  <span className="row__title">Dokumenty</span>
                  <span className="text-secondary">Oferty, umowy, rachunki; odczyt oferty z PDF</span>
                </span>
                <ChevronRight aria-hidden size={20} />
              </Link>
            </li>
  
          )}
          <li>
            <Link to="/ustawienia" className="row link-card">
              <Palette aria-hidden size={22} strokeWidth={1.75} />
              <span className="row__body">
                <span className="row__title">Wygląd</span>
                <span className="text-secondary">Motyw jasny, ciemny, ograniczenie animacji</span>
              </span>
              <ChevronRight aria-hidden size={20} />
            </Link>
          </li>
          <li>
            <Link
              to="/?wybierz=1"
              className="row link-card"
              onClick={() => forgetWedding()}
            >
              <Rows3 aria-hidden size={22} strokeWidth={1.75} />
              <span className="row__body">
                <span className="row__title">Wszystkie wesela</span>
                <span className="text-secondary">Zmień wesele albo utwórz nowe</span>
              </span>
              <ChevronRight aria-hidden size={20} />
            </Link>
          </li>
        </ul>
      </Card>
      <Button
        variant="secondary"
        pending={leaving}
        icon={<LogOut aria-hidden size={20} strokeWidth={1.75} />}
        onPress={async () => {
          setLeaving(true);
          forgetWedding();
          await logout();
          navigate("/logowanie", { replace: true });
        }}
      >
        Wyloguj
      </Button>
    </main>
  );
}
