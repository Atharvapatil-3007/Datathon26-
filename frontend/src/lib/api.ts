/**
 * Thin typed fetch client for the FastAPI backend.
 *
 * The Vite dev server proxies `/api` and `/health` to the backend, so we
 * always call relative paths — no CORS, no base URL juggling.
 */

import type {
  AnalysisOptionsResponse,
  AnalysisResult,
  ApiErrorPayload,
  ChatQueryPayload,
  ChatResponse,
  ChatSessionResponse,
  ChatSuggestionsPayload,
  ChatSuggestionsResponse,
  DatasetSummary,
  HealthResponse,
  IngestionResponse,
  ProfileResponse,
} from "./types";

// ---------------------------------------------------------------------------
// ApiError — thrown for every non-2xx response
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(
    message: string,
    status: number,
    code: string = "UNKNOWN",
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

// ---------------------------------------------------------------------------
// Low-level fetch helper
// ---------------------------------------------------------------------------
async function request<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      signal,
      headers: {
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(
      "Network request failed — is the backend running on port 8000?",
      0,
      "NETWORK_ERROR",
      err instanceof Error ? err.message : String(err),
    );
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const body: unknown = isJson ? await response.json().catch(() => null) : await response.text();

  if (!response.ok) {
    const payload = body as ApiErrorPayload | null;
    const err = payload?.error;
    throw new ApiError(
      err?.message ?? `Request failed with status ${response.status}`,
      response.status,
      err?.code ?? "HTTP_ERROR",
      err?.details ?? body,
    );
  }

  return body as T;
}

// ---------------------------------------------------------------------------
// Endpoint methods
// ---------------------------------------------------------------------------
export const api = {
  health(signal?: AbortSignal): Promise<HealthResponse> {
    return request<HealthResponse>("/health", { method: "GET" }, signal);
  },

  uploadDataset(
    file: File,
    options: {
      sheetName?: string;
      tableName?: string;
      delimiter?: string;
      encoding?: string;
      member?: string;
    } = {},
    signal?: AbortSignal,
  ): Promise<IngestionResponse> {
    const form = new FormData();
    form.append("file", file, file.name);
    if (options.sheetName) form.append("sheet_name", options.sheetName);
    if (options.tableName) form.append("table_name", options.tableName);
    if (options.delimiter) form.append("delimiter", options.delimiter);
    if (options.encoding) form.append("encoding", options.encoding);
    if (options.member) form.append("member", options.member);

    return request<IngestionResponse>(
      "/api/v1/ingestion/upload",
      { method: "POST", body: form },
      signal,
    );
  },

  listDatasets(
    limit = 50,
    offset = 0,
    signal?: AbortSignal,
  ): Promise<DatasetSummary[]> {
    const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return request<DatasetSummary[]>(
      `/api/v1/datasets?${qs.toString()}`,
      { method: "GET" },
      signal,
    );
  },

  getDataset(datasetId: string, signal?: AbortSignal): Promise<DatasetSummary> {
    return request<DatasetSummary>(
      `/api/v1/datasets/${encodeURIComponent(datasetId)}`,
      { method: "GET" },
      signal,
    );
  },

  deleteDataset(datasetId: string, signal?: AbortSignal): Promise<void> {
    return request<void>(
      `/api/v1/datasets/${encodeURIComponent(datasetId)}`,
      { method: "DELETE" },
      signal,
    );
  },

  getProfile(datasetId: string, signal?: AbortSignal): Promise<ProfileResponse> {
    return request<ProfileResponse>(
      `/api/v1/datasets/${encodeURIComponent(datasetId)}/profile`,
      { method: "GET" },
      signal,
    );
  },

  reprofile(datasetId: string, signal?: AbortSignal): Promise<ProfileResponse> {
    return request<ProfileResponse>(
      `/api/v1/datasets/${encodeURIComponent(datasetId)}/reprofile`,
      { method: "POST" },
      signal,
    );
  },

  // -------------------------------------------------------------------------
  // Phase 3 - Financial Intelligence
  // -------------------------------------------------------------------------
  getAnalysisOptions(signal?: AbortSignal): Promise<AnalysisOptionsResponse> {
    return request<AnalysisOptionsResponse>(
      "/api/v1/analysis/options",
      { method: "GET" },
      signal,
    );
  },

  runSelfAnalysis(
    datasetId: string,
    displayName?: string,
    signal?: AbortSignal,
  ): Promise<AnalysisResult> {
    return request<AnalysisResult>(
      "/api/v1/analysis/self",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, display_name: displayName }),
      },
      signal,
    );
  },

  runMergerAnalysis(
    payload: {
      primary_dataset_id: string;
      secondary_dataset_id: string;
      deal_type?: string;
      primary_display_name?: string;
      secondary_display_name?: string;
    },
    signal?: AbortSignal,
  ): Promise<AnalysisResult> {
    return request<AnalysisResult>(
      "/api/v1/analysis/merger",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      signal,
    );
  },

  runBenchmarkAnalysis(
    payload: {
      primary_dataset_id: string;
      competitor_dataset_id: string;
      market_dataset_id?: string;
      primary_display_name?: string;
      competitor_display_name?: string;
      market_display_name?: string;
    },
    signal?: AbortSignal,
  ): Promise<AnalysisResult> {
    return request<AnalysisResult>(
      "/api/v1/analysis/benchmark",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      signal,
    );
  },

  // -------------------------------------------------------------------------
  // Chatbot - Dataset Intelligence Assistant
  // -------------------------------------------------------------------------
  chatQuery(payload: ChatQueryPayload, signal?: AbortSignal): Promise<ChatResponse> {
    return request<ChatResponse>(
      "/api/v1/chat/query",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      signal,
    );
  },

  chatSession(sessionId: string, signal?: AbortSignal): Promise<ChatSessionResponse> {
    return request<ChatSessionResponse>(
      `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`,
      { method: "GET" },
      signal,
    );
  },

  chatClearSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    return request<void>(
      `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`,
      { method: "DELETE" },
      signal,
    );
  },

  chatSuggestions(
    payload: ChatSuggestionsPayload,
    signal?: AbortSignal,
  ): Promise<ChatSuggestionsResponse> {
    return request<ChatSuggestionsResponse>(
      "/api/v1/chat/suggestions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      signal,
    );
  },
};
