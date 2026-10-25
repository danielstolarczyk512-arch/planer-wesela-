import { useEffect, useRef } from "react";
import { Link, Navigate } from "react-router";

import { welcomePending } from "../../lib/welcome";

import "./landing.css";

/**
 * Nagrania z Pexels (licencja Pexels: użytek komercyjny bez opłat), przycięte do 6 s, bez dźwięku —
 * źródła i autorzy w `public/media/ZRODLA.md`.
 */
const clip = (name: string) => `/media/${name}`;

// Dwie kolumny nagrań płyną w górę w różnym tempie (--speed), obok zdanie zapala się słowo po słowie.
const STRIPS = [
  { speed: 1, clips: ["obraczki", "taniec", "ceremonia", "tort"].map(clip) },
  { speed: 0.55, clips: ["stol", "pocalunek", "bukiet", "panna-mloda"].map(clip) },
];

const SENTENCE =
  "Oferty, budżet, goście i cały dzień ślubu w jednym miejscu. Bez arkuszy, bez niespodzianek, bez chaosu.".split(" ");

const clamp = (v: number) => Math.min(1, Math.max(0, v));
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Bez ruchu i oszczędzanie danych: same klatki (plakaty), wideo się nie odtwarza. */
function stillOnly() {
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
  return reducedMotion() || saveData === true;
}

/** Po zalogowaniu (każde wpisanie hasła): ta sama scena, zamiast rejestracji — przejście do planowania. */
export function WelcomePage() {
  if (!welcomePending()) return <Navigate to="/" replace />;
  return <LandingPage signedIn />;
}

/** Strona tytułowa: nagłówek, a przy przewijaniu słowa zapalają się po kolei obok płynących nagrań. */
export function LandingPage({ signedIn = false }: { signedIn?: boolean }) {
  const track = useRef<HTMLDivElement>(null);

  // --p (0…1) = jak daleko przewinięto scenę; liczone raz na klatkę.
  useEffect(() => {
    const el = track.current;
    if (!el) return;
    if (reducedMotion()) {
      el.style.setProperty("--p", "1");
      return;
    }
    let frame = 0;
    const update = () => {
      frame = 0;
      const rect = el.getBoundingClientRect();
      const range = rect.height - window.innerHeight;
      el.style.setProperty("--p", String(range > 0 ? clamp(-rect.top / range) : 1));
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  // Grają tylko nagrania widoczne na ekranie (bateria, dane).
  useEffect(() => {
    const el = track.current;
    if (!el || stillOnly()) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const video = e.target as HTMLVideoElement;
          if (e.isIntersecting) void video.play().catch(() => undefined);
          else video.pause();
        }
      },
      { threshold: 0.05 },
    );
    el.querySelectorAll("video").forEach((video) => io.observe(video));
    return () => io.disconnect();
  }, []);

  return (
    <div className="landing">
      <header className="landing__bar">
        <span className="landing__brand">Nasz dzień</span>
        <nav aria-label={signedIn ? "Aplikacja" : "Konto"} className="landing__nav">
          {signedIn ? (
            <Link to="/" className="landing__nav-cta">
              Przejdź do planowania
            </Link>
          ) : (
            <>
              <Link to="/logowanie">Zaloguj się</Link>
              <Link to="/rejestracja" className="landing__nav-cta">
                Załóż konto
              </Link>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="landing__hero" aria-labelledby="landing-title">
          {/* Zdjęcie pary w łuku (dekoracja, bez treści). */}
          <img className="landing__arch-photo" src="/media/zdjecia/para-zachod.webp" alt="" width={195} height={480} decoding="async" />
          <p className="overline landing__overline">Planer wesela</p>
          <h1 id="landing-title">
            {signedIn ? "Witajcie! Planujemy dalej " : "Zaplanujcie swoje wesele "}
            <em>spokojnie</em>
          </h1>
          <p>
            Oferty, umowy, budżet, goście i harmonogram dnia w jednej aplikacji. Wszystko po polsku, z prawdziwym
            kosztem zamiast niespodzianek.
          </p>
          <a className="landing__scroll" href="#scena" aria-label="Przewiń w dół">
            <span aria-hidden="true">↓</span>
          </a>
        </section>

        <div className="landing__track" id="scena" ref={track}>
          <div className="landing__stage">
            <p className="landing__words">
              <span className="visually-hidden">{SENTENCE.join(" ")}</span>
              {SENTENCE.map((word, k) => (
                <span key={k} aria-hidden="true" style={{ ["--k" as string]: k / SENTENCE.length }}>
                  {word}{" "}
                </span>
              ))}
            </p>
            <div className="landing__strips" aria-hidden="true">
              {STRIPS.map((strip, s) => (
                <div key={s} className="landing__strip" style={{ ["--speed" as string]: strip.speed }}>
                  {strip.clips.map((media) => (
                    <video
                      key={media}
                      className="landing__clip"
                      src={media + ".mp4"}
                      poster={media + ".jpg"}
                      muted
                      loop
                      playsInline
                      preload="metadata"
                      disablePictureInPicture
                      tabIndex={-1}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>

        <section className="landing__final" aria-labelledby="landing-final">
          {signedIn ? (
            <>
              <h2 id="landing-final">Wracamy do Waszego planu</h2>
              <p>Najbliższe zadania, budżet i goście czekają tam, gdzie je zostawiliście.</p>
              <div className="landing__actions">
                <Link to="/" className="wp-button wp-button--primary">
                  Przejdź do planowania
                </Link>
              </div>
            </>
          ) : (
            <>
              <h2 id="landing-final">Zacznijcie od pierwszego zadania</h2>
              <p>Dane Waszego wesela widzicie tylko Wy i osoby, które zaprosicie.</p>
              <div className="landing__actions">
                <Link to="/rejestracja" className="wp-button wp-button--primary">
                  Załóż konto
                </Link>
                <Link to="/logowanie" className="wp-button wp-button--secondary">
                  Mam już konto
                </Link>
              </div>
            </>
          )}
        </section>
      </main>

      <footer className="landing__foot">
        <Link to="/regulamin">Regulamin</Link>
        <Link to="/prywatnosc">Prywatność</Link>
      </footer>
    </div>
  );
}
