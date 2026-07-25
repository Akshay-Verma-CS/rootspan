import { describe, expect, it } from "vitest";

import { architectureStages, documentBySlug, documents, searchDocuments } from "./content";

describe("project document catalog", () => {
  it("publishes every repository guide with a unique route", () => {
    expect(documents).toHaveLength(9);
    expect(new Set(documents.map((document) => document.slug)).size).toBe(documents.length);
    expect(documents.every((document) => document.markdown.length > 500)).toBe(true);
    expect(documents.map((document) => document.sourcePath)).toContain(
      "docs/STACK_AND_ARCHITECTURE.md",
    );
  });

  it("resolves document routes and searches source content", () => {
    expect(documentBySlug("architecture")?.title).toBe("Stack & architecture");
    expect(documentBySlug("missing")).toBeUndefined();
    expect(searchDocuments("SQLite lease").map((document) => document.slug)).toContain(
      "architecture",
    );
    expect(searchDocuments("no-result-sentinel")).toEqual([]);
  });
});

describe("architecture narrative", () => {
  it("keeps the observable incident sequence complete and ordered", () => {
    expect(architectureStages.map((stage) => stage.id)).toEqual([
      "impact",
      "mesh",
      "correlation",
      "handoff",
    ]);
    expect(architectureStages.every((stage) => stage.detail.length > 40)).toBe(true);
  });
});
