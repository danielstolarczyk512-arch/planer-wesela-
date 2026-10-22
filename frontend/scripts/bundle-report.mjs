// Udział pakietów w zbudowanym JS (wg mapy źródeł; rozmiary przed minifikacją, do porównań).
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const dir = "dist/assets";
for (const file of readdirSync(dir).filter((f) => f.endsWith(".js.map"))) {
  const map = JSON.parse(readFileSync(join(dir, file), "utf8"));
  const sizes = new Map();
  map.sources.forEach((src, i) => {
    const m = src.match(/node_modules\/((?:@[^/]+\/)?[^/]+)/);
    const pkg = m ? m[1] : "(aplikacja)";
    sizes.set(pkg, (sizes.get(pkg) ?? 0) + (map.sourcesContent?.[i]?.length ?? 0));
  });
  const total = [...sizes.values()].reduce((a, b) => a + b, 0);
  console.log(`\n${file.replace(".map", "")}: ${(total / 1024).toFixed(0)} KB źródeł`);
  [...sizes.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .forEach(([pkg, size]) => console.log(`  ${pkg.padEnd(36)} ${(size / 1024).toFixed(0).padStart(5)} KB`));
}
