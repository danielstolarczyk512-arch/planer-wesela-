// Powitanie pokazujemy tylko tuż po wpisaniu hasła. Znacznik żyje w pamięci karty:
// odświeżenie strony go kasuje, więc /powitanie po przeładowaniu przechodzi od razu do aplikacji.
let pending = false;

export function markWelcome() {
  pending = true;
}

export function welcomePending() {
  return pending;
}
