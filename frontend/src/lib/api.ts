export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type SourceType = "pdf" | "youtube" | "web";

export type Citation = {
  source: string;
  page?: number | null;
  source_id?: string | null;
  chunk_id?: string | null;
  score?: number | null;
  snippet?: string | null;
  source_type: SourceType;
  start_seconds?: number | null;
  url?: string | null;
};

export type SourceInfo = {
  source_id: string;
  source: string;
  source_type: "pdf" | "youtube";
  chunks: number;
  url?: string | null;
};

export type ModelsInfo = {
  models: string[];
  default: string;
  web_search_available: boolean;
};

export type HistoryMessage = { role: "user" | "assistant"; content: string };

export type StreamEvent =
  | { type: "meta"; model?: string; models?: string[]; sources: Citation[]; web_used: boolean }
  | { type: "token"; model: string; text: string }
  | { type: "done"; model: string; latency_ms: number; first_token_ms: number | null }
  | { type: "error"; model?: string; message: string }
  | { type: "end" };

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  if (response.status === 429) return "Too many requests. Please wait a minute and try again.";
  return `Request failed (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(`Can't reach the backend at ${API_URL}. Is it running?`);
  }
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
}

export const getModels = () => request<ModelsInfo>("/models");

export const listSources = (sessionId: string) =>
  request<{ session_id: string; sources: SourceInfo[] }>(
    `/sources?session_id=${encodeURIComponent(sessionId)}`,
  ).then((r) => r.sources);

export const deleteSource = (sessionId: string, sourceId: string) =>
  request<unknown>(`/sources/${encodeURIComponent(sourceId)}?session_id=${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });

export const deleteSession = (sessionId: string) =>
  request<unknown>(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });

export function ingestPdf(file: File, sessionId: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("session_id", sessionId);
  return request<{ source_id: string; filename: string; chunks: number }>("/ingest/pdf", {
    method: "POST",
    body: form,
  });
}

export const ingestYoutube = (url: string, sessionId: string) =>
  request<{ source_id: string; filename: string; chunks: number }>("/ingest/youtube", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, session_id: sessionId }),
  });

/** POST + read a Server-Sent Events response, calling `onEvent` for each event. */
export async function streamEvents(
  path: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    throw new Error(`Can't reach the backend at ${API_URL}. Is it running?`);
  }
  if (!response.ok || !response.body) throw new Error(await errorMessage(response));

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);
        if (block.startsWith("data:")) {
          try {
            onEvent(JSON.parse(block.slice(5).trim()) as StreamEvent);
          } catch {
            /* ignore a malformed event */
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") throw error;
  }
}

export function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
}

export function shortModelName(model: string): string {
  return model.split("/").pop() ?? model;
}
