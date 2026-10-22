// Budżet wydajności (GUI-SPEC v1.1, sekcja 9): JS ładowany na start ≤ 170 KB po gzip.
// Liczy plik wejściowy z dist/index.html i jego statyczne importy (modulepreload).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const LIMIT_KB = 170;
const html = readFileSync("dist/index.html", "utf8");
const files = new Set(
  [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((m) => m[1]),
);
let total = 0;
for (const f of files) {
  const size = gzipSync(readFileSync(join("dist", f)), { level: 9 }).length;
  total += size;
  console.log(`${f}: ${(size / 1024).toFixed(1)} KB gzip`);
}
const kb = total / 1024;
console.log(`Start aplikacji: ${kb.toFixed(1)} KB gzip (limit ${LIMIT_KB} KB)`);
if (kb > LIMIT_KB) {
  console.error("Przekroczony budżet JS na start.");
  process.exit(1);
}
