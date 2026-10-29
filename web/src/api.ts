import type {
  ArticleImportResponse,
  Asset,
  AssetGenerateResponse,
  Episode,
  EpisodeActionAccepted,
  EpisodeAudioRead,
  QcReport,
  ScriptRead,
  ScriptOptimizeResponse,
  Series,
  Shot,
  StoryboardRead,
  ValidationResult,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

function action(episodeId: string, name: string): Promise<EpisodeActionAccepted> {
  return request(`/api/v1/episodes/${episodeId}/actions/${name}`, {
    method: "POST",
  });
}

export const api = {
  health: () => request<{ status: string; env: string; database: string }>("/health"),
  listSeries: () => request<Series[]>("/api/v1/series"),
  createSeries: (payload: Record<string, unknown>) =>
    request<Series>("/api/v1/series", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listEpisodes: (status?: string) =>
    request<Episode[]>(
      `/api/v1/episodes${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  getEpisode: (id: string) => request<Episode>(`/api/v1/episodes/${id}`),
  createEpisode: (payload: Record<string, unknown>) =>
    request<Episode>("/api/v1/episodes", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteEpisode: (id: string) =>
    request<null>(`/api/v1/episodes/${id}`, { method: "DELETE" }),
  action,
  confirmScript: (id: string) =>
    request<Episode>(`/api/v1/episodes/${id}/actions/confirm-script`, {
      method: "POST",
    }),
  confirmStoryboard: (id: string) =>
    request<Episode>(`/api/v1/episodes/${id}/actions/confirm-storyboard`, {
      method: "POST",
    }),
  reviseLine: (id: string, lineId: string, text: string) =>
    request(`/api/v1/episodes/${id}/actions/revise-line`, {
      method: "POST",
      body: JSON.stringify({ line_id: lineId, text }),
    }),
  getScript: (id: string) => request<ScriptRead>(`/api/v1/episodes/${id}/script`),
  validateScript: (id: string) =>
    request<ValidationResult>(`/api/v1/episodes/${id}/script/validate`, {
      method: "POST",
    }),
  optimizeScript: (
    id: string,
    payload: { apply?: boolean; instructions?: string } = {},
  ) =>
    request<ScriptOptimizeResponse>(
      `/api/v1/episodes/${id}/actions/optimize-script`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  importArticle: (
    id: string,
    payload: { article: string; optimize?: boolean; instructions?: string },
  ) =>
    request<ArticleImportResponse>(
      `/api/v1/episodes/${id}/actions/import-script`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  updateScriptLine: (lineId: string, text: string) =>
    request<{ line: unknown; validation: ValidationResult }>(
      `/api/v1/script-lines/${lineId}`,
      { method: "PATCH", body: JSON.stringify({ text }) },
    ),
  getStoryboard: (id: string) =>
    request<StoryboardRead>(`/api/v1/episodes/${id}/storyboard`),
  getAudio: (id: string) =>
    request<EpisodeAudioRead>(`/api/v1/episodes/${id}/audio`),
  getQc: (id: string) => request<QcReport>(`/api/v1/episodes/${id}/qc`),
  getPackage: async (id: string) => {
    try {
      return await request<Record<string, any>>(
        `/api/v1/episodes/${id}/package`,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  buildPackage: (id: string) =>
    request<Record<string, any>>(`/api/v1/episodes/${id}/actions/package`, {
      method: "POST",
    }),
  publish: (id: string) =>
    request<Episode>(`/api/v1/episodes/${id}/actions/publish`, {
      method: "POST",
    }),
  updateShot: (shotId: string, patch: Record<string, unknown>) =>
    request<{ shot: Shot }>(`/api/v1/shots/${shotId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  resolveReview: (reviewId: string, resolvedBy = "operator") =>
    request(`/api/v1/reviews/${reviewId}/resolve?resolved_by=${resolvedBy}`, {
      method: "POST",
    }),
  listAssets: (params?: {
    type?: string;
    status?: string;
    reuse_key?: string;
    tag?: string;
  }) => {
    const query = new URLSearchParams();
    Object.entries(params ?? {}).forEach(([key, value]) => {
      if (value) query.set(key, value);
    });
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<Asset[]>(`/api/v1/assets${suffix}`);
  },
  approveAsset: (id: string) =>
    request<Asset>(`/api/v1/assets/${id}/approve`, { method: "POST" }),
  rejectAsset: (id: string) =>
    request<Asset>(`/api/v1/assets/${id}/reject`, { method: "POST" }),
  checkAsset: (id: string) =>
    request<{ asset_id: string; passed: boolean; issues: unknown[]; meta: Record<string, any> }>(
      `/api/v1/assets/${id}/check`,
      { method: "POST" },
    ),
  generateAssetsFromText: (payload: Record<string, unknown>) =>
    request<AssetGenerateResponse>("/api/v1/assets/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  generateAssetsForEpisode: (episodeId: string, payload: Record<string, unknown>) =>
    request<AssetGenerateResponse>(
      `/api/v1/episodes/${episodeId}/actions/generate-assets`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
};
