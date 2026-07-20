import { readFile, writeFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { marked } from "file:///Users/akshayverma/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/marked@17.0.5/node_modules/marked/lib/marked.esm.js";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const sourcePath = join(scriptDirectory, "signoz-mcp-incident-triage-draft.md");
const outputPath = join(scriptDirectory, "rootspan-article.html");

const source = await readFile(sourcePath, "utf8");
const frontMatterMatch = source.match(/^---\n([\s\S]*?)\n---\n/);

if (!frontMatterMatch) {
  throw new Error("The article is missing YAML front matter.");
}

const frontMatter = frontMatterMatch[1];
const field = (name) => {
  const match = frontMatter.match(new RegExp(`^${name}:\\s*[\"']?(.+?)[\"']?$`, "m"));
  return match?.[1] ?? "";
};

const title = field("title");
const description = field("description");
const tags = field("tags").split(",").map((tag) => tag.trim()).filter(Boolean);

let markdown = source.slice(frontMatterMatch[0].length);
markdown = markdown.replace(/<!--\s*DEV\.TO PUBLISHING CHECKLIST[\s\S]*?-->/, "");
markdown = markdown.replace(/<!--\s*AI DISCLOSURE[\s\S]*?-->/, "");

const imagePattern = /\]\(\.\/assets\/([^)]+)\)/g;
const imageMatches = [...markdown.matchAll(imagePattern)];

for (const match of imageMatches) {
  const filename = match[1];
  const imagePath = resolve(scriptDirectory, "assets", filename);
  const extension = extname(filename).toLowerCase();
  const mimeType = extension === ".jpg" || extension === ".jpeg" ? "image/jpeg" : "image/png";
  const encoded = (await readFile(imagePath)).toString("base64");
  markdown = markdown.replace(`](./assets/${filename})`, `](data:${mimeType};base64,${encoded})`);
}

marked.use({
  gfm: true,
  breaks: false,
});

const articleBody = await marked.parse(markdown);
const escapedTitle = title.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const escapedDescription = description.replaceAll("&", "&amp;").replaceAll("\"", "&quot;");
const tagMarkup = tags.map((tag) => `<span class="tag">#${tag}</span>`).join("");

