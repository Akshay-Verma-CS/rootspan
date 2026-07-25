import { access, readFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";

const dist = new URL("../dist/", import.meta.url);
const indexPath = new URL("index.html", dist);
const assetsPath = new URL("assets/", dist);
const socialPreviewPath = new URL("og.png", dist);

await access(indexPath);
await access(assetsPath);
await access(socialPreviewPath);

const html = await readFile(indexPath, "utf8");
if (!html.includes("RootSpan // Evidence before action")) {
  throw new Error("production index is missing the RootSpan title");
}
if (!html.includes("/rootspan/assets/")) {
  throw new Error("production assets are not rooted at the GitHub Pages project path");
}

const assets = await readdir(assetsPath);
const compiledScripts = assets.filter((name) => name.endsWith(".js"));
const compiledStyles = assets.filter((name) => name.endsWith(".css"));
if (compiledScripts.length !== 1 || compiledStyles.length !== 1) {
  throw new Error("expected one compiled JavaScript bundle and one stylesheet");
}

for (const file of [...compiledScripts, ...compiledStyles]) {
  const details = await stat(join(assetsPath.pathname, file));
  if (details.size === 0) {
    throw new Error(`compiled asset is empty: ${file}`);
  }
}

const socialPreview = await stat(socialPreviewPath);
if (socialPreview.size < 100_000) {
  throw new Error("social preview is missing or unexpectedly small");
}

const script = await readFile(join(assetsPath.pathname, compiledScripts[0]), "utf8");
for (const expectedTitle of [
  "RootSpan overview",
  "Stack & architecture",
  "Engineering standards",
  "Agent guide",
]) {
  if (!script.includes(expectedTitle)) {
    throw new Error(`compiled documentation is missing: ${expectedTitle}`);
  }
}

console.log("Validated GitHub Pages artifact: routes, assets, and embedded docs are present.");
