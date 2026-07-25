# RootSpan documentation website

This directory contains the static RootSpan product and architecture website published at `https://akshay-verma-cs.github.io/rootspan/`.

## Content architecture

The website imports the repository's Markdown at build time rather than maintaining a second copy:

- `README.md` is the product overview;
- every file under `docs/` is available in the searchable document explorer;
- `AGENTS.md` is published as the repository contract;
- `src/content.ts` owns display metadata and stable document routes;
- `src/App.tsx` owns the product narrative, system map, Sentinel Mesh, evidence protocol, and document reader.

Markdown is bundled into the static JavaScript artifact. GitHub Pages does not need an application server, database, runtime secret, or production telemetry credential.

## Local development

```sh
pnpm --dir website install
pnpm --dir website dev
```

The development server listens on `http://127.0.0.1:4174/rootspan/`.

Run the same gate used by GitHub Actions:

```sh
pnpm --dir website verify
```

This runs catalog tests, strict TypeScript checking, the production Vite build, and artifact validation. The artifact validator checks the GitHub Pages base path, compiled assets, and embedded documentation titles.

## Deployment

`.github/workflows/pages.yml` runs when `website/`, repository docs, the root README, or the workflow changes on `main`. The workflow:

1. installs the locked website dependencies;
2. runs the complete website verification gate;
3. uploads only `website/dist` as the Pages artifact;
4. deploys through the protected `github-pages` environment.

The repository's Pages source must be set to **GitHub Actions**. No deployment token or custom secret is required; the workflow uses GitHub's short-lived Pages identity permissions.

## Visual and accessibility rules

- The visual language is an original neon operations HUD inspired by cyberpunk interfaces; it does not use copied game artwork or trademarks.
- Semantic headings, labels, focus states, keyboard-operable controls, responsive layouts, and sufficient contrast are required.
- Motion is restrained and disabled when the visitor requests reduced motion.
- Project claims must continue to match the source Markdown and the product's read-only, deterministic, human-authority boundary.
