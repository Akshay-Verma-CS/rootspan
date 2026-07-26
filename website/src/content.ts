import agentGuide from "../../AGENTS.md?raw";
import overview from "../../README.md?raw";
import decisions from "../../docs/DECISIONS.md?raw";
import demoPlan from "../../docs/DEMO_PLAN.md?raw";
import developmentWorkflow from "../../docs/DEVELOPMENT_WORKFLOW.md?raw";
import engineeringStandards from "../../docs/ENGINEERING_STANDARDS.md?raw";
import executionPlan from "../../docs/EXECUTION_PLAN.md?raw";
import projectStrategy from "../../docs/PROJECT_STRATEGY.md?raw";
import stackAndArchitecture from "../../docs/STACK_AND_ARCHITECTURE.md?raw";

export type DocCategory = "Product" | "Architecture" | "Delivery" | "Engineering";

export interface ProjectDocument {
  slug: string;
  title: string;
  label: string;
  description: string;
  category: DocCategory;
  sourcePath: string;
  readingMinutes: number;
  markdown: string;
}

export interface ArchitectureStage {
  id: string;
  index: string;
  label: string;
  detail: string;
  tone: "cyan" | "yellow" | "magenta";
}

export interface JudgeStep {
  id: "signal" | "compare" | "locate" | "handoff";
  index: string;
  label: string;
  value: string;
  detail: string;
}

export const judgeSteps: readonly JudgeStep[] = [
  {
    id: "signal",
    index: "01",
    label: "Start with impact",
    value: "Checkout SLO burn",
    detail: "The alert is the loud upstream symptom, not a root-cause claim.",
  },
  {
    id: "compare",
    index: "02",
    label: "Compare cohorts",
    value: "5 healthy / 5 failing",
    detail: "Matched trace trees expose what changed without relying on one noisy trace.",
  },
  {
    id: "locate",
    index: "03",
    label: "Find local truth",
    value: "inventory.reserve",
    detail: "Attribution removes propagated parent time and ranks the first local divergence.",
  },
  {
    id: "handoff",
    index: "04",
    label: "Verify and decide",
    value: "9 evidence records",
    detail: "Every claim stays linked to provenance; every production action stays human-owned.",
  },
] as const;

export const architectureStages: readonly ArchitectureStage[] = [
  {
    id: "impact",
    index: "01",
    label: "Impact signal",
    detail: "SigNoz detects the upstream SLO symptom and opens a bounded incident window.",
    tone: "yellow",
  },
  {
    id: "mesh",
    index: "02",
    label: "Sentinel Mesh",
    detail: "One leased leader delegates system-scoped, read-only observations to four sentinels.",
    tone: "magenta",
  },
  {
    id: "correlation",
    index: "03",
    label: "First divergence",
    detail: "Healthy and failing cohorts are aligned and ranked with deterministic attribution.",
    tone: "cyan",
  },
  {
    id: "handoff",
    index: "04",
    label: "Human handoff",
    detail: "The responder receives cited evidence, contradictions, blast radius, and next queries.",
    tone: "yellow",
  },
] as const;

export const documents: readonly ProjectDocument[] = [
  {
    slug: "overview",
    title: "RootSpan overview",
    label: "Start here",
    description: "Product boundary, implemented slice, quickstart, and hackathon alignment.",
    category: "Product",
    sourcePath: "README.md",
    readingMinutes: 6,
    markdown: overview,
  },
  {
    slug: "strategy",
    title: "Project strategy",
    label: "Product thesis",
    description: "The golden incident, first-divergence thesis, evidence model, and success metrics.",
    category: "Product",
    sourcePath: "docs/PROJECT_STRATEGY.md",
    readingMinutes: 11,
    markdown: projectStrategy,
  },
  {
    slug: "architecture",
    title: "Stack & architecture",
    label: "System map",
    description: "Runtime boundaries, domain contracts, correlation algorithm, and deployment model.",
    category: "Architecture",
    sourcePath: "docs/STACK_AND_ARCHITECTURE.md",
    readingMinutes: 16,
    markdown: stackAndArchitecture,
  },
  {
    slug: "decisions",
    title: "Decision record",
    label: "Why this shape",
    description: "Accepted tradeoffs behind human authority, MCP access, the monolith, and sentinels.",
    category: "Architecture",
    sourcePath: "docs/DECISIONS.md",
    readingMinutes: 12,
    markdown: decisions,
  },
  {
    slug: "execution",
    title: "Execution plan",
    label: "Seven-day build",
    description: "Milestones, current implementation checkpoint, priorities, risks, and exit tests.",
    category: "Delivery",
    sourcePath: "docs/EXECUTION_PLAN.md",
    readingMinutes: 9,
    markdown: executionPlan,
  },
  {
    slug: "demo",
    title: "Demo & judging plan",
    label: "Four-minute story",
    description: "Demo sequence, evidence to capture, judge questions, and honest claims.",
    category: "Delivery",
    sourcePath: "docs/DEMO_PLAN.md",
    readingMinutes: 7,
    markdown: demoPlan,
  },
  {
    slug: "standards",
    title: "Engineering standards",
    label: "Quality contract",
    description: "Evidence integrity, coding rules, observability, testing, and security hygiene.",
    category: "Engineering",
    sourcePath: "docs/ENGINEERING_STANDARDS.md",
    readingMinutes: 10,
    markdown: engineeringStandards,
  },
  {
    slug: "workflow",
    title: "Development workflow",
    label: "Build discipline",
    description: "The vertical-slice loop from acceptance criteria through verification and integration.",
    category: "Engineering",
    sourcePath: "docs/DEVELOPMENT_WORKFLOW.md",
    readingMinutes: 8,
    markdown: developmentWorkflow,
  },
  {
    slug: "agent-guide",
    title: "Agent guide",
    label: "Repository contract",
    description: "Mission, non-negotiable invariants, repository boundaries, and definition of done.",
    category: "Engineering",
    sourcePath: "AGENTS.md",
    readingMinutes: 6,
    markdown: agentGuide,
  },
] as const;

export function documentBySlug(slug: string): ProjectDocument | undefined {
  return documents.find((document) => document.slug === slug);
}

export function searchDocuments(query: string): readonly ProjectDocument[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) {
    return documents;
  }

  return documents.filter((document) =>
    [document.title, document.label, document.description, document.category, document.markdown]
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalized),
  );
}
