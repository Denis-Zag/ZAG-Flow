import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile, copyFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, "dist");
await mkdir(output, { recursive: true });
let html = await readFile(join(root, "index.html"), "utf8");

for (const [name, extension] of [["styles", "css"], ["app", "js"]]) {
  const content = await readFile(join(root, `${name}.${extension}`));
  const hash = createHash("sha256").update(content).digest("hex").slice(0, 12);
  const assetName = `${name}.${hash}.${extension}`;
  await writeFile(join(output, assetName), content);
  html = html.replace(`/${name}.${extension}`, `/${assetName}`);
  console.log(`${assetName}: ${content.length} bytes`);
}

await writeFile(join(output, "index.html"), html);
await copyFile(join(root, "favicon.svg"), join(output, "favicon.svg"));
console.log("Готово: dist/index.html, CSS, JavaScript и favicon. Зависимости не требуются.");
