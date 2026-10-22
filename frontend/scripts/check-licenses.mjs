// Licencje zależności produkcyjnych i deweloperskich (ADR-0006): blokada AGPL/SSPL/GPL.
// MPL-2.0 dopuszczona tylko dla narzędzi testowych i budowania (bez modyfikacji, nie trafiają
// do kodu aplikacji; MPL obejmuje wyłącznie zmienione pliki samej biblioteki).
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const BLOCKED = /\b(AGPL|SSPL|GPL-[23]|GPL v[23]|LGPL)/i;
const DEV_ONLY_ALLOWED = new Set([
  "axe-core", // audyt dostępności w testach
  "@axe-core/playwright",
  "lightningcss", // minifikacja CSS w Vite (tylko build)
  "lightningcss-win32-x64-msvc",
  "lightningcss-linux-x64-gnu",
  "lightningcss-linux-x64-musl",
  "lightningcss-darwin-arm64",
]);
const root = "node_modules";
const prodDeps = new Set(Object.keys(JSON.parse(readFileSync("package.json", "utf8")).dependencies));
const rows = [];
let failed = 0;

function visit(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    if (entry.name.startsWith("@")) {
      visit(path);
      continue;
    }
    const pkgFile = join(path, "package.json");
    if (!existsSync(pkgFile)) continue;
    const pkg = JSON.parse(readFileSync(pkgFile, "utf8"));
    const license = typeof pkg.license === "string" ? pkg.license : (pkg.license?.type ?? "BRAK");
    rows.push([pkg.name, pkg.version, license]);
    const isMpl = /MPL/i.test(license);
    if (BLOCKED.test(license) || license === "BRAK" || (isMpl && !DEV_ONLY_ALLOWED.has(pkg.name))) {
      // Pakiety z podwójną licencją (np. "MIT OR GPL") są dopuszczalne: wybieramy MIT.
      if (/\bOR\b/.test(license) && /(MIT|Apache|BSD|ISC)/.test(license)) continue;
      console.error(`Niedozwolona lub brak licencji: ${pkg.name}@${pkg.version} (${license})`);
      failed++;
    }
    if (isMpl && prodDeps.has(pkg.name)) {
      console.error(`MPL w zależnościach produkcyjnych: ${pkg.name}`);
      failed++;
    }
  }
}

visit(root);
const counts = rows.reduce((acc, [, , l]) => ((acc[l] = (acc[l] ?? 0) + 1), acc), {});
console.log(`Pakietów: ${rows.length}. Licencje:`, counts);
process.exit(failed ? 1 : 0);
