// Single API client. The browser talks ONLY to the backend API; the backend
// holds provider keys. No secret ever reaches this layer.
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,
  health: () => req<any>("/health"),
  ready: () => req<any>("/ready"),
  stats: (includeDemo = false) => req<any>(`/api/stats?include_demo=${includeDemo}`),
  system: () => req<any>("/api/settings/system"),

  documents: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(params as any).toString();
    return req<any>(`/api/documents?${q}`);
  },
  document: (id: string) => req<any>(`/api/documents/${id}`),
  documentPages: (id: string) => req<any>(`/api/documents/${id}/pages`),
  fileUrl: (id: string) => `${BASE}/api/documents/${id}/file`,

  search: (body: any) => req<any>("/api/search", { method: "POST", body: JSON.stringify(body) }),
  ask: (body: any) => req<any>("/api/ask", { method: "POST", body: JSON.stringify(body) }),
  askDocument: (id: string, body: any) =>
    req<any>(`/api/documents/${id}/ask`, { method: "POST", body: JSON.stringify(body) }),
  summarizeDocument: (id: string, body: any) =>
    req<any>(`/api/documents/${id}/summarize`, { method: "POST", body: JSON.stringify(body) }),

  providers: () => req<any>("/api/providers"),
  setProviderKey: (id: string, body: any) =>
    req<any>(`/api/providers/${id}/key`, { method: "PUT", body: JSON.stringify(body) }),
  deleteProviderKey: (id: string) => req<any>(`/api/providers/${id}/key`, { method: "DELETE" }),
  setProviderConfig: (id: string, body: any) =>
    req<any>(`/api/providers/${id}/config`, { method: "PUT", body: JSON.stringify(body) }),
  testProvider: (id: string) => req<any>(`/api/providers/${id}/test`, { method: "POST" }),
  refreshModels: (id: string) => req<any>(`/api/providers/${id}/refresh-models`, { method: "POST" }),
  embeddingsStatus: () => req<any>("/api/providers/embeddings/status"),

  sources: () => req<any>("/api/ingestion/sources"),
  startCrawl: (body: any) => req<any>("/api/ingestion/crawl", { method: "POST", body: JSON.stringify(body) }),
  ingestUrl: (body: any) => req<any>("/api/ingestion/ingest-url", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => req<any>("/api/ingestion/jobs"),
  job: (id: number) => req<any>(`/api/ingestion/jobs/${id}`),
  retryJob: (id: number) => req<any>(`/api/ingestion/jobs/${id}/retry`, { method: "POST" }),
  crawls: () => req<any>("/api/ingestion/crawls"),
  seedDemo: () => req<any>("/api/ingestion/demo/seed", { method: "POST" }),
  clearDemo: () => req<any>("/api/ingestion/demo/clear", { method: "POST" }),

  topics: () => req<any>("/api/topics"),
  collections: () => req<any>("/api/collections"),
  entities: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(params as any).toString();
    return req<any>(`/api/entities?${q}`);
  },
  entity: (id: number) => req<any>(`/api/entities/${id}`),
  mapEntities: () => req<any>("/api/map/entities"),
  timeline: () => req<any>("/api/timeline"),

  notes: () => req<any>("/api/notes"),
  createNote: (body: any) => req<any>("/api/notes", { method: "POST", body: JSON.stringify(body) }),
  sessions: () => req<any>("/api/sessions"),
  session: (id: number) => req<any>(`/api/sessions/${id}`),

  retrievalSettings: () => req<any>("/api/settings/retrieval"),
  setRetrievalSettings: (body: any) =>
    req<any>("/api/settings/retrieval", { method: "PUT", body: JSON.stringify(body) }),
};
