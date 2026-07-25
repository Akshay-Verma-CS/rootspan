import { marked } from "marked";
import { describe, expect, it } from "vitest";

import { documents } from "./content";

function diagramSources(markdown: string): readonly string[] {
  return Array.from(markdown.matchAll(/```mermaid\s+([\s\S]*?)```/g), (match) => match[1].trim());
}

describe("repository Mermaid diagrams", () => {
  it("keeps every architecture diagram fenced for the runtime renderer", () => {
    const diagramDocuments = documents
      .map((document) => ({ slug: document.slug, diagrams: diagramSources(document.markdown) }))
      .filter((document) => document.diagrams.length > 0);

    expect(diagramDocuments.map((document) => document.slug)).toEqual([
      "strategy",
      "architecture",
    ]);

    const diagrams = diagramDocuments.flatMap((document) => document.diagrams);
    expect(diagrams).toHaveLength(2);
    expect(diagrams.every((diagram) => diagram.startsWith("flowchart"))).toBe(true);

    for (const document of diagramDocuments) {
      const sourceDocument = documents.find((item) => item.slug === document.slug);
      expect(marked.parse(sourceDocument?.markdown ?? "")).toContain(
        '<code class="language-mermaid">',
      );
    }
  });
});