const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="${escapedDescription}">
  <meta name="author" content="Akshay Verma">
  <meta name="theme-color" content="#0b0d12">
  <title>${escapedTitle}</title>
  <style>
    :root {
      color-scheme: dark;
      --background: #0b0d12;
      --surface: #121722;
      --surface-raised: #171d2a;
      --text: #f4f7fb;
      --muted: #a9b2c3;
      --line: #2a3344;
      --accent: #ff6b35;
      --accent-soft: rgba(255, 107, 53, 0.14);
      --link: #79a9ff;
      --code: #0a0d13;
      --max-width: 820px;
    }

    * { box-sizing: border-box; }

    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      background:
        radial-gradient(circle at 15% -10%, rgba(255, 107, 53, 0.16), transparent 34rem),
        radial-gradient(circle at 88% 3%, rgba(74, 116, 255, 0.12), transparent 30rem),
        var(--background);
      color: var(--text);
      font: 18px/1.72 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      text-rendering: optimizeLegibility;
    }

    a { color: var(--link); text-underline-offset: 0.18em; }
    a:hover { color: #a8c6ff; }

    .hero {
      border-bottom: 1px solid var(--line);
      padding: 5.5rem 1.5rem 4rem;
    }

    .hero-inner,
    article,
    .footer-inner {
      width: min(100%, var(--max-width));
      margin: 0 auto;
    }

    .eyebrow {
      margin: 0 0 1rem;
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      max-width: 18ch;
      font-size: clamp(2.6rem, 7vw, 5rem);
      line-height: 1.02;
      letter-spacing: -0.055em;
    }

    .description {
      max-width: 62ch;
      margin: 1.5rem 0 0;
      color: var(--muted);
      font-size: 1.15rem;
    }

    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 0.7rem 1.1rem;
      align-items: center;
      margin-top: 1.75rem;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .tags { display: flex; flex-wrap: wrap; gap: 0.45rem; }

    .tag {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0.2rem 0.62rem;
      background: var(--surface);
      color: #d7dfec;
    }

    article { padding: 4rem 1.5rem 5rem; }

    article > p:first-child {
      margin-top: 0;
      color: #ffffff;
      font-size: 1.35rem;
      line-height: 1.55;
    }

    h2 {
      margin: 4rem 0 1.15rem;
      padding-top: 0.35rem;
      font-size: clamp(1.7rem, 4vw, 2.35rem);
      line-height: 1.16;
      letter-spacing: -0.032em;
    }

    h2::before {
      display: block;
      width: 2.4rem;
      height: 0.22rem;
      margin-bottom: 1rem;
      border-radius: 999px;
      background: var(--accent);
      content: "";
    }

    p, ul, ol { margin: 1.1rem 0; }
    li + li { margin-top: 0.52rem; }
    strong { color: #ffffff; }

    code {
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 0.34rem;
      padding: 0.12rem 0.35rem;
      background: var(--code);
      color: #ffb49a;
      font: 0.88em/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }

    pre {
      overflow-x: auto;
      margin: 1.6rem 0;
      border: 1px solid var(--line);
      border-radius: 0.8rem;
      padding: 1.2rem 1.3rem;
      background: var(--code);
      box-shadow: 0 18px 55px rgba(0,0,0,0.22);
    }

    pre code { border: 0; padding: 0; background: transparent; color: #dce5f3; }

    img {
      display: block;
      width: min(1100px, calc(100vw - 2rem));
      max-width: none;
      height: auto;
      margin: 2.1rem 50%;
      border: 1px solid var(--line);
      border-radius: 0.85rem;
      box-shadow: 0 24px 70px rgba(0,0,0,0.38);
      transform: translateX(-50%);
    }

    blockquote {
      margin: 1.8rem 0;
      border-left: 0.25rem solid var(--accent);
      padding: 0.25rem 0 0.25rem 1.25rem;
      color: #d8dfeb;
    }

    .disclosure {
      margin-top: 4.5rem;
      border: 1px solid rgba(255, 107, 53, 0.4);
      border-radius: 0.9rem;
      padding: 1.3rem 1.4rem;
      background: var(--accent-soft);
    }

    .disclosure h2 { margin: 0 0 0.65rem; padding: 0; font-size: 1.15rem; }
    .disclosure h2::before { display: none; }
    .disclosure p { margin: 0; color: #e3e7ef; font-size: 0.92rem; }

    footer {
      border-top: 1px solid var(--line);
      padding: 2rem 1.5rem 3rem;
      color: var(--muted);
      font-size: 0.86rem;
    }

    @media (max-width: 720px) {
      body { font-size: 16px; }
      .hero { padding-top: 3.5rem; }
      article { padding-top: 2.8rem; }
      img { width: calc(100vw - 1.5rem); border-radius: 0.55rem; }
    }

    @media print {
      :root { color-scheme: light; --background: #fff; --text: #111; --muted: #444; --line: #ddd; --code: #f5f5f5; --link: #174ea6; }
      body { background: #fff; }
      .hero { padding-top: 2rem; }
      img { width: 100%; max-width: 100%; margin-inline: 0; transform: none; box-shadow: none; }
      a { color: #174ea6; }
      pre { box-shadow: none; }
    }
  </style>
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <p class="eyebrow">Agents of SigNoz · Engineering note</p>
      <h1>${escapedTitle}</h1>
      <p class="description">${escapedDescription}</p>
      <div class="meta">
        <span>Akshay Verma</span>
        <span>18 July 2026</span>
        <span>Approximately 9 minutes</span>
        <span class="tags">${tagMarkup}</span>
      </div>
    </div>
  </header>

  <main>
    <article>
${articleBody}
      <aside class="disclosure" aria-labelledby="disclosure-heading">
        <h2 id="disclosure-heading">AI assistance disclosure</h2>
        <p>This article was drafted and edited with assistance from OpenAI Codex. I personally verified the commands, screenshots, measurements, and conclusions in the local SigNoz lab.</p>
      </aside>
    </article>
  </main>

  <footer>
    <div class="footer-inner">RootSpan · Evidence-first incident correlation for human responders</div>
  </footer>
</body>
</html>
`;

await writeFile(outputPath, html, "utf8");
console.log(outputPath);
