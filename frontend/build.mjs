import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile, copyFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, "dist");
const prefix = process.env.PUBLIC_BASE_PATH || "";
if (prefix && !/^\/[a-z0-9-]+$/.test(prefix)) throw new Error("Некорректный PUBLIC_BASE_PATH");
await mkdir(output, { recursive: true });
const pages = new Map(await Promise.all(["index.html", "admin.html"].map(async (name) => [name, await readFile(join(root, name), "utf8")])));

for (const [name, extension] of [["styles", "css"], ["app", "js"], ["admin", "css"], ["admin", "js"], ["behavior-metrics", "js"]]) {
  const source = await readFile(join(root, `${name}.${extension}`), "utf8");
  const content = Buffer.from(source.replaceAll('"/api/', `"${prefix}/api/`).replaceAll('`/api/', `\`${prefix}/api/`));
  const hash = createHash("sha256").update(content).digest("hex").slice(0, 12);
  const assetName = `${name}.${hash}.${extension}`;
  await writeFile(join(output, assetName), content);
  for (const [page, html] of pages) pages.set(page, html.replace(`/${name}.${extension}`, `${prefix}/${assetName}`));
  console.log(`${assetName}: ${content.length} bytes`);
}

for (const [name, html] of pages) {
  await writeFile(join(output, name), html.replaceAll('href="/favicon.svg"', `href="${prefix}/favicon.svg"`).replaceAll('href="/"', `href="${prefix}/"`));
}
await copyFile(join(root, "favicon.svg"), join(output, "favicon.svg"));
console.log("Готово: dist/index.html, CSS, JavaScript и favicon. Зависимости не требуются.");
