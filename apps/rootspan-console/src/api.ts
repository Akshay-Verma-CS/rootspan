import type { IncidentBrief, IncidentListResponse } from "./types";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function listIncidents(): Promise<IncidentBrief[]> {
  const response = await fetch("/api/v1/incidents?limit=20");
  const payload = await readJson<IncidentListResponse>(response);
  return payload.incidents;
}

export async function replayGoldenIncident(): Promise<IncidentBrief> {
  const response = await fetch("/api/v1/incidents/replay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: "inventory-cohort-timeout" }),
  });
  return readJson<IncidentBrief>(response);
}
