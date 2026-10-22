// Preferencje wyglądu (nie są danymi wrażliwymi) ustawiane przed pierwszym malowaniem.
try {
  var theme = localStorage.getItem("wp.theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  if (localStorage.getItem("wp.reduceMotion") === "1") {
    document.documentElement.classList.add("reduce-motion");
  }
} catch (e) {
  // Prywatny tryb przeglądarki: zostaje motyw systemowy.
}
