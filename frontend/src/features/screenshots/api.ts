import {
  API_BASE,
  apiFetch,
  ApiError,
  ensureCsrfToken,
  toApiError,
} from "@/services/api-client";
import type { Screenshot, ScreenshotCategory } from "@/types/api";

/** Miroir indicatif des limites serveur (le serveur reste seul juge : SCREENSHOT_MAX_BYTES). */
export const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export const MAX_FILE_BYTES = 10 * 1024 * 1024;

export const listScreenshots = (tradeId: string) =>
  apiFetch<Screenshot[]>(`/trades/${tradeId}/screenshots/`);

export const updateScreenshot = (
  id: string,
  payload: { category?: ScreenshotCategory; description?: string },
) => apiFetch<Screenshot>(`/screenshots/${id}/`, { method: "PATCH", body: payload });

export const deleteScreenshot = (id: string) =>
  apiFetch<void>(`/screenshots/${id}/`, { method: "DELETE" });

export interface UploadOptions {
  tradeId: string;
  file: File;
  category: ScreenshotCategory;
  description?: string;
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

/**
 * Envoi d'un fichier avec progression réelle (fetch ne sait pas suivre l'envoi, XHR si).
 * Un fichier par requête : les erreurs sont ainsi attribuées fichier par fichier.
 */
export async function uploadScreenshot(options: UploadOptions): Promise<Screenshot[]> {
  const { tradeId, file, category, description, onProgress, signal } = options;
  const token = await ensureCsrfToken();

  return new Promise<Screenshot[]>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/trades/${tradeId}/screenshots/`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    if (token) xhr.setRequestHeader("X-CSRFToken", token);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as Screenshot[]);
      else reject(toApiError(xhr.status, data));
    };
    xhr.onerror = () => reject(new ApiError(0, "Serveur injoignable. Vérifiez votre connexion."));
    xhr.onabort = () => reject(new DOMException("Envoi annulé", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });

    const form = new FormData();
    form.append("files", file);
    form.append("category", category);
    if (description) form.append("description", description);
    xhr.send(form);
  });
}

/** Message lisible pour un échec d'envoi (détail du fichier refusé en priorité). */
export function uploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const fileErrors = error.fieldErrors.files;
    if (fileErrors?.length) return fileErrors.map((m) => m.replace(/^.*? : /, "")).join(" ");
    const first = Object.values(error.fieldErrors)[0];
    if (first?.length) return first.join(" ");
    return error.message;
  }
  return "Envoi impossible.";
}
